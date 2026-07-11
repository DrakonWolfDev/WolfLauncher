import unittest

from PySide6.QtCore import QTimer

from wolflauncher import app
from wolflauncher.launch_dialogs import (
    LaunchDialog,
    NativeLaunchPreviewDialog,
    format_launch_command,
)


class LaunchDialogModuleTests(unittest.TestCase):
    def test_main_window_keeps_its_refresh_timer_dependency(self):
        self.assertIs(app.QTimer, QTimer)

    def test_app_uses_extracted_launch_dialogs(self):
        self.assertIs(app.LaunchDialog, LaunchDialog)
        self.assertIs(app.NativeLaunchPreviewDialog, NativeLaunchPreviewDialog)

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
