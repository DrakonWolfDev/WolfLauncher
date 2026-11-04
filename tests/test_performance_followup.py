import threading
import unittest
from concurrent.futures import ThreadPoolExecutor
from types import SimpleNamespace
from unittest.mock import Mock, patch

from wolflauncher.http_client import HttpClientError
from wolflauncher.launch_preflight import usable_mod_result
from wolflauncher.mod_presenter import mod_readiness_text, mod_row, mod_summary_text
from wolflauncher.models import DiscoveredServer, Server
from wolflauncher.mods import ModCheckResult, RequiredMod, fetch_workshop_metadata
from wolflauncher.server_launch_coordinator import ServerLaunchCoordinator
from wolflauncher.status import ServerStatus
from wolflauncher.workers import ModWorker, ServerEnrichmentWorker
from wolflauncher.workshop_metadata import WorkshopMetadataBroker


class MetadataSharingTests(unittest.TestCase):
    def test_identical_concurrent_requests_use_one_http_load(self):
        broker = WorkshopMetadataBroker()
        entered, joined = threading.Event(), threading.Event()
        guard_calls = []

        def following():
            guard_calls.append(True)
            if len(guard_calls) > 1:
                joined.set()
            return False

        def load(ids):
            entered.set()
            self.assertTrue(joined.wait(2))
            return {item: {"result": 1, "title": item} for item in ids}

        load = Mock(side_effect=load)
        with ThreadPoolExecutor(2) as pool:
            first = pool.submit(broker.fetch, ("1", "2"), include_children=False, load=load)
            self.assertTrue(entered.wait(2))
            second = pool.submit(
                broker.fetch, ("1", "2"), include_children=False, load=load, cancelled=following
            )
            self.assertEqual(first.result(3), second.result(3))
        load.assert_called_once_with(("1", "2"))

    def test_overlapping_batches_share_items_and_return_independent_objects(self):
        broker = WorkshopMetadataBroker()
        entered, release = threading.Event(), threading.Event()
        calls = []

        def load(ids):
            calls.append(ids)
            if "1" in ids:
                entered.set()
                self.assertTrue(release.wait(2))
            else:
                release.set()
            return {item: {"result": 1, "title": item, "time_updated": 7} for item in ids}

        with ThreadPoolExecutor(2) as pool:
            first = pool.submit(broker.fetch, ("1", "2"), include_children=False, load=load)
            self.assertTrue(entered.wait(2))
            second = pool.submit(broker.fetch, ("2", "3"), include_children=False, load=load)
            a, b = first.result(3), second.result(3)
        self.assertEqual(calls, [("1", "2"), ("3",)])
        a["2"]["title"] = "changed"
        self.assertEqual(b["2"]["title"], "2")
        self.assertEqual(broker.display(["2"]), {"2": {"title": "2"}})

    def test_display_cache_is_bounded_expires_and_never_supplies_revision_evidence(self):
        broker = WorkshopMetadataBroker(max_entries=1, max_bytes=100)
        load = Mock(return_value={"1": {"result": 1, "title": "old", "time_updated": 50}})
        with patch("wolflauncher.workshop_metadata.time.monotonic", return_value=1):
            broker.fetch(("1",), include_children=False, load=load)
            self.assertEqual(broker.display(["1"]), {"1": {"title": "old"}})
            load.return_value["1"]["time_updated"] = 60
            self.assertEqual(
                broker.fetch(("1",), include_children=False, load=load)["1"]["time_updated"], 60
            )
            self.assertEqual(load.call_count, 2)
            broker.fetch(
                ("2",), include_children=False, load=lambda _: {"2": {"result": 1, "title": "two"}}
            )
            self.assertEqual(broker.display(["1"]), {})
        with patch("wolflauncher.workshop_metadata.time.monotonic", return_value=302):
            self.assertEqual(broker.display(["2"]), {})
        broker.fetch(
            ("3",), include_children=False, load=lambda _: {"3": {"result": 1, "title": "x" * 200}}
        )
        self.assertEqual(broker.display(["3"]), {})

    def test_forced_refresh_bypasses_old_request_and_old_result_cannot_replace_display(self):
        broker = WorkshopMetadataBroker()
        entered, release = threading.Event(), threading.Event()

        def old_load(_):
            entered.set()
            self.assertTrue(release.wait(2))
            return {"1": {"result": 1, "title": "old", "time_updated": 1}}

        with ThreadPoolExecutor(1) as pool:
            old = pool.submit(broker.fetch, ("1",), include_children=False, load=old_load)
            self.assertTrue(entered.wait(2))
            try:
                fresh = broker.fetch(
                    ("1",),
                    include_children=False,
                    force_refresh=True,
                    load=lambda _: {"1": {"result": 1, "title": "fresh", "time_updated": 2}},
                )
            finally:
                release.set()
            self.assertEqual(old.result(3)["1"]["time_updated"], 1)
        self.assertEqual(fresh["1"]["time_updated"], 2)
        self.assertEqual(broker.display(["1"])["1"]["title"], "fresh")

    def test_follower_can_cancel_without_cancelling_owner(self):
        broker = WorkshopMetadataBroker()
        entered, release, cancel = threading.Event(), threading.Event(), threading.Event()

        def load(_):
            entered.set()
            self.assertTrue(release.wait(2))
            return {"1": {"result": 1, "title": "ok"}}

        def cancelled():
            # Initial admission succeeds; cancellation occurs while following
            # the owner's already-running request.
            if not cancel.is_set():
                cancel.set()
                return False
            return True

        with ThreadPoolExecutor(1) as pool:
            owner = pool.submit(broker.fetch, ("1",), include_children=False, load=load)
            self.assertTrue(entered.wait(2))
            try:
                with self.assertRaises(HttpClientError):
                    broker.fetch(("1",), include_children=False, load=Mock(), cancelled=cancelled)
            finally:
                release.set()
            self.assertEqual(owner.result(3)["1"]["title"], "ok")
        self.assertTrue(cancel.is_set())

    def test_cancelled_owner_releases_follower_to_retry(self):
        broker = WorkshopMetadataBroker()
        entered, follower_waiting = threading.Event(), threading.Event()
        cancelled = threading.Event()

        def owner_load(_):
            entered.set()
            self.assertTrue(follower_waiting.wait(2))
            cancelled.set()
            return {"1": {"result": 1, "title": "cancelled"}}

        guards = []

        def follower_cancelled():
            guards.append(True)
            if len(guards) > 1:
                follower_waiting.set()
            return False

        with ThreadPoolExecutor(2) as pool:
            owner = pool.submit(
                broker.fetch,
                ("1",),
                include_children=False,
                load=owner_load,
                cancelled=cancelled.is_set,
            )
            self.assertTrue(entered.wait(2))
            follower = pool.submit(
                broker.fetch,
                ("1",),
                include_children=False,
                load=lambda _: {"1": {"result": 1, "title": "retried"}},
                cancelled=follower_cancelled,
            )
            with self.assertRaises(HttpClientError):
                owner.result(3)
            self.assertEqual(follower.result(3)["1"]["title"], "retried")
        self.assertEqual(broker._active_items, 0)

    def test_children_completeness_and_failed_requests_are_not_cached_as_success(self):
        broker = WorkshopMetadataBroker()
        with self.assertRaises(OSError):
            broker.fetch(("1",), include_children=False, load=Mock(side_effect=OSError("offline")))
        self.assertEqual(broker._active_items, 0)
        self.assertEqual(broker.display(["1"]), {})
        load = Mock(return_value={"1": {"result": 9}})
        broker.fetch(("1",), include_children=False, load=load)
        broker.fetch(("1",), include_children=True, load=load)
        self.assertEqual(load.call_count, 2)
        self.assertEqual(broker.display(["1"]), {})

    def test_public_requests_split_large_batches_and_forward_cancellation(self):
        ids = [str(i) for i in range(1, 206)]
        cancel = Mock(return_value=False)
        with patch("wolflauncher.mods.post_form_json", return_value={}) as post:
            self.assertEqual(fetch_workshop_metadata(ids, cancelled=cancel, force_refresh=True), {})
        self.assertEqual(
            [call.args[1][0] for call in post.call_args_list],
            [("itemcount", "100"), ("itemcount", "100"), ("itemcount", "5")],
        )
        self.assertTrue(all(call.kwargs["cancel"] is cancel for call in post.call_args_list))

    def test_active_http_requests_are_bounded(self):
        broker = WorkshopMetadataBroker()
        four_started, release = threading.Event(), threading.Event()
        lock = threading.Lock()
        active, peak = 0, 0

        def load(ids):
            nonlocal active, peak
            with lock:
                active += 1
                peak = max(peak, active)
                if active == 4:
                    four_started.set()
            try:
                self.assertTrue(release.wait(2))
                return {item: {"result": 1, "title": item} for item in ids}
            finally:
                with lock:
                    active -= 1

        with ThreadPoolExecutor(8) as pool:
            futures = [
                pool.submit(broker.fetch, (str(i),), include_children=False, load=load)
                for i in range(8)
            ]
            try:
                self.assertTrue(four_started.wait(2))
            finally:
                release.set()
            for future in futures:
                self.assertTrue(future.result(3))
        self.assertEqual(peak, 4)
        self.assertEqual(broker._active_items, 0)


class ProgressiveResultTests(unittest.TestCase):
    def setUp(self):
        self.server = Server("Test", "Group", "127.0.0.1", 2302, 2303)
        self.context = SimpleNamespace(
            request_id="request",
            mod_context_key=("stable", "library"),
            server=self.server,
            install=SimpleNamespace(workshop_dir=None, dayz_dir=None),
            product=SimpleNamespace(label="Stable"),
            matches=lambda _: True,
            fresh=lambda: True,
        )

    def result(self):
        return ModCheckResult(
            True,
            self.server,
            [RequiredMod("1", "Mod", installed=True)],
            request_id="request",
            launch_context_key=self.context.mod_context_key,
        )

    def test_worker_emits_isolated_checking_then_readiness_before_advisory(self):
        worker = ModWorker(self.server, None, include_hashes=True, launch_context=self.context)
        progress, ready, final, order = [], [], [], []
        worker.mods_progress.connect(
            lambda result: (progress.append(result), order.append("progress"))
        )
        worker.readiness_ready.connect(lambda result: (ready.append(result), order.append("ready")))
        worker.mods_ready.connect(lambda result: (final.append(result), order.append("final")))

        def metadata(*args, **kwargs):
            self.assertEqual(order, ["progress"])
            self.assertTrue(progress[0].checking)
            self.assertFalse(progress[0].required_mods[0].ready)
            return {"1": {"time_updated": 3}}

        def hashes(result, *_args, **_kwargs):
            self.assertEqual(order, ["progress", "ready"])
            self.assertIsNone(ready[0].required_mods[0].hash_comparison)
            result.required_mods[0].name = "enriched"

        with (
            patch("wolflauncher.workers.check_server_mods", return_value=self.result()),
            patch("wolflauncher.workers.fetch_workshop_metadata", side_effect=metadata),
            patch("wolflauncher.workers.apply_mod_hash_comparisons", side_effect=hashes),
        ):
            worker.run()
        self.assertEqual(order, ["progress", "ready", "final"])
        self.assertEqual(ready[0].required_mods[0].name, "Mod")
        self.assertEqual(progress[0].required_mods[0].workshop_updated_at, 0)
        self.assertEqual(final[0].required_mods[0].name, "enriched")
        self.assertEqual(progress[0].request_id, "request")

    def coordinator(self):
        window = SimpleNamespace(
            active_server_context=lambda: self.server,
            _shutting_down=False,
            last_mod_result=None,
            display_mods_result=Mock(),
        )
        coordinator = ServerLaunchCoordinator(window)
        coordinator.request_id = "request"
        return coordinator, window

    def test_progress_never_populates_launch_cache_or_runs_continuation(self):
        coordinator, window = self.coordinator()
        callback = Mock()
        with patch("wolflauncher.workers.ModWorker") as worker:
            coordinator.check_mods(self.context, callback, include_hashes=True)
            progress = worker.return_value.mods_progress.connect.call_args.args[0]
            ready = worker.return_value.readiness_ready.connect.call_args.args[0]
            final = worker.return_value.mods_ready.connect.call_args.args[0]
            snapshot = self.result()
            snapshot.checking = True
            snapshot.required_mods[0].checking = True
            progress(snapshot)
            self.assertIsNone(window.last_mod_result)
            self.assertIsNone(usable_mod_result(self.server, snapshot))
            callback.assert_not_called()
            self.assertIn("Checking", mod_readiness_text(snapshot))
            self.assertNotIn("Ready", mod_summary_text(snapshot))
            self.assertIn("Checking", mod_row(snapshot.required_mods[0]).values[0])
            ready(self.result())
            callback.assert_called_once()
            final(self.result())
            callback.assert_called_once()

    def test_stale_and_mutated_readiness_cannot_be_replaced_by_advisory(self):
        coordinator, window = self.coordinator()
        callback = Mock()
        with patch("wolflauncher.workers.ModWorker") as worker:
            coordinator.check_mods(self.context, callback, include_hashes=True)
            ready = worker.return_value.readiness_ready.connect.call_args.args[0]
            final = worker.return_value.mods_ready.connect.call_args.args[0]
            ready(self.result())
            snapshot = window.last_mod_result
            snapshot.required_mods[0].workshop_state = 32
            final(self.result())
            self.assertIs(window.last_mod_result, snapshot)
            coordinator.invalidate()
            final(self.result())
            callback.assert_called_once()

    def test_forced_recheck_invalidates_queued_callbacks_and_bypasses_metadata_flights(self):
        coordinator, window = self.coordinator()
        old_callback, fresh_callback = Mock(), Mock()
        with patch("wolflauncher.workers.ModWorker") as worker:
            coordinator.check_mods(self.context, old_callback)
            late_ready = worker.return_value.mods_ready.connect.call_args.args[0]
            coordinator.check_mods(self.context, fresh_callback, force=True)
            worker.return_value.cancel.assert_called_once()
            late_ready(self.result())
            self.assertIsNone(window.last_mod_result)
            old_callback.assert_not_called()
            coordinator._mod_finished("request")
            self.assertTrue(worker.call_args.kwargs["force_metadata"])
            worker.return_value.mods_ready.connect.call_args.args[0](self.result())
            fresh_callback.assert_called_once()

    def test_cancellation_between_readiness_and_hashes_suppresses_final_result(self):
        worker = ModWorker(self.server, None, include_metadata=False, include_hashes=True)
        readiness, final = [], []
        worker.readiness_ready.connect(readiness.append)
        worker.mods_ready.connect(final.append)
        with (
            patch("wolflauncher.workers.check_server_mods", return_value=self.result()),
            patch(
                "wolflauncher.workers.apply_mod_hash_comparisons",
                side_effect=lambda *_a, **_kw: worker.cancel(),
            ),
        ):
            worker.run()
        self.assertEqual(len(readiness), 1)
        self.assertEqual(final, [])

    def test_progress_for_another_library_or_request_cannot_change_display(self):
        coordinator, window = self.coordinator()
        with patch("wolflauncher.workers.ModWorker") as worker:
            coordinator.check_mods(self.context, Mock())
            progress = worker.return_value.mods_progress.connect.call_args.args[0]
            snapshot = self.result()
            snapshot.checking = True
            snapshot.launch_context_key = ("experimental", "other library")
            progress(snapshot)
            snapshot.launch_context_key = self.context.mod_context_key
            snapshot.request_id = "old request"
            progress(snapshot)
        window.display_mods_result.assert_not_called()

    def test_advisory_failure_does_not_revoke_readiness(self):
        worker = ModWorker(self.server, None, include_metadata=False, include_hashes=True)
        readiness, final = [], []
        worker.readiness_ready.connect(readiness.append)
        worker.mods_ready.connect(final.append)
        with (
            patch("wolflauncher.workers.check_server_mods", return_value=self.result()),
            patch(
                "wolflauncher.workers.apply_mod_hash_comparisons",
                side_effect=OSError("unavailable"),
            ),
        ):
            worker.run()
        self.assertTrue(readiness[0].ok)
        self.assertTrue(final[0].ok)
        self.assertEqual(final[0].required_mods[0].hash_comparison.status, "unknown")

    def test_real_table_retains_selected_mod_and_blocks_partial_resolution(self):
        from PySide6.QtWidgets import QApplication, QLabel, QPushButton, QTableWidget

        from wolflauncher.mods_feature import ModsFeatureMixin

        app = QApplication.instance() or QApplication([])

        class View(ModsFeatureMixin):
            def apply_mod_filter(self):
                pass

            def update_mod_detail_card(self):
                pass

            def viewing_installed_workshop_library(self):
                return False

        view = View()
        view.mods_table = QTableWidget(0, 4)
        view.mod_server_title, view.mod_readiness, view.mod_summary = QLabel(), QLabel(), QLabel()
        view.subscribe_missing_button, view.force_update_button = QPushButton(), QPushButton()
        view.last_mod_result = None
        partial = self.result()
        partial.checking = True
        partial.required_mods.append(RequiredMod("2", "Second", installed=True))
        for mod in partial.required_mods:
            mod.checking = True
        view.display_mods_result(partial)
        view.mods_table.selectRow(1)
        self.assertFalse(view.subscribe_missing_button.isEnabled())
        self.assertFalse(view.force_update_button.isEnabled())
        self.assertTrue(view.selected_required_mod().checking)
        final = self.result()
        final.required_mods.append(RequiredMod("2", "Second", installed=True))
        view.last_mod_result = final
        view.display_mods_result(final)
        self.assertEqual(view.selected_required_mod().workshop_id, "2")
        self.assertIs(view.selected_required_mod(), final.required_mods[1])
        view.mods_table.close()
        app.processEvents()


class CompletionOrderTests(unittest.TestCase):
    def test_fast_result_arrives_before_slow_query_is_released_and_final_order_is_stable(self):
        slow_entered, release = threading.Event(), threading.Event()
        servers = [
            DiscoveredServer("Slow", "127.0.0.1", 2302, 2303),
            DiscoveredServer("Fast", "127.0.0.2", 2302, 2303),
        ]
        worker = ServerEnrichmentWorker(servers, probe_fallbacks=False)
        progress, final = [], []

        def query(server, **kwargs):
            if server.name == "Slow":
                slow_entered.set()
                if not release.wait(2):
                    raise AssertionError("Fast result was held behind slow query")
            else:
                self.assertTrue(slow_entered.wait(2))
            return ServerStatus(True)

        def receive(payload, count, total):
            progress.append((payload[0], count, total))
            if payload[0] == servers[1].cache_key:
                release.set()

        worker.enrichment_progress.connect(receive)
        worker.enrichment_ready.connect(lambda rows, _: final.extend(rows))
        with patch("wolflauncher.workers.check_server", side_effect=query):
            worker.run()
        self.assertEqual(progress, [(servers[1].cache_key, 1, 2), (servers[0].cache_key, 2, 2)])
        self.assertEqual([row.name for row in final], ["Slow", "Fast"])

    def test_cancelled_batch_never_delivers_late_results(self):
        worker = ServerEnrichmentWorker([DiscoveredServer("One", "127.0.0.1", 2302, 2303)])
        progress, final = [], []
        worker.enrichment_progress.connect(lambda *args: progress.append(args))
        worker.enrichment_ready.connect(lambda *args: final.append(args))

        def query(*args, **kwargs):
            worker.cancel()
            return ServerStatus(True)

        with patch("wolflauncher.workers.check_server", side_effect=query):
            worker.run()
        self.assertEqual((progress, final), ([], []))
