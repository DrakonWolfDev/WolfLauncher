import unittest

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication

from wolflauncher import app
from wolflauncher.launch_dialogs import (
    LaunchDialog,
    NativeLaunchPreviewDialog,
    PreflightLaunchDialog,
    format_launch_command,
)


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
