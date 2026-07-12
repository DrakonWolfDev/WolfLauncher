import os
from dataclasses import replace
from pathlib import Path
from datetime import datetime
import sys

from PySide6.QtCore import QPoint, QTimer, QUrl, Qt
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QDialog,
    QComboBox,
    QMenu,
    QPushButton,
    QProgressDialog,
    QProgressBar,
    QSpinBox,
    QTabWidget,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)
from PySide6.QtGui import QColor, QDesktopServices, QAction

from .config import (
    add_curated_server,
    ensure_servers_file,
    find_default_launcher_path,
    load_servers,
    remove_curated_server,
    update_curated_server,
)
from .curated_dialogs import EditCuratedServerDialog, PromoteServerDialog
from .curated_server_presenter import curated_server_row
from .diagnostics import (
    format_settings_health_report,
    run_diagnostics,
)
from .discovery_refresh import auto_refresh_due, auto_refresh_timestamp
from .curated_status_cache import (
    cached_status_for_server,
    load_status_cache,
    update_status_cache,
)
from .launcher import DEFAULT_PLAYER_NAME, LaunchError, build_launch_command
from .launch_history import load_last_launch_report, save_last_launch_report
from .launch_dialogs import LaunchDialog, NativeLaunchPreviewDialog
from .launch_preflight import (
    LaunchPreflightAction,
    build_launch_preflight_state,
    matching_mod_result,
    next_launch_preflight_action,
    usable_mod_result,
)
from .launch_selection import server_with_resolved_ipv4
from .models import DiscoveredServer, Server
from .native_launcher import (
    NativeLaunchError,
    format_native_launch_parity_report,
    native_launch_failure_details,
    prepare_native_launch,
    prepare_native_launch_parity_report,
)
from .platform_detection import (
    SteamInstall,
    best_install,
    dayz_process_check,
    detect_steam,
    select_steam_install,
    steam_mode_label,
    install_label,
)
from .mods import (
    ModCheckResult,
    apply_workshop_item_states,
    check_server_mods,
    format_missing_workshop_links,
    format_mod_check_report,
)
from .mod_presenter import combined_download_estimate, mod_download_size, mod_row, mod_summary_text
from . import server_cache
from .server_discovery import parse_master_address
from .server_enrichment import (
    parse_connect_port,
)
from .server_browser_presenter import (
    browser_style_terms,
    browser_summary_text,
    discovered_server_details,
)
from .server_browser_controller import BrowserQuery, browser_filter_options, load_browser_snapshot
from .server_browser_table import populate_browser_table
from .settings import (
    load_favourites,
    load_settings,
    save_favourites,
    save_settings,
    server_key,
)
from .settings_health import build_settings_health_snapshot
from .status import ServerStatus, check_server
from .ui_sections import set_disclosure_state
from .workers import (
    BattleMetricsDiscoveryWorker,
    ModWorker,
    ServerEnrichmentWorker,
    StatusWorker,
    SteamDiscoveryWorker,
    SteamWebApiDiscoveryWorker,
    WolfApiDiscoveryWorker,
    WorkshopSubscriptionWorker,
    WorkshopStateWorker,
)
from .workshop_subscription import (
    ITEM_STATE_DOWNLOADING,
    current_workshop_item,
    workshop_recovery_state,
)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("WolfLauncher")
        self.resize(1350, 720)

        self.config_path = Path(__file__).resolve().parent.parent / "servers.yaml"
        ensure_servers_file(self.config_path)
        self.servers = load_servers(self.config_path)
        self.curated_status_cache = load_status_cache()
        self.settings = load_settings()
        self.favourites = load_favourites()
        self.worker = None
        self.mod_worker = None
        self.workshop_subscription_worker = None
        self.workshop_state_worker = None
        self.workshop_subscription_dialog = None
        self.workshop_subscription_monitor_hidden = False
        self.workshop_subscription_names = {}
        self.workshop_subscription_server_key = ""
        self.workshop_subscription_server = None
        self.active_discovered_server = None
        self.active_discovered_cache_key = ""
        self.workshop_recovery_ids = ()
        self.launch_after_workshop_download = False
        self.discovery_worker = None
        self.web_api_worker = None
        self.battlemetrics_worker = None
        self.wolfapi_worker = None
        self.enrichment_worker = None
        self.last_mod_result = None
        self.active_mod_server_key = ""
        self.pending_mod_check_row = None
        self.pending_mod_server = None
        self.browser_servers = []
        self.server_cache = server_cache.connect()

        for server in self.servers:
            key = server_key(server)
            if self.favourites:
                server.favourite = key in self.favourites
            elif server.favourite:
                self.favourites.add(key)
        if self.favourites:
            save_favourites(self.favourites)

        self.launcher_path = QLineEdit(
            str(self.settings.get("launcher_path") or find_default_launcher_path())
        )
        self.player_name = QLineEdit(str(self.settings.get("player_name") or DEFAULT_PLAYER_NAME))
        self.launch_engine = QComboBox()
        self.launch_engine.addItems(["Native launcher", "External launcher"])
        self.launch_engine.setCurrentText(
            "Native launcher"
            if str(self.settings.get("launch_engine") or "native") == "native"
            else "External launcher"
        )
        self.launch_engine.currentTextChanged.connect(self.handle_launch_engine_changed)
        self.native_steam_mode = QComboBox()
        self.native_steam_mode.addItems(["Auto", "Native Steam", "Flatpak Steam", "STEAM_ROOT Steam library"])
        self.native_steam_mode.setCurrentText(
            self._native_steam_mode_label(str(self.settings.get("native_steam_mode") or "auto"))
        )
        self.native_steam_mode.currentTextChanged.connect(self.handle_native_steam_mode_changed)
        self.refresh_seconds = QSpinBox()
        self.refresh_seconds.setRange(0, 3600)
        self.refresh_seconds.setValue(int(self.settings.get("refresh_seconds", 30)))
        self.refresh_seconds.setSuffix(" seconds")
        self.refresh_seconds.valueChanged.connect(self.handle_refresh_seconds_changed)

        self.last_refresh_label = QLabel("Last updated: never")

        self.timer = QTimer(self)
        self.timer.timeout.connect(self.refresh_statuses)

        self.tabs = QTabWidget()
        self.tabs.addTab(self._build_servers_tab(), "Servers")
        self.tabs.addTab(self._build_server_browser_tab(), "Server Browser")
        self.mods_tab_index = self.tabs.addTab(self._build_mods_tab(), "Mods")
        self.tabs.addTab(self._build_settings_tab(), "Settings")
        self.setCentralWidget(self.tabs)

        self.apply_refresh_timer()
        self.refresh_statuses()
        self.refresh_server_browser()
        self.update_settings_health()
        QTimer.singleShot(0, self.check_initial_server_mods)
        QTimer.singleShot(30000, self.maybe_auto_refresh_configured_provider)

    def _build_servers_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)

        layout.addWidget(self.last_refresh_label)

        common_settings = QFormLayout()
        player_name_row = QHBoxLayout()
        player_name_row.addWidget(self.player_name)
        self.player_name.returnPressed.connect(self.save_player_name)
        set_player_name = QPushButton("Set name")
        set_player_name.clicked.connect(self.save_player_name)
        player_name_row.addWidget(set_player_name)
        common_settings.addRow("Player name", player_name_row)
        common_settings.addRow("Auto refresh", self.refresh_seconds)
        layout.addLayout(common_settings)

        self.table = QTableWidget(len(self.servers), 16)
        self.table.setHorizontalHeaderLabels([
            "Fav",
            "Group",
            "Config Name",
            "Server Name",
            "Host",
            "Resolved IP",
            "Game Port",
            "Query Port",
            "Status",
            "Map",
            "Players",
            "Time",
            "Ping",
            "Version",
            "Flags",
            "Connect",
        ])
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.cellClicked.connect(self.handle_cell_clicked)
        self.table.cellDoubleClicked.connect(self.handle_cell_double_clicked)
        self.table.itemSelectionChanged.connect(self.handle_server_selection_changed)
        self.table.setContextMenuPolicy(Qt.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self.show_server_context_menu)

        for row, server in enumerate(self.servers):
            cached = cached_status_for_server(self.curated_status_cache, server)
            values = curated_server_row(
                server,
                cached,
            )
            for column, value in enumerate(values):
                self._set_curated_server_table_item(row, column, value, cached=bool(cached))

        self.table.resizeColumnsToContents()
        last_row = self.saved_selected_row()
        if 0 <= last_row < len(self.servers):
            self.table.selectRow(last_row)
        layout.addWidget(self.table)

        buttons = QHBoxLayout()
        add_server = QPushButton("Add curated server")
        add_server.clicked.connect(self.add_curated_server)
        self.refresh_status_button = QPushButton("Refresh status")
        self.refresh_status_button.clicked.connect(self.refresh_statuses)
        self.launch_button = QPushButton("Launch selected server")
        self.launch_button.clicked.connect(self.launch_selected)
        buttons.addStretch(1)
        buttons.addWidget(add_server)
        buttons.addWidget(self.refresh_status_button)
        buttons.addWidget(self.launch_button)
        layout.addLayout(buttons)
        return widget

    def _build_server_browser_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)

        self.browser_summary = QLabel("Cached discovered servers: loading")
        layout.addWidget(self.browser_summary)

        filters = QHBoxLayout()
        self.browser_search = QLineEdit()
        self.browser_search.setPlaceholderText("Search discovered servers")
        self.browser_search.textChanged.connect(self.refresh_server_browser)
        filters.addWidget(QLabel("Search"))
        filters.addWidget(self.browser_search, 2)

        self.browser_online_only = QCheckBox("Online")
        self.browser_online_only.stateChanged.connect(self.refresh_server_browser)
        filters.addWidget(self.browser_online_only)

        self.browser_modded = QComboBox()
        self.browser_modded.addItems(["Any mods", "Modded", "Vanilla"])
        self.browser_modded.currentTextChanged.connect(self.refresh_server_browser)
        filters.addWidget(self.browser_modded)

        self.browser_style = QComboBox()
        self.browser_style.addItems(["Any style", "PvE", "PvP"])
        self.browser_style.currentTextChanged.connect(self.refresh_server_browser)
        filters.addWidget(self.browser_style)

        self.browser_map = QComboBox()
        self.browser_map.addItem("Any map")
        self.browser_map.currentTextChanged.connect(self.refresh_server_browser)
        filters.addWidget(self.browser_map)

        self.browser_version = QComboBox()
        self.browser_version.addItem("Any version")
        self.browser_version.currentTextChanged.connect(self.refresh_server_browser)

        self.browser_source = QComboBox()
        self.browser_source.addItem("Any source")
        self.browser_source.currentTextChanged.connect(self.refresh_server_browser)

        self.browser_sort = QComboBox()
        self.browser_sort.addItems(["Name", "Players", "Ping", "Map", "Version", "Last checked", "Last seen"])
        self.browser_sort.currentTextChanged.connect(self.refresh_server_browser)

        self.browser_descending = QCheckBox("Desc")
        self.browser_descending.stateChanged.connect(self.refresh_server_browser)

        self.browser_limit = QComboBox()
        self.browser_limit.addItems(["200", "500", "1000"])
        self.browser_limit.currentTextChanged.connect(self.refresh_server_browser)
        layout.addLayout(filters)

        self.browser_advanced_toggle = QPushButton()
        self.browser_advanced_toggle.setCheckable(True)

        self.browser_advanced_panel = QWidget()
        advanced_layout = QVBoxLayout(self.browser_advanced_panel)
        advanced_layout.setContentsMargins(0, 0, 0, 0)
        advanced_filters = QHBoxLayout()
        advanced_filters.addWidget(QLabel("Version"))
        advanced_filters.addWidget(self.browser_version)
        advanced_filters.addWidget(QLabel("Source"))
        advanced_filters.addWidget(self.browser_source)
        advanced_filters.addWidget(QLabel("Sort"))
        advanced_filters.addWidget(self.browser_sort)
        advanced_filters.addWidget(self.browser_descending)
        advanced_filters.addWidget(QLabel("Limit"))
        advanced_filters.addWidget(self.browser_limit)
        advanced_filters.addStretch(1)
        advanced_layout.addLayout(advanced_filters)

        self.browser_table = QTableWidget(0, 15)
        self.browser_table.setHorizontalHeaderLabels([
            "Name",
            "Live Name",
            "Host",
            "Game Port",
            "Query Port",
            "Status",
            "Map",
            "Players",
            "Ping",
            "Version",
            "Flags",
            "Required Mods",
            "Last Checked",
            "Last Seen",
            "Source",
        ])
        self.browser_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.browser_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.browser_table.setSortingEnabled(True)
        self.browser_table.cellDoubleClicked.connect(self.handle_browser_double_clicked)
        self.browser_table.setContextMenuPolicy(Qt.CustomContextMenu)
        self.browser_table.customContextMenuRequested.connect(self.show_browser_context_menu)
        layout.addWidget(self.browser_table)

        buttons = QHBoxLayout()
        self.refresh_database_button = QPushButton("Refresh database")
        self.refresh_database_button.clicked.connect(self.refresh_from_configured_provider)
        self.enrich_visible_button = QPushButton("Enrich visible")
        self.enrich_visible_button.clicked.connect(self.enrich_visible_discovered_servers)
        promote = QPushButton("Promote to curated")
        promote.clicked.connect(self.promote_selected_discovered_server)
        use_server = QPushButton("Inspect mods")
        use_server.clicked.connect(self.inspect_selected_discovered_server)
        launch_discovered = QPushButton("Launch server")
        launch_discovered.clicked.connect(self.launch_selected_discovered_server)
        clear_filters = QPushButton("Reset filters")
        clear_filters.clicked.connect(self.reset_browser_filters)
        refresh = QPushButton("Refresh cache view")
        refresh.clicked.connect(self.refresh_server_browser)
        advanced_tools = QHBoxLayout()
        advanced_tools.addWidget(self.refresh_database_button)
        advanced_tools.addWidget(self.enrich_visible_button)
        advanced_tools.addWidget(refresh)
        advanced_tools.addStretch(1)
        advanced_layout.addLayout(advanced_tools)

        buttons.addWidget(self.browser_advanced_toggle)
        buttons.addStretch(1)
        buttons.addWidget(promote)
        buttons.addWidget(use_server)
        buttons.addWidget(launch_discovered)
        buttons.addWidget(clear_filters)
        layout.addLayout(buttons)
        layout.addWidget(self.browser_advanced_panel)

        self.browser_advanced_toggle.toggled.connect(
            lambda expanded: set_disclosure_state(
                self.browser_advanced_toggle,
                self.browser_advanced_panel,
                "advanced filters and tools",
                expanded,
            )
        )
        set_disclosure_state(
            self.browser_advanced_toggle,
            self.browser_advanced_panel,
            "advanced filters and tools",
            False,
        )
        return widget

    def _build_mods_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)

        self.mod_summary = QLabel("Select a server to check its required mods.")
        layout.addWidget(self.mod_summary)

        buttons = QHBoxLayout()
        check = QPushButton("Recheck selected server mods")
        check.clicked.connect(lambda _checked=False: self.check_selected_server_mods(force=True))
        native_preview = QPushButton("Native launch preview")
        native_preview.clicked.connect(self.preview_native_launch)
        copy_report = QPushButton("Copy mod report")
        copy_report.clicked.connect(self.copy_mod_check_report)
        copy_missing = QPushButton("Copy missing links")
        copy_missing.clicked.connect(self.copy_missing_workshop_links)
        open_selected = QPushButton("Open selected Workshop page")
        open_selected.clicked.connect(self.open_selected_workshop_page)
        open_missing = QPushButton("Open missing Workshop pages")
        open_missing.clicked.connect(self.open_missing_workshop_pages)
        self.subscribe_missing_button = QPushButton("Subscribe to missing mods (experimental)")
        self.subscribe_missing_button.clicked.connect(self.subscribe_missing_workshop_mods)
        buttons.addWidget(check)
        self.mod_filter = QComboBox()
        self.mod_filter.addItems(["All mods", "Missing only", "Installed only"])
        self.mod_filter.currentTextChanged.connect(self.apply_mod_filter)
        buttons.addWidget(open_missing)
        buttons.addWidget(self.subscribe_missing_button)
        buttons.addStretch(1)
        buttons.addWidget(QLabel("Filter"))
        buttons.addWidget(self.mod_filter)
        layout.addLayout(buttons)

        self.mods_advanced_toggle = QPushButton()
        self.mods_advanced_toggle.setCheckable(True)
        advanced_toggle_row = QHBoxLayout()
        advanced_toggle_row.addWidget(self.mods_advanced_toggle)
        advanced_toggle_row.addStretch(1)

        self.mods_advanced_panel = QWidget()
        advanced_layout = QHBoxLayout(self.mods_advanced_panel)
        advanced_layout.setContentsMargins(0, 0, 0, 0)
        advanced_layout.addWidget(native_preview)
        advanced_layout.addWidget(copy_report)
        advanced_layout.addWidget(copy_missing)
        advanced_layout.addWidget(open_selected)
        advanced_layout.addStretch(1)

        self.mods_advanced_toggle.toggled.connect(
            lambda expanded: set_disclosure_state(
                self.mods_advanced_toggle,
                self.mods_advanced_panel,
                "advanced mod tools",
                expanded,
            )
        )
        set_disclosure_state(
            self.mods_advanced_toggle,
            self.mods_advanced_panel,
            "advanced mod tools",
            False,
        )

        self.mods_table = QTableWidget(0, 5)
        self.mods_table.setHorizontalHeaderLabels([
            "Status",
            "Name",
            "Workshop ID",
            "Size",
            "Workshop URL",
        ])
        self.mods_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.mods_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.mods_table.setSortingEnabled(True)
        self.mods_table.setStyleSheet(
            "QTableWidget::item { padding: 4px 8px; } "
            "QHeaderView::section { padding: 4px 8px; }"
        )
        self.mods_table.verticalHeader().setDefaultSectionSize(30)
        self.mods_table.horizontalHeader().setStretchLastSection(True)
        self.mods_table.cellDoubleClicked.connect(self.handle_mod_double_clicked)
        self.mods_table.setContextMenuPolicy(Qt.CustomContextMenu)
        self.mods_table.customContextMenuRequested.connect(self.show_mod_context_menu)
        layout.addWidget(self.mods_table)
        layout.addLayout(advanced_toggle_row)
        layout.addWidget(self.mods_advanced_panel)
        return widget

    def _build_settings_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)

        self.system_summary = QLabel("Checking Steam and DayZ installation...")
        layout.addWidget(self.system_summary)

        launcher_settings = QFormLayout()
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
        launcher_settings.addRow("Steam install mode", self.native_steam_mode)
        layout.addLayout(launcher_settings)
        self.launch_engine.currentTextChanged.connect(
            self.update_external_launcher_settings_visibility
        )
        self.update_external_launcher_settings_visibility()

        self.health_table = QTableWidget(0, 3)
        self.health_table.setHorizontalHeaderLabels(["Check", "Status", "Details"])
        self.health_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.health_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.health_table.setContextMenuPolicy(Qt.CustomContextMenu)
        self.health_table.customContextMenuRequested.connect(self.show_health_context_menu)
        layout.addWidget(self.health_table)

        self.settings_advanced_toggle = QPushButton()
        self.settings_advanced_toggle.setCheckable(True)

        self.settings_advanced_panel = QWidget()
        advanced_layout = QVBoxLayout(self.settings_advanced_panel)
        advanced_layout.setContentsMargins(0, 0, 0, 0)

        discovery_settings = QFormLayout()

        self.discovery_provider = QComboBox()
        self.discovery_provider.addItems([
            "WolfAPI",
            "BattleMetrics",
            "Steam Web API",
            "Steam Master",
            "Disabled",
        ])
        self.discovery_provider.setCurrentText(
            self._provider_label(str(self.settings.get("discovery_provider") or "battlemetrics"))
        )
        self.discovery_provider.currentTextChanged.connect(self.handle_settings_changed)
        discovery_settings.addRow("Server API provider", self.discovery_provider)

        self.discovery_limit = QSpinBox()
        self.discovery_limit.setRange(1, 10000)
        self.discovery_limit.setValue(int(self.settings.get("discovery_limit", 500)))
        self.discovery_limit.valueChanged.connect(self.handle_settings_changed)
        discovery_settings.addRow("Refresh limit", self.discovery_limit)

        self.discovery_auto_refresh = QCheckBox("Refresh selected provider quietly after startup")
        self.discovery_auto_refresh.setChecked(bool(self.settings.get("discovery_auto_refresh", False)))
        self.discovery_auto_refresh.stateChanged.connect(self.handle_settings_changed)
        discovery_settings.addRow("Automatic refresh", self.discovery_auto_refresh)

        self.experimental_workshop_subscription = QCheckBox(
            "Enable Steam-native subscription controls (experimental)"
        )
        self.experimental_workshop_subscription.setChecked(
            bool(self.settings.get("experimental_workshop_subscription", False))
        )
        self.experimental_workshop_subscription.stateChanged.connect(
            self.handle_experimental_workshop_subscription_changed
        )
        discovery_settings.addRow("Workshop subscription", self.experimental_workshop_subscription)
        self.update_experimental_workshop_controls()

        self.steam_web_api_key = QLineEdit(
            str(self.settings.get("steam_web_api_key") or "")
            or os.environ.get("WOLFLAUNCHER_STEAM_WEB_API_KEY")
            or os.environ.get("STEAM_WEB_API_KEY")
            or ""
        )
        self.steam_web_api_key.setEchoMode(QLineEdit.Password)
        self.steam_web_api_key.setPlaceholderText("Steam Web API key")
        self.steam_web_api_key.editingFinished.connect(self.handle_settings_changed)
        discovery_settings.addRow("Steam API key", self.steam_web_api_key)

        self.steam_master_endpoints = QLineEdit(str(self.settings.get("steam_master_endpoints") or ""))
        self.steam_master_endpoints.setPlaceholderText("Comma separated host[:port]")
        self.steam_master_endpoints.editingFinished.connect(self.handle_settings_changed)
        discovery_settings.addRow("Steam masters", self.steam_master_endpoints)
        advanced_layout.addLayout(discovery_settings)

        support_tools = QHBoxLayout()
        copy_health = QPushButton("Copy health")
        copy_health.clicked.connect(self.copy_settings_health)
        copy_diagnostics = QPushButton("Copy diagnostics")
        copy_diagnostics.clicked.connect(self.copy_diagnostics_report)
        copy_last_launch = QPushButton("Copy last launch")
        copy_last_launch.clicked.connect(self.copy_last_launch_report)
        import_file = QPushButton("Import server list")
        import_file.clicked.connect(self.import_server_cache_file)
        support_tools.addWidget(copy_health)
        support_tools.addWidget(copy_diagnostics)
        support_tools.addWidget(copy_last_launch)
        support_tools.addWidget(import_file)
        support_tools.addStretch(1)
        advanced_layout.addLayout(support_tools)

        row = QHBoxLayout()
        health = QPushButton("Check health")
        health.clicked.connect(self.update_settings_health)
        save = QPushButton("Save settings")
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

    def update_external_launcher_settings_visibility(self, *_args):
        if hasattr(self, "external_launcher_settings"):
            self.external_launcher_settings.setVisible(
                self.launch_engine.currentText() == "External launcher"
            )

    def browse_launcher(self):
        path, _ = QFileDialog.getOpenFileName(self, "Select dayz-launcher.sh")
        if path:
            self.launcher_path.setText(path)
            self.save_user_settings(silent=True)
            self.update_settings_health()

    def import_server_cache_file(self):
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Import discovered servers",
            "",
            "Server cache files (*.yaml *.yml *.json);;All files (*)",
        )
        if not path:
            return
        try:
            count = server_cache.import_servers_from_file(self.server_cache, Path(path))
        except ValueError as exc:
            QMessageBox.critical(self, "Import failed", str(exc))
            return

        self.refresh_server_browser()
        QMessageBox.information(
            self,
            "Import complete",
            f"Imported {count} discovered server row(s) into the cache.",
        )

    def refresh_from_configured_provider(self):
        provider = self.discovery_provider_key()
        self.save_user_settings(silent=True)
        if provider == "wolfapi":
            self.refresh_from_wolfapi()
        elif provider == "battlemetrics":
            self.refresh_from_battlemetrics()
        elif provider == "steam_web_api":
            self.refresh_from_steam_web_api()
        elif provider == "steam_master":
            self.refresh_from_steam_master()
        else:
            QMessageBox.information(
                self,
                "Discovery disabled",
                "Choose a server API provider in Settings before refreshing the database.",
            )

    def _set_database_refresh_enabled(self, enabled: bool):
        if hasattr(self, "refresh_database_button"):
            self.refresh_database_button.setEnabled(enabled)

    def refresh_from_steam_master(self):
        if self.discovery_worker and self.discovery_worker.isRunning():
            return
        self.browser_summary.setText("Cached discovered servers: querying Steam master server...")
        self._set_database_refresh_enabled(False)
        try:
            master_addresses = self.steam_master_addresses()
        except ValueError as exc:
            self._set_database_refresh_enabled(True)
            QMessageBox.warning(self, "Invalid Steam master endpoints", str(exc))
            return
        self.discovery_worker = SteamDiscoveryWorker(max_batches=1, master_addresses=master_addresses)
        self.discovery_worker.discovery_ready.connect(self.handle_steam_discovery_ready)
        self.discovery_worker.start()

    def steam_master_addresses(self):
        text = self.steam_master_endpoints.text().strip()
        if not text:
            return None
        return [parse_master_address(item) for item in text.split(",") if item.strip()]

    def handle_steam_discovery_ready(self, servers, error: str):
        self._set_database_refresh_enabled(True)
        if error:
            self.refresh_server_browser()
            QMessageBox.warning(
                self,
                "Steam discovery failed",
                f"{error}\n\nExisting cached Steam master rows were kept. Check DNS/network access to the Steam master server, or use a YAML/JSON import file.",
            )
            return
        inserted, removed = server_cache.sync_source_servers(self.server_cache, "steam_master", servers)
        self.refresh_server_browser()
        self.statusBar().showMessage(
            f"Steam discovery complete: added {inserted} candidate(s), removed {removed} stale row(s).",
            7000,
        )

    def refresh_from_steam_web_api(self):
        if self.web_api_worker and self.web_api_worker.isRunning():
            return
        api_key = self.steam_web_api_key.text().strip()
        if not api_key:
            QMessageBox.warning(self, "Steam Web API key required", "Enter a Steam Web API key first.")
            return
        self.browser_summary.setText("Cached discovered servers: querying Steam Web API...")
        self._set_database_refresh_enabled(False)
        self.web_api_worker = SteamWebApiDiscoveryWorker(api_key=api_key, limit=self.discovery_limit.value())
        self.web_api_worker.discovery_ready.connect(self.handle_steam_web_api_ready)
        self.web_api_worker.start()

    def handle_steam_web_api_ready(self, servers, error: str):
        self._set_database_refresh_enabled(True)
        if error:
            self.refresh_server_browser()
            QMessageBox.warning(
                self,
                "Steam Web API discovery failed",
                f"{error}\n\nExisting cached Steam Web API rows were kept.",
            )
            return
        inserted, removed = server_cache.sync_source_servers(self.server_cache, "steam_web_api", servers)
        self.refresh_server_browser()
        self.statusBar().showMessage(
            f"Steam Web API discovery complete: added {inserted} row(s), removed {removed} stale row(s).",
            7000,
        )

    def refresh_from_battlemetrics(self):
        if self.battlemetrics_worker and self.battlemetrics_worker.isRunning():
            return
        self.browser_summary.setText("Cached discovered servers: querying BattleMetrics...")
        self._set_database_refresh_enabled(False)
        self.battlemetrics_worker = BattleMetricsDiscoveryWorker(limit=self.discovery_limit.value())
        self.battlemetrics_worker.discovery_ready.connect(self.handle_battlemetrics_ready)
        self.battlemetrics_worker.start()

    def refresh_from_wolfapi(self):
        if self.wolfapi_worker and self.wolfapi_worker.isRunning():
            return
        self.browser_summary.setText("Cached discovered servers: querying WolfAPI...")
        self._set_database_refresh_enabled(False)
        self.wolfapi_worker = WolfApiDiscoveryWorker(limit=self.discovery_limit.value())
        self.wolfapi_worker.discovery_ready.connect(self.handle_wolfapi_ready)
        self.wolfapi_worker.start()

    def maybe_auto_refresh_configured_provider(self):
        if not hasattr(self, "discovery_auto_refresh") or not self.discovery_auto_refresh.isChecked():
            return
        provider = self.discovery_provider_key()
        if provider == "disabled":
            return
        if self.discovery_worker and self.discovery_worker.isRunning():
            return
        if self.web_api_worker and self.web_api_worker.isRunning():
            return
        if self.battlemetrics_worker and self.battlemetrics_worker.isRunning():
            return
        if self.wolfapi_worker and self.wolfapi_worker.isRunning():
            return
        if not self.should_auto_refresh_provider(provider):
            return
        self.browser_summary.setText("Cached discovered servers: quietly refreshing configured provider...")
        self._set_database_refresh_enabled(False)
        if provider == "wolfapi":
            self.wolfapi_worker = WolfApiDiscoveryWorker(
                limit=self.discovery_limit.value(),
                automatic=True,
            )
            self.wolfapi_worker.discovery_ready.connect(self.handle_wolfapi_ready)
            self.wolfapi_worker.start()
        elif provider == "battlemetrics":
            self.battlemetrics_worker = BattleMetricsDiscoveryWorker(
                limit=self.discovery_limit.value(),
                page_delay=2.0,
                automatic=True,
            )
            self.battlemetrics_worker.discovery_ready.connect(self.handle_battlemetrics_ready)
            self.battlemetrics_worker.start()
        elif provider == "steam_web_api":
            api_key = self.steam_web_api_key.text().strip()
            if not api_key:
                self._set_database_refresh_enabled(True)
                return
            self.web_api_worker = SteamWebApiDiscoveryWorker(
                api_key=api_key,
                limit=self.discovery_limit.value(),
            )
            self.web_api_worker.discovery_ready.connect(self.handle_auto_web_api_ready)
            self.web_api_worker.start()
        elif provider == "steam_master":
            try:
                master_addresses = self.steam_master_addresses()
            except ValueError as exc:
                self._set_database_refresh_enabled(True)
                self.statusBar().showMessage(f"Steam master auto-refresh skipped: {exc}", 7000)
                return
            self.discovery_worker = SteamDiscoveryWorker(max_batches=1, master_addresses=master_addresses)
            self.discovery_worker.discovery_ready.connect(self.handle_auto_steam_discovery_ready)
            self.discovery_worker.start()

    def should_auto_refresh_provider(self, provider: str) -> bool:
        return auto_refresh_due(self.settings.get(f"last_{provider}_auto_refresh_at"))

    def mark_auto_refresh(self, provider: str):
        self.settings[f"last_{provider}_auto_refresh_at"] = auto_refresh_timestamp()
        self.save_user_settings(silent=True)

    def handle_auto_steam_discovery_ready(self, servers, error: str):
        self._set_database_refresh_enabled(True)
        self.mark_auto_refresh("steam_master")
        if error:
            self.refresh_server_browser()
            self.statusBar().showMessage(
                f"Steam master auto-refresh failed; cached rows kept: {error}",
                7000,
            )
            return
        inserted, removed = server_cache.sync_source_servers(self.server_cache, "steam_master", servers)
        self.refresh_server_browser()
        self.statusBar().showMessage(
            f"Steam master auto-refresh added {inserted} row(s), removed {removed}.",
            7000,
        )

    def handle_auto_web_api_ready(self, servers, error: str):
        self._set_database_refresh_enabled(True)
        self.mark_auto_refresh("steam_web_api")
        if error:
            self.refresh_server_browser()
            self.statusBar().showMessage(
                f"Steam Web API auto-refresh failed; cached rows kept: {error}",
                7000,
            )
            return
        inserted, removed = server_cache.sync_source_servers(self.server_cache, "steam_web_api", servers)
        self.refresh_server_browser()
        self.statusBar().showMessage(
            f"Steam Web API auto-refresh added {inserted} row(s), removed {removed}.",
            7000,
        )

    def handle_battlemetrics_ready(self, servers, error: str):
        automatic = bool(self.battlemetrics_worker and self.battlemetrics_worker.automatic)
        self._set_database_refresh_enabled(True)
        if automatic:
            self.mark_auto_refresh("battlemetrics")
        if error:
            self.refresh_server_browser()
            if automatic:
                self.statusBar().showMessage(
                    f"BattleMetrics auto-refresh failed; cached rows kept: {error}",
                    7000,
                )
                return
            QMessageBox.warning(
                self,
                "BattleMetrics discovery failed",
                f"{error}\n\nExisting cached BattleMetrics rows were kept.",
            )
            return
        inserted, removed = server_cache.sync_source_servers(self.server_cache, "battlemetrics", servers)
        self.refresh_server_browser()
        if automatic:
            self.statusBar().showMessage(
                f"BattleMetrics auto-refresh added {inserted} row(s), removed {removed}.",
                7000,
            )
            return
        self.statusBar().showMessage(
            f"BattleMetrics discovery complete: added {inserted} row(s), removed {removed} stale row(s).",
            7000,
        )

    def handle_wolfapi_ready(self, servers, error: str):
        automatic = bool(self.wolfapi_worker and self.wolfapi_worker.automatic)
        self._set_database_refresh_enabled(True)
        if automatic:
            self.mark_auto_refresh("wolfapi")
        if error:
            self.refresh_server_browser()
            if automatic:
                self.statusBar().showMessage(
                    f"WolfAPI auto-refresh failed; cached rows kept: {error}",
                    7000,
                )
                return
            QMessageBox.warning(
                self,
                "WolfAPI discovery failed",
                f"{error}\n\nExisting cached WolfAPI rows were kept.",
            )
            return
        inserted, removed = server_cache.sync_source_servers(self.server_cache, "wolfapi", servers)
        self.refresh_server_browser()
        if automatic:
            self.statusBar().showMessage(
                f"WolfAPI auto-refresh added {inserted} row(s), removed {removed}.",
                7000,
            )
            return
        self.statusBar().showMessage(
            f"WolfAPI discovery complete: added {inserted} row(s), removed {removed} stale row(s).",
            7000,
        )

    def enrich_visible_discovered_servers(self):
        if self.enrichment_worker and self.enrichment_worker.isRunning():
            return
        servers = list(self.browser_servers)
        if not servers:
            QMessageBox.warning(self, "No visible servers", "No discovered servers are visible to enrich.")
            return
        self.browser_summary.setText(f"Cached discovered servers: enriching {len(servers)} visible row(s)...")
        self.enrich_visible_button.setEnabled(False)
        self.enrichment_worker = ServerEnrichmentWorker(servers)
        self.enrichment_worker.enrichment_progress.connect(
            self.handle_enrichment_progress
        )
        self.enrichment_worker.enrichment_ready.connect(self.handle_enrichment_ready)
        self.enrichment_worker.start()

    def handle_enrichment_progress(self, server, completed: int, total: int):
        server_cache.upsert_server(self.server_cache, server)
        if completed == total or completed % 10 == 0:
            self.refresh_server_browser()
        self.browser_summary.setText(
            f"Cached discovered servers: enriched {completed} of {total} visible row(s)..."
        )

    def handle_enrichment_ready(self, servers, error: str):
        self.enrich_visible_button.setEnabled(True)
        count = server_cache.upsert_servers(self.server_cache, servers)
        self.refresh_server_browser()
        if error:
            QMessageBox.warning(
                self,
                "Enrichment stopped",
                f"Updated {count} row(s) before enrichment stopped:\n\n{error}",
            )
            return
        self.statusBar().showMessage(
            f"Enrichment complete: updated {count} discovered server row(s).",
            7000,
        )

    def promote_selected_discovered_server(self):
        server = self.selected_discovered_server()
        if not server:
            QMessageBox.warning(self, "No discovered server selected", "Select a discovered server first.")
            return

        dialog = PromoteServerDialog(self, server.name)
        if dialog.exec() != QDialog.Accepted:
            return
        name = dialog.curated_name()
        if not name:
            QMessageBox.warning(self, "Name required", "Enter a curated server name.")
            return

        curated = Server(
            name=name,
            group=dialog.curated_group(),
            host=server.host,
            game_port=server.game_port,
            query_port=server.query_port,
            favourite=False,
        )
        try:
            add_curated_server(self.config_path, curated)
        except ValueError as exc:
            QMessageBox.warning(self, "Could not promote server", str(exc))
            return

        self.add_curated_server_row(curated)
        QMessageBox.information(
            self,
            "Server promoted",
            f"{curated.name} was added to the curated Servers list.",
        )

    def selected_discovered_server(self):
        row = self.browser_table.currentRow()
        if row < 0:
            return None
        item = self.browser_table.item(row, 0)
        cache_key = item.data(Qt.UserRole) if item else None
        if not cache_key:
            return None
        return server_cache.get_server(self.server_cache, str(cache_key))

    @staticmethod
    def discovered_server_context(server: DiscoveredServer) -> Server:
        """Create a read-only, in-memory launch context from a discovered row."""
        return Server(
            name=server.server_name or server.name or server.connect_target,
            group="Discovered (read-only)",
            host=server.host,
            game_port=server.game_port,
            query_port=server.query_port,
            favourite=False,
        )

    def activate_selected_discovered_server(self) -> Server | None:
        discovered = self.selected_discovered_server()
        if not discovered:
            QMessageBox.warning(self, "No discovered server selected", "Select a discovered server first.")
            return None
        self.active_discovered_server = self.discovered_server_context(discovered)
        self.active_discovered_cache_key = discovered.cache_key
        self.update_launch_button_text()
        return self.active_discovered_server

    def inspect_selected_discovered_server(self):
        server = self.activate_selected_discovered_server()
        if server:
            self.tabs.setCurrentIndex(self.mods_tab_index)
            self.check_server_mods(server, force=True)

    def launch_selected_discovered_server(self):
        if self.activate_selected_discovered_server():
            self.launch_selected()

    def active_server_context(self) -> Server | None:
        if self.active_discovered_server is not None:
            return self.active_discovered_server
        row = self.table.currentRow()
        return self.servers[row] if 0 <= row < len(self.servers) else None

    def apply_refresh_timer(self):
        seconds = self.refresh_seconds.value()
        if seconds <= 0:
            self.timer.stop()
        else:
            self.timer.start(seconds * 1000)

    def _provider_label(self, key: str) -> str:
        labels = {
            "wolfapi": "WolfAPI",
            "battlemetrics": "BattleMetrics",
            "steam_web_api": "Steam Web API",
            "steam_master": "Steam Master",
            "disabled": "Disabled",
        }
        return labels.get(key, "BattleMetrics")

    def _native_steam_mode_label(self, key: str) -> str:
        return steam_mode_label(key)

    def discovery_provider_key(self) -> str:
        if not hasattr(self, "discovery_provider"):
            return str(self.settings.get("discovery_provider") or "battlemetrics")
        keys = {
            "WolfAPI": "wolfapi",
            "BattleMetrics": "battlemetrics",
            "Steam Web API": "steam_web_api",
            "Steam Master": "steam_master",
            "Disabled": "disabled",
        }
        return keys.get(self.discovery_provider.currentText(), "battlemetrics")

    def launch_engine_key(self) -> str:
        if not hasattr(self, "launch_engine"):
            return str(self.settings.get("launch_engine") or "native")
        return "native" if self.launch_engine.currentText() == "Native launcher" else "external"

    def native_steam_mode_key(self) -> str:
        if not hasattr(self, "native_steam_mode"):
            return str(self.settings.get("native_steam_mode") or "auto")
        keys = {
            "Auto": "auto",
            "Native Steam": "native",
            "Flatpak Steam": "flatpak",
            "STEAM_ROOT Steam library": "STEAM_ROOT env",
        }
        return keys.get(self.native_steam_mode.currentText(), "auto")

    def selected_steam_install(self) -> SteamInstall | None:
        return select_steam_install(self.native_steam_mode_key())

    def saved_selected_row(self) -> int:
        try:
            return int(self.settings.get("last_selected_row", -1))
        except (TypeError, ValueError):
            return -1

    def handle_settings_changed(self, *_args):
        self.save_user_settings(silent=True)
        self.update_settings_health()

    def handle_experimental_workshop_subscription_changed(self, *_args):
        self.update_experimental_workshop_controls()
        self.handle_settings_changed()

    def update_experimental_workshop_controls(self):
        enabled = (
            self.experimental_workshop_subscription.isChecked()
            if hasattr(self, "experimental_workshop_subscription")
            else bool(self.settings.get("experimental_workshop_subscription", False))
        )
        if hasattr(self, "subscribe_missing_button"):
            self.subscribe_missing_button.setVisible(enabled)

    def handle_launch_engine_changed(self, *_args):
        MainWindow._recheck_after_mod_context_change(
            self,
            "Launch engine changed. Rechecking selected server mods..."
        )

    def handle_native_steam_mode_changed(self, *_args):
        MainWindow._recheck_after_mod_context_change(
            self,
            "Steam install changed. Rechecking selected server mods..."
        )

    def _recheck_after_mod_context_change(self, message: str):
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
        self.statusBar().showMessage(f"Player name saved as {self.player_name.text().strip()}.", 5000)

    def save_user_settings(self, silent: bool = False):
        auto_refresh_timestamps = {
            key: value
            for key, value in self.settings.items()
            if key.startswith("last_") and key.endswith("_auto_refresh_at")
        }
        self.settings = {
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
            "experimental_workshop_subscription": self.experimental_workshop_subscription.isChecked()
            if hasattr(self, "experimental_workshop_subscription")
            else bool(self.settings.get("experimental_workshop_subscription", False)),
            "steam_web_api_key": self.steam_web_api_key.text().strip()
            if hasattr(self, "steam_web_api_key")
            else str(self.settings.get("steam_web_api_key") or ""),
            "steam_master_endpoints": self.steam_master_endpoints.text().strip()
            if hasattr(self, "steam_master_endpoints")
            else "",
        }
        self.settings.update(auto_refresh_timestamps)
        save_settings(self.settings)
        save_favourites(self.favourites)
        self.apply_refresh_timer()
        if not silent:
            QMessageBox.information(self, "Settings saved", "WolfLauncher settings were saved.")

    def refresh_statuses(self):
        self.refresh_status_rows(list(range(len(self.servers))), "Last updated: refreshing...")

    def refresh_selected_status(self):
        row = self.table.currentRow()
        if row < 0 or row >= len(self.servers):
            QMessageBox.warning(self, "No server selected", "Select a curated server first.")
            return
        self.refresh_status_rows([row], f"Last updated: refreshing {self.servers[row].name}...")

    def refresh_status_rows(self, rows: list[int], label: str):
        if self.worker and self.worker.isRunning():
            return
        if not rows:
            return
        self._set_status_refresh_enabled(False)
        self.last_refresh_label.setText(label)
        self.worker = StatusWorker(self.servers, rows)
        self.worker.status_ready.connect(self.update_status_row)
        self.worker.finished_all.connect(self.handle_refresh_finished)
        self.worker.start()

    def _set_status_refresh_enabled(self, enabled: bool):
        if hasattr(self, "refresh_status_button"):
            self.refresh_status_button.setEnabled(enabled)

    def refresh_server_browser(self, *_args):
        if not hasattr(self, "browser_table"):
            return

        self._refresh_browser_filter_options()
        sort_key = self.browser_sort.currentText().lower().replace(" ", "_")
        modded = None
        if self.browser_modded.currentText() == "Modded":
            modded = True
        elif self.browser_modded.currentText() == "Vanilla":
            modded = False
        map_name = self._combo_filter_value(self.browser_map, "Any map")
        version = self._combo_filter_value(self.browser_version, "Any version")
        source = self._combo_filter_value(self.browser_source, "Any source")
        style_terms = browser_style_terms(self.browser_style.currentText())
        limit = int(self.browser_limit.currentText())

        snapshot = load_browser_snapshot(
            self.server_cache,
            BrowserQuery(
                text=self.browser_search.text(),
                online_only=self.browser_online_only.isChecked(),
                map_name=map_name,
                version=version,
                source=source,
                style_terms=tuple(style_terms),
                modded=modded,
                sort_by=sort_key,
                descending=self.browser_descending.isChecked(),
                limit=limit,
            ),
        )
        servers = snapshot.servers
        self.browser_servers = servers

        populate_browser_table(self.browser_table, servers)
        self.browser_summary.setText(
            browser_summary_text(snapshot.cache_summary, len(servers), snapshot.match_count, limit)
        )

    def _refresh_browser_filter_options(self):
        options = browser_filter_options(self.server_cache)
        self._set_combo_filter_options(
            self.browser_map,
            "Any map",
            options["map"],
        )
        self._set_combo_filter_options(
            self.browser_version,
            "Any version",
            options["version"],
        )
        self._set_combo_filter_options(
            self.browser_source,
            "Any source",
            options["source"],
        )

    def _set_combo_filter_options(self, combo: QComboBox, any_label: str, values: list[str]):
        choices = [any_label, *values]
        existing = [combo.itemText(index) for index in range(combo.count())]
        if existing == choices:
            return

        current = combo.currentText()
        combo.blockSignals(True)
        combo.clear()
        combo.addItems(choices)
        combo.setCurrentText(current if current in choices else any_label)
        combo.blockSignals(False)

    def _combo_filter_value(self, combo: QComboBox, any_label: str) -> str:
        value = combo.currentText().strip()
        return "" if value == any_label else value

    def reset_browser_filters(self):
        self.browser_search.clear()
        self.browser_online_only.setChecked(False)
        self.browser_modded.setCurrentText("Any mods")
        self.browser_style.setCurrentText("Any style")
        self.browser_map.setCurrentText("Any map")
        self.browser_version.setCurrentText("Any version")
        self.browser_source.setCurrentText("Any source")
        self.browser_sort.setCurrentText("Name")
        self.browser_descending.setChecked(False)
        self.browser_limit.setCurrentText("200")
        self.refresh_server_browser()

    def _set_item(self, row: int, column: int, text: str, colour: str | None = None):
        item = QTableWidgetItem(text)
        if colour:
            item.setForeground(QColor(colour))
        self.table.setItem(row, column, item)

    def _set_curated_server_table_item(
        self,
        row: int,
        column: int,
        value: str,
        cached: bool = False,
    ):
        item = QTableWidgetItem(value)
        item.setData(Qt.UserRole, row)
        if cached and column in {3, 5, 8, 9, 10, 11, 12, 13, 14, 15}:
            item.setToolTip("Last known status; refresh is checking for current data.")
        self.table.setItem(row, column, item)

    def add_curated_server(self):
        dialog = EditCuratedServerDialog(
            self,
            Server(
                name="",
                group="Community",
                host="",
                game_port=2302,
                query_port=2303,
                favourite=False,
            ),
            title="Add curated server",
        )
        if dialog.exec() != QDialog.Accepted:
            return

        server = dialog.curated_server()
        if not server.name or not server.host:
            QMessageBox.warning(self, "Server details required", "Enter a server name and host.")
            return

        try:
            add_curated_server(self.config_path, server)
        except ValueError as exc:
            QMessageBox.warning(self, "Could not add server", str(exc))
            return

        if server.favourite:
            self.favourites.add(server_key(server))
            save_favourites(self.favourites)
        self.add_curated_server_row(server)
        row = len(self.servers) - 1
        self.table.selectRow(row)
        self.update_launch_button_text()
        self.statusBar().showMessage(f"Added curated server: {server.name}", 7000)
        self.refresh_status_rows([row], f"Last updated: refreshing {server.name}...")

    def add_curated_server_row(self, server: Server):
        self.servers.append(server)
        row = len(self.servers) - 1
        self.table.insertRow(row)
        values = [
            "★" if server.favourite else "☆",
            server.group,
            server.name,
            "",
            server.host,
            "Not checked",
            str(server.game_port),
            str(server.query_port),
            "Not checked",
            "",
            "",
            "",
            "",
            "",
            "",
            "",
        ]
        for column, value in enumerate(values):
            item = QTableWidgetItem(value)
            item.setData(Qt.UserRole, row)
            self.table.setItem(row, column, item)
        self.table.resizeColumnsToContents()

    def remove_curated_server_row(self, row: int):
        if row < 0 or row >= len(self.servers):
            return
        server = self.servers[row]
        answer = QMessageBox.question(
            self,
            "Remove curated server",
            f"Remove {server.name} from the curated Servers list?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if answer != QMessageBox.Yes:
            return

        try:
            removed = remove_curated_server(self.config_path, server)
        except ValueError as exc:
            QMessageBox.warning(self, "Could not remove server", str(exc))
            return
        if not removed:
            QMessageBox.warning(
                self,
                "Could not remove server",
                "This server was not found in servers.yaml.",
            )
            return

        self.favourites.discard(server_key(server))
        save_favourites(self.favourites)
        del self.servers[row]
        self.table.removeRow(row)
        self._reindex_server_rows()
        self.update_launch_button_text()

    def edit_curated_server_row(self, row: int):
        if row < 0 or row >= len(self.servers):
            return
        original = self.servers[row]
        dialog = EditCuratedServerDialog(self, original)
        if dialog.exec() != QDialog.Accepted:
            return

        updated = dialog.curated_server()
        if not updated.name or not updated.host:
            QMessageBox.warning(self, "Server details required", "Enter a server name and host.")
            return

        try:
            changed = update_curated_server(self.config_path, original, updated)
        except ValueError as exc:
            QMessageBox.warning(self, "Could not edit server", str(exc))
            return
        if not changed:
            QMessageBox.warning(
                self,
                "Could not edit server",
                "This server was not found in servers.yaml.",
            )
            return

        self.favourites.discard(server_key(original))
        if updated.favourite:
            self.favourites.add(server_key(updated))
        save_favourites(self.favourites)
        self.servers[row] = updated
        self.update_curated_server_row(row)
        self.update_launch_button_text()

    def apply_live_connect_port_to_curated_server(self, row: int):
        if row < 0 or row >= len(self.servers):
            return
        live_port = self._live_connect_port_for_row(row)
        if live_port is None:
            QMessageBox.warning(
                self,
                "No live port available",
                "Refresh this server successfully before applying a live connect port.",
            )
            return

        original = self.servers[row]
        if live_port == original.game_port:
            self.statusBar().showMessage("Curated server already uses the live connect port.", 7000)
            return

        updated = Server(
            name=original.name,
            group=original.group,
            host=original.host,
            game_port=live_port,
            query_port=original.query_port,
            favourite=original.favourite,
        )
        try:
            changed = update_curated_server(self.config_path, original, updated)
        except ValueError as exc:
            QMessageBox.warning(self, "Could not update server port", str(exc))
            return
        if not changed:
            QMessageBox.warning(
                self,
                "Could not update server port",
                "This server was not found in servers.yaml.",
            )
            return

        self.servers[row] = updated
        self._set_item(row, 6, str(live_port))
        self.statusBar().showMessage(
            f"Updated {updated.name} game port to live connect port {live_port}.",
            7000,
        )
        self.update_launch_button_text()

    def update_curated_server_row(self, row: int):
        if row < 0 or row >= len(self.servers):
            return
        server = self.servers[row]
        cached = cached_status_for_server(self.curated_status_cache, server)
        values = curated_server_row(server, cached)
        for column, value in enumerate(values):
            self._set_curated_server_table_item(row, column, value, cached=bool(cached))
        self.table.resizeColumnsToContents()

    def _reindex_server_rows(self):
        for row in range(self.table.rowCount()):
            for column in range(self.table.columnCount()):
                item = self.table.item(row, column)
                if item:
                    item.setData(Qt.UserRole, row)

    def update_status_row(self, row: int, status: ServerStatus):
        if row < 0 or row >= len(self.servers) or row >= self.table.rowCount():
            return
        update_status_cache(self.curated_status_cache, self.servers[row], status)
        self._set_item(row, 5, status.resolved_ip)
        if status.online:
            flags = []
            if status.password:
                flags.append("Password")
            if status.modded:
                flags.append("Mods")
            flags_text = ", ".join(flags) if flags else "Vanilla/unknown"
            ping_text = f"{status.ping}ms" if status.ping else ""
            self._set_item(row, 3, status.server_name or "Unknown")
            self._set_item(row, 8, "ONLINE", "#6ee16e")
            self._set_item(row, 9, status.map_name)
            self._set_item(row, 10, status.players)
            self._set_item(row, 11, status.time)
            self._set_item(row, 12, ping_text)
            self._set_item(row, 13, status.version)
            self._set_item(row, 14, flags_text)
            self._set_item(row, 15, status.connect)
        else:
            self._set_item(row, 3, "")
            self._set_item(row, 8, "OFFLINE", "#ff6b6b")
            self._set_item(row, 9, status.error)
            for column in range(10, 16):
                self._set_item(row, column, "")

    def handle_cell_clicked(self, row: int, column: int):
        if column == 0:
            self.toggle_favourite(row)

    def handle_cell_double_clicked(self, row: int, column: int):
        if column != 0:
            self.launch_selected()

    def toggle_favourite(self, row: int):
        if row < 0 or row >= len(self.servers):
            return
        server = self.servers[row]
        server.favourite = not server.favourite
        key = server_key(server)
        if server.favourite:
            self.favourites.add(key)
        else:
            self.favourites.discard(key)
        self.table.setItem(row, 0, QTableWidgetItem("★" if server.favourite else "☆"))
        save_favourites(self.favourites)

    def handle_refresh_finished(self):
        self._set_status_refresh_enabled(True)
        self.table.resizeColumnsToContents()
        self.last_refresh_label.setText(f"Last updated: {datetime.now().strftime('%H:%M:%S')}")
        self.update_launch_button_text()

    def handle_refresh_seconds_changed(self):
        self.apply_refresh_timer()
        self.save_user_settings(silent=True)

    def update_launch_button_text(self):
        if not hasattr(self, "launch_button"):
            return
        server = self.active_server_context()
        if server:
            self.launch_button.setText(f"Launch {server.name}")
        else:
            self.launch_button.setText("Launch selected server")

    def check_initial_server_mods(self):
        if self.servers and self.table.currentRow() < 0:
            last_row = self.saved_selected_row()
            row = last_row if 0 <= last_row < len(self.servers) else 0
            self.table.selectRow(row)
        self.check_selected_server_mods(silent=True)

    def handle_server_selection_changed(self):
        self.active_discovered_server = None
        self.active_discovered_cache_key = ""
        self.update_launch_button_text()
        if not hasattr(self, "mod_summary"):
            return
        self.check_selected_server_mods(silent=True)

    def check_selected_server_mods(self, silent: bool = False, force: bool = False):
        server = self.active_server_context()
        if not server:
            if not silent:
                QMessageBox.warning(self, "No server selected", "Select a server first.")
            return

        self.check_server_mods(server, silent=silent, force=force)

    def check_server_mods_for_row(self, row: int, silent: bool = False, force: bool = False):
        if row < 0 or row >= len(self.servers):
            return

        server = self.servers[row]
        self.check_server_mods(server, silent=silent, force=force)

    def check_server_mods(self, server: Server, silent: bool = False, force: bool = False):
        if not hasattr(self, "mod_summary") or not hasattr(self, "mods_table"):
            return
        selected_key = server_key(server)
        install = self.selected_steam_install() if self.launch_engine_key() == "native" else best_install()
        workshop_dir = install.workshop_dir if install else None
        cached_mod_result = usable_mod_result(server, self.last_mod_result, workshop_dir)
        if not force and cached_mod_result:
            if self.mods_table.rowCount() == 0:
                self.display_mods_result(cached_mod_result)
            self.update_workshop_recovery_state(cached_mod_result, install)
            return

        if self.mod_worker and self.mod_worker.isRunning():
            if self.active_mod_server_key != selected_key:
                self.pending_mod_server = server
                self.mod_summary.setText(
                    f"Queued mod check for {server.name}; finishing the current server check first."
                )
            return

        steam_context = self.mod_check_steam_context(install)
        if not workshop_dir:
            self.last_mod_result = None
            self.workshop_recovery_ids = ()
            self.mod_summary.setText(
                f"Workshop folder not detected for {steam_context or 'the current launch mode'}. "
                "Open Settings health to check the selected Steam install."
            )
            self.mods_table.setRowCount(0)
            if not silent:
                QMessageBox.warning(
                    self,
                    "Workshop folder not found",
                    "WolfLauncher could not find the DayZ Workshop folder for the current launch mode. Check Settings health.",
                )
            return

        self.mod_summary.setText(f"Checking required mods for {server.name}. {steam_context}.")
        self.workshop_recovery_ids = ()
        self.mods_table.setRowCount(0)
        self.active_mod_server_key = selected_key
        self.pending_mod_check_row = None
        self.pending_mod_server = None
        workshop_install = (
            install
            if bool(self.settings.get("experimental_workshop_subscription", False))
            and install
            and install.running
            else None
        )
        self.mod_worker = ModWorker(
            server, workshop_dir, steam_context, workshop_install=workshop_install
        )
        self.mod_worker.mods_ready.connect(self.update_mods_table)
        self.mod_worker.finished.connect(self.handle_mod_worker_finished)
        self.mod_worker.start()

    def update_mods_table(self, result: ModCheckResult):
        self.active_mod_server_key = ""
        current_server = self.active_server_context()
        install = self.selected_steam_install() if self.launch_engine_key() == "native" else best_install()
        workshop_dir = install.workshop_dir if install else None
        if not current_server:
            return
        if not matching_mod_result(current_server, result, workshop_dir):
            self.pending_mod_server = current_server
            return

        self.last_mod_result = result
        self.update_discovered_required_mod_count(result)
        self.display_mods_result(result)
        self.update_workshop_recovery_state(result, install)

    def update_discovered_required_mod_count(self, result: ModCheckResult):
        cache_key = self.active_discovered_cache_key
        if not result.ok or not cache_key:
            return
        discovered = server_cache.get_server(self.server_cache, cache_key)
        if not discovered or server_key(result.server) != server_key(
            self.discovered_server_context(discovered)
        ):
            return
        count = len(result.required_mods)
        if discovered.required_mod_count == count:
            return
        server_cache.upsert_server(
            self.server_cache, replace(discovered, required_mod_count=count)
        )
        self.refresh_server_browser()

    def handle_mod_worker_finished(self):
        self.mod_worker = None
        self._check_pending_server_mods()
        self.maybe_launch_after_workshop_download()

    def update_workshop_recovery_state(self, result: ModCheckResult, install: SteamInstall | None):
        missing_ids = [mod.workshop_id for mod in result.missing_mods] if result.ok else []
        recovery = workshop_recovery_state(install, missing_ids)
        self.workshop_recovery_ids = recovery.item_ids
        if recovery.active:
            count = len(recovery.item_ids)
            noun = "item" if count == 1 else "items"
            self.mod_summary.setText(
                f"{mod_summary_text(result)} Steam may still be downloading {count} required "
                f"Workshop {noun} from an earlier session. Check Steam Downloads; WolfLauncher "
                "will recheck when you use Recheck mods."
            )

    def display_mods_result(self, result: ModCheckResult):
        self.mods_table.setSortingEnabled(False)
        self.mod_summary.setText(mod_summary_text(result))
        if not result.ok:
            self.mods_table.setRowCount(0)
            self.mods_table.setSortingEnabled(True)
            return

        required = result.required_mods
        self.mods_table.setRowCount(len(required))
        for row, mod in enumerate(required):
            row_data = mod_row(mod)
            for column, value in enumerate(row_data.values):
                item = QTableWidgetItem(value)
                item.setData(Qt.UserRole, row_data.workshop_id)
                if column in {0, 2, 3}:
                    item.setTextAlignment(Qt.AlignCenter)
                if column == 0:
                    item.setForeground(QColor(row_data.status_colour))
                self.mods_table.setItem(row, column, item)
        self.mods_table.resizeColumnsToContents()
        self.mods_table.setSortingEnabled(True)
        self.mods_table.sortItems(0, Qt.DescendingOrder)
        self.apply_mod_filter()

    def mod_check_steam_context(self, install: SteamInstall | None) -> str:
        if not install:
            return "Steam install not detected"
        if self.launch_engine_key() == "native":
            return f"Selected Steam install: {install_label(install)}"
        return f"Auto Steam install: {install_label(install)}"

    def _check_pending_server_mods(self):
        if self.mod_worker and self.mod_worker.isRunning():
            return
        pending_server = getattr(self, "pending_mod_server", None)
        if pending_server is not None:
            self.pending_mod_server = None
            self.check_server_mods(pending_server, silent=True)
            return
        if self.pending_mod_check_row is None:
            return
        row = self.pending_mod_check_row
        self.pending_mod_check_row = None
        self.check_server_mods_for_row(row, silent=True)

    def apply_mod_filter(self):
        mode = self.mod_filter.currentText() if hasattr(self, "mod_filter") else "All mods"
        for row in range(self.mods_table.rowCount()):
            status_item = self.mods_table.item(row, 0)
            status = status_item.text() if status_item else ""
            hide = False
            if mode == "Missing only":
                hide = "Missing" not in status
            elif mode == "Installed only":
                hide = "Installed" not in status
            self.mods_table.setRowHidden(row, hide)

    def handle_mod_double_clicked(self, row: int, column: int):
        self.open_workshop_page_for_mod_row(row)

    def handle_browser_double_clicked(self, row: int, column: int):
        self.browser_table.selectRow(row)
        self.inspect_selected_discovered_server()

    def open_workshop_page_for_mod_row(self, row: int):
        if row < 0:
            return
        url = self._mods_cell(row, 4)
        if not url:
            workshop_id = self._mods_cell(row, 2)
            if workshop_id:
                url = f"https://steamcommunity.com/sharedfiles/filedetails/?id={workshop_id}"
        if not url:
            QMessageBox.warning(self, "No Workshop URL", "This mod row does not have a Workshop URL.")
            return
        QDesktopServices.openUrl(QUrl(url))

    def copy_to_clipboard(self, text: str, label: str = "Text"):
        QApplication.clipboard().setText(text)
        self.statusBar().showMessage(f"{label} copied to clipboard", 3000)

    def copy_settings_health(self):
        if not hasattr(self, "health_table") or self.health_table.rowCount() == 0:
            self.update_settings_health()
        self.copy_to_clipboard(self.settings_health_text(), "Settings health")

    def copy_diagnostics_report(self):
        self.copy_to_clipboard(
            run_diagnostics(
                self.launcher_path.text(),
                self.servers,
                self.native_steam_mode_key(),
                self.launch_engine_key(),
            ),
            "Diagnostics report",
        )

    def copy_mod_check_report(self):
        result = self._selected_mod_result()
        if not result:
            QMessageBox.information(
                self,
                "No mod check yet",
                "Check the selected server mods before copying its mod report.",
            )
            return
        self.copy_to_clipboard(format_mod_check_report(result), "Mod check report")

    def copy_missing_workshop_links(self):
        result = self._selected_mod_result(successful=True)
        if not result:
            QMessageBox.information(
                self,
                "No mod check yet",
                "Check the selected server mods successfully before copying missing Workshop links.",
            )
            return
        links = format_missing_workshop_links(result)
        if not links:
            QMessageBox.information(
                self,
                "No missing mods",
                "No missing Workshop links are available from the current mod check.",
            )
            return
        self.copy_to_clipboard(links, "Missing Workshop links")

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

    def show_mod_context_menu(self, pos: QPoint):
        row = self.mods_table.rowAt(pos.y())
        if row < 0:
            return
        self.mods_table.selectRow(row)
        menu = QMenu(self)
        open_action = QAction("Open Workshop page", self)
        copy_id_action = QAction("Copy Workshop ID", self)
        copy_name_action = QAction("Copy mod name", self)
        copy_url_action = QAction("Copy Workshop URL", self)
        check_update_action = QAction("Check/update this mod", self)
        open_action.triggered.connect(lambda: self.open_workshop_page_for_mod_row(row))
        copy_id_action.triggered.connect(lambda: self.copy_to_clipboard(self._mods_cell(row, 2), "Workshop ID"))
        copy_name_action.triggered.connect(lambda: self.copy_to_clipboard(self._mods_cell(row, 1), "Mod name"))
        copy_url_action.triggered.connect(lambda: self.copy_to_clipboard(self._mods_cell(row, 4), "Workshop URL"))
        check_update_action.triggered.connect(lambda: self.check_update_mod_row(row))
        check_update_action.setVisible(
            bool(self.settings.get("experimental_workshop_subscription", False))
        )
        menu.addAction(check_update_action)
        menu.addSeparator()
        menu.addAction(open_action)
        menu.addAction(copy_id_action)
        menu.addAction(copy_name_action)
        menu.addAction(copy_url_action)
        menu.exec(self.mods_table.viewport().mapToGlobal(pos))

    def show_browser_context_menu(self, pos: QPoint):
        row = self.browser_table.rowAt(pos.y())
        if row < 0:
            return
        self.browser_table.selectRow(row)
        server = self.selected_discovered_server()
        if not server:
            return
        menu = QMenu(self)
        inspect_action = QAction("Inspect mods", self)
        launch_action = QAction("Launch server", self)
        promote_action = QAction("Promote to curated", self)
        copy_connect_action = QAction("Copy connect address", self)
        copy_host_action = QAction("Copy host", self)
        copy_details_action = QAction("Copy server details", self)
        inspect_action.triggered.connect(self.inspect_selected_discovered_server)
        launch_action.triggered.connect(self.launch_selected_discovered_server)
        promote_action.triggered.connect(self.promote_selected_discovered_server)
        copy_connect_action.triggered.connect(
            lambda: self.copy_to_clipboard(server.connect_target, "Connect address")
        )
        copy_host_action.triggered.connect(
            lambda: self.copy_to_clipboard(server.host, "Server host")
        )
        copy_details_action.triggered.connect(
            lambda: self.copy_to_clipboard(discovered_server_details(server), "Server details")
        )
        menu.addAction(inspect_action)
        menu.addAction(launch_action)
        menu.addAction(promote_action)
        menu.addSeparator()
        menu.addAction(copy_connect_action)
        menu.addAction(copy_host_action)
        menu.addAction(copy_details_action)
        menu.exec(self.browser_table.viewport().mapToGlobal(pos))

    def _mods_cell(self, row: int, column: int) -> str:
        item = self.mods_table.item(row, column)
        return item.text() if item else ""

    def show_server_context_menu(self, pos: QPoint):
        row = self.table.rowAt(pos.y())
        if row < 0:
            menu = QMenu(self)
            add_action = QAction("Add curated server", self)
            add_action.triggered.connect(self.add_curated_server)
            menu.addAction(add_action)
            menu.exec(self.table.viewport().mapToGlobal(pos))
            return
        self.table.selectRow(row)
        menu = QMenu(self)
        add_action = QAction("Add curated server", self)
        refresh_selected_action = QAction("Refresh selected status", self)
        apply_live_port_action = QAction("Apply live connect port", self)
        copy_connect_action = QAction("Copy connect address", self)
        copy_details_action = QAction("Copy server details", self)
        edit_action = QAction("Edit curated server", self)
        toggle_fav_action = QAction("Toggle favourite", self)
        remove_action = QAction("Remove from curated list", self)
        add_action.triggered.connect(self.add_curated_server)
        refresh_selected_action.triggered.connect(self.refresh_selected_status)
        apply_live_port_action.triggered.connect(
            lambda: self.apply_live_connect_port_to_curated_server(row)
        )
        copy_connect_action.triggered.connect(lambda: self.copy_to_clipboard(self._server_cell(row, 15), "Connect address"))
        copy_details_action.triggered.connect(lambda: self.copy_to_clipboard(self.server_details_text(row), "Server details"))
        edit_action.triggered.connect(lambda: self.edit_curated_server_row(row))
        toggle_fav_action.triggered.connect(lambda: self.toggle_favourite(row))
        remove_action.triggered.connect(lambda: self.remove_curated_server_row(row))
        apply_live_port_action.setEnabled(
            self._live_connect_port_for_row(row) not in (None, self.servers[row].game_port)
        )
        menu.addAction(add_action)
        menu.addSeparator()
        menu.addAction(refresh_selected_action)
        menu.addAction(apply_live_port_action)
        menu.addAction(copy_connect_action)
        menu.addAction(copy_details_action)
        menu.addAction(edit_action)
        menu.addAction(toggle_fav_action)
        menu.addSeparator()
        menu.addAction(remove_action)
        menu.exec(self.table.viewport().mapToGlobal(pos))

    def _server_cell(self, row: int, column: int) -> str:
        item = self.table.item(row, column)
        return item.text() if item else ""

    def _live_connect_port_for_row(self, row: int) -> int | None:
        return parse_connect_port(self._server_cell(row, 15))

    def server_details_text(self, row: int) -> str:
        return "\n".join([
            self._server_cell(row, 3) or self._server_cell(row, 2),
            self._server_cell(row, 15),
            f"Map: {self._server_cell(row, 9)}",
            f"Players: {self._server_cell(row, 10)}",
            f"Version: {self._server_cell(row, 13)}",
        ]).strip()

    def open_selected_workshop_page(self):
        row = self.mods_table.currentRow()
        if row < 0:
            QMessageBox.warning(self, "No mod selected", "Select a mod first.")
            return
        self.open_workshop_page_for_mod_row(row)

    def open_missing_workshop_pages(self):
        result = self._selected_mod_result(successful=True)
        if not result:
            QMessageBox.warning(
                self,
                "No mod check yet",
                "Check the selected server mods successfully before opening missing Workshop pages.",
            )
            return
        missing = result.missing_mods
        if not missing:
            QMessageBox.information(self, "Mods ready", "All required mods appear to be ready.")
            return
        if len(missing) > 10:
            reply = QMessageBox.question(
                self,
                "Open many tabs?",
                f"This will open {len(missing)} Workshop pages. Continue?",
            )
            if reply != QMessageBox.Yes:
                return
        for mod in missing:
            QDesktopServices.openUrl(QUrl(mod.workshop_url))

    def subscribe_missing_workshop_mods(self):
        if not bool(self.settings.get("experimental_workshop_subscription", False)):
            QMessageBox.information(
                self,
                "Experimental feature disabled",
                "Enable Steam-native subscription controls in Settings first.",
            )
            return
        result = self._selected_mod_result(successful=True)
        if not result:
            QMessageBox.warning(
                self,
                "No mod check yet",
                "Check the selected server mods successfully before subscribing.",
            )
            return
        missing = result.missing_mods
        if not missing:
            QMessageBox.information(self, "No missing mods", "All required mods appear to be installed.")
            return
        if self.workshop_subscription_worker and self.workshop_subscription_worker.isRunning():
            if self.workshop_subscription_dialog:
                self.workshop_subscription_monitor_hidden = False
                self.workshop_subscription_dialog.show()
                self.workshop_subscription_dialog.raise_()
                self.workshop_subscription_dialog.activateWindow()
            self.statusBar().showMessage(
                "Showing the existing Steam Workshop monitor; no new session was started.",
                5000,
            )
            return
        recovery = workshop_recovery_state(
            self.selected_steam_install() if self.launch_engine_key() == "native" else best_install(),
            (mod.workshop_id for mod in missing),
        )
        if recovery.active:
            QMessageBox.information(
                self,
                "Steam Workshop activity detected",
                "Steam appears to have required DayZ Workshop items in its download staging "
                "area from an earlier session. Check Steam Downloads and wait for it to finish, "
                "then use Recheck mods. WolfLauncher will not start a second helper session yet.",
            )
            return

        install = self.selected_steam_install() if self.launch_engine_key() == "native" else best_install()
        if not install or not install.workshop_dir:
            QMessageBox.warning(
                self,
                "Steam installation unavailable",
                "WolfLauncher could not find the selected Steam/DayZ Workshop installation.",
            )
            return
        if not install.running:
            QMessageBox.warning(
                self,
                "Steam is not running",
                f"{install_label(install)} is currently not running.\n\n"
                "Open Steam, sign in to an account that owns DayZ, then try subscribing again.",
            )
            return
        names = "\n".join(
            f"- {mod.name or mod.workshop_id} — {mod_download_size(mod)}"
            for mod in missing[:12]
        )
        if len(missing) > 12:
            names += f"\n- ...and {len(missing) - 12} more"
        update_count = len(result.update_mods)
        absent_count = len(result.absent_mods)
        reply = QMessageBox.question(
            self,
            "Resolve using Steam?",
            f"Steam will resolve {len(missing)} required item(s) "
            f"({absent_count} missing, {update_count} update/pending) using the signed-in "
            f"Steam account. Missing items will be subscribed; existing items will be "
            f"asked to update.\n\n{names}\n\n"
            f"{combined_download_estimate(missing)}\n\n"
            "This feature is experimental. Continue?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if reply != QMessageBox.Yes:
            return

        self.start_workshop_resolution(missing, result, install)

    def check_update_mod_row(self, row: int):
        result = self._selected_mod_result(successful=True)
        workshop_id = self._mods_cell(row, 2)
        mod = next(
            (item for item in result.required_mods if item.workshop_id == workshop_id),
            None,
        ) if result else None
        if mod is None:
            QMessageBox.warning(
                self, "Mod check unavailable", "Recheck the selected server before updating this mod."
            )
            return
        if mod.ready:
            QMessageBox.information(
                self, "Mod already ready", f"{mod.name or mod.workshop_id} is already reported ready."
            )
            return
        if self.workshop_subscription_worker and self.workshop_subscription_worker.isRunning():
            self.subscribe_missing_workshop_mods()
            return
        install = self.selected_steam_install() if self.launch_engine_key() == "native" else best_install()
        if not install or not install.workshop_dir or not install.running:
            QMessageBox.warning(
                self,
                "Steam unavailable",
                "Start the selected Steam client and confirm its DayZ Workshop installation, then try again.",
            )
            return
        reply = QMessageBox.question(
            self,
            "Check/update using Steam?",
            f"Ask Steam to resolve {mod.name or mod.workshop_id}, then wait for a verified ready state?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if reply == QMessageBox.Yes:
            self.start_workshop_resolution([mod], result, install)

    def start_workshop_resolution(self, mods, result, install):
        """Start the existing isolated Steam resolution flow for selected mods."""
        ids = [mod.workshop_id for mod in mods]

        self.workshop_subscription_names = {
            mod.workshop_id: (mod.name or mod.workshop_id) for mod in mods
        }
        self.workshop_subscription_server_key = server_key(result.server)
        self.workshop_subscription_server = result.server
        self.workshop_subscription_dialog = QProgressDialog(
            "Sending subscriptions to Steam...", "Hide monitor", 0, 100, self
        )
        self.workshop_subscription_dialog.setWindowTitle("Steam Workshop (experimental)")
        self.workshop_subscription_dialog.setMinimumDuration(0)
        self.workshop_subscription_dialog.setAutoClose(False)
        self.workshop_subscription_dialog.setAutoReset(False)
        self.workshop_subscription_monitor_hidden = False

        self.workshop_subscription_worker = WorkshopSubscriptionWorker(ids, install)
        self.workshop_subscription_worker.progress_ready.connect(
            self.update_workshop_subscription_progress
        )
        self.workshop_subscription_worker.subscription_ready.connect(
            self.finish_workshop_subscription
        )
        self.workshop_subscription_worker.finished.connect(
            self.clear_workshop_subscription_worker
        )
        self.workshop_subscription_dialog.canceled.connect(
            self.stop_workshop_subscription_monitoring
        )
        self.launch_button.setEnabled(False)
        self.workshop_subscription_worker.start()

    def stop_workshop_subscription_monitoring(self):
        self.workshop_subscription_monitor_hidden = True
        if self.workshop_subscription_dialog:
            self.workshop_subscription_dialog.hide()
        self.statusBar().showMessage(
            "Workshop monitoring continues in the background; Steam downloads and launch "
            "readiness are unchanged.",
            8000,
        )

    def update_workshop_subscription_progress(self, snapshots):
        if hasattr(self, "update_mod_progress_rows"):
            self.update_mod_progress_rows(snapshots)
        dialog = self.workshop_subscription_dialog
        if not dialog or self.workshop_subscription_monitor_hidden or not snapshots:
            return
        installed = sum(1 for item in snapshots if item.installed)
        known = [item.percent for item in snapshots if item.percent is not None]
        progress = int(sum(known) / len(known)) if known else int(installed * 100 / len(snapshots))
        active = current_workshop_item(snapshots)
        detail = ""
        if active:
            item_name = self.workshop_subscription_names.get(
                active.workshop_id, active.workshop_id
            )
            detail = f" Current item: {item_name}"
            if active.percent is not None:
                detail += f" ({active.percent}%)"
        elif installed < len(snapshots):
            detail = " Waiting for Steam to start the next item."
        dialog.setLabelText(
            f"Steam has installed {installed} of {len(snapshots)} required item(s).{detail}"
        )
        dialog.setValue(progress)

    def update_mod_progress_rows(self, snapshots):
        result = self._selected_mod_result(successful=True)
        if not result:
            return
        apply_workshop_item_states(result, snapshots)
        mods = {mod.workshop_id: mod for mod in result.required_mods}
        for row in range(self.mods_table.rowCount()):
            id_item = self.mods_table.item(row, 2)
            workshop_id = id_item.data(Qt.UserRole) if id_item else ""
            mod = mods.get(str(workshop_id))
            if not mod:
                continue
            row_data = mod_row(mod)
            status_item = self.mods_table.item(row, 0)
            size_item = self.mods_table.item(row, 3)
            if status_item:
                status_item.setText(row_data.values[0])
                status_item.setForeground(QColor(row_data.status_colour))
            if size_item:
                size_item.setText(row_data.values[3])
            snapshot = next(
                (item for item in snapshots if item.workshop_id == mod.workshop_id),
                None,
            )
            percent = snapshot.percent if snapshot else None
            if (
                snapshot
                and snapshot.state & ITEM_STATE_DOWNLOADING
                and percent is not None
                and 0 <= percent < 100
            ):
                progress = self.mods_table.cellWidget(row, 0)
                if not isinstance(progress, QProgressBar):
                    progress = QProgressBar()
                    progress.setTextVisible(True)
                    progress.setStyleSheet(
                        "QProgressBar { text-align: center; padding: 1px; } "
                        "QProgressBar::chunk { background-color: #3da35a; }"
                    )
                    self.mods_table.setCellWidget(row, 0, progress)
                progress.setValue(percent)
                progress.setFormat(f"Downloading {percent}%")
            else:
                self.mods_table.removeCellWidget(row, 0)

    def finish_workshop_subscription(self, result):
        if self.workshop_subscription_dialog:
            self.workshop_subscription_dialog.close()
            self.workshop_subscription_dialog = None
        self.workshop_subscription_monitor_hidden = False
        if result.ok:
            self.launch_button.setEnabled(False)
            installed_count = len(result.installed_ids)
            noun = "mod" if installed_count == 1 else "mods"
            box = QMessageBox(self)
            box.setIcon(QMessageBox.Information)
            box.setWindowTitle("Mod download complete")
            box.setText(f"{installed_count} required {noun} downloaded successfully.")
            launch_button = box.addButton(
                "Launch server", QMessageBox.ButtonRole.AcceptRole
            )
            close_button = box.addButton("Close", QMessageBox.ButtonRole.RejectRole)
            box.setDefaultButton(launch_button)
            box.exec()
            self.launch_after_workshop_download = box.clickedButton() == launch_button
        elif result.cancelled:
            self.statusBar().showMessage(
                "Stopped waiting for Steam; subscriptions and Steam downloads may continue.", 8000
            )
        else:
            QMessageBox.warning(
                self,
                "Steam Workshop incomplete",
                (result.error or "Steam did not install every requested Workshop item.")
                + "\n\nYou can still use the manual Workshop links.",
            )
        self.workshop_subscription_names = {}
        self.check_selected_server_mods(force=True)

    def clear_workshop_subscription_worker(self):
        self.workshop_subscription_worker = None
        self.launch_button.setEnabled(True)
        self.statusBar().showMessage(
            "Steam Workshop helper finished; launch is available.", 5000
        )
        self.maybe_launch_after_workshop_download()

    def maybe_launch_after_workshop_download(self):
        if not self.launch_after_workshop_download:
            return
        workshop_worker = self.workshop_subscription_worker
        if workshop_worker and workshop_worker.isRunning():
            return
        if self.mod_worker and self.mod_worker.isRunning():
            return

        target_row = next(
            (
                row
                for row, server in enumerate(self.servers)
                if server_key(server) == self.workshop_subscription_server_key
            ),
            -1,
        )
        server = getattr(self, "workshop_subscription_server", None)
        if server is None:
            self.launch_after_workshop_download = False
            QMessageBox.warning(
                self,
                "Server unavailable",
                "The server selected for the Workshop download is no longer available.",
            )
            return

        install = self.selected_steam_install() if self.launch_engine_key() == "native" else best_install()
        workshop_dir = install.workshop_dir if install else None
        result = usable_mod_result(server, self.last_mod_result, workshop_dir)
        if not result or not result.ok or result.missing_mods:
            self.launch_after_workshop_download = False
            QMessageBox.warning(
                self,
                "Mods not ready",
                "The post-download mod check did not confirm every required mod. "
                "Review the Mods tab before launching.",
            )
            return

        self.launch_after_workshop_download = False
        if target_row >= 0:
            self.table.selectRow(target_row)
        else:
            self.active_discovered_server = server
        QTimer.singleShot(0, self.launch_selected)

    def workshop_launch_block_reason(self) -> str:
        state_worker = getattr(self, "workshop_state_worker", None)
        if state_worker and state_worker.isRunning():
            return "WolfLauncher is completing the final Steam Workshop readiness check."
        worker = self.workshop_subscription_worker
        if worker and worker.isRunning():
            return (
                "Steam is still processing the required Workshop items. Wait for monitoring "
                "to finish. Hide monitor only hides the progress window; use Install "
                "missing mods again to reopen the same monitor."
            )
        if self.workshop_recovery_ids:
            count = len(self.workshop_recovery_ids)
            noun = "item is" if count == 1 else "items are"
            return (
                f"Steam may still be downloading {count} required Workshop {noun} staged from "
                "an earlier session. Check Steam Downloads, wait for it to finish, then use "
                "Recheck mods before launching."
            )
        return ""

    def _selected_mod_result(self, *, successful: bool = False) -> ModCheckResult | None:
        server = self.active_server_context()
        if not server:
            return None
        install = self.selected_steam_install() if self.launch_engine_key() == "native" else best_install()
        workshop_dir = install.workshop_dir if install else None
        result = matching_mod_result(server, self.last_mod_result, workshop_dir)
        if successful and result and not result.ok:
            return None
        return result

    def preview_native_launch(self):
        if not self.last_mod_result or not self.last_mod_result.ok:
            QMessageBox.warning(
                self,
                "No mod check yet",
                "Check selected server mods successfully before preparing a native launch preview.",
            )
            return

        server = self.active_server_context()
        if not server:
            QMessageBox.warning(self, "No server selected", "Select a curated server first.")
            return
        if server_key(server) != server_key(self.last_mod_result.server):
            QMessageBox.warning(
                self,
                "Mods are for another server",
                "Recheck selected server mods before preparing a native launch preview.",
            )
            return

        install = self.selected_steam_install()
        if not install:
            QMessageBox.critical(
                self,
                "Steam not detected",
                "WolfLauncher could not detect the selected Steam installation.",
            )
            return

        try:
            report = prepare_native_launch_parity_report(
                install,
                self.launcher_path.text(),
                server,
                self.player_name.text().strip() or DEFAULT_PLAYER_NAME,
                self.last_mod_result.required_mods,
                selected_steam_mode=self.native_steam_mode_key(),
            )
        except NativeLaunchError as exc:
            self.show_native_preview_error(exc)
            return

        dialog = NativeLaunchPreviewDialog(
            self,
            f"Native launch preview for {server.name}",
            format_native_launch_parity_report(report),
            report.preview.command,
        )
        dialog.exec()

    def update_settings_health(self):
        if not hasattr(self, "health_table"):
            return
        install_rows = detect_steam()
        provider = self.discovery_provider_key()
        provider_detail = self.discovery_provider.currentText()
        if provider == "steam_web_api":
            provider_status = "OK" if self.steam_web_api_key.text().strip() else "MISSING"
            provider_detail = "Steam Web API key saved" if provider_status == "OK" else "Steam Web API key required"
        elif provider == "steam_master":
            try:
                addresses = self.steam_master_addresses()
            except ValueError as exc:
                provider_status = "WARN"
                provider_detail = str(exc)
            else:
                provider_status = "OK"
                provider_detail = ", ".join(address.address for address in addresses) if addresses else "Default Steam masters"
        elif provider == "wolfapi":
            provider_status = "OK"
            provider_detail = "WolfAPI hosted cache"
        elif provider == "battlemetrics":
            provider_status = "OK"
            provider_detail = "BattleMetrics public API"
        elif provider == "disabled":
            provider_status = "WARN"
            provider_detail = "Database refresh is disabled"
        else:
            provider_status = "OK"

        snapshot = build_settings_health_snapshot(
            self.launcher_path.text(),
            self.launch_engine_key(),
            self.native_steam_mode_key(),
            provider_status,
            provider_detail,
            install_rows,
        )
        self.system_summary.setText(snapshot.summary)
        rows = snapshot.rows
        self.health_table.setRowCount(len(rows))
        for row, (name, status, details) in enumerate(rows):
            self._set_health_item(row, 0, name)
            self._set_health_item(row, 1, status, self._health_colour(status))
            self._set_health_item(row, 2, details)
        self.health_table.resizeColumnsToContents()

    def _health_colour(self, status: str) -> str:
        if status == "OK":
            return "#6ee16e"
        if status == "WARN":
            return "#f6c453"
        return "#ff6b6b"

    def _set_health_item(self, row: int, column: int, text: str, colour: str | None = None):
        item = QTableWidgetItem(text)
        if colour:
            item.setForeground(QColor(colour))
        self.health_table.setItem(row, column, item)

    def launch_selected(self):
        workshop_block = self.workshop_launch_block_reason()
        if workshop_block:
            QMessageBox.information(
                self, "Steam Workshop in progress", workshop_block
            )
            return
        server = self.active_server_context()
        if not server:
            QMessageBox.warning(self, "No server selected", "Select a server first.")
            return

        self.save_user_settings(silent=True)

        if not self.confirm_launch_preflight(server):
            return

        install = self.selected_steam_install() if self.launch_engine_key() == "native" else best_install()
        result = usable_mod_result(
            server, self.last_mod_result, install.workshop_dir if install else None
        )
        if (
            bool(self.settings.get("experimental_workshop_subscription", False))
            and install
            and install.running
            and result
            and result.required_mods
        ):
            self.launch_button.setEnabled(False)
            self.statusBar().showMessage("Verifying current Steam Workshop readiness before launch...")
            self.workshop_state_worker = WorkshopStateWorker(
                (mod.workshop_id for mod in result.required_mods), install
            )
            self.workshop_state_worker.state_ready.connect(
                lambda state_result: self.finish_prelaunch_workshop_check(
                    server, result, state_result
                )
            )
            self.workshop_state_worker.finished.connect(
                self.clear_workshop_state_worker
            )
            self.workshop_state_worker.start()
            return

        self.perform_launch(server)

    def finish_prelaunch_workshop_check(self, server, result, state_result):
        current = self.active_server_context()
        if not current or server_key(current) != server_key(server):
            QMessageBox.warning(
                self, "Server selection changed", "Launch was cancelled because the active server changed."
            )
            return
        if state_result.error:
            QMessageBox.warning(
                self,
                "Workshop verification unavailable",
                "WolfLauncher could not complete the final Steam Workshop readiness check, "
                f"so launch was not started.\n\n{state_result.error}",
            )
            return
        apply_workshop_item_states(result, state_result.items)
        self.last_mod_result = result
        self.display_mods_result(result)
        if result.missing_mods:
            QMessageBox.warning(
                self,
                "Workshop items not ready",
                f"Steam reports {len(result.missing_mods)} required item(s) as update pending "
                "or downloading. Review the Mods tab and resolve them before launching.",
            )
            return
        self.perform_launch(server)

    def clear_workshop_state_worker(self):
        self.workshop_state_worker = None
        self.launch_button.setEnabled(True)

    def perform_launch(self, server: Server):

        try:
            command = self.build_selected_launch_command(server)
        except NativeLaunchError as exc:
            self.show_native_launch_error(exc)
            return
        except LaunchError as exc:
            QMessageBox.critical(self, "Launch failed", str(exc))
            return

        handoff_label = "native launch command" if self.launch_engine_key() == "native" else "external launcher"
        dialog = LaunchDialog(self, command, f"Launching {server.name}", handoff_label)
        dialog.exec()
        save_last_launch_report(dialog.copyable_output_text())

    def build_selected_launch_command(self, server: Server, row: int | None = None) -> list[str]:
        # Launch with the resolved IP address when available. This mirrors the
        # original terminal menu and avoids DayZSA API failures with some DNS
        # hostnames.
        if row is None and self.active_discovered_server is None:
            row = self.table.currentRow()
        resolved_item = self.table.item(row, 5) if row is not None and row >= 0 else None
        resolved_ip = resolved_item.text().strip() if resolved_item else ""
        launch_server = server_with_resolved_ipv4(server, resolved_ip)

        player_name = self.player_name.text().strip() or DEFAULT_PLAYER_NAME
        if self.launch_engine_key() == "native":
            install = self.selected_steam_install()
            if not install:
                raise NativeLaunchError(
                    "Selected Steam installation not detected",
                    stage="Steam detection",
                    guidance="Open Settings health and confirm the selected native or Flatpak Steam install can be detected.",
                )
            current_mod_result = usable_mod_result(
                server, self.last_mod_result, install.workshop_dir
            )
            required_mods = current_mod_result.required_mods if current_mod_result else None
            try:
                prepared = prepare_native_launch(install, launch_server, player_name, required_mods)
            except NativeLaunchError as exc:
                raise exc.with_details(
                    native_launch_failure_details(
                        install,
                        self.launcher_path.text(),
                        launch_server,
                        player_name,
                        required_mods,
                        self.native_steam_mode_key(),
                    )
                ) from exc
            return prepared.command

        return build_launch_command(self.launcher_path.text(), player_name, launch_server)

    def show_native_launch_error(self, error: NativeLaunchError):
        box = QMessageBox(self)
        box.setIcon(QMessageBox.Critical)
        box.setWindowTitle(f"Launch failed during {error.stage}")
        box.setText(error.user_message())
        if error.details:
            box.setDetailedText(error.details)
        box.exec()

    def show_native_preview_error(self, error: NativeLaunchError):
        box = QMessageBox(self)
        box.setIcon(QMessageBox.Critical)
        box.setWindowTitle(f"Native preview failed during {error.stage}")
        box.setText(error.user_message())
        if error.details:
            box.setDetailedText(error.details)
        box.exec()

    def confirm_launch_preflight(self, server: Server) -> bool:
        install = self.selected_steam_install() if self.launch_engine_key() == "native" else best_install()
        state = build_launch_preflight_state(
            install,
            server,
            self.last_mod_result,
            native_engine=self.launch_engine_key() == "native",
        )
        missing = self.last_mod_result.missing_mods if state.mods_checked else []
        steam_stopped_confirmed = False

        action = next_launch_preflight_action(state)
        if action == LaunchPreflightAction.BLOCK_MISSING_DAYZ:
            QMessageBox.critical(
                self,
                "DayZ not detected",
                "WolfLauncher could not detect a DayZ installation. Check Settings health before launching.",
            )
            return False

        if action == LaunchPreflightAction.BLOCK_MISSING_WORKSHOP:
            QMessageBox.critical(
                self,
                "Workshop folder not detected",
                "WolfLauncher could not detect the DayZ Workshop folder. Check Settings health before launching.",
            )
            return False

        if action == LaunchPreflightAction.CONFIRM_STEAM_STOPPED:
            reply = QMessageBox.question(
                self,
                "Steam is not running",
                f"{install.mode.title()} Steam was detected, but it does not appear to be running.\n\n"
                "The selected launch engine may still be able to start Steam, but starting Steam first is recommended.\n\n"
                "Launch anyway?",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No,
            )
            if reply != QMessageBox.Yes:
                return False
            steam_stopped_confirmed = True
            action = next_launch_preflight_action(
                state, steam_stopped_confirmed=steam_stopped_confirmed
            )

        if action in {
            LaunchPreflightAction.BLOCK_NATIVE_MISSING_MODS,
            LaunchPreflightAction.CONFIRM_EXTERNAL_MISSING_MODS,
        }:
            if missing:
                names = "\n".join(f"- {mod.name or mod.workshop_id}" for mod in missing[:12])
                if len(missing) > 12:
                    names += f"\n- ...and {len(missing) - 12} more"
                if action == LaunchPreflightAction.BLOCK_NATIVE_MISSING_MODS:
                    box = QMessageBox(self)
                    box.setIcon(QMessageBox.Warning)
                    box.setWindowTitle("Missing required mods")
                    box.setText(f"{server.name} is missing {len(missing)} required mod(s).")
                    box.setInformativeText(
                        f"{names}\n\n"
                        "The native launcher needs every required Workshop directory before it can "
                        "build the DayZ mod command."
                    )
                    open_button = box.addButton("Open Workshop", QMessageBox.ButtonRole.ActionRole)
                    install_button = None
                    if bool(self.settings.get("experimental_workshop_subscription", False)):
                        install_button = box.addButton(
                            "Install missing mods", QMessageBox.ButtonRole.ActionRole
                        )
                    cancel_button = box.addButton("Cancel", QMessageBox.ButtonRole.RejectRole)
                    box.setDefaultButton(cancel_button)
                    box.exec()
                    clicked = box.clickedButton()
                    if clicked == open_button:
                        self.open_missing_workshop_pages()
                    elif install_button is not None and clicked == install_button:
                        self.subscribe_missing_workshop_mods()
                    return False

                box = QMessageBox(self)
                box.setIcon(QMessageBox.Warning)
                box.setWindowTitle("Missing required mods")
                box.setText(f"{server.name} is missing {len(missing)} required mod(s).")
                box.setInformativeText(
                    f"{names}\n\nOpen the missing Workshop page(s), launch anyway, or cancel?"
                )
                open_button = box.addButton("Open Workshop", QMessageBox.ButtonRole.ActionRole)
                install_button = None
                if bool(self.settings.get("experimental_workshop_subscription", False)):
                    install_button = box.addButton(
                        "Install missing mods", QMessageBox.ButtonRole.ActionRole
                    )
                launch_button = box.addButton("Launch anyway", QMessageBox.ButtonRole.DestructiveRole)
                cancel_button = box.addButton("Cancel", QMessageBox.ButtonRole.RejectRole)
                box.setDefaultButton(cancel_button)
                box.exec()
                clicked = box.clickedButton()
                if clicked == open_button:
                    self.open_missing_workshop_pages()
                    return False
                if install_button is not None and clicked == install_button:
                    self.subscribe_missing_workshop_mods()
                    return False
                if clicked != launch_button:
                    return False
        elif action == LaunchPreflightAction.CONFIRM_MODS_UNCHECKED:
            reply = QMessageBox.question(
                self,
                "Mods not checked",
                "Required mods have not been checked for this server in this session.\n\nLaunch anyway?",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No,
            )
            if reply != QMessageBox.Yes:
                return False

        return True

    def closeEvent(self, event):
        worker = self.workshop_subscription_worker
        if worker and worker.isRunning():
            worker.cancel()
            worker.wait(5000)
        self.save_user_settings(silent=True)
        self.server_cache.close()
        super().closeEvent(event)


def main():
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    try:
        exit_code = app.exec()
    except KeyboardInterrupt:
        window.close()
        exit_code = 130
    sys.exit(exit_code)
