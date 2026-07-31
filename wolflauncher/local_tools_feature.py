"""Editor and local-development UI for explicit, user-owned mod profiles."""

from PySide6.QtCore import QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QComboBox,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from .launcher import DEFAULT_PLAYER_NAME
from .local_tools import DAYZ_EDITOR_MODS, LocalToolProfile, normalise_workshop_ids, parse_local_endpoint, profiles_from_settings
from .models import Server
from .mods import RequiredMod, WORKSHOP_URL, scan_installed_mods
from .native_launcher import NativeLaunchError, prepare_native_launch, prepare_native_local_launch
from .platform_detection import install_label
from .launch_dialogs import LaunchDialog
from .theme import set_monospace, set_ui_role


class LocalToolsFeatureMixin:
    def _build_local_tools_tab(self) -> QWidget:
        widget = QWidget()
        set_ui_role(widget, "workspace")
        layout = QVBoxLayout(widget)
        title = QLabel("Editor / Local Tools")
        set_ui_role(title, "summary")
        layout.addWidget(title)
        intro = QLabel(
            "Advanced local development sessions. WolfLauncher launches DayZ and joins an existing LAN/test server; it does not host or expose public servers."
        )
        intro.setWordWrap(True)
        set_ui_role(intro, "metadata")
        layout.addWidget(intro)

        self.local_tool_profiles = profiles_from_settings(self.settings.get("local_tool_profiles"))
        self.local_tool_active_index = 0
        profile_card = QFrame()
        set_ui_role(profile_card, "healthGroup")
        profile_layout = QVBoxLayout(profile_card)
        profile_layout.addWidget(QLabel("Local mod profile"))
        picker_row = QHBoxLayout()
        self.local_profile_picker = QComboBox()
        self.local_profile_picker.currentIndexChanged.connect(self._load_local_tool_profile)
        picker_row.addWidget(self.local_profile_picker, 1)
        new_profile = QPushButton("New profile")
        new_profile.clicked.connect(self._new_local_tool_profile)
        picker_row.addWidget(new_profile)
        profile_layout.addLayout(picker_row)
        form = QFormLayout()
        self.local_profile_name = QLineEdit()
        self.local_profile_mods = QLineEdit()
        set_monospace(self.local_profile_mods)
        self.local_profile_mods.setPlaceholderText("Workshop IDs, separated by commas")
        self.local_profile_endpoint = QLineEdit()
        self.local_profile_endpoint.setPlaceholderText("192.168.1.25:2302 (optional for Editor)")
        form.addRow("Name", self.local_profile_name)
        form.addRow("Client Workshop IDs", self.local_profile_mods)
        form.addRow("LAN test server", self.local_profile_endpoint)
        profile_layout.addLayout(form)
        profile_actions = QHBoxLayout()
        save_profile = QPushButton("Save profile")
        set_ui_role(save_profile, "accent")
        save_profile.clicked.connect(self._save_local_tool_profile)
        profile_actions.addWidget(save_profile)
        profile_actions.addStretch(1)
        profile_layout.addLayout(profile_actions)
        layout.addWidget(profile_card)

        self.local_tools_status = QLabel("Save a local mod profile, then verify its Workshop items before launching.")
        self.local_tools_status.setWordWrap(True)
        set_ui_role(self.local_tools_status, "metadata")

        editor_card = QFrame()
        set_ui_role(editor_card, "healthGroup")
        editor_layout = QVBoxLayout(editor_card)
        editor_title = QLabel("DayZ Editor")
        set_ui_role(editor_title, "cardTitle")
        editor_layout.addWidget(editor_title)
        editor_detail = QLabel("Launches an offline Editor session. DayZ Editor, CF and Dabs Framework are always included with the selected profile mods.")
        editor_detail.setWordWrap(True)
        set_ui_role(editor_detail, "metadata")
        editor_layout.addWidget(editor_detail)
        editor_actions = QHBoxLayout()
        verify_editor = QPushButton("Verify Editor mods")
        verify_editor.clicked.connect(lambda: self._verify_local_tool_mods(editor=True))
        open_editor_missing = QPushButton("Open missing Workshop pages")
        open_editor_missing.clicked.connect(lambda: self._open_missing_local_tool_pages(editor=True))
        launch_editor = QPushButton("Open DayZ Editor")
        set_ui_role(launch_editor, "primary")
        launch_editor.clicked.connect(self._launch_local_editor)
        editor_actions.addWidget(verify_editor)
        editor_actions.addWidget(open_editor_missing)
        editor_actions.addStretch(1)
        editor_actions.addWidget(launch_editor)
        editor_layout.addLayout(editor_actions)
        layout.addWidget(editor_card)

        local_card = QFrame()
        set_ui_role(local_card, "healthGroup")
        local_layout = QVBoxLayout(local_card)
        local_title = QLabel("Local Development")
        set_ui_role(local_title, "cardTitle")
        local_layout.addWidget(local_title)
        local_detail = QLabel("Launch DayZ with this profile and connect to an already-running local or LAN test server. Local server hosting, process control and logs are planned follow-on work.")
        local_detail.setWordWrap(True)
        set_ui_role(local_detail, "metadata")
        local_layout.addWidget(local_detail)
        local_actions = QHBoxLayout()
        verify_local = QPushButton("Verify profile mods")
        verify_local.clicked.connect(lambda: self._verify_local_tool_mods(editor=False))
        open_local_missing = QPushButton("Open missing Workshop pages")
        open_local_missing.clicked.connect(lambda: self._open_missing_local_tool_pages(editor=False))
        join_local = QPushButton("Join local test server")
        set_ui_role(join_local, "primary")
        join_local.clicked.connect(self._join_local_test_server)
        local_actions.addWidget(verify_local)
        local_actions.addWidget(open_local_missing)
        local_actions.addStretch(1)
        local_actions.addWidget(join_local)
        local_layout.addLayout(local_actions)
        layout.addWidget(local_card)
        layout.addWidget(self.local_tools_status)
        layout.addStretch(1)
        self._refresh_local_profile_picker()
        return widget

    def _refresh_local_profile_picker(self):
        if not hasattr(self, "local_profile_picker"):
            return
        self.local_profile_picker.blockSignals(True)
        self.local_profile_picker.clear()
        self.local_profile_picker.addItems([profile.name for profile in self.local_tool_profiles])
        self.local_profile_picker.blockSignals(False)
        if self.local_tool_profiles:
            self.local_profile_picker.setCurrentIndex(min(self.local_tool_active_index, len(self.local_tool_profiles) - 1))
            self._load_local_tool_profile(self.local_profile_picker.currentIndex())
        else:
            self._new_local_tool_profile()

    def _load_local_tool_profile(self, index: int):
        if index < 0 or index >= len(self.local_tool_profiles):
            return
        self.local_tool_active_index = index
        profile = self.local_tool_profiles[index]
        self.local_profile_name.setText(profile.name)
        self.local_profile_mods.setText(", ".join(profile.workshop_ids))
        self.local_profile_endpoint.setText(profile.endpoint)

    def _new_local_tool_profile(self):
        self.local_tool_active_index = -1
        self.local_profile_picker.setCurrentIndex(-1)
        self.local_profile_name.setText("New local profile")
        self.local_profile_mods.clear()
        self.local_profile_endpoint.clear()

    def _current_local_tool_profile(self) -> LocalToolProfile:
        name = self.local_profile_name.text().strip() or "Local development"
        return LocalToolProfile(name, normalise_workshop_ids(self.local_profile_mods.text()), self.local_profile_endpoint.text().strip())

    def _save_local_tool_profile(self):
        profile = self._current_local_tool_profile()
        if self.local_tool_active_index < 0:
            self.local_tool_profiles.append(profile)
            self.local_tool_active_index = len(self.local_tool_profiles) - 1
        else:
            self.local_tool_profiles[self.local_tool_active_index] = profile
        self._refresh_local_profile_picker()
        self.save_user_settings(silent=True)
        self.local_tools_status.setText(f"Saved local profile: {profile.name}.")

    def _local_required_mods(self, *, editor: bool) -> list[RequiredMod]:
        profile = self._current_local_tool_profile()
        names = dict(DAYZ_EDITOR_MODS) if editor else {}
        ids = list(names) + [item for item in profile.workshop_ids if item not in names]
        install = self.selected_steam_install()
        installed = scan_installed_mods(install.workshop_dir if install else None)
        return [RequiredMod(item, names.get(item, installed.get(item, "")), item in installed, installed.get(item, ""), WORKSHOP_URL.format(mod_id=item)) for item in ids]

    def _verify_local_tool_mods(self, *, editor: bool) -> list[RequiredMod]:
        mods = self._local_required_mods(editor=editor)
        missing = [mod for mod in mods if not mod.installed]
        label = "Editor" if editor else "local profile"
        if missing:
            self.local_tools_status.setText(f"{label}: {len(missing)} of {len(mods)} Workshop mod(s) missing. Open their Workshop pages or use Steam Downloads, then verify again.")
        else:
            self.local_tools_status.setText(f"{label}: all {len(mods)} Workshop mod(s) are installed locally.")
        return mods

    def _open_missing_local_tool_pages(self, *, editor: bool):
        missing = [mod for mod in self._verify_local_tool_mods(editor=editor) if not mod.installed]
        for mod in missing:
            QDesktopServices.openUrl(QUrl(mod.workshop_url))

    def _native_local_install(self):
        if self.launch_engine_key() != "native":
            QMessageBox.information(self, "Native launcher required", "Editor and Local Development use WolfLauncher’s native Steam handoff. Choose Native launcher in Settings first.")
            return None
        install = self.selected_steam_install()
        if not install:
            QMessageBox.warning(self, "Steam not detected", "WolfLauncher could not detect the selected Steam installation. Check Settings health.")
        return install

    def _launch_local_editor(self):
        install = self._native_local_install()
        if not install:
            return
        mods = self._verify_local_tool_mods(editor=True)
        try:
            prepared = prepare_native_local_launch(install, self.player_name.text().strip() or DEFAULT_PLAYER_NAME, mods)
        except NativeLaunchError as exc:
            QMessageBox.warning(self, f"Editor launch blocked during {exc.stage}", exc.user_message())
            return
        self._show_local_launch(prepared.command, "Opening DayZ Editor")

    def _join_local_test_server(self):
        install = self._native_local_install()
        if not install:
            return
        profile = self._current_local_tool_profile()
        try:
            host, port = parse_local_endpoint(profile.endpoint)
        except ValueError as exc:
            QMessageBox.warning(self, "LAN test server required", str(exc))
            return
        mods = self._verify_local_tool_mods(editor=False)
        if any(not mod.installed for mod in mods):
            QMessageBox.warning(self, "Local profile mods missing", "Install every listed Workshop item before joining the local test server.")
            return
        server = Server(profile.name, "Local development", host, port, port)
        try:
            prepared = prepare_native_launch(install, server, self.player_name.text().strip() or DEFAULT_PLAYER_NAME, mods)
        except NativeLaunchError as exc:
            QMessageBox.warning(self, f"Local launch blocked during {exc.stage}", exc.user_message())
            return
        self._show_local_launch(prepared.command, f"Joining {server.connect_target}")

    def _show_local_launch(self, command: list[str], title: str):
        self._save_local_tool_profile()
        dialog = LaunchDialog(self, command, title, "native local launch command")
        dialog.exec()
