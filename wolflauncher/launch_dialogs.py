import shlex

from PySide6.QtCore import QProcess, QTimer
from PySide6.QtGui import QTextCursor
from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
)

from .diagnostics import format_launch_output_report, post_handoff_launch_option_guidance
from .platform_detection import dayz_process_check
from .theme import set_monospace, set_ui_role

POST_HANDOFF_PROCESS_CHECK_INTERVAL_MS = 5000
POST_HANDOFF_PROCESS_CHECK_ATTEMPTS = 9


def format_launch_command(command: list[str]) -> str:
    """Format a QProcess argument vector as a copyable shell command."""
    return shlex.join(command)


class PostHandoffProcessCheckMixin:
    def start_post_handoff_process_checks(self):
        self.post_handoff_check_attempt = 0
        self.output.append("Watching for known DayZ processes for up to 45 seconds...")
        QTimer.singleShot(POST_HANDOFF_PROCESS_CHECK_INTERVAL_MS, self.append_dayz_process_check)

    def append_dayz_process_check(self):
        self.post_handoff_check_attempt += 1
        check = dayz_process_check()
        elapsed_seconds = (
            self.post_handoff_check_attempt * POST_HANDOFF_PROCESS_CHECK_INTERVAL_MS // 1000
        )
        if check.running:
            self.output.append(
                f"\nPost-handoff process check: {check.detail} after about {elapsed_seconds} seconds."
            )
            return

        if self.post_handoff_check_attempt < POST_HANDOFF_PROCESS_CHECK_ATTEMPTS:
            QTimer.singleShot(
                POST_HANDOFF_PROCESS_CHECK_INTERVAL_MS, self.append_dayz_process_check
            )
            return

        self.output.append(
            f"\nPost-handoff process check: no known DayZ process detected after about {elapsed_seconds} seconds. "
            "Steam may still be preparing Proton, but if there is no Steam activity, check downloads, Proton/BattlEye prompts, "
            "and the selected Steam install in Settings health. "
            f"{post_handoff_launch_option_guidance()}"
        )


class LaunchDialog(PostHandoffProcessCheckMixin, QDialog):
    def __init__(
        self, parent, command: list[str], title: str, handoff_label: str = "launch command"
    ):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.resize(820, 460)
        self.handoff_label = handoff_label
        self.command_text = format_launch_command(command)
        self.process = QProcess(self)
        self.process.setProcessChannelMode(QProcess.MergedChannels)

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Launch command:"))
        command_box = QLineEdit(self.command_text)
        command_box.setReadOnly(True)
        set_monospace(command_box)
        layout.addWidget(command_box)

        self.output = QTextEdit()
        self.output.setReadOnly(True)
        set_monospace(self.output)
        layout.addWidget(self.output)

        button_row = QHBoxLayout()
        self.close_button = QPushButton("Close")
        set_ui_role(self.close_button, "primary")
        self.close_button.clicked.connect(self.close)
        self.close_button.setEnabled(False)
        copy_button = QPushButton("Copy")
        copy_button.clicked.connect(self.copy_output)
        button_row.addStretch(1)
        button_row.addWidget(copy_button)
        button_row.addWidget(self.close_button)
        layout.addLayout(button_row)

        self.process.readyReadStandardOutput.connect(self.read_output)
        self.process.finished.connect(self.handle_finished)
        self.process.errorOccurred.connect(self.handle_process_error)
        self.output.append("Starting launcher...\n")
        self.process.start(command[0], command[1:])

    def copy_output(self):
        QApplication.clipboard().setText(self.copyable_output_text())
        self.output.append("\nLaunch command and output copied to clipboard.")

    def copyable_output_text(self) -> str:
        return format_launch_output_report(self.command_text, self.output.toPlainText())

    def read_output(self):
        data = bytes(self.process.readAllStandardOutput()).decode("utf-8", errors="replace")
        if data:
            self.output.moveCursor(QTextCursor.End)
            self.output.insertPlainText(data)
            self.output.moveCursor(QTextCursor.End)

    def handle_finished(self, exit_code: int, exit_status):
        self.read_output()
        if exit_code == 0:
            self.output.append(
                f"\n{self.handoff_label.title()} exited successfully, which means WolfLauncher handed control "
                "to Steam. Steam may still need time to start, update, initialize Proton or show a BattlEye prompt."
            )
            self.start_post_handoff_process_checks()
        else:
            self.output.append(
                f"\nLauncher exited with code {exit_code}. "
                "Check the messages above for the script or Steam error."
            )
        self.close_button.setEnabled(True)

    def handle_process_error(self, error):
        if error == QProcess.ProcessError.FailedToStart:
            self.output.append(
                "\nLaunch command could not start. Check that the configured launcher or Steam command exists."
            )
            self.close_button.setEnabled(True)


class PreflightLaunchDialog(QDialog):
    """Compact, live checklist for the automatic Connect workflow."""

    PROCESS_CHECK_INTERVAL_MS = 2000
    PROCESS_CHECK_ATTEMPTS = 30

    def __init__(self, parent, server_name: str):
        super().__init__(parent)
        self.setWindowTitle(f"Connecting to {server_name}")
        self.resize(560, 330)
        self.process = QProcess(self)
        self.process.setProcessChannelMode(QProcess.MergedChannels)
        self.process.readyReadStandardOutput.connect(self.read_output)
        self.process.finished.connect(self.handle_finished)
        self.process.errorOccurred.connect(self.handle_process_error)
        self.process_check_attempt = 0

        layout = QVBoxLayout(self)
        intro = QLabel(f"Preparing <b>{server_name}</b>")
        layout.addWidget(intro)
        self.steps = {}
        for key, text in (
            ("steam", "Steam running"),
            ("mods", "Mods ready"),
            ("launcher", "Launcher ready"),
            ("game", "Game launching"),
        ):
            label = QLabel(f"○  {text}")
            self.steps[key] = (label, text)
            layout.addWidget(label)

        self.detail = QLabel("Starting pre-flight…")
        self.detail.setWordWrap(True)
        layout.addWidget(self.detail)
        self.output = QTextEdit()
        self.output.setReadOnly(True)
        self.output.setMaximumHeight(100)
        set_monospace(self.output)
        layout.addWidget(self.output)

        buttons = QHBoxLayout()
        self.close_button = QPushButton("Cancel")
        self.close_button.clicked.connect(self.close)
        buttons.addStretch(1)
        buttons.addWidget(self.close_button)
        layout.addLayout(buttons)

    def set_working(self, key: str, detail: str = ""):
        label, text = self.steps[key]
        label.setText(f"◔  {text}")
        if detail:
            self.detail.setText(detail)

    def set_complete(self, key: str, detail: str = ""):
        label, text = self.steps[key]
        label.setText(f"✓  {text}")
        if detail:
            self.detail.setText(detail)

    def set_failed(self, key: str, detail: str):
        label, text = self.steps[key]
        label.setText(f"✗  {text}")
        self.detail.setText(detail)
        self.close_button.setText("Close")

    def start_launch(self, command: list[str]):
        self.set_complete("launcher", "Sending the launch instructions to Steam…")
        self.process.start(command[0], command[1:])

    def read_output(self):
        data = bytes(self.process.readAllStandardOutput()).decode("utf-8", errors="replace")
        if data:
            self.output.moveCursor(QTextCursor.End)
            self.output.insertPlainText(data)

    def handle_finished(self, exit_code: int, _exit_status):
        self.read_output()
        if exit_code != 0:
            self.set_failed("launcher", f"Steam launch handoff exited with code {exit_code}.")
            return
        self.set_working("game", "Steam accepted the launch. Waiting for the DayZ process…")
        self.process_check_attempt = 0
        QTimer.singleShot(self.PROCESS_CHECK_INTERVAL_MS, self.check_dayz_process)

    def check_dayz_process(self):
        self.process_check_attempt += 1
        check = dayz_process_check()
        if check.running:
            self.set_complete("game", check.detail)
            self.close_button.setText("Close")
            return
        if self.process_check_attempt < self.PROCESS_CHECK_ATTEMPTS:
            QTimer.singleShot(self.PROCESS_CHECK_INTERVAL_MS, self.check_dayz_process)
            return
        self.set_failed(
            "game",
            "Steam accepted the launch, but no DayZ process was detected within 60 seconds. "
            "Steam may still be preparing Proton or BattlEye.",
        )

    def handle_process_error(self, error):
        if error == QProcess.ProcessError.FailedToStart:
            self.set_failed("launcher", "The Steam launch command could not be started.")


class NativeLaunchPreviewDialog(PostHandoffProcessCheckMixin, QDialog):
    def __init__(self, parent, title: str, preview_text: str, command: list[str]):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.resize(860, 540)
        self.command = command
        self.command_text = format_launch_command(command) if command else ""
        self.process = QProcess(self)
        self.process.setProcessChannelMode(QProcess.MergedChannels)

        layout = QVBoxLayout(self)
        self.output = QTextEdit()
        self.output.setReadOnly(True)
        set_monospace(self.output)
        self.output.setPlainText(preview_text)
        layout.addWidget(self.output)

        button_row = QHBoxLayout()
        copy = QPushButton("Copy")
        copy.clicked.connect(self.copy_preview)
        copy_command = QPushButton("Copy native command")
        copy_command.setEnabled(bool(command))
        copy_command.clicked.connect(self.copy_native_command)
        self.launch_button = QPushButton("Launch native")
        set_ui_role(self.launch_button, "primary")
        self.launch_button.setEnabled(bool(command))
        self.launch_button.clicked.connect(self.launch_native)
        close = QPushButton("Close")
        close.clicked.connect(self.close)
        button_row.addStretch(1)
        button_row.addWidget(copy)
        button_row.addWidget(copy_command)
        button_row.addWidget(self.launch_button)
        button_row.addWidget(close)
        layout.addLayout(button_row)

        self.process.readyReadStandardOutput.connect(self.read_output)
        self.process.finished.connect(self.handle_finished)
        self.process.errorOccurred.connect(self.handle_process_error)

    def copy_preview(self):
        QApplication.clipboard().setText(self.output.toPlainText())

    def copy_native_command(self):
        if self.command_text:
            QApplication.clipboard().setText(self.command_text)

    def launch_native(self):
        reply = QMessageBox.warning(
            self,
            "Launch native command",
            "This bypasses the external dayz-launcher.sh script and hands the previewed command directly to Steam.\n\n"
            "Continue?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if reply != QMessageBox.Yes or not self.command:
            return

        self.launch_button.setEnabled(False)
        self.output.moveCursor(QTextCursor.End)
        self.output.append("\n\nStarting native launch...\n")
        self.process.start(self.command[0], self.command[1:])

    def read_output(self):
        data = bytes(self.process.readAllStandardOutput()).decode("utf-8", errors="replace")
        if data:
            self.output.moveCursor(QTextCursor.End)
            self.output.insertPlainText(data)
            self.output.moveCursor(QTextCursor.End)

    def handle_finished(self, exit_code: int, exit_status):
        self.read_output()
        if exit_code == 0:
            self.output.append(
                "\nNative command handed off to Steam successfully. "
                "Steam may still need time to start, update, initialize Proton or show a BattlEye prompt."
            )
            self.start_post_handoff_process_checks()
        else:
            self.output.append(
                f"\nNative command exited with code {exit_code}. "
                "Check the messages above for the Steam error."
            )
        self.launch_button.setEnabled(bool(self.command))

    def handle_process_error(self, error):
        if error == QProcess.ProcessError.FailedToStart:
            self.output.append(
                "\nNative command could not start. Check Steam detection in Settings health."
            )
            self.launch_button.setEnabled(bool(self.command))
