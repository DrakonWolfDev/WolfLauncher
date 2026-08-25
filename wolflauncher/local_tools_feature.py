"""Editor and local-development UI for explicit, user-owned mod profiles."""

from pathlib import Path

from PySide6.QtCore import QPropertyAnimation, QProcess, Qt, QTimer, QUrl
from PySide6.QtGui import QDesktopServices, QPixmap
from PySide6.QtNetwork import QNetworkAccessManager, QNetworkReply, QNetworkRequest
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFileDialog,
    QFormLayout,
    QFrame,
    QGraphicsOpacityEffect,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from .launch_dialogs import LaunchDialog
from .launcher import DEFAULT_PLAYER_NAME
from .local_server import (
    LocalServerLaunch,
    build_local_server_command,
    build_steamcmd_install_command,
    server_executable,
    steam_server_root,
    sync_public_keys,
)
from .local_tools import (
    DAYZ_EDITOR_MODS,
    LocalToolProfile,
    parse_local_endpoint,
    profiles_from_settings,
)
from .models import Server
from .mods import WORKSHOP_URL, RequiredMod, scan_installed_mods
from .native_launcher import NativeLaunchError, prepare_native_launch, prepare_native_local_launch
from .platform_detection import build_steam_start_command
from .platforms import current_platform
from .theme import set_monospace, set_ui_role
from .thumbnail_safety import (
    MAX_THUMBNAIL_BYTES,
    THUMBNAIL_REQUEST_TIMEOUT_MS,
    is_safe_thumbnail_content_type,
    is_safe_thumbnail_dimensions,
    is_safe_thumbnail_url,
)
from .workers import WorkshopDependencyWorker, WorkshopSubscriptionWorker

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
        # Editor selections are an ephemeral launch workspace. Keeping them
        # between app sessions is surprising and can quietly launch old mods.
        self.editor_extra_mod_ids = set()
        self.local_extra_mod_ids = set()
        self.mod_selection_target = "editor"
        self.editor_dependency_mod_ids = set()
        self.editor_dependency_excluded_ids = set()
        self.editor_dependency_metadata = {}
        self.editor_dependency_request = 0
        self.editor_dependency_worker = None
        self.editor_dependency_pending = False
        self.editor_addon_dependency_worker = None
        self.editor_addon_dependencies_checked = False
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
        self.local_profile_mods.textChanged.connect(self._update_mod_selection_summary)
        set_monospace(self.local_profile_mods)
        self.local_profile_mods.setPlaceholderText(
            "Packed or unpacked local mod folders, separated by ;"
        )
        self.local_profile_endpoint = QLineEdit()
        self.local_profile_endpoint.setPlaceholderText("192.168.1.25:2302")
        form.addRow("Name", self.local_profile_name)
        form.addRow("LAN test server", self.local_profile_endpoint)
        local_mod_row = QHBoxLayout()
        local_mod_row.addWidget(self.local_profile_mods, 1)
        browse_local_mod = QPushButton("Browse")
        browse_local_mod.clicked.connect(self._browse_local_profile_mod)
        local_mod_row.addWidget(browse_local_mod)
        form.addRow("Local mod folders", local_mod_row)
        self.local_file_patching = QCheckBox("Source testing (enable file patching)")
        self.local_file_patching.setChecked(bool(self.local_host_settings.get("file_patching")))
        self.local_file_patching.setToolTip(
            "Enable this only for unpacked source testing. Packed @mod folders do not need it."
        )
        form.addRow("Source testing", self.local_file_patching)
        profile_layout.addLayout(form)
        profile_actions = QHBoxLayout()
        save_profile = QPushButton("Save profile")
        set_ui_role(save_profile, "accent")
        save_profile.clicked.connect(self._save_local_tool_profile)
        profile_actions.addWidget(save_profile)
        profile_actions.addStretch(1)
        profile_layout.addLayout(profile_actions)
        self.local_tools_status = QLabel(
            "Save a local mod profile, then verify its Workshop items before launching."
        )
        self.local_tools_status.setWordWrap(True)
        set_ui_role(self.local_tools_status, "metadata")

        editor_card = QFrame()
        set_ui_role(editor_card, "healthGroup")
        editor_layout = QHBoxLayout(editor_card)
        editor_layout.setAlignment(Qt.AlignTop)
        editor_launch_panel = QWidget()
        editor_launch_layout = QHBoxLayout(editor_launch_panel)
        editor_launch_layout.setAlignment(Qt.AlignTop)
        editor_launch_layout.setSpacing(14)
        self.editor_workshop_image = QLabel("DayZ Editor Workshop image")
        self.editor_workshop_image.setFixedSize(180, 180)
        self.editor_workshop_image.setAlignment(Qt.AlignCenter)
        set_ui_role(self.editor_workshop_image, "modThumbnail")
        editor_launch_layout.addWidget(self.editor_workshop_image, 0, Qt.AlignTop)
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
        self.editor_session_button = QPushButton("Choose DayZ Editor")
        set_ui_role(self.editor_session_button, "primary")
        self.editor_session_button.clicked.connect(lambda: self._choose_local_tool_session("editor"))
        editor_actions.addWidget(verify_editor)
        editor_actions.addStretch(1)
        editor_actions.addWidget(self.editor_session_button)
        editor_content.addStretch(1)
        editor_content.addLayout(editor_actions)
        editor_launch_layout.addLayout(editor_content, 1)
        editor_layout.addWidget(editor_launch_panel, 3)

        editor_mods_panel = QWidget()
        editor_mods_layout = QVBoxLayout(editor_mods_panel)
        editor_mods_layout.setContentsMargins(0, 0, 0, 0)
        self.editor_mods_title = QLabel("Installed Workshop mods")
        editor_mods_title = self.editor_mods_title
        set_ui_role(editor_mods_title, "cardTitle")
        editor_mods_layout.addWidget(editor_mods_title)
        self.mod_selection_detail = QLabel()
        self.mod_selection_detail.setWordWrap(True)
        set_ui_role(self.mod_selection_detail, "metadata")
        editor_mods_layout.addWidget(self.mod_selection_detail)
        editor_mods_layout.addSpacing(8)
        editor_filter_row = QHBoxLayout()
        self.editor_mod_filter = QLineEdit()
        self.editor_mod_filter.setPlaceholderText("Filter installed mods")
        self.editor_mod_filter.setClearButtonEnabled(True)
        self.editor_mod_filter.textChanged.connect(self._filter_editor_mod_picker)
        refresh_editor_mods = QPushButton("Refresh installed mods")
        refresh_editor_mods.clicked.connect(self._refresh_editor_mod_picker)
        self.reset_editor_mods = QPushButton("Clear enabled mods")
        self.reset_editor_mods.clicked.connect(self._reset_editor_mod_picker)
        editor_filter_row.addWidget(self.editor_mod_filter, 1)
        editor_filter_row.addWidget(refresh_editor_mods)
        editor_filter_row.addWidget(self.reset_editor_mods)
        editor_mods_layout.addLayout(editor_filter_row)
        self.editor_mod_picker = QListWidget()
        self.editor_mod_picker.setAccessibleName("Installed additional mods")
        self.editor_mod_picker.itemChanged.connect(self._editor_mod_selection_changed)
        self.editor_mod_picker_opacity = QGraphicsOpacityEffect(self.editor_mod_picker)
        self.editor_mod_picker.setGraphicsEffect(self.editor_mod_picker_opacity)
        self.editor_mod_picker_animation = QPropertyAnimation(self.editor_mod_picker_opacity, b"opacity", self)
        self.editor_mod_picker_animation.setDuration(180)
        editor_mods_layout.addWidget(self.editor_mod_picker)
        self.editor_image_manager = QNetworkAccessManager(self)
        self.editor_image_manager.finished.connect(self._finish_editor_image_load)
        self.editor_image_reply = None
        self._load_editor_image()

        local_card = QFrame()
        set_ui_role(local_card, "healthGroup")
        local_layout = QVBoxLayout(local_card)
        local_layout.setAlignment(Qt.AlignTop)
        local_title = QLabel("Local Server")
        set_ui_role(local_title, "cardTitle")
        local_layout.addWidget(local_title)
        local_detail = QLabel(
            "Select the installed Workshop mods required for this local development profile, then launch DayZ "
            "and connect to an already-running local or LAN test server. Local server hosting, process control "
            "and logs are planned follow-on work."
        )
        local_detail.setWordWrap(True)
        set_ui_role(local_detail, "metadata")
        local_layout.addWidget(local_detail)
        local_layout.addWidget(profile_card)

        local_actions = QHBoxLayout()
        verify_local = QPushButton("Verify profile mods")
        verify_local.clicked.connect(lambda: self._verify_local_tool_mods(editor=False))
        self.local_session_button = QPushButton("Choose local server")
        set_ui_role(self.local_session_button, "primary")
        self.local_session_button.clicked.connect(lambda: self._choose_local_tool_session("local"))
        local_actions.addWidget(verify_local)
        local_actions.addStretch(1)
        local_actions.addWidget(self.local_session_button)
        local_layout.addLayout(local_actions)

        # Choosing a session clears the other large card from the work area. The
        # focused card then shares the page evenly with the mod picker.
        self.local_tool_workspace = QStackedWidget()
        choice_page = QWidget()
        self.local_tool_choice_layout = QHBoxLayout(choice_page)
        self.local_tool_choice_layout.setContentsMargins(0, 0, 0, 0)
        self.local_tool_choice_layout.setSpacing(12)
        self.local_tool_choice_layout.addWidget(editor_card, 1)
        self.local_tool_choice_layout.addWidget(local_card, 1)

        active_page = QWidget()
        active_layout = QHBoxLayout(active_page)
        active_layout.setContentsMargins(0, 0, 0, 0)
        active_layout.setSpacing(12)
        active_left = QWidget()
        self.local_tool_active_left_layout = QVBoxLayout(active_left)
        self.local_tool_active_left_layout.setContentsMargins(0, 0, 0, 0)
        back_row = QHBoxLayout()
        back_to_choice = QPushButton("← Choose a different session")
        set_ui_role(back_to_choice, "disclosure")
        back_to_choice.clicked.connect(self._return_to_local_tool_choice)
        back_row.addWidget(back_to_choice)
        back_row.addStretch(1)
        self.local_tool_active_left_layout.addLayout(back_row)
        self.selected_mods_title = QLabel("Selected mods")
        set_ui_role(self.selected_mods_title, "cardTitle")
        self.selected_mods_panel = QFrame()
        set_ui_role(self.selected_mods_panel, "healthGroup")
        selected_mods_layout = QVBoxLayout(self.selected_mods_panel)
        selected_mods_layout.addWidget(self.selected_mods_title)
        self.selected_mods_hint = QLabel()
        self.selected_mods_hint.setWordWrap(True)
        set_ui_role(self.selected_mods_hint, "metadata")
        selected_mods_layout.addWidget(self.selected_mods_hint)
        self.selected_mods_scroll = QScrollArea()
        self.selected_mods_scroll.setWidgetResizable(True)
        self.selected_mods_scroll.setFrameShape(QFrame.NoFrame)
        self.selected_mods_container = QWidget()
        self.selected_mods_layout = QVBoxLayout(self.selected_mods_container)
        self.selected_mods_layout.setContentsMargins(0, 4, 0, 0)
        self.selected_mods_layout.setSpacing(6)
        # The scroll area's child grows to the viewport. A trailing stretch
        # consequently absorbs that spare height *between* the pills as the
        # viewport is relaid out, leaving apparent gaps after scrolling.
        # Keep the normal layout top-aligned instead.
        self.selected_mods_layout.setAlignment(Qt.AlignTop)
        self.selected_mods_scroll.setWidget(self.selected_mods_container)
        selected_mods_layout.addWidget(self.selected_mods_scroll, 1)
        self.local_tool_active_left_layout.addWidget(self.selected_mods_panel, 1)
        active_layout.addWidget(active_left, 1)
        active_layout.addWidget(editor_mods_panel, 1)
        self.local_tool_workspace.addWidget(choice_page)
        self.local_tool_workspace.addWidget(active_page)
        self.local_tool_cards = {"editor": editor_card, "local": local_card}
        self.local_tool_active_target = None
        # This is the primary tab content. Give it the spare vertical space so
        # the focused selection and installed-mod list reach the tab footer.
        layout.addWidget(self.local_tool_workspace, 1)
        layout.addWidget(self.local_tools_status)
        self._refresh_local_profile_picker()
        self._refresh_editor_mod_picker()
        self._set_mod_selection_target("editor", animate=False)
        return widget

    def _refresh_local_profile_picker(self):
        if not hasattr(self, "local_profile_picker"):
            return
        self.local_profile_picker.blockSignals(True)
        self.local_profile_picker.clear()
        self.local_profile_picker.addItems([profile.name for profile in self.local_tool_profiles])
        self.local_profile_picker.blockSignals(False)
        if self.local_tool_profiles:
            self.local_profile_picker.setCurrentIndex(
                min(self.local_tool_active_index, len(self.local_tool_profiles) - 1)
            )
            self._load_local_tool_profile(self.local_profile_picker.currentIndex())
        else:
            self._new_local_tool_profile()

    def _load_local_tool_profile(self, index: int):
        if index < 0 or index >= len(self.local_tool_profiles):
            return
        self.local_tool_active_index = index
        profile = self.local_tool_profiles[index]
        self.local_profile_name.setText(profile.name)
        self.local_profile_mods.setText("; ".join(profile.mod_paths))
        self.local_profile_endpoint.setText(profile.endpoint)
        self.local_extra_mod_ids = set(profile.workshop_mod_ids)
        self._refresh_editor_mod_picker()

    def _new_local_tool_profile(self):
        self.local_tool_active_index = -1
        self.local_profile_picker.setCurrentIndex(-1)
        self.local_profile_name.setText("New local profile")
        self.local_profile_mods.clear()
        self.local_profile_endpoint.clear()
        self.local_extra_mod_ids.clear()
        self._refresh_editor_mod_picker()

    def _current_local_tool_profile(self) -> LocalToolProfile:
        name = self.local_profile_name.text().strip() or "Local development"
        return LocalToolProfile(
            name,
            tuple(str(path) for path in self._local_path_list(self.local_profile_mods.text())),
            self.local_profile_endpoint.text().strip(),
            tuple(sorted(self.local_extra_mod_ids, key=int)),
        )

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
        known_names = {
            workshop_id: str(detail.get("title") or "")
            for workshop_id, detail in self.editor_dependency_metadata.items()
        }
        available = [
            (workshop_id, name)
            for workshop_id, name in installed.items()
            if workshop_id not in fixed_ids
        ]
        available_ids = {workshop_id for workshop_id, _name in available}
        for workshop_id in self.editor_dependency_mod_ids if self.mod_selection_target == "editor" else ():
            if workshop_id not in available_ids and workshop_id not in fixed_ids:
                available.append((workshop_id, known_names.get(workshop_id, "")))
        available.sort(key=lambda entry: ((entry[1] or entry[0]).casefold(), entry[0]))
        self.editor_mod_picker.blockSignals(True)
        self.editor_mod_picker.clear()
        for workshop_id, name in available:
            available_ids.add(workshop_id)
            required = self.mod_selection_target == "editor" and workshop_id in self.editor_dependency_mod_ids
            label = f"{name or workshop_id}  ({workshop_id})"
            if required:
                label += " — auto-detected requirement"
            item = QListWidgetItem(label)
            item.setData(Qt.UserRole, workshop_id)
            item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
            item.setCheckState(
                Qt.Checked
                if workshop_id in self._active_extra_mod_ids()
                or (required and workshop_id not in self.editor_dependency_excluded_ids)
                else Qt.Unchecked
            )
            self.editor_mod_picker.addItem(item)
        self.editor_mod_picker.blockSignals(False)
        self._filter_editor_mod_picker(self.editor_mod_filter.text())
        self._update_mod_selection_summary()

    def _filter_editor_mod_picker(self, text: str):
        needle = text.strip().casefold()
        for row in range(self.editor_mod_picker.count()):
            item = self.editor_mod_picker.item(row)
            item.setHidden(bool(needle and needle not in item.text().casefold()))

    def _reset_editor_mod_picker(self):
        self.editor_mod_filter.clear()
        self._active_extra_mod_ids().clear()
        if self.mod_selection_target == "editor":
            self.editor_dependency_mod_ids.clear()
            self.editor_dependency_excluded_ids.clear()
            self.editor_dependency_metadata.clear()
        for row in range(self.editor_mod_picker.count()):
            self.editor_mod_picker.item(row).setCheckState(Qt.Unchecked)
        self.save_user_settings(silent=True)
        self.local_tools_status.setText("Enabled mod selection cleared.")

    def _selected_editor_extra_mod_ids(self) -> tuple[str, ...]:
        selected = list(self.editor_extra_mod_ids)
        selected.extend(
            workshop_id
            for workshop_id in self.editor_dependency_mod_ids
            if workshop_id not in self.editor_extra_mod_ids
            and workshop_id not in self.editor_dependency_excluded_ids
        )
        return tuple(selected)

    def _selected_local_extra_mod_ids(self) -> tuple[str, ...]:
        return tuple(sorted(self.local_extra_mod_ids, key=int))

    def _active_extra_mod_ids(self) -> set[str]:
        return self.editor_extra_mod_ids if self.mod_selection_target == "editor" else self.local_extra_mod_ids

    def _choose_local_tool_session(self, target: str):
        """Focus one session card and reveal its mod workspace beside it."""
        if self.local_tool_active_target == target:
            if target == "editor":
                self._launch_local_editor()
            else:
                self._join_local_test_server()
            return
        if self.local_tool_active_target:
            self._return_to_local_tool_choice()
        card = self.local_tool_cards[target]
        self.local_tool_choice_layout.removeWidget(card)
        self.local_tool_active_left_layout.insertWidget(1, card)
        self.local_tool_active_target = target
        self._set_mod_selection_target(target)
        if target == "editor":
            self.editor_session_button.setText("Open DayZ Editor")
            self.editor_mods_title.setText("Add installed Editor mods")
        else:
            self.local_session_button.setText("Join local test server")
            self.editor_mods_title.setText("Add installed server mods")
        self.local_tool_workspace.setCurrentIndex(1)

    def _return_to_local_tool_choice(self):
        target = self.local_tool_active_target
        if not target:
            return
        card = self.local_tool_cards[target]
        self.local_tool_active_left_layout.removeWidget(card)
        # Restore the initial left-to-right choice order every time. Appending
        # the card made the previously focused session swap sides on return.
        self.local_tool_choice_layout.insertWidget(0 if target == "editor" else 1, card, 1)
        self.editor_session_button.setText("Choose DayZ Editor")
        self.local_session_button.setText("Choose local server")
        self.local_tool_active_target = None
        self.local_tool_workspace.setCurrentIndex(0)

    def _set_mod_selection_target(self, target: str, *, animate: bool = True):
        self.mod_selection_target = target
        if target == "editor":
            self.mod_selection_detail.setText(
                "DayZ Editor automatically enables DayZ Editor, CF and Dabs Framework. Choose any additional installed Workshop mods below."
            )
        else:
            self.mod_selection_detail.setText(
                "Choose the installed Workshop mods required by the active local development profile. Local folders are added from the profile on the left."
            )
        if animate:
            self.editor_mod_picker_animation.stop()
            self.editor_mod_picker_animation.setStartValue(0.35)
            self.editor_mod_picker_animation.setEndValue(1.0)
            self.editor_mod_picker_animation.start()
        self._refresh_editor_mod_picker()

    def _editor_mod_selection_changed(self, item):
        workshop_id = str(item.data(Qt.UserRole) or "")
        if not workshop_id:
            return
        if self.mod_selection_target == "editor" and workshop_id in self.editor_dependency_mod_ids:
            if item.checkState() == Qt.Checked:
                self.editor_dependency_excluded_ids.discard(workshop_id)
            else:
                self.editor_dependency_excluded_ids.add(workshop_id)
            self.save_user_settings(silent=True)
            return
        if item.checkState() == Qt.Checked:
            self._active_extra_mod_ids().add(workshop_id)
        else:
            self._active_extra_mod_ids().discard(workshop_id)
        if self.mod_selection_target == "editor":
            self.editor_addon_dependencies_checked = False
            self._resolve_editor_dependencies()
        self.save_user_settings(silent=True)
        self._update_mod_selection_summary()

    def _resolve_editor_dependencies(self):
        self.editor_dependency_request += 1
        if self.editor_dependency_worker and self.editor_dependency_worker.isRunning():
            # Steam's dependency endpoint is unreliable under overlapping
            # requests. Finish this pass, then resolve the newest full set.
            self.editor_dependency_pending = True
            return
        self._start_editor_dependency_resolution()

    def _start_editor_dependency_resolution(self):
        request = self.editor_dependency_request
        roots = tuple(sorted(self.editor_extra_mod_ids, key=int))
        if not roots:
            self.editor_dependency_pending = False
            self.editor_dependency_mod_ids.clear()
            self.editor_dependency_excluded_ids.clear()
            self.editor_dependency_metadata.clear()
            self._refresh_editor_mod_picker()
            return
        worker = WorkshopDependencyWorker(roots)
        worker.setParent(self)
        self.editor_dependency_worker = worker
        worker.dependencies_ready.connect(
            lambda resolved, metadata: self._finish_editor_dependency_resolution(
                request, roots, resolved, metadata
            )
        )
        worker.finished.connect(lambda active=worker: self._clear_editor_dependency_worker(active))
        worker.start()

    def _finish_editor_dependency_resolution(self, request, roots, resolved, metadata):
        if request != self.editor_dependency_request:
            # A newer selection is queued, but do not discard a completed
            # result for roots that are still selected. The queued pass will
            # reconcile the full set afterwards.
            if set(roots).intersection(self.editor_extra_mod_ids):
                fixed_ids = {workshop_id for workshop_id, _name in DAYZ_EDITOR_MODS}
                self.editor_dependency_mod_ids.update(set(resolved) - set(roots) - fixed_ids)
                self.editor_dependency_metadata.update(metadata)
                self._refresh_editor_mod_picker()
            return
        fixed_ids = {workshop_id for workshop_id, _name in DAYZ_EDITOR_MODS}
        self.editor_dependency_mod_ids = set(resolved) - set(roots) - fixed_ids
        self.editor_dependency_excluded_ids.intersection_update(self.editor_dependency_mod_ids)
        self.editor_dependency_metadata = dict(metadata)
        self._refresh_editor_mod_picker()
        self._update_mod_selection_summary()
        count = len(self.editor_dependency_mod_ids)
        if count:
            self.local_tools_status.setText(
                f"Added {count} detected Workshop requirement(s) to the selection."
            )

    def _enabled_mod_entries(self, *, editor: bool) -> list[str]:
        """Return readable entries for the selected launch mode."""
        install = self.selected_steam_install()
        installed = scan_installed_mods(install.workshop_dir if install else None)
        dependency_names = {
            workshop_id: str(detail.get("title") or "")
            for workshop_id, detail in self.editor_dependency_metadata.items()
        }
        entries = []
        if editor:
            entries.extend(
                f"{name} ({workshop_id}) — included automatically"
                for workshop_id, name in DAYZ_EDITOR_MODS
            )
        selected_ids = (
            self._selected_editor_extra_mod_ids()
            if editor
            else self._selected_local_extra_mod_ids()
        )
        for workshop_id in selected_ids:
            name = installed.get(workshop_id) or dependency_names.get(workshop_id) or workshop_id
            entries.append(f"{name} ({workshop_id})")
        return entries

    def _update_mod_selection_summary(self):
        if not hasattr(self, "selected_mods_layout"):
            return
        entries = self._enabled_mod_entries(editor=self.mod_selection_target == "editor")
        local_paths = (
            [str(path) for path in self._current_local_tool_profile().mod_paths]
            if self.mod_selection_target == "local"
            else []
        )
        self._update_selected_mod_pills(entries, local_paths)

    def _update_selected_mod_pills(self, entries: list[str], local_paths: list[str]):
        """Keep the focused workspace's selection readable as individual pills."""
        if not hasattr(self, "selected_mods_layout"):
            return
        while self.selected_mods_layout.count():
            item = self.selected_mods_layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()
        all_entries = entries + [f"Local folder: {path}" for path in local_paths]
        session_name = "DayZ Editor" if self.mod_selection_target == "editor" else "Local Server"
        self.selected_mods_title.setText(f"{session_name} selection")
        self.selected_mods_hint.setText(
            f"{len(all_entries)} mod{'s' if len(all_entries) != 1 else ''} enabled. "
            "Selections appear here as you check them."
        )
        if not all_entries:
            empty = QLabel("No additional mods selected yet.")
            set_ui_role(empty, "metadata")
            self.selected_mods_layout.addWidget(empty)
            return
        for entry in all_entries:
            pill = QFrame()
            set_ui_role(pill, "selectedModPill")
            pill_layout = QHBoxLayout(pill)
            pill_layout.setContentsMargins(9, 5, 9, 5)
            label = QLabel(entry)
            label.setWordWrap(True)
            pill_layout.addWidget(label)
            opacity = QGraphicsOpacityEffect(pill)
            pill.setGraphicsEffect(opacity)
            animation = QPropertyAnimation(opacity, b"opacity", pill)
            animation.setDuration(180)
            animation.setStartValue(0.0)
            animation.setEndValue(1.0)
            animation.start()
            pill._selection_animation = animation
            self.selected_mods_layout.addWidget(pill)

    def _clear_editor_dependency_worker(self, worker):
        if self.editor_dependency_worker is worker:
            self.editor_dependency_worker = None
            if self.editor_dependency_pending:
                self.editor_dependency_pending = False
                self._start_editor_dependency_resolution()
        worker.deleteLater()

    def _local_required_mods(self, *, editor: bool) -> list[RequiredMod]:
        install = self.selected_steam_install()
        installed = scan_installed_mods(install.workshop_dir if install else None)
        if editor:
            names = dict(DAYZ_EDITOR_MODS)
            ids = list(names) + list(self._selected_editor_extra_mod_ids())
        else:
            names = {}
            ids = list(self._selected_local_extra_mod_ids())
        return [
            RequiredMod(
                item,
                names.get(item, installed.get(item, "")),
                item in installed,
                installed.get(item, ""),
                WORKSHOP_URL.format(mod_id=item),
            )
            for item in ids
        ]

    def _verify_local_tool_mods(self, *, editor: bool) -> list[RequiredMod]:
        mods = self._local_required_mods(editor=editor)
        missing = [mod for mod in mods if not mod.installed]
        label = "Editor" if editor else "local profile"
        if missing:
            self.local_tools_status.setText(
                f"{label}: {len(missing)} of {len(mods)} Workshop mod(s) missing. Open their Workshop pages or use Steam Downloads, then verify again."
            )
        else:
            self.local_tools_status.setText(
                f"{label}: all {len(mods)} Workshop mod(s) are installed locally."
            )
        return mods

    def _open_missing_local_tool_pages(self, *, editor: bool):
        missing = [mod for mod in self._verify_local_tool_mods(editor=editor) if not mod.installed]
        for mod in missing:
            QDesktopServices.openUrl(QUrl(mod.workshop_url))

    def _native_local_install(self):
        if self.launch_engine_key() != "native":
            QMessageBox.information(
                self,
                "Native launcher required",
                "Editor and Local Development use WolfLauncher’s native Steam handoff. Choose Native launcher in Settings first.",
            )
            return None
        install = self.selected_steam_install()
        if not install:
            QMessageBox.warning(
                self,
                "Steam not detected",
                "WolfLauncher could not detect the selected Steam installation. Check Settings health.",
            )
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
        if self.editor_addon_dependency_worker and self.editor_addon_dependency_worker.isRunning():
            return
        if not self.editor_addon_dependencies_checked:
            roots = tuple(sorted(self.editor_extra_mod_ids, key=int))
            if roots:
                self.local_tools_status.setText(
                    "Checking selected Editor mods for declared Workshop requirements…"
                )
                worker = WorkshopDependencyWorker(roots)
                worker.setParent(self)
                self.editor_addon_dependency_worker = worker
                worker.dependencies_ready.connect(
                    lambda resolved, metadata: self._finish_editor_addon_dependency_scan(
                        roots, resolved, metadata, install
                    )
                )
                worker.finished.connect(self._clear_editor_addon_dependency_worker)
                worker.start()
                return
            self.editor_addon_dependencies_checked = True
        mods = self._local_required_mods(editor=True)
        self.local_tools_status.setText(
            f"Checking {len(mods)} DayZ Editor mod(s), including declared requirements, with Steam for updatesâ€¦"
        )
        worker = WorkshopSubscriptionWorker(
            [mod.workshop_id for mod in mods], install, force_update=True
        )
        self.workshop_subscription_worker = worker
        worker.progress_ready.connect(self._update_editor_workshop_progress)
        worker.subscription_ready.connect(self._finish_editor_workshop_resolution)
        worker.finished.connect(self._clear_editor_workshop_worker)
        worker.start()

    def _finish_editor_addon_dependency_scan(self, roots, resolved, metadata, install):
        fixed_ids = {workshop_id for workshop_id, _name in DAYZ_EDITOR_MODS}
        self.editor_dependency_mod_ids = set(resolved) - set(roots) - fixed_ids
        self.editor_dependency_excluded_ids.intersection_update(self.editor_dependency_mod_ids)
        self.editor_dependency_metadata.update(metadata)
        self.editor_addon_dependencies_checked = True
        self._refresh_editor_mod_picker()
        self._start_editor_workshop_resolution(install)

    def _clear_editor_addon_dependency_worker(self):
        worker = self.editor_addon_dependency_worker
        self.editor_addon_dependency_worker = None
        if worker:
            worker.deleteLater()

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
            QMessageBox.warning(
                self, f"Editor launch blocked during {exc.stage}", exc.user_message()
            )
            return
        self._show_local_launch(prepared.command, "Opening DayZ Editor", minimize_on_handoff=True)

    def _clear_editor_workshop_worker(self):
        self.workshop_subscription_worker = None

    def _load_editor_image(self):
        request = QNetworkRequest(QUrl(DAYZ_EDITOR_IMAGE_URL))
        request.setAttribute(
            QNetworkRequest.RedirectPolicyAttribute, QNetworkRequest.NoLessSafeRedirectPolicy
        )
        reply = self.editor_image_manager.get(request)
        self.editor_image_reply = reply
        reply.downloadProgress.connect(
            lambda received, _total, active_reply=reply: self._abort_editor_image_if_oversize(
                active_reply, received
            )
        )
        QTimer.singleShot(
            THUMBNAIL_REQUEST_TIMEOUT_MS,
            lambda active_reply=reply: self._abort_editor_image_if_active(active_reply),
        )

    @staticmethod
    def _abort_editor_image_if_oversize(reply: QNetworkReply, received: int) -> None:
        if received > MAX_THUMBNAIL_BYTES:
            reply.abort()

    def _abort_editor_image_if_active(self, reply: QNetworkReply) -> None:
        if reply is self.editor_image_reply and not reply.isFinished():
            reply.abort()

    def _finish_editor_image_load(self, reply):
        try:
            if reply is not self.editor_image_reply:
                return
            self.editor_image_reply = None
            content_type = reply.header(QNetworkRequest.ContentTypeHeader) or ""
            payload = bytes(reply.readAll())
            image = QPixmap()
            if (
                reply.error() == QNetworkReply.NoError
                and is_safe_thumbnail_url(reply.url().toString())
                and len(payload) <= MAX_THUMBNAIL_BYTES
                and is_safe_thumbnail_content_type(str(content_type))
                and image.loadFromData(payload)
                and is_safe_thumbnail_dimensions(image.width(), image.height())
            ):
                self.editor_workshop_image.setPixmap(
                    image.scaled(
                        self.editor_workshop_image.size(),
                        Qt.KeepAspectRatio,
                        Qt.SmoothTransformation,
                    )
                )
        finally:
            reply.deleteLater()

    def _browse_local_folder(self, target: QLineEdit):
        selected = QFileDialog.getExistingDirectory(self, "Select local DayZ folder")
        if selected:
            target.setText(selected)
            if target is self.local_server_root and not self.local_server_config.text().strip():
                self.local_server_config.setText(str(Path(selected) / "serverDZ.cfg"))

    def _browse_local_profile_mod(self):
        selected = QFileDialog.getExistingDirectory(self, "Select local DayZ mod folder")
        if not selected:
            return
        existing = [
            part.strip() for part in self.local_profile_mods.text().split(";") if part.strip()
        ]
        if selected not in existing:
            existing.append(selected)
        self.local_profile_mods.setText("; ".join(existing))

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
        self.local_tools_status.setText(
            "SteamCMD is preparing the temporary DayZ dedicated serverâ€¦"
        )

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

    def _install_server_with_steam(self):
        if current_platform().capabilities.platform_id != "windows":
            return
        install = self.selected_steam_install()
        if not install or not install.root:
            QMessageBox.warning(
                self, "Steam not detected", "Open Steam, then try the Steam-owned install again."
            )
            return
        if not QDesktopServices.openUrl(QUrl("steam://install/223350")):
            QMessageBox.warning(
                self,
                "Steam install unavailable",
                "WolfLauncher could not ask Steam to install DayZ Dedicated Server.",
            )
            return
        self.steam_server_progress.setRange(0, 0)
        self.steam_server_progress.setFormat("Waiting for Steam to finish DayZ Dedicated Server…")
        self.steam_server_progress.setVisible(True)
        self.steam_server_install.setEnabled(False)
        self.steam_server_install_timer.start()
        self.local_tools_status.setText(
            "Steam is managing the DayZ Dedicated Server download. WolfLauncher will detect it when installation completes."
        )

    def _poll_steam_server_install(self):
        install = self.selected_steam_install()
        libraries = list(getattr(install, "library_steamapps", []) or []) if install else []
        if install and install.steamapps and install.steamapps not in libraries:
            libraries.append(install.steamapps)
        root = steam_server_root(libraries)
        if not root:
            return
        self.steam_server_install_timer.stop()
        self.steam_server_install.setEnabled(True)
        self.steam_server_progress.setRange(0, 100)
        self.steam_server_progress.setValue(100)
        self.steam_server_progress.setFormat("Steam installation detected")
        self.local_server_root.setText(str(root))
        self.local_server_config.setText(str(root / "serverDZ.cfg"))
        self._save_local_host_settings()
        self.local_tools_status.setText(
            "Steam-installed DayZ Dedicated Server is ready to configure and start."
        )

    def _local_server_launch(self) -> LocalServerLaunch:
        root = Path(self.local_server_root.text().strip())
        executable = server_executable(root)
        if executable is None:
            raise ValueError(
                "DayZ dedicated-server executable was not found in the selected server root."
            )
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
            QMessageBox.information(
                self,
                "Local server running",
                "Stop the managed local server before starting it again.",
            )
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
        local_paths = self._local_path_list(self.local_profile_mods.text())
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
        selected_ids = list(self._selected_local_extra_mod_ids())
        if not selected_ids:
            self._launch_verified_local_test_server(install)
            return
        if self.workshop_subscription_worker and self.workshop_subscription_worker.isRunning():
            QMessageBox.information(
                self,
                "Steam Workshop in progress",
                "WolfLauncher is already waiting for a Steam Workshop operation to finish.",
            )
            return
        self.local_tools_status.setText("Checking selected Additional mods with Steam for updates…")
        worker = WorkshopSubscriptionWorker(selected_ids, install, force_update=True)
        self.workshop_subscription_worker = worker
        worker.progress_ready.connect(self._update_local_workshop_progress)
        worker.subscription_ready.connect(self._finish_local_workshop_resolution)
        worker.finished.connect(self._clear_editor_workshop_worker)
        worker.start()

    def _update_local_workshop_progress(self, snapshots):
        ready = sum(1 for item in snapshots if item.installed)
        self.local_tools_status.setText(
            f"Steam is preparing selected Additional mods: {ready} of {len(snapshots)} ready."
        )

    def _finish_local_workshop_resolution(self, result):
        if not result.ok:
            QMessageBox.warning(
                self,
                "Additional mods incomplete",
                result.error or "Steam did not finish every selected Additional mod.",
            )
            return
        install = self._native_local_install()
        if install:
            self._launch_verified_local_test_server(install)

    def _launch_verified_local_test_server(self, install):
        profile = self._current_local_tool_profile()
        try:
            host, port = parse_local_endpoint(profile.endpoint)
        except ValueError as exc:
            QMessageBox.warning(self, "LAN test server required", str(exc))
            return
        mods = self._verify_local_tool_mods(editor=False)
        if any(not mod.installed for mod in mods):
            QMessageBox.warning(
                self,
                "Local profile mods missing",
                "Install every listed Workshop item before joining the local test server.",
            )
            return
        server = Server(profile.name, "Local development", host, port, port)
        try:
            prepared = prepare_native_launch(
                install, server, self.player_name.text().strip() or DEFAULT_PLAYER_NAME, mods
            )
            command = self._with_local_client_mods(prepared.command)
        except NativeLaunchError as exc:
            QMessageBox.warning(
                self, f"Local launch blocked during {exc.stage}", exc.user_message()
            )
            return
        except ValueError as exc:
            QMessageBox.warning(self, "Local launch blocked", str(exc))
            return
        self._show_local_launch(command, f"Joining {server.connect_target}")

    def _show_local_launch(
        self, command: list[str], title: str, *, minimize_on_handoff: bool = False
    ):
        self._save_local_tool_profile()
        dialog = LaunchDialog(
            self,
            command,
            title,
            "native local launch command",
            minimize_on_handoff=minimize_on_handoff,
        )
        dialog.exec()
