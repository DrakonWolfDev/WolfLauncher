"""Editor and local-development UI for explicit, user-owned mod profiles."""

from pathlib import Path

from PySide6.QtCore import QProcess, QTimer, Qt, QUrl
from PySide6.QtGui import QDesktopServices, QPixmap
from PySide6.QtNetwork import QNetworkAccessManager, QNetworkReply, QNetworkRequest
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFormLayout,
    QFrame,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from .launcher import DEFAULT_PLAYER_NAME
from .local_server import (
    LocalServerLaunch,
    build_local_server_command,
    build_steamcmd_install_command,
    server_executable,
    sync_public_keys,
)
from .local_tools import (
    DAYZ_EDITOR_MODS,
    LocalToolProfile,
    normalise_workshop_ids,
    parse_local_endpoint,
    profiles_from_settings,
)
from .models import Server
from .mods import RequiredMod, WORKSHOP_URL, scan_installed_mods
from .native_launcher import NativeLaunchError, prepare_native_launch, prepare_native_local_launch
from .platform_detection import build_steam_start_command
from .launch_dialogs import LaunchDialog
from .theme import set_monospace, set_ui_role
from .workers import WorkshopSubscriptionWorker


DAYZ_EDITOR_IMAGE_URL = (
    "https://images.steamusercontent.com/ugc/11750326816948686244/"
    "3C971A82DF39596395E37D2F4AD63354D45006ED/?imw=360&imh=360&impolicy=Letterbox"
)


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
        self.local_host_settings = dict(self.settings.get("local_host_settings") or {})
        self.local_tool_active_index = 0
        self.editor_extra_mod_ids = set(
            normalise_workshop_ids(self.settings.get("editor_extra_mod_ids", []))
        )
        profile_card = QFrame()
        set_ui_role(profile_card, "healthGroup")
        profile_layout = QVBoxLayout(profile_card)
        profile_layout.addWidget(QLabel("Local development profile"))
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
        self.local_profile_endpoint.setPlaceholderText("192.168.1.25:2302")
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
        self.local_tools_status = QLabel("Save a local mod profile, then verify its Workshop items before launching.")
        self.local_tools_status.setWordWrap(True)
        set_ui_role(self.local_tools_status, "metadata")

        editor_card = QFrame()
        set_ui_role(editor_card, "healthGroup")
        editor_layout = QHBoxLayout(editor_card)
        editor_launch_panel = QWidget()
        editor_launch_layout = QHBoxLayout(editor_launch_panel)
        editor_launch_layout.setSpacing(14)
        self.editor_workshop_image = QLabel("DayZ Editor Workshop image")
        self.editor_workshop_image.setFixedSize(180, 180)
        self.editor_workshop_image.setAlignment(Qt.AlignCenter)
        set_ui_role(self.editor_workshop_image, "modThumbnail")
        editor_launch_layout.addWidget(self.editor_workshop_image)
        editor_content = QVBoxLayout()
        editor_title = QLabel("DayZ Editor")
        set_ui_role(editor_title, "cardTitle")
        editor_content.addWidget(editor_title)
        editor_detail = QLabel(
            "The DayZ Editor is an Open Source 3D Editing tool built to design new areas, "
            "create vivid screenshots, and test game mechanics. Users can place any item "
            "available in the game, import and export files from all types of mods, and brush "
            "the landscape with your new ideas."
        )
        editor_detail.setWordWrap(True)
        set_ui_role(editor_detail, "metadata")
        editor_content.addWidget(editor_detail)
        editor_actions = QHBoxLayout()
        verify_editor = QPushButton("Verify Editor mods")
        verify_editor.clicked.connect(lambda: self._verify_local_tool_mods(editor=True))
        launch_editor = QPushButton("Open DayZ Editor")
        set_ui_role(launch_editor, "primary")
        launch_editor.clicked.connect(self._launch_local_editor)
        editor_actions.addWidget(verify_editor)
        editor_actions.addStretch(1)
        editor_actions.addWidget(launch_editor)
        editor_content.addStretch(1)
        editor_content.addLayout(editor_actions)
        editor_launch_layout.addLayout(editor_content, 1)
        editor_layout.addWidget(editor_launch_panel, 3)

        editor_mods_panel = QWidget()
        editor_mods_layout = QVBoxLayout(editor_mods_panel)
        editor_mods_layout.setContentsMargins(8, 0, 0, 0)
        editor_mods_title = QLabel("Editor mods")
        set_ui_role(editor_mods_title, "cardTitle")
        editor_mods_layout.addWidget(editor_mods_title)
        editor_mods_detail = QLabel(
            "Extra locally installed mods. Core Editor requirements are included automatically."
        )
        editor_mods_detail.setWordWrap(True)
        set_ui_role(editor_mods_detail, "metadata")
        editor_mods_layout.addWidget(editor_mods_detail)
        editor_filter_row = QHBoxLayout()
        self.editor_mod_filter = QLineEdit()
        self.editor_mod_filter.setPlaceholderText("Filter installed mods")
        self.editor_mod_filter.setClearButtonEnabled(True)
        self.editor_mod_filter.textChanged.connect(self._filter_editor_mod_picker)
        refresh_editor_mods = QPushButton("Refresh installed mods")
        refresh_editor_mods.clicked.connect(self._refresh_editor_mod_picker)
        reset_editor_mods = QPushButton("Reset Editor mods")
        reset_editor_mods.clicked.connect(self._reset_editor_mod_picker)
        editor_filter_row.addWidget(self.editor_mod_filter, 1)
        editor_filter_row.addWidget(refresh_editor_mods)
        editor_filter_row.addWidget(reset_editor_mods)
        editor_mods_layout.addLayout(editor_filter_row)
        self.editor_mod_picker = QListWidget()
        self.editor_mod_picker.setAccessibleName("Installed extra Editor mods")
        self.editor_mod_picker.setMaximumHeight(154)
        editor_mods_layout.addWidget(self.editor_mod_picker)
        editor_layout.addWidget(editor_mods_panel, 2)
        layout.addWidget(editor_card)
        self.editor_image_manager = QNetworkAccessManager(self)
        self.editor_image_manager.finished.connect(self._finish_editor_image_load)
        self.editor_image_manager.get(QNetworkRequest(QUrl(DAYZ_EDITOR_IMAGE_URL)))
        layout.addSpacing(18)

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
        local_layout.addWidget(profile_card)

        host_card = QFrame()
        set_ui_role(host_card, "modDetail")
        host_layout = QVBoxLayout(host_card)
        host_title = QLabel("Local dedicated server")
        set_ui_role(host_title, "cardTitle")
        host_layout.addWidget(host_title)
        host_detail = QLabel(
            "Manage a server root available on this machine or mounted share. SteamCMD "
            "creates a disposable clean server; local packed mod folders stay user-owned."
        )
        host_detail.setWordWrap(True)
        set_ui_role(host_detail, "metadata")
        host_layout.addWidget(host_detail)
        host_form = QFormLayout()
        self.local_server_root = QLineEdit(str(self.local_host_settings.get("server_root") or ""))
        root_row = QHBoxLayout()
        root_row.addWidget(self.local_server_root, 1)
        root_browse = QPushButton("Browse")
        root_browse.clicked.connect(lambda: self._browse_local_folder(self.local_server_root))
        root_row.addWidget(root_browse)
        host_form.addRow("Server root", root_row)
        self.local_server_config = QLineEdit(str(self.local_host_settings.get("config") or ""))
        host_form.addRow("Server config", self.local_server_config)
        self.local_steamcmd = QLineEdit(str(self.local_host_settings.get("steamcmd") or ""))
        steamcmd_row = QHBoxLayout()
        steamcmd_row.addWidget(self.local_steamcmd, 1)
        steamcmd_browse = QPushButton("Browse")
        steamcmd_browse.clicked.connect(self._browse_steamcmd)
        steamcmd_row.addWidget(steamcmd_browse)
        host_form.addRow("SteamCMD", steamcmd_row)
        self.local_client_mod_paths = QLineEdit(
            str(self.local_host_settings.get("client_mod_paths") or "")
        )
        self.local_client_mod_paths.setPlaceholderText("Local packed/source folders, separated by ;")
        host_form.addRow("Client local mods", self.local_client_mod_paths)
        self.local_server_mod_paths = QLineEdit(
            str(self.local_host_settings.get("server_mod_paths") or "")
        )
        self.local_server_mod_paths.setPlaceholderText("Local packed/source folders, separated by ;")
        host_form.addRow("Server local mods", self.local_server_mod_paths)
        self.local_file_patching = QCheckBox("Development source mode (enable file patching)")
        self.local_file_patching.setChecked(bool(self.local_host_settings.get("file_patching")))
        self.local_file_patching.setToolTip(
            "For unpacked source testing only. Run a packed/signature test before release."
        )
        host_form.addRow("Source testing", self.local_file_patching)
        host_layout.addLayout(host_form)
        host_actions = QHBoxLayout()
        install_server = QPushButton("Install temporary server")
        install_server.clicked.connect(self._install_temporary_server)
        sync_keys = QPushButton("Sync public keys")
        sync_keys.clicked.connect(self._sync_local_server_keys)
        self.local_server_start = QPushButton("Start local server")
        set_ui_role(self.local_server_start, "primary")
        self.local_server_start.clicked.connect(self._start_local_server)
        self.local_server_stop = QPushButton("Stop server")
        self.local_server_stop.setEnabled(False)
        self.local_server_stop.clicked.connect(self._stop_local_server)
        host_actions.addWidget(install_server)
        host_actions.addWidget(sync_keys)
        host_actions.addStretch(1)
        host_actions.addWidget(self.local_server_stop)
        host_actions.addWidget(self.local_server_start)
        host_layout.addLayout(host_actions)
        local_layout.addWidget(host_card)
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
        self._refresh_editor_mod_picker()
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

    def _refresh_editor_mod_picker(self):
        if not hasattr(self, "editor_mod_picker"):
            return
        install = self.selected_steam_install()
        installed = scan_installed_mods(install.workshop_dir if install else None)
        fixed_ids = {workshop_id for workshop_id, _name in DAYZ_EDITOR_MODS}
        available = [
            (workshop_id, name)
            for workshop_id, name in installed.items()
            if workshop_id not in fixed_ids
        ]
        available.sort(key=lambda entry: ((entry[1] or entry[0]).casefold(), entry[0]))
        self.editor_mod_picker.clear()
        available_ids = set()
        for workshop_id, name in available:
            available_ids.add(workshop_id)
            item = QListWidgetItem(f"{name or workshop_id}  ({workshop_id})")
            item.setData(Qt.UserRole, workshop_id)
            item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
            item.setCheckState(
                Qt.Checked if workshop_id in self.editor_extra_mod_ids else Qt.Unchecked
            )
            self.editor_mod_picker.addItem(item)
        self.editor_extra_mod_ids.intersection_update(available_ids)
        self._filter_editor_mod_picker(self.editor_mod_filter.text())

    def _filter_editor_mod_picker(self, text: str):
        needle = text.strip().casefold()
        for row in range(self.editor_mod_picker.count()):
            item = self.editor_mod_picker.item(row)
            item.setHidden(bool(needle and needle not in item.text().casefold()))

    def _reset_editor_mod_picker(self):
        self.editor_mod_filter.clear()
        self.editor_extra_mod_ids.clear()
        for row in range(self.editor_mod_picker.count()):
            self.editor_mod_picker.item(row).setCheckState(Qt.Unchecked)
        self.save_user_settings(silent=True)
        self.local_tools_status.setText("Editor extra-mod selection cleared.")

    def _selected_editor_extra_mod_ids(self) -> tuple[str, ...]:
        selected = []
        for row in range(self.editor_mod_picker.count()):
            item = self.editor_mod_picker.item(row)
            if item.checkState() == Qt.Checked:
                selected.append(str(item.data(Qt.UserRole)))
        self.editor_extra_mod_ids = set(selected)
        return tuple(selected)

    def _local_required_mods(self, *, editor: bool) -> list[RequiredMod]:
        install = self.selected_steam_install()
        installed = scan_installed_mods(install.workshop_dir if install else None)
        if editor:
            names = dict(DAYZ_EDITOR_MODS)
            ids = list(names) + list(self._selected_editor_extra_mod_ids())
        else:
            profile = self._current_local_tool_profile()
            names = {}
            ids = list(profile.workshop_ids)
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
        self.save_user_settings(silent=True)
        if not install.running:
            command = build_steam_start_command(install)
            if not command or not QProcess.startDetached(command[0], command[1:])[0]:
                QMessageBox.warning(
                    self,
                    "Steam could not start",
                    "Start the selected Steam client, sign in, then open DayZ Editor again.",
                )
                return
            self.local_tools_status.setText("Starting Steam before preparing DayZ Editorâ€¦")
            self.local_editor_steam_attempts = 0
            QTimer.singleShot(1000, self._wait_for_editor_steam)
            return
        self._start_editor_workshop_resolution(install)

    def _wait_for_editor_steam(self):
        self.local_editor_steam_attempts += 1
        install = self.selected_steam_install()
        if install and install.running:
            self._start_editor_workshop_resolution(install)
            return
        if self.local_editor_steam_attempts >= 60:
            QMessageBox.warning(
                self,
                "Steam is not ready",
                "Steam did not become ready within 60 seconds. Sign in, then open DayZ Editor again.",
            )
            return
        QTimer.singleShot(1000, self._wait_for_editor_steam)

    def _start_editor_workshop_resolution(self, install):
        if self.workshop_subscription_worker and self.workshop_subscription_worker.isRunning():
            QMessageBox.information(
                self,
                "Steam Workshop in progress",
                "WolfLauncher is already waiting for a Steam Workshop operation to finish.",
            )
            return
        mods = self._local_required_mods(editor=True)
        editor_mods = mods[: len(DAYZ_EDITOR_MODS)]
        self.local_tools_status.setText(
            "Checking DayZ Editor, CF and Dabs Framework with Steam for updatesâ€¦"
        )
        worker = WorkshopSubscriptionWorker(
            [mod.workshop_id for mod in editor_mods], install, force_update=True
        )
        self.workshop_subscription_worker = worker
        worker.progress_ready.connect(self._update_editor_workshop_progress)
        worker.subscription_ready.connect(self._finish_editor_workshop_resolution)
        worker.finished.connect(self._clear_editor_workshop_worker)
        worker.start()

    def _update_editor_workshop_progress(self, snapshots):
        installed = sum(1 for item in snapshots if item.installed)
        self.local_tools_status.setText(
            f"Steam is preparing DayZ Editor requirements: {installed} of {len(snapshots)} ready."
        )

    def _finish_editor_workshop_resolution(self, result):
        if not result.ok:
            QMessageBox.warning(
                self,
                "DayZ Editor requirements incomplete",
                result.error or "Steam did not finish every required DayZ Editor item.",
            )
            return
        install = self.selected_steam_install()
        if not install:
            QMessageBox.warning(
                self,
                "Steam not detected",
                "The selected Steam installation is no longer available.",
            )
            return
        mods = self._verify_local_tool_mods(editor=True)
        try:
            prepared = prepare_native_local_launch(
                install, self.player_name.text().strip() or DEFAULT_PLAYER_NAME, mods
            )
        except NativeLaunchError as exc:
            QMessageBox.warning(self, f"Editor launch blocked during {exc.stage}", exc.user_message())
            return
        self._show_local_launch(prepared.command, "Opening DayZ Editor", minimize_on_handoff=True)

    def _clear_editor_workshop_worker(self):
        self.workshop_subscription_worker = None

    def _finish_editor_image_load(self, reply):
        if reply.error() != QNetworkReply.NoError:
            reply.deleteLater()
            return
        image = QPixmap()
        if image.loadFromData(bytes(reply.readAll())):
            self.editor_workshop_image.setPixmap(
                image.scaled(
                    self.editor_workshop_image.size(),
                    Qt.KeepAspectRatio,
                    Qt.SmoothTransformation,
                )
            )
        reply.deleteLater()

    def _browse_local_folder(self, target: QLineEdit):
        selected = QFileDialog.getExistingDirectory(self, "Select local DayZ folder")
        if selected:
            target.setText(selected)
            if target is self.local_server_root and not self.local_server_config.text().strip():
                self.local_server_config.setText(str(Path(selected) / "serverDZ.cfg"))

    def _browse_steamcmd(self):
        path, _ = QFileDialog.getOpenFileName(self, "Select SteamCMD")
        if path:
            self.local_steamcmd.setText(path)

    @staticmethod
    def _local_path_list(value: str) -> tuple[Path, ...]:
        return tuple(Path(part.strip()) for part in value.split(";") if part.strip())

    def _save_local_host_settings(self):
        self.local_host_settings = {
            "server_root": self.local_server_root.text().strip(),
            "config": self.local_server_config.text().strip(),
            "steamcmd": self.local_steamcmd.text().strip(),
            "client_mod_paths": self.local_client_mod_paths.text().strip(),
            "server_mod_paths": self.local_server_mod_paths.text().strip(),
            "file_patching": self.local_file_patching.isChecked(),
        }
        self.save_user_settings(silent=True)

    def _install_temporary_server(self):
        root = Path(self.local_server_root.text().strip())
        try:
            command = build_steamcmd_install_command(Path(self.local_steamcmd.text().strip()), root)
        except ValueError as exc:
            QMessageBox.warning(self, "SteamCMD install unavailable", str(exc))
            return
        reply = QMessageBox.question(
            self,
            "Install temporary DayZ server?",
            "SteamCMD will download or validate DayZ Dedicated Server into the selected server root. "
            "Existing files in that folder may be updated. Continue?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if reply != QMessageBox.Yes:
            return
        self._save_local_host_settings()
        process = QProcess(self)
        process.setWorkingDirectory(str(root.parent))
        process.finished.connect(lambda _code, _status: self._finish_temporary_server_install())
        self.local_server_install_process = process
        process.start(command[0], command[1:])
        self.local_tools_status.setText("SteamCMD is preparing the temporary DayZ dedicated serverâ€¦")

    def _finish_temporary_server_install(self):
        process = getattr(self, "local_server_install_process", None)
        if not process:
            return
        if process.exitCode() == 0:
            root = Path(self.local_server_root.text().strip())
            executable = server_executable(root)
            if executable:
                self.local_tools_status.setText("Temporary DayZ dedicated server is ready.")
            else:
                self.local_tools_status.setText(
                    "SteamCMD completed, but the dedicated-server executable was not found. "
                    "Check the selected server root."
                )
        else:
            self.local_tools_status.setText(
                "SteamCMD could not prepare the temporary server. Check SteamCMD's output and login state."
            )
        self.local_server_install_process = None

    def _local_server_launch(self) -> LocalServerLaunch:
        root = Path(self.local_server_root.text().strip())
        executable = server_executable(root)
        if executable is None:
            raise ValueError("DayZ dedicated-server executable was not found in the selected server root.")
        profile = self._current_local_tool_profile()
        _host, port = parse_local_endpoint(profile.endpoint)
        config = Path(self.local_server_config.text().strip() or root / "serverDZ.cfg")
        return LocalServerLaunch(
            root=root,
            executable=executable,
            config=config,
            profiles=root / "profiles",
            port=port,
            mod_paths=self._local_path_list(self.local_client_mod_paths.text()),
            server_mod_paths=self._local_path_list(self.local_server_mod_paths.text()),
            file_patching=self.local_file_patching.isChecked(),
        )

    def _start_local_server(self):
        process = getattr(self, "local_server_process", None)
        if process and process.state() != QProcess.NotRunning:
            QMessageBox.information(self, "Local server running", "Stop the managed local server before starting it again.")
            return
        try:
            launch = self._local_server_launch()
            command = build_local_server_command(launch)
        except ValueError as exc:
            QMessageBox.warning(self, "Local server cannot start", str(exc))
            return
        self._save_local_host_settings()
        process = QProcess(self)
        process.setWorkingDirectory(str(launch.root))
        process.finished.connect(self._local_server_finished)
        self.local_server_process = process
        self.local_server_start.setEnabled(False)
        self.local_server_stop.setEnabled(True)
        process.start(command[0], command[1:])
        self.local_tools_status.setText(f"Starting local DayZ server on port {launch.port}â€¦")

    def _stop_local_server(self):
        process = getattr(self, "local_server_process", None)
        if process and process.state() != QProcess.NotRunning:
            process.terminate()
            self.local_tools_status.setText("Stopping the managed local DayZ serverâ€¦")

    def _local_server_finished(self, _exit_code, _status):
        self.local_server_process = None
        self.local_server_start.setEnabled(True)
        self.local_server_stop.setEnabled(False)
        self.local_tools_status.setText("Managed local DayZ server stopped.")

    def _sync_local_server_keys(self):
        root = Path(self.local_server_root.text().strip())
        paths = self._local_path_list(self.local_client_mod_paths.text()) + self._local_path_list(
            self.local_server_mod_paths.text()
        )
        reply = QMessageBox.question(
            self,
            "Sync public mod keys?",
            "WolfLauncher will copy public .bikey files from the selected packed local mod "
            "folders into the server keys directory. Existing matching public keys may be replaced. "
            "Private keys are never copied. Continue?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if reply != QMessageBox.Yes:
            return
        try:
            copied = sync_public_keys(paths, root)
        except (OSError, ValueError) as exc:
            QMessageBox.warning(self, "Could not sync public keys", str(exc))
            return
        self._save_local_host_settings()
        self.local_tools_status.setText(
            f"Synced {len(copied)} public mod key(s) to {root / 'keys'}."
        )

    def _with_local_client_mods(self, command: list[str]) -> list[str]:
        local_paths = self._local_path_list(self.local_client_mod_paths.text())
        missing = [str(path) for path in local_paths if not path.is_dir()]
        if missing:
            raise ValueError("Local client mod folder not found: " + ", ".join(missing))
        if not local_paths:
            return command
        updated = list(command)
        mod_index = next(
            (index for index, value in enumerate(updated) if value.startswith("-mod=")), None
        )
        suffix = ";".join(str(path) for path in local_paths)
        if mod_index is None:
            connect_index = next(
                (index for index, value in enumerate(updated) if value.startswith("-connect=")),
                len(updated),
            )
            updated.insert(connect_index, f"-mod={suffix}")
        else:
            updated[mod_index] = updated[mod_index] + ";" + suffix
        if self.local_file_patching.isChecked() and "-filePatching" not in updated:
            updated.append("-filePatching")
        return updated

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
            command = self._with_local_client_mods(prepared.command)
        except NativeLaunchError as exc:
            QMessageBox.warning(self, f"Local launch blocked during {exc.stage}", exc.user_message())
            return
        except ValueError as exc:
            QMessageBox.warning(self, "Local launch blocked", str(exc))
            return
        self._show_local_launch(command, f"Joining {server.connect_target}")

    def _show_local_launch(self, command: list[str], title: str, *, minimize_on_handoff: bool = False):
        self._save_local_tool_profile()
        dialog = LaunchDialog(
            self,
            command,
            title,
            "native local launch command",
            minimize_on_handoff=minimize_on_handoff,
        )
        dialog.exec()
