import unittest
from unittest.mock import patch

from PySide6.QtCore import QProcess, QTimer
from PySide6.QtWidgets import QApplication

from wolflauncher import app
from wolflauncher.launch_dialogs import (
    LaunchDialog,
    NativeLaunchPreviewDialog,
    PreflightLaunchDialog,
    format_launch_command,
)
from wolflauncher.platform_detection import ProcessCheck


class LaunchDialogModuleTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.qt_app = QApplication.instance() or QApplication([])

    def test_main_window_keeps_its_refresh_timer_dependency(self):
        self.assertIs(app.QTimer, QTimer)

    def test_app_uses_extracted_launch_dialogs(self):
        self.assertIs(app.LaunchDialog, LaunchDialog)
        self.assertIs(app.NativeLaunchPreviewDialog, NativeLaunchPreviewDialog)
        self.assertIs(app.PreflightLaunchDialog, PreflightLaunchDialog)

    def test_copyable_command_preserves_argument_boundaries(self):
        command = [
            "bash",
            "/tmp/dayz launcher.sh",
            "-n",
            "Wolf Player; echo nope",
            "--launch",
        ]

        self.assertEqual(
            format_launch_command(command),
            "bash '/tmp/dayz launcher.sh' -n 'Wolf Player; echo nope' --launch",
        )

    def test_preflight_dialog_emits_copyable_launch_report(self):
        dialog = PreflightLaunchDialog(None, "Example")
        dialog.command_text = "steam -applaunch 221100"
        dialog.output.setPlainText("Steam accepted the launch handoff.")
        reports = []
        dialog.launch_report_ready.connect(reports.append)

        dialog.emit_launch_report()

        self.assertEqual(len(reports), 1)
        self.assertIn("Command: steam -applaunch 221100", reports[0])
        self.assertIn("Steam accepted the launch handoff.", reports[0])

    def test_preflight_dialog_closes_and_minimizes_after_dayz_is_detected(self):
        dialog = PreflightLaunchDialog(None, "Example")
        scheduled = []
        minimized = []
        dialog.show()
        dialog.launcher_minimize_requested.connect(lambda: minimized.append(True))

        with (
            patch(
                "wolflauncher.launch_dialogs.dayz_game_process_check",
                return_value=ProcessCheck(True, "Detected known DayZ process: DayZ_x64.exe"),
            ),
            patch(
                "wolflauncher.launch_dialogs.QTimer.singleShot",
                side_effect=lambda ms, call: scheduled.append((ms, call)),
            ),
        ):
            dialog.check_dayz_process()

        self.assertTrue(dialog.dayz_detected)
        self.assertIn(
            "will close and WolfLauncher will minimize in 3 seconds", dialog.detail.text()
        )
        self.assertEqual(len(scheduled), 1)
        self.assertEqual(scheduled[0][0], dialog.SUCCESS_CLOSE_DELAY_MS)

        scheduled[0][1]()

        self.assertFalse(dialog.isVisible())
        self.assertEqual(minimized, [True])

    def test_direct_battleye_launch_offers_guarded_retry_after_stall(self):
        dialog = PreflightLaunchDialog(None, "Example")
        dialog.command = [r"C:\DayZ Exp\DayZ_BE.exe", "0", "1", "1"]
        dialog.command_text = format_launch_command(dialog.command)
        dialog.process_check_attempt = dialog.BATTLEYE_STALL_ATTEMPTS - 1
        dialog.show()

        with (
            patch(
                "wolflauncher.launch_dialogs.dayz_game_process_check",
                return_value=ProcessCheck(False, "No DayZ game process detected"),
            ),
            patch(
                "wolflauncher.launch_dialogs.dayz_battleye_process_check",
                return_value=ProcessCheck(True, "Detected BattlEye bootstrap process: DayZ_BE.exe"),
            ),
            patch("wolflauncher.launch_dialogs.QTimer.singleShot"),
        ):
            dialog.check_dayz_process()

        self.assertTrue(dialog.retry_button.isVisible())
        self.assertIn("appears stalled", dialog.output.toPlainText())

    def test_retry_stops_only_the_owned_battleye_process(self):
        dialog = PreflightLaunchDialog(None, "Example")
        dialog.command = [r"C:\DayZ Exp\DayZ_BE.exe", "0", "1", "1"]

        with (
            patch.object(dialog.process, "state", return_value=QProcess.Running),
            patch.object(dialog.process, "terminate") as terminate,
            patch("wolflauncher.launch_dialogs.QTimer.singleShot") as single_shot,
        ):
            dialog.retry_battleye_launch()

        terminate.assert_called_once_with()
        self.assertTrue(dialog.retrying_battleye)
        single_shot.assert_called_once_with(
            dialog.BATTLEYE_STOP_TIMEOUT_MS, dialog._kill_stalled_battleye_if_needed
        )
