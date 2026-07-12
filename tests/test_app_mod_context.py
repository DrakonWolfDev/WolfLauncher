import unittest
from types import SimpleNamespace
from unittest.mock import Mock

from wolflauncher.app import MainWindow
from wolflauncher.models import Server


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
        )

        self.assertEqual(MainWindow.workshop_launch_block_reason(window), "")

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
