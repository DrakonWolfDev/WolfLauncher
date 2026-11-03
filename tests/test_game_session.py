import unittest
from unittest.mock import Mock, patch

from wolflauncher.game_session import minimize_for_game
from wolflauncher.platform_detection import ProcessCheck


class GameSessionTests(unittest.TestCase):
    def test_restore_after_game_exits_ignoring_transient_missing_snapshot(self):
        window = Mock(game_session_monitor=None)
        with (
            patch("wolflauncher.game_session.QTimer") as timer_type,
            patch("wolflauncher.game_session.activate_window") as activate,
            patch("wolflauncher.game_session.dayz_game_process_check") as process,
        ):
            minimize_for_game(window)
            timer = timer_type.return_value
            window.showMinimized.assert_called_once_with()
            timer.start.assert_called_once_with()
            process.side_effect = [
                ProcessCheck(True, "Running"),
                ProcessCheck(False, "Missing"),
                ProcessCheck(True, "Running"),
                ProcessCheck(False, "Missing"),
                ProcessCheck(False, "Missing"),
            ]
            for _ in range(4):
                window.game_session_monitor.check()
                activate.assert_not_called()
            window.game_session_monitor.check()
            timer.stop.assert_called_once_with()
            activate.assert_called_once_with(window)

    def test_next_session_reuses_monitor_and_resets_missing_checks(self):
        window = Mock(game_session_monitor=None)
        with patch("wolflauncher.game_session.QTimer") as timer_type:
            minimize_for_game(window)
            monitor = window.game_session_monitor
            monitor.missing_checks = 1
            minimize_for_game(window)
            self.assertIs(window.game_session_monitor, monitor)
            self.assertEqual(monitor.missing_checks, 0)
            timer_type.assert_called_once_with(window)
            self.assertEqual(timer_type.return_value.start.call_count, 2)

    def test_nonminimising_session_pauses_polling_without_activating_window_on_exit(self):
        from wolflauncher.game_session import monitor_game_handoff

        window = Mock(game_session_monitor=None)
        with (
            patch("wolflauncher.game_session.QTimer"),
            patch("wolflauncher.game_session.activate_window") as activate,
            patch("wolflauncher.game_session.dayz_game_process_check") as process,
        ):
            monitor_game_handoff(window)
            self.assertTrue(window._game_session_active)
            window.showMinimized.assert_not_called()
            process.side_effect = [
                ProcessCheck(True, "Running"),
                ProcessCheck(False, "Missing"),
                ProcessCheck(False, "Missing"),
            ]
            for _ in range(3):
                window.game_session_monitor.check()
            self.assertFalse(window._game_session_active)
            activate.assert_not_called()

    def test_startup_grace_does_not_end_session_before_game_appears(self):
        from wolflauncher.game_session import monitor_game_handoff

        window = Mock(game_session_monitor=None)
        with (
            patch("wolflauncher.game_session.QTimer"),
            patch("wolflauncher.game_session.time.monotonic", return_value=0) as clock,
            patch(
                "wolflauncher.game_session.dayz_game_process_check",
                return_value=ProcessCheck(False, "Starting"),
            ),
        ):
            monitor_game_handoff(window)
            clock.return_value = 10
            window.game_session_monitor.check()
            window.game_session_monitor.check()
            self.assertTrue(window._game_session_active)
            clock.return_value = 31
            window.game_session_monitor.check()
            window.game_session_monitor.check()
            self.assertFalse(window._game_session_active)
