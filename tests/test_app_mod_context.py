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


if __name__ == "__main__":
    unittest.main()
