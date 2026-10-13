import os

from PySide6.QtCore import QPoint, Qt
from PySide6.QtGui import QAction
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QDialog,
    QFileDialog,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMenu,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from .diagnostics import (
    format_settings_health_report,
    run_diagnostics,
)
from .known_issues import known_external_issues_text
from .launch_history import load_last_launch_report, save_last_launch_report
from .launcher import DEFAULT_PLAYER_NAME
from .platform_detection import (
    steam_mode_label,
)
from .platforms import current_platform
from .redaction import redact_support_text
from .secret_store import (
    settings_with_stored_steam_api_key,
)
from .settings import (
    DEFAULT_DISCOVERY_PROVIDER,
    save_favourites,
    save_settings,
)
from .settings_health_presenter import GROUP_SPECS, settings_health_groups
from .theme import (
    configure_data_table,
    set_ui_role,
)
from .ui_sections import set_disclosure_state


class SettingsFeatureMixin:
    def _build_settings_tab(self) -> QWidget:
        widget = QWidget()
        set_ui_role(widget, "workspace")
        layout = QVBoxLayout(widget)

        # Retain the summary for support reports, outside the visible settings flow.
        self.system_summary = QLabel("Checking Steam and DayZ installation...", widget)
        self.system_summary.hide()

        capabilities = current_platform().capabilities
        launcher_settings = QFormLayout()
        if capabilities.supports_external_launcher:
            launcher_controls = QWidget()
            launcher_controls_layout = QHBoxLayout(launcher_controls)
            launcher_controls_layout.setContentsMargins(0, 0, 0, 0)
            launcher_controls_layout.addWidget(self.launch_engine, 1)

            self.external_launcher_settings = QWidget()
            external_launcher_layout = QHBoxLayout(self.external_launcher_settings)
            external_launcher_layout.setContentsMargins(0, 0, 0, 0)
            external_launcher_layout.addWidget(QLabel("Script"))
            external_launcher_layout.addWidget(self.launcher_path, 1)
            browse = QPushButton("Browse")
            browse.clicked.connect(self.browse_launcher)
            external_launcher_layout.addWidget(browse)
            launcher_controls_layout.addWidget(self.external_launcher_settings, 1)
            launcher_settings.addRow("Launch engine", launcher_controls)
        if capabilities.platform_id == "windows":
            self.settings_player_name = QLineEdit(self.player_name.text())
            self.settings_player_name.setToolTip(
                "This is the same player name shown on Favourite Servers."
            )
            self.settings_player_name.textChanged.connect(self.sync_favourites_player_name)
            self.settings_player_name.returnPressed.connect(self.save_player_name)
            launcher_settings.addRow("Player name", self.settings_player_name)
        else:
            launcher_settings.addRow("Steam installation", self.native_steam_mode)
        layout.addLayout(launcher_settings)
        self.launch_engine.currentTextChanged.connect(
            self.update_external_launcher_settings_visibility
        )
        self.update_external_launcher_settings_visibility()

        self.discovery_auto_refresh = QCheckBox("Keep the server list current automatically")
        self.discovery_auto_refresh.setChecked(
            bool(self.settings.get("discovery_auto_refresh", True))
        )
        self.discovery_auto_refresh.stateChanged.connect(self.handle_settings_changed)
        browser_settings = QFormLayout()
        browser_settings.addRow("Server Browser", self.discovery_auto_refresh)
        layout.addLayout(browser_settings)

        self.health_table = QTableWidget(0, 3)
        self.health_table.setHorizontalHeaderLabels(["Check", "Status", "Details"])
        self.health_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.health_table.setEditTriggers(QTableWidget.NoEditTriggers)
        configure_data_table(self.health_table)
        self.health_table.setContextMenuPolicy(Qt.CustomContextMenu)
        self.health_table.customContextMenuRequested.connect(self.show_health_context_menu)
        self.health_group_badges = {}
        self.health_group_rows = {}
        health_overview = QVBoxLayout()
        health_overview.setSpacing(10)
        for key, title, names in GROUP_SPECS:
            card = self._build_settings_health_group(key, title, names)
            health_overview.addWidget(card)
        layout.addLayout(health_overview)

        self.settings_advanced_toggle = QPushButton()
        self.settings_advanced_toggle.setCheckable(True)

        self.settings_advanced_panel = QWidget()
        advanced_layout = QVBoxLayout(self.settings_advanced_panel)
        advanced_layout.setContentsMargins(0, 0, 0, 0)
        self.health_table.hide()

        discovery_settings = QFormLayout()

        self.discovery_provider = QComboBox()
        self.discovery_provider.addItems(
            [
                "WolfAPI",
                "Steam Master",
            ]
        )
        self.discovery_provider.setCurrentText(
            self._provider_label(
                str(self.settings.get("discovery_provider") or DEFAULT_DISCOVERY_PROVIDER)
            )
        )
        self.discovery_provider.currentTextChanged.connect(self.handle_discovery_provider_changed)
        discovery_settings.addRow("Server API provider", self.discovery_provider)

        self.discovery_limit = QSpinBox()
        self.discovery_limit.setRange(1, 10000)
        self.discovery_limit.setValue(int(self.settings.get("discovery_limit", 500)))
        self.discovery_limit.valueChanged.connect(self.handle_settings_changed)
        discovery_settings.addRow("Refresh limit", self.discovery_limit)

        self.steam_web_api_key = QLineEdit(
            self.steam_api_key
            or os.environ.get("WOLFLAUNCHER_STEAM_WEB_API_KEY")
            or os.environ.get("STEAM_WEB_API_KEY")
            or ""
        )
        self.steam_web_api_key.setEchoMode(QLineEdit.Password)
        self.steam_web_api_key.setPlaceholderText("Steam Web API key")
        self.steam_web_api_key.editingFinished.connect(self.handle_settings_changed)
        key_storage = "desktop keyring" if self.secret_store.available() else "protected local file"
        discovery_settings.addRow(f"Steam API key ({key_storage})", self.steam_web_api_key)

        self.steam_master_endpoints = QLineEdit(
            str(self.settings.get("steam_master_endpoints") or "")
        )
        self.steam_master_endpoints.setPlaceholderText("Comma separated host[:port]")
        self.steam_master_endpoints.editingFinished.connect(self.handle_settings_changed)
        discovery_settings.addRow("Steam masters", self.steam_master_endpoints)
        advanced_layout.addLayout(discovery_settings)
        self.discovery_settings_layout = discovery_settings
        self.update_discovery_settings_visibility()

        support_tools = QHBoxLayout()
        copy_health = QPushButton("Copy health")
        copy_health.clicked.connect(self.copy_settings_health)
        view_health = QPushButton("View full health")
        view_health.clicked.connect(self.show_full_health_details)
        copy_diagnostics = QPushButton("Copy diagnostics")
        copy_diagnostics.clicked.connect(self.copy_diagnostics_report)
        copy_last_launch = QPushButton("Copy last launch")
        copy_last_launch.clicked.connect(self.copy_last_launch_report)
        import_file = QPushButton("Import server list")
        import_file.clicked.connect(self.import_server_cache_file)
        support_tools.addWidget(copy_health)
        support_tools.addWidget(view_health)
        support_tools.addWidget(copy_diagnostics)
        support_tools.addWidget(copy_last_launch)
        support_tools.addWidget(import_file)
        support_tools.addStretch(1)
        advanced_layout.addLayout(support_tools)

        self.leopard_toggle = QPushButton("▸ Beware of the leopard")
        self.leopard_toggle.setCheckable(True)
        set_ui_role(self.leopard_toggle, "disclosure")
        self.leopard_panel = QLabel(
            "Mostly harmless. This cupboard may contain diagnostics, advanced controls, "
            "and the occasional leopard. If you don't know what they're for, you probably "
            "don't need them. Mind the leopard."
        )
        set_ui_role(self.leopard_panel, "metadata")
        self.leopard_panel.setWordWrap(True)
        self.leopard_panel.hide()
        self.leopard_toggle.toggled.connect(
            lambda expanded: (
                self.leopard_panel.setVisible(expanded),
                self.leopard_toggle.setText(f"{'▾' if expanded else '▸'} Beware of the leopard"),
            )
        )
        leopard_row = QHBoxLayout()
        leopard_row.addWidget(self.leopard_toggle)
        leopard_row.addStretch(1)
        advanced_layout.addLayout(leopard_row)
        advanced_layout.addWidget(self.leopard_panel)

        self.known_issues_toggle = QPushButton()
        self.known_issues_toggle.setCheckable(True)
        set_ui_role(self.known_issues_toggle, "disclosure")
        self.known_issues_panel = QLabel(known_external_issues_text())
        set_ui_role(self.known_issues_panel, "metadata")
        self.known_issues_panel.setWordWrap(True)
        self.known_issues_panel.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.known_issues_toggle.toggled.connect(
            lambda expanded: set_disclosure_state(
                self.known_issues_toggle,
                self.known_issues_panel,
                "known external issues",
                expanded,
            )
        )
        advanced_layout.addWidget(self.known_issues_toggle)
        advanced_layout.addWidget(self.known_issues_panel)
        set_disclosure_state(
            self.known_issues_toggle,
            self.known_issues_panel,
            "known external issues",
            False,
        )

        layout.addStretch(1)
        row = QHBoxLayout()
        health = QPushButton("Check health")
        set_ui_role(health, "accent")
        health.clicked.connect(self.update_settings_health)
        save = QPushButton("Save settings")
        set_ui_role(save, "primary")
        save.clicked.connect(self.save_user_settings)
        row.addWidget(self.settings_advanced_toggle)
        row.addStretch(1)
        row.addWidget(health)
        row.addWidget(save)
        layout.addLayout(row)
        layout.addWidget(self.settings_advanced_panel)

        self.settings_advanced_toggle.toggled.connect(
            lambda expanded: set_disclosure_state(
                self.settings_advanced_toggle,
                self.settings_advanced_panel,
                "discovery and support tools",
                expanded,
            )
        )
        set_disclosure_state(
            self.settings_advanced_toggle,
            self.settings_advanced_panel,
            "discovery and support tools",
            False,
        )
        return widget

    def _build_settings_health_group(self, key: str, title: str, names: tuple[str, ...]) -> QFrame:
        card = QFrame()
        set_ui_role(card, "healthGroup")
        card.setProperty("healthStatus", "OK")
        card.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Maximum)
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(12, 10, 12, 13)
        card_layout.setSpacing(7)
        header = QHBoxLayout()
        title_label = QLabel(title)
        set_ui_role(title_label, "cardTitle")
        badge = QLabel("OK")
        set_ui_role(badge, "healthBadge")
        badge.setProperty("healthStatus", "OK")
        header.addWidget(title_label)
        header.addStretch(1)
        header.addWidget(badge)
        card_layout.addLayout(header)
        self.health_group_badges[key] = (card, badge)
        for name in names:
            row = QWidget()
            set_ui_role(row, "healthRow")
            row_layout = QHBoxLayout(row)
            row_layout.setContentsMargins(0, 0, 0, 0)
            row_layout.setSpacing(10)
            status_label = QLabel("●")
            status_label.setFixedWidth(12)
            name_label = QLabel(name)
            name_label.setFixedWidth(120)
            detail_label = QLabel("Checking…")
            detail_label.setMinimumWidth(0)
            detail_label.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
            detail_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
            set_ui_role(detail_label, "metadata")
            row_layout.addWidget(status_label)
            row_layout.addWidget(name_label)
            row_layout.addWidget(detail_label, 1)
            card_layout.addWidget(row)
            self.health_group_rows[name] = (row, status_label, detail_label)
        return card

    def update_settings_health_groups(self, rows):
        visible_names = {name for name, _status, _detail in rows}
        for name, (row, _status_label, _detail_label) in self.health_group_rows.items():
            row.setVisible(name in visible_names)
        for group in settings_health_groups(tuple(rows)):
            card, badge = self.health_group_badges[group.key]
            card.setVisible(bool(group.rows))
            card.setProperty("healthStatus", group.status)
            badge.setProperty("healthStatus", group.status)
            badge.setText(
                "READY"
                if group.status == "OK"
                else "CHECK"
                if group.status == "WARN"
                else "OPTIONAL"
                if group.status == "OPTIONAL"
                else "ISSUE"
            )
            card.style().unpolish(card)
            card.style().polish(card)
            badge.style().unpolish(badge)
            badge.style().polish(badge)
            for name, status, detail in group.rows:
                _row, status_label, detail_label = self.health_group_rows[name]
                status_label.setText("●")
                status_label.setStyleSheet(f"color: {self._health_colour(status)};")
                detail_label.setText(detail)
                detail_label.setToolTip(detail)

    def update_external_launcher_settings_visibility(self, *_args):
        if hasattr(self, "external_launcher_settings"):
            self.external_launcher_settings.setVisible(
                self.launch_engine.currentText() == "External launcher"
            )

    def update_discovery_settings_visibility(self):
        if not hasattr(self, "discovery_settings_layout"):
            return
        provider = self.discovery_provider_key()
        self.discovery_settings_layout.setRowVisible(
            self.steam_web_api_key, provider == "steam_web_api"
        )
        self.discovery_settings_layout.setRowVisible(
            self.steam_master_endpoints, provider == "steam_master"
        )

    def browse_launcher(self):
        path, _ = QFileDialog.getOpenFileName(self, "Select dayz-launcher.sh")
        if path:
            self.launcher_path.setText(path)
            self.save_user_settings(silent=True)
            self.update_settings_health()

    def apply_refresh_timer(self):
        seconds = self.refresh_seconds.value()
        if seconds <= 0:
            self.timer.stop()
        else:
            self.timer.start(seconds * 1000)

    def _native_steam_mode_label(self, key: str) -> str:
        return steam_mode_label(key)

    def saved_selected_row(self) -> int:
        try:
            return int(self.settings.get("last_selected_row", -1))
        except (TypeError, ValueError):
            return -1

    def handle_settings_changed(self, *_args):
        self.save_user_settings(silent=True)
        self.update_settings_health()

    def handle_discovery_provider_changed(self, *_args):
        self.update_discovery_settings_visibility()
        self.handle_settings_changed()
        if hasattr(self, "browser_search"):
            self.schedule_remote_wolfapi_search(self.browser_search.text())

    def handle_launch_engine_changed(self, *_args):
        SettingsFeatureMixin._recheck_after_mod_context_change(
            self, "Launch engine changed. Rechecking selected server mods..."
        )

    def handle_native_steam_mode_changed(self, *_args):
        SettingsFeatureMixin._recheck_after_mod_context_change(
            self, "Steam install changed. Rechecking selected server mods..."
        )

    def _recheck_after_mod_context_change(self, message: str):
        if hasattr(self, "server_launch"):
            self.server_launch.invalidate()
        self.last_mod_result = None
        self.workshop_recovery_ids = ()
        if hasattr(self, "mod_summary"):
            self.mod_summary.setText(message)
        if hasattr(self, "mods_table"):
            self.mods_table.setRowCount(0)
        self.handle_settings_changed()
        if not hasattr(self, "table"):
            return
        row = self.table.currentRow()
        if row < 0 or row >= len(self.servers):
            return
        if self.mod_worker and self.mod_worker.isRunning():
            self.pending_mod_check_row = row
            self._check_pending_server_mods()
            return
        self.check_server_mods_for_row(row, silent=True, force=True)

    def save_player_name(self):
        if not self.player_name.text().strip():
            self.player_name.setText(DEFAULT_PLAYER_NAME)
        self.save_user_settings(silent=True)
        self.statusBar().showMessage(
            f"Player name saved as {self.player_name.text().strip()}.", 5000
        )

    def sync_settings_player_name(self, text: str):
        if hasattr(self, "settings_player_name") and self.settings_player_name.text() != text:
            self.settings_player_name.setText(text)

    def sync_favourites_player_name(self, text: str):
        if self.player_name.text() != text:
            self.player_name.setText(text)

    def save_user_settings(self, silent: bool = False):
        auto_refresh_timestamps = {
            key: value
            for key, value in self.settings.items()
            if key.startswith("last_") and key.endswith("_auto_refresh_at")
        }
        updated_settings = {
            **self.settings,
            "launcher_path": self.launcher_path.text(),
            "player_name": self.player_name.text(),
            "launch_engine": self.launch_engine_key(),
            "native_steam_mode": self.native_steam_mode_key(),
            "refresh_seconds": self.refresh_seconds.value(),
            "last_selected_row": self.table.currentRow(),
            "discovery_provider": self.discovery_provider_key(),
            "discovery_limit": self.discovery_limit.value()
            if hasattr(self, "discovery_limit")
            else int(self.settings.get("discovery_limit", 500)),
            "discovery_auto_refresh": self.discovery_auto_refresh.isChecked()
            if hasattr(self, "discovery_auto_refresh")
            else bool(self.settings.get("discovery_auto_refresh", False)),
            "hide_quality_flagged": self.browser_hide_quality_flagged.isChecked()
            if hasattr(self, "browser_hide_quality_flagged")
            else bool(self.settings.get("hide_quality_flagged", True)),
            "steam_master_endpoints": self.steam_master_endpoints.text().strip()
            if hasattr(self, "steam_master_endpoints")
            else "",
            "wolfapi_directory_total": self.wolfapi_directory_total,
            "local_tool_profiles": [
                {
                    "name": profile.name,
                    "mod_paths": list(profile.mod_paths),
                    "endpoint": profile.endpoint,
                    "workshop_mod_ids": list(profile.workshop_mod_ids),
                }
                for profile in getattr(self, "local_tool_profiles", [])
            ],
            # Editor selections intentionally reset when WolfLauncher closes.
            "editor_extra_mod_ids": [],
            "local_host_settings": dict(getattr(self, "local_host_settings", {})),
        }
        api_key = (
            self.steam_web_api_key.text().strip()
            if hasattr(self, "steam_web_api_key")
            else self.steam_api_key
        )
        updated_settings = settings_with_stored_steam_api_key(
            updated_settings, api_key, self.secret_store
        )
        updated_settings.update(auto_refresh_timestamps)
        try:
            save_settings(updated_settings)
        except OSError as exc:
            message = f"WolfLauncher could not save your settings.\n\n{exc}"
            if silent:
                if hasattr(self, "statusBar"):
                    self.statusBar().showMessage(message.replace("\n\n", " "), 10000)
            else:
                QMessageBox.warning(self, "Could not save settings", message)
            return False
        self.settings = updated_settings
        self.steam_api_key = api_key
        self.apply_refresh_timer()
        if not silent:
            QMessageBox.information(self, "Settings saved", "WolfLauncher settings were saved.")
        return True

    def _save_favourites_index(self) -> bool:
        try:
            product_key = (
                self.dayz_product_key()
                if hasattr(self, "dayz_product_key")
                else str(getattr(self, "settings", {}).get("dayz_product", "stable"))
            )
            if hasattr(self, "saved_server_repository"):
                self.saved_server_repository.save_favourites(self.favourites)
            else:
                save_favourites(self.favourites, product_key)
        except (OSError, ValueError) as exc:
            QMessageBox.warning(
                self,
                "Could not save favourites",
                f"WolfLauncher could not save the favourites index.\n\n{exc}",
            )
            return False
        return True

    def copy_to_clipboard(self, text: str, label: str = "Text"):
        secrets = []
        if hasattr(self, "steam_web_api_key"):
            secrets.append(self.steam_web_api_key.text().strip())
        QApplication.clipboard().setText(redact_support_text(text, secrets))
        self.statusBar().showMessage(f"{label} copied to clipboard", 3000)

    def copy_settings_health(self):
        if not hasattr(self, "health_table") or self.health_table.rowCount() == 0:
            self.update_settings_health()
        self.copy_to_clipboard(self.settings_health_text(), "Settings health")

    def show_full_health_details(self):
        if self.health_table.rowCount() == 0:
            self.update_settings_health()
        dialog = QDialog(self)
        dialog.setWindowTitle("Full Settings health details")
        dialog.resize(1000, 560)
        dialog_layout = QVBoxLayout(dialog)
        summary = QLabel(self.system_summary.text())
        set_ui_role(summary, "summary")
        dialog_layout.addWidget(summary)
        table = QTableWidget(self.health_table.rowCount(), self.health_table.columnCount())
        table.setHorizontalHeaderLabels(["Check", "Status", "Details"])
        table.setSelectionBehavior(QTableWidget.SelectRows)
        table.setEditTriggers(QTableWidget.NoEditTriggers)
        configure_data_table(table)
        for row in range(self.health_table.rowCount()):
            for column in range(self.health_table.columnCount()):
                source = self.health_table.item(row, column)
                item = QTableWidgetItem(source.text() if source else "")
                if column == 1 and source:
                    item.setForeground(source.foreground())
                table.setItem(row, column, item)
        table.resizeColumnsToContents()
        table.horizontalHeader().setStretchLastSection(True)
        dialog_layout.addWidget(table)
        buttons = QHBoxLayout()
        buttons.addStretch(1)
        copy = QPushButton("Copy health")
        copy.clicked.connect(self.copy_settings_health)
        close = QPushButton("Close")
        close.clicked.connect(dialog.accept)
        buttons.addWidget(copy)
        buttons.addWidget(close)
        dialog_layout.addLayout(buttons)
        dialog.exec()

    def copy_diagnostics_report(self):
        self.copy_to_clipboard(
            run_diagnostics(
                self.launcher_path.text(),
                self.servers,
                self.native_steam_mode_key(),
                self.launch_engine_key(),
                server_statuses=self.curated_status_cache,
            ),
            "Diagnostics report",
        )

    def copy_last_launch_report(self):
        report = load_last_launch_report()
        if not report:
            QMessageBox.information(
                self,
                "No launch report yet",
                "Launch a server once before copying the last launch report.",
            )
            return
        self.copy_to_clipboard(report, "Last launch report")

    def persist_launch_report(self, report: str):
        try:
            save_last_launch_report(report)
        except OSError as exc:
            QMessageBox.warning(
                self,
                "Could not save launch report",
                f"WolfLauncher could not save its support report.\n\n{exc}",
            )

    def copy_selected_health_row(self):
        row = self.health_table.currentRow()
        if row < 0:
            return
        self.copy_to_clipboard(self.health_row_text(row), "Health row")

    def show_health_context_menu(self, pos: QPoint):
        row = self.health_table.rowAt(pos.y())
        if row >= 0:
            self.health_table.selectRow(row)

        menu = QMenu(self)
        copy_row_action = QAction("Copy selected row", self)
        copy_report_action = QAction("Copy health report", self)
        copy_diagnostics_action = QAction("Copy diagnostics report", self)
        copy_row_action.setEnabled(row >= 0)
        copy_row_action.triggered.connect(self.copy_selected_health_row)
        copy_report_action.triggered.connect(self.copy_settings_health)
        copy_diagnostics_action.triggered.connect(self.copy_diagnostics_report)
        menu.addAction(copy_row_action)
        menu.addAction(copy_report_action)
        menu.addAction(copy_diagnostics_action)
        menu.exec(self.health_table.viewport().mapToGlobal(pos))

    def settings_health_text(self) -> str:
        summary = self.system_summary.text() if hasattr(self, "system_summary") else ""
        rows = []
        for row in range(self.health_table.rowCount()):
            values = []
            for column in range(self.health_table.columnCount()):
                item = self.health_table.item(row, column)
                values.append(item.text() if item else "")
            rows.append(values)
        return format_settings_health_report(summary, rows)

    def health_row_text(self, row: int) -> str:
        values = []
        for column in range(self.health_table.columnCount()):
            item = self.health_table.item(row, column)
            values.append(item.text().strip() if item else "")
        return " | ".join(values)

    def update_settings_health(self):
        self.settings_health.refresh()

    def _health_colour(self, status: str) -> str:
        return self.settings_health.colour(status)
