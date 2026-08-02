import unittest
from types import SimpleNamespace
from unittest.mock import Mock

from PySide6.QtCore import QProcess

from wolflauncher.lifecycle import (
    RuntimeShutdownCoordinator,
    WORKER_ATTRIBUTES,
    WORKER_COLLECTION_ATTRIBUTES,
    active_workers,
    begin_runtime_shutdown,
    runtime_shutdown_complete,
    stop_runtime,
)


def owner_with(**overrides):
    values = {
        "timer": Mock(),
        "remote_search_timer": Mock(),
        "browser_filter_timer": Mock(),
        "browser_selection_timer": Mock(),
        "worker": None,
        "mod_worker": None,
        "workshop_subscription_worker": None,
        "workshop_state_worker": None,
        "preflight_mod_worker": None,
        "preflight_workshop_worker": None,
        "discovery_worker": None,
        "web_api_worker": None,
        "battlemetrics_worker": None,
        "wolfapi_worker": None,
        "wolfapi_cache_worker": None,
        "wolfapi_search_worker": None,
        "results_freshness_worker": None,
        "workshop_library_worker": None,
        "enrichment_worker": None,
        "selection_enrichment_workers": {},
        "browser_mod_workers": {},
        "pending_selection_checks": {"one": object()},
        "pending_browser_mod_previews": {"two": object()},
        "pending_wolfapi_search": "query",
        "pending_results_freshness": True,
        "results_freshness_attempted_keys": {"three"},
        "wolfapi_refresh_process": None,
        "mod_thumbnail_reply": None,
        "editor_image_reply": None,
    }
    values.update(overrides)
    return SimpleNamespace(**values)


class LifecycleTests(unittest.TestCase):
    def test_shutdown_coordinator_starts_once_and_reports_completion(self):
        worker = Mock()
        worker.isRunning.side_effect = [True, True, False]
        owner = owner_with(mod_worker=worker)
        coordinator = RuntimeShutdownCoordinator(owner, monotonic=lambda: 10)

        self.assertFalse(coordinator.begin())
        self.assertTrue(coordinator.started)
        self.assertEqual(coordinator.deadline, 25)
        self.assertTrue(coordinator.poll())

        worker.cancel.assert_called_once_with()
        worker.requestInterruption.assert_called_once_with()

    def test_shutdown_coordinator_kills_only_an_overdue_process(self):
        process = Mock()
        process.state.return_value = QProcess.Running
        owner = owner_with(wolfapi_refresh_process=process)
        now = [10]
        coordinator = RuntimeShutdownCoordinator(owner, monotonic=lambda: now[0])

        self.assertFalse(coordinator.begin())
        self.assertFalse(coordinator.poll())
        process.kill.assert_not_called()

        now[0] = 25
        self.assertFalse(coordinator.poll())
        self.assertTrue(coordinator.overdue())
        process.kill.assert_called_once_with()

    def test_nonblocking_shutdown_requests_cancellation_without_waiting(self):
        worker = Mock()
        worker.isRunning.return_value = True
        owner = owner_with(mod_worker=worker)

        begin_runtime_shutdown(owner)

        worker.cancel.assert_called_once_with()
        worker.requestInterruption.assert_called_once_with()
        worker.wait.assert_not_called()
        self.assertFalse(runtime_shutdown_complete(owner))

    def test_every_declared_singleton_worker_is_coordinated(self):
        for attribute in WORKER_ATTRIBUTES:
            with self.subTest(attribute=attribute):
                worker = Mock()
                worker.isRunning.return_value = True
                owner = owner_with(**{attribute: worker})
                self.assertEqual(active_workers(owner), [worker])

    def test_every_declared_worker_collection_is_coordinated(self):
        for attribute in WORKER_COLLECTION_ATTRIBUTES:
            with self.subTest(attribute=attribute):
                worker = Mock()
                worker.isRunning.return_value = True
                owner = owner_with(**{attribute: {"one": worker}})
                self.assertEqual(active_workers(owner), [worker])

    def test_active_workers_deduplicates_slots_and_collections(self):
        worker = Mock()
        worker.isRunning.return_value = True
        owner = owner_with(worker=worker, selection_enrichment_workers={"same": worker})

        self.assertEqual(active_workers(owner), [worker])

    def test_stop_runtime_stops_timers_clears_queues_and_waits_for_workers(self):
        worker = Mock()
        worker.isRunning.side_effect = [True, True, True, False]
        worker.wait.return_value = True
        owner = owner_with(workshop_subscription_worker=worker)

        self.assertTrue(stop_runtime(owner, timeout_ms=100))

        owner.timer.stop.assert_called_once_with()
        owner.remote_search_timer.stop.assert_called_once_with()
        owner.browser_filter_timer.stop.assert_called_once_with()
        owner.browser_selection_timer.stop.assert_called_once_with()
        worker.cancel.assert_called_once_with()
        worker.requestInterruption.assert_called_once_with()
        worker.wait.assert_called_once()
        self.assertEqual(owner.pending_selection_checks, {})
        self.assertEqual(owner.pending_browser_mod_previews, {})
        self.assertEqual(owner.pending_wolfapi_search, "")
        self.assertFalse(owner.pending_results_freshness)
        self.assertEqual(owner.results_freshness_attempted_keys, set())
        self.assertTrue(owner._shutting_down)

    def test_stop_runtime_aborts_active_thumbnail_requests(self):
        reply = Mock()
        reply.isFinished.return_value = False
        owner = owner_with(mod_thumbnail_reply=reply)

        self.assertTrue(stop_runtime(owner, timeout_ms=100))

        reply.abort.assert_called_once_with()

    def test_stop_runtime_reports_worker_that_outlives_deadline(self):
        worker = Mock()
        worker.isRunning.return_value = True
        worker.wait.return_value = False
        owner = owner_with(mod_worker=worker)

        self.assertFalse(stop_runtime(owner, timeout_ms=0))

    def test_stop_runtime_terminates_then_kills_stuck_process(self):
        process = Mock()
        process.state.return_value = QProcess.Running
        process.waitForFinished.side_effect = [False, True]
        owner = owner_with(wolfapi_refresh_process=process)

        self.assertTrue(stop_runtime(owner, timeout_ms=100))

        process.terminate.assert_called_once_with()
        process.kill.assert_called_once_with()


if __name__ == "__main__":
    unittest.main()
