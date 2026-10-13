"""Wolf Update presentation and WolfLauncher-specific configuration."""

from __future__ import annotations

from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QTextEdit,
    QVBoxLayout,
)

from wolf_update import (
    CheckStatus,
    GitHubReleaseSource,
    MemoryStateStore,
    UpdateApplication,
    UpdateService,
    UpdateState,
)
from wolf_update.qt import QtUpdateChecker

from . import __version__
from .theme import set_ui_role

UPDATE_REPOSITORY = "DrakonWolfDev/WolfLauncher"
UPDATE_DESTINATION = "https://wolf-forge.co.uk/wolf-launcher.html"
UPDATE_CHANNEL = "experimental"


class UpdateFeatureMixin:
    def setup_update_feature(self) -> None:
        state = UpdateState(
            last_successful_check=self.settings.get("update_last_successful_check"),
            dismissed_version=self.settings.get("update_dismissed_version"),
        )
        self.update_state_store = MemoryStateStore(state)
        application = UpdateApplication(
            current_version=__version__,
            repository=UPDATE_REPOSITORY,
            update_url=UPDATE_DESTINATION,
            channel=UPDATE_CHANNEL,
        )
        source = GitHubReleaseSource(
            application.repository,
            user_agent=f"WolfLauncher/{__version__}",
        )
        self.update_service = UpdateService(application, self.update_state_store, source=source)
        self.update_checker = QtUpdateChecker(self.update_service, self)
        self.update_checker.result_ready.connect(self.handle_update_result)
        self.update_thread = self.update_checker
        self.available_update = None

    def _build_update_banner(self) -> QFrame:
        banner = QFrame()
        banner.setObjectName("updateBanner")
        set_ui_role(banner, "updateBanner")
        banner.setVisible(False)
        banner.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Maximum)

        layout = QVBoxLayout(banner)
        layout.setContentsMargins(18, 12, 18, 12)
        layout.setSpacing(7)

        heading_row = QHBoxLayout()
        self.update_title = QLabel("WolfLauncher Update Available")
        set_ui_role(self.update_title, "cardTitle")
        self.update_version_label = QLabel()
        set_ui_role(self.update_version_label, "metadata")
        heading_row.addWidget(self.update_title)
        heading_row.addWidget(self.update_version_label)
        heading_row.addStretch(1)
        layout.addLayout(heading_row)

        self.update_notes_heading = QLabel("What's new:")
        self.update_notes_heading.setVisible(False)
        layout.addWidget(self.update_notes_heading)

        self.update_notes = QTextEdit()
        self.update_notes.setReadOnly(True)
        self.update_notes.setAcceptRichText(False)
        self.update_notes.setMaximumHeight(110)
        self.update_notes.setVisible(False)
        layout.addWidget(self.update_notes)

        actions = QHBoxLayout()
        self.update_notes_toggle = QPushButton("Show all notes")
        set_ui_role(self.update_notes_toggle, "disclosure")
        self.update_notes_toggle.clicked.connect(self.toggle_update_notes)
        self.update_notes_toggle.setVisible(False)
        actions.addWidget(self.update_notes_toggle)
        actions.addStretch(1)
        self.view_update_button = QPushButton("View Update")
        set_ui_role(self.view_update_button, "primary")
        self.view_update_button.clicked.connect(self.view_available_update)
        self.dismiss_update_button = QPushButton("Dismiss")
        self.dismiss_update_button.clicked.connect(self.dismiss_available_update)
        actions.addWidget(self.view_update_button)
        actions.addWidget(self.dismiss_update_button)
        layout.addLayout(actions)
        return banner

    def start_automatic_update_check(self) -> None:
        if getattr(self, "_shutting_down", False):
            return
        self._start_update_check(manual=False)

    def check_for_updates(self) -> None:
        if not self._start_update_check(manual=True):
            self.statusBar().showMessage("An update check is already running.", 5000)
            return
        self.statusBar().showMessage("Checking for WolfLauncher updates…")

    def _start_update_check(self, *, manual: bool) -> bool:
        if not self.update_checker.check(manual=manual):
            return False
        return True

    def handle_update_result(self, result, manual: bool) -> None:
        if manual:
            self.statusBar().clearMessage()
        self._persist_update_state()
        if result.status is CheckStatus.AVAILABLE:
            self.show_update_banner(result.release)
            if manual:
                self.statusBar().showMessage("A WolfLauncher update is available.", 5000)
            return
        if not manual:
            return
        if result.status is CheckStatus.UP_TO_DATE:
            QMessageBox.information(
                self,
                "WolfLauncher is up to date",
                f"Version {__version__} is the newest applicable release.",
            )
        elif result.status is CheckStatus.FAILED:
            QMessageBox.warning(
                self,
                "Could not check for updates",
                result.message or "WolfLauncher could not reach GitHub. Please try again later.",
            )

    def _persist_update_state(self) -> None:
        state = self.update_state_store.load()
        self.settings["update_last_successful_check"] = state.last_successful_check
        self.settings["update_dismissed_version"] = state.dismissed_version
        self.save_user_settings(silent=True)

    def show_update_banner(self, release) -> None:
        self.available_update = release
        self.update_version_label.setText(f"Version {release.version} is available.")
        notes = release.notes.strip()
        self.update_notes.setPlainText(notes)
        has_notes = bool(notes)
        self.update_notes_heading.setVisible(has_notes)
        self.update_notes.setVisible(has_notes)
        self.update_notes.setMaximumHeight(110)
        lengthy = len(notes) > 600 or notes.count("\n") > 7
        self.update_notes_toggle.setVisible(lengthy)
        self.update_notes_toggle.setText("Show all notes")
        self.update_banner.setVisible(True)

    def toggle_update_notes(self) -> None:
        expanded = self.update_notes.maximumHeight() > 110
        self.update_notes.setMaximumHeight(110 if expanded else 320)
        self.update_notes_toggle.setText("Show all notes" if expanded else "Show fewer notes")

    def dismiss_available_update(self) -> None:
        if self.available_update is not None:
            self.update_service.dismiss(self.available_update)
            self._persist_update_state()
        self.update_banner.setVisible(False)
        self.available_update = None

    def view_available_update(self) -> None:
        if self.update_service.view_update():
            return
        QMessageBox.warning(
            self,
            "Could not open the update page",
            "WolfLauncher could not open the Wolf Forge update page in your default browser.",
        )
