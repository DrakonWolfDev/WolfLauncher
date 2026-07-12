import unittest
from types import SimpleNamespace
from unittest.mock import Mock

from wolflauncher.app import MainWindow
from wolflauncher.models import DiscoveredServer, Server
from wolflauncher.workshop_subscription import (
    ITEM_STATE_DOWNLOADING,
    ITEM_STATE_SUBSCRIBED,
    WorkshopItemProgress,
)


def window_state(worker=None):
    return SimpleNamespace(
        last_mod_result=object(),
        mod_summary=Mock(),
        mods_table=Mock(),
        table=Mock(currentRow=Mock(return_value=0)),
        servers=[Server("Example", "Tests", "dayz.test", 2302, 27016)],
        mod_worker=worker,
        pending_mod_check_row=None,
        handle_settings_changed=Mock(),
        check_server_mods_for_row=Mock(),
        _check_pending_server_mods=Mock(),
    )


class ModContextChangeTests(unittest.TestCase):
    def test_discovered_row_becomes_read_only_in_memory_context(self):
        discovered = DiscoveredServer(
            name="Provider name",
            server_name="Live name",
            host="203.0.113.10",
            game_port=2302,
            query_port=27016,
        )

        server = MainWindow.discovered_server_context(discovered)

        self.assertEqual(server.name, "Live name")
        self.assertEqual(server.group, "Discovered (read-only)")
        self.assertEqual(server.connect_target, "203.0.113.10:2302")
        self.assertEqual(server.query_port, 27016)

    def test_active_discovered_context_takes_priority_over_curated_selection(self):
        discovered = Server("Discovered", "Discovered (read-only)", "new.test", 2302, 27016)
        curated = Server("Curated", "Tests", "saved.test", 2302, 27016)
        window = SimpleNamespace(
            active_discovered_server=discovered,
            table=Mock(currentRow=Mock(return_value=0)),
            servers=[curated],
        )

        self.assertIs(MainWindow.active_server_context(window), discovered)

    def test_finished_mod_worker_hands_off_to_latest_queued_server(self):
        window = SimpleNamespace(
            mod_worker=object(),
            _check_pending_server_mods=Mock(),
            maybe_launch_after_workshop_download=Mock(),
        )

        MainWindow.handle_mod_worker_finished(window)

        self.assertIsNone(window.mod_worker)
        window._check_pending_server_mods.assert_called_once_with()
        window.maybe_launch_after_workshop_download.assert_called_once_with()

    def test_pending_mod_check_waits_for_running_worker_without_polling(self):
        worker = Mock()
        worker.isRunning.return_value = True
        window = SimpleNamespace(
            mod_worker=worker,
            pending_mod_server=Server("Latest", "Discovered", "latest.test", 2302, 27016),
            pending_mod_check_row=None,
            check_server_mods=Mock(),
        )

        MainWindow._check_pending_server_mods(window)

        window.check_server_mods.assert_not_called()

    def test_steam_mode_change_starts_forced_recheck_when_idle(self):
        window = window_state()

        MainWindow.handle_native_steam_mode_changed(window)

        self.assertIsNone(window.last_mod_result)
        window.mods_table.setRowCount.assert_called_once_with(0)
        window.check_server_mods_for_row.assert_called_once_with(
            0, silent=True, force=True
        )
        window._check_pending_server_mods.assert_not_called()

    def test_steam_mode_change_queues_recheck_behind_running_worker(self):
        worker = Mock()
        worker.isRunning.return_value = True
        window = window_state(worker)

        MainWindow.handle_native_steam_mode_changed(window)

        self.assertEqual(window.pending_mod_check_row, 0)
        window._check_pending_server_mods.assert_called_once_with()
        window.check_server_mods_for_row.assert_not_called()

    def test_launch_engine_change_uses_same_context_recheck(self):
        window = window_state()

        MainWindow.handle_launch_engine_changed(window)

        self.assertIsNone(window.last_mod_result)
        window.mod_summary.setText.assert_called_once_with(
            "Launch engine changed. Rechecking selected server mods..."
        )
        window.check_server_mods_for_row.assert_called_once_with(
            0, silent=True, force=True
        )


class WorkshopLaunchReadinessTests(unittest.TestCase):
    def test_progress_dialog_names_the_item_steam_is_downloading(self):
        dialog = Mock()
        window = SimpleNamespace(
            workshop_subscription_dialog=dialog,
            workshop_subscription_monitor_hidden=False,
            workshop_subscription_names={"111": "Stalled", "222": "Active Mod"},
        )
        snapshots = [
            WorkshopItemProgress("111", ITEM_STATE_SUBSCRIBED),
            WorkshopItemProgress("222", ITEM_STATE_DOWNLOADING, 30, 100),
        ]

        MainWindow.update_workshop_subscription_progress(window, snapshots)

        label = dialog.setLabelText.call_args.args[0]
        self.assertIn("Current item: Active Mod (30%)", label)
        self.assertNotIn("Stalled", label)

    def test_running_subscription_worker_blocks_launch(self):
        worker = Mock()
        worker.isRunning.return_value = True
        window = SimpleNamespace(
            workshop_subscription_worker=worker,
        )

        reason = MainWindow.workshop_launch_block_reason(window)

        self.assertIn("still processing", reason)

    def test_idle_workshop_state_allows_launch(self):
        window = SimpleNamespace(
            workshop_subscription_worker=None,
            workshop_recovery_ids=(),
        )

        self.assertEqual(MainWindow.workshop_launch_block_reason(window), "")

    def test_restart_recovery_activity_blocks_launch(self):
        window = SimpleNamespace(
            workshop_subscription_worker=None,
            workshop_recovery_ids=("111", "222"),
        )

        reason = MainWindow.workshop_launch_block_reason(window)

        self.assertIn("2 required Workshop items", reason)
        self.assertIn("Recheck mods", reason)

    def test_stop_monitoring_only_hides_dialog(self):
        dialog = Mock()
        status_bar = Mock()
        window = SimpleNamespace(
            workshop_subscription_dialog=dialog,
            workshop_subscription_monitor_hidden=False,
            statusBar=Mock(return_value=status_bar),
        )

        MainWindow.stop_workshop_subscription_monitoring(window)

        self.assertTrue(window.workshop_subscription_monitor_hidden)
        dialog.hide.assert_called_once_with()
        status_bar.showMessage.assert_called_once()

    def test_hidden_monitor_ignores_progress_dialog_updates(self):
        dialog = Mock()
        window = SimpleNamespace(
            workshop_subscription_dialog=dialog,
            workshop_subscription_monitor_hidden=True,
        )

        MainWindow.update_workshop_subscription_progress(window, [object()])

        dialog.setLabelText.assert_not_called()
        dialog.setValue.assert_not_called()

    def test_download_launch_waits_for_mod_recheck_worker(self):
        mod_worker = Mock()
        mod_worker.isRunning.return_value = True
        window = SimpleNamespace(
            launch_after_workshop_download=True,
            workshop_subscription_worker=None,
            mod_worker=mod_worker,
        )

        MainWindow.maybe_launch_after_workshop_download(window)

        self.assertTrue(window.launch_after_workshop_download)


if __name__ == "__main__":
    unittest.main()
