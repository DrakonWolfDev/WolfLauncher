import json
import os
import sys
import time
from dataclasses import replace
from datetime import datetime
from pathlib import Path

from PySide6.QtCore import QPoint, QProcess, QSize, Qt, QTimer, QUrl
from PySide6.QtGui import QAction, QColor, QDesktopServices, QIcon, QPixmap
from PySide6.QtNetwork import QNetworkAccessManager, QNetworkReply, QNetworkRequest
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QDialog,
    QFileDialog,
    QFormLayout,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMenu,
    QMessageBox,
    QProgressBar,
    QProgressDialog,
    QPushButton,
    QSizePolicy,
    QSpinBox,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from . import __version__, server_cache
from .config import (
    CURATED_SERVERS_PATH,
    add_curated_server,
    ensure_servers_file,
    find_default_launcher_path,
    load_servers,
    remove_curated_server,
    update_curated_server,
)
from .curated_dialogs import EditCuratedServerDialog, PromoteServerDialog
from .curated_server_cards import CuratedServerCard
from .curated_server_presenter import curated_server_row
from .curated_status_cache import (
    cached_status_for_server,
    load_status_cache,
    update_status_cache,
)
from .diagnostics import (
    format_settings_health_report,
    run_diagnostics,
)
from .discovery_refresh import (
    auto_refresh_due,
    auto_refresh_timestamp,
)
from .launch_dialogs import LaunchDialog, NativeLaunchPreviewDialog, PreflightLaunchDialog
from .launch_history import load_last_launch_report, save_last_launch_report
from .launch_preflight import (
    LaunchPreflightAction,
    build_launch_preflight_state,
    matching_mod_result,
    next_launch_preflight_action,
    usable_mod_result,
)
from .launch_selection import server_with_resolved_ipv4
from .launcher import DEFAULT_PLAYER_NAME, LaunchError, build_launch_command
from .lifecycle import (
    begin_runtime_shutdown,
    kill_runtime_process,
    runtime_shutdown_complete,
)
from .mod_presenter import (
    combined_download_estimate,
    mod_description_preview,
    mod_detail_status,
    mod_download_size,
    mod_file_size,
    mod_inspector_scale,
    mod_inspector_type_scale,
    mod_readiness_text,
    mod_row,
    mod_server_heading,
    mod_summary_text,
)
from .models import DiscoveredServer, Server
from .mods import (
    ModCheckResult,
    apply_workshop_item_states,
    format_missing_workshop_links,
    format_mod_check_report,
)
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
    best_install_from,
    build_steam_start_command,
    detect_steam,
    install_label,
    select_steam_install,
    steam_mode_label,
)
from .platforms import current_platform
from .redaction import redact_support_text
from .secret_store import (
    SecretStore,
    load_steam_api_key,
    settings_with_stored_steam_api_key,
)
from .server_browser_controller import BrowserQuery, browser_filter_options, load_browser_snapshot
from .server_browser_presenter import (
    browser_inspector,
    browser_mod_pill,
    browser_style_terms,
    browser_summary_text,
    browser_summary_tooltip,
    discovered_server_details,
    display_server_name,
)
from .server_browser_table import (
    BROWSER_COLUMN_COUNT,
    populate_browser_table,
    selected_browser_cache_key,
    update_browser_mod_cell,
    update_browser_table_row,
)
from .server_discovery import parse_master_address
from .server_display import display_map_name, display_server_flags, ping_severity
from .server_enrichment import (
    local_enrichment_due,
    parse_connect_port,
)
from .server_map_atmosphere import ServerMapAtmosphereFrame
from .settings import (
    DEFAULT_DISCOVERY_PROVIDER,
    load_favourites,
    load_settings,
    save_favourites,
    save_settings,
    server_key,
)
from .settings_health import build_settings_health_snapshot
from .settings_health_presenter import GROUP_SPECS, settings_health_groups
from .status import ServerStatus
from .theme import (
    COLOURS,
    STATUS_COLOURS,
    WOLF_MARK_PATH,
    apply_application_theme,
    configure_data_table,
    configure_priority_columns,
    monospace_font,
    set_monospace,
    set_ui_role,
    theme_icon,
)
from .ui_sections import set_disclosure_state
from .workers import (
    BattleMetricsDiscoveryWorker,
    ModWorker,
    ServerEnrichmentWorker,
    StatusWorker,
    SteamDiscoveryWorker,
    SteamWebApiDiscoveryWorker,
    WolfApiCacheMergeWorker,
    WolfApiSearchWorker,
    WorkshopSubscriptionWorker,
)
from .workshop_subscription import (
    ITEM_STATE_DOWNLOADING,
    current_workshop_item,
    workshop_automation_unavailable_reason,
    workshop_recovery_state,
)

MAX_SELECTED_BROWSER_RUNNERS = 3
MAX_SELECTED_STATUS_RUNNERS = 1
MAX_RESULTS_FRESHNESS_BATCH = 10


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("WolfLauncher")
        self.resize(1350, 720)

        self.config_path = CURATED_SERVERS_PATH
        self._shutting_down = False
        self._shutdown_started = False
        self._shutdown_dialog = None
        self._shutdown_deadline = None
        ensure_servers_file(self.config_path)
        self.servers = load_servers(self.config_path)
        self.curated_status_cache = load_status_cache()
        self.settings = load_settings()
        self.secret_store = SecretStore()
        self.steam_api_key = load_steam_api_key(self.settings, self.secret_store)
        self.favourites = load_favourites()
        self.detected_steam_installs = []
        self.worker = None
        self.mod_worker = None
        self.workshop_subscription_worker = None
        self.workshop_state_worker = None
        self.preflight_dialog = None
        self.preflight_mod_worker = None
        self.preflight_workshop_worker = None
        self.preflight_server = None
        self.preflight_steam_attempts = 0
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
        self.wolfapi_refresh_process = None
        self.wolfapi_cache_worker = None
        self.wolfapi_cache_context = (False, "WolfAPI", "wolfapi")
        self.wolfapi_search_worker = None
        self.pending_wolfapi_search = ""
        self.selection_enrichment_workers = {}
        self.pending_selection_checks = {}
        self.results_freshness_worker = None
        self.pending_results_freshness = False
        self.browser_mod_workers = {}
        self.pending_browser_mod_previews = {}
        self.browser_mod_results = {}
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
            self._save_favourites_index()

        self.launcher_path = QLineEdit(
            str(self.settings.get("launcher_path") or find_default_launcher_path())
        )
        set_monospace(self.launcher_path)
        self.player_name = QLineEdit(str(self.settings.get("player_name") or DEFAULT_PLAYER_NAME))
        self.launch_engine = QComboBox()
        self.launch_engine.addItem("Native launcher")
        if current_platform().capabilities.supports_external_launcher:
            self.launch_engine.addItem("External launcher")
        saved_launch_engine = str(self.settings.get("launch_engine") or "native")
        self.launch_engine.setCurrentText(
            "Native launcher"
            if saved_launch_engine == "native"
            or not current_platform().capabilities.supports_external_launcher
            else "External launcher"
        )
        self.launch_engine.currentTextChanged.connect(self.handle_launch_engine_changed)
        self.native_steam_mode = QComboBox()
        steam_modes = ["Auto", "Native Steam"]
        if current_platform().capabilities.supports_flatpak:
            steam_modes.append("Flatpak Steam")
        steam_modes.append("STEAM_ROOT Steam library")
        self.native_steam_mode.addItems(steam_modes)
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
        set_ui_role(self.last_refresh_label, "metadata")

        self.timer = QTimer(self)
        self.timer.timeout.connect(self.refresh_statuses)
        self.remote_search_timer = QTimer(self)
        self.remote_search_timer.setSingleShot(True)
        self.remote_search_timer.setInterval(450)
        self.remote_search_timer.timeout.connect(self.start_remote_wolfapi_search)
        self.browser_selection_timer = QTimer(self)
        self.browser_selection_timer.setSingleShot(True)
        self.browser_selection_timer.setInterval(450)
        self.browser_selection_timer.timeout.connect(self.check_selected_discovered_server_status)

        self.tabs = QTabWidget()
        self.tabs.setObjectName("mainTabs")
        self.tabs.setCornerWidget(self._build_brand_lockup(), Qt.TopRightCorner)
        self.tabs.addTab(self._build_servers_tab(), theme_icon("servers"), "Servers")
        self.server_browser_tab_index = self.tabs.addTab(
            self._build_server_browser_tab(), theme_icon("browser"), "Server Browser"
        )
        self.mods_tab_index = self.tabs.addTab(self._build_mods_tab(), theme_icon("mods"), "Mods")
        self.tabs.addTab(self._build_settings_tab(), theme_icon("settings"), "Settings")
        self.tabs.currentChanged.connect(self.handle_main_tab_changed)
        self.setCentralWidget(self.tabs)

        self.apply_refresh_timer()
        self.refresh_statuses()
        self.refresh_server_browser()
        self.update_settings_health()
        QTimer.singleShot(0, self.check_startup_steam_state)
        QTimer.singleShot(0, self.check_initial_server_mods)
        QTimer.singleShot(30000, self.maybe_auto_refresh_configured_provider)

    def _build_brand_lockup(self) -> QWidget:
        lockup = QWidget()
        set_ui_role(lockup, "brandLockup")
        layout = QHBoxLayout(lockup)
        layout.setContentsMargins(8, 0, 10, 0)
        layout.setSpacing(7)
        mark = QLabel()
        mark.setPixmap(QIcon(str(WOLF_MARK_PATH)).pixmap(QSize(22, 22)))
        mark.setToolTip("WolfLauncher")
        wordmark = QLabel("WOLF // LAUNCHER")
        set_ui_role(wordmark, "brandWordmark")
        layout.addWidget(mark)
        layout.addWidget(wordmark)
        return lockup

    def _build_servers_tab(self) -> QWidget:
        widget = QWidget()
        set_ui_role(widget, "workspace")
        layout = QVBoxLayout(widget)

        status_summary = QHBoxLayout()
        status_summary.addWidget(self.last_refresh_label)
        status_summary.addStretch(1)
        self.curated_online_summary = QLabel("0 online")
        set_ui_role(self.curated_online_summary, "statusPositive")
        self.curated_offline_summary = QLabel("0 offline")
        set_ui_role(self.curated_offline_summary, "statusNegative")
        status_summary.addWidget(self.curated_online_summary)
        status_summary.addWidget(self.curated_offline_summary)
        layout.addLayout(status_summary)

        common_settings = QFormLayout()
        player_name_row = QHBoxLayout()
        player_name_row.addWidget(self.player_name)
        self.player_name.returnPressed.connect(self.save_player_name)
        self.player_name.textChanged.connect(self.sync_settings_player_name)
        set_player_name = QPushButton("Set name")
        set_player_name.clicked.connect(self.save_player_name)
        player_name_row.addWidget(set_player_name)
        common_settings.addRow("Player name", player_name_row)
        common_settings.addRow("Auto refresh", self.refresh_seconds)
        layout.addLayout(common_settings)

        self.table = QTableWidget(len(self.servers), 16)
        self.table.setHorizontalHeaderLabels(
            [
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
            ]
        )
        for column in (10, 12):
            self.table.horizontalHeaderItem(column).setTextAlignment(
                Qt.AlignRight | Qt.AlignVCenter
            )
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        configure_data_table(self.table)
        configure_priority_columns(
            self.table,
            (0, 3, 8, 9, 10, 12, 15),
            show_details=False,
            stretch_columns=(3,),
        )
        self.table.verticalHeader().setDefaultSectionSize(34)
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
        self.server_cards = QListWidget()
        set_ui_role(self.server_cards, "serverCards")
        self.server_cards.currentRowChanged.connect(self._select_curated_table_row)
        layout.addWidget(self.server_cards)
        layout.addWidget(self.table)
        self.table.hide()

        buttons = QHBoxLayout()
        add_server = QPushButton("Add a favourite server")
        add_server.setIcon(theme_icon("add"))
        add_server.clicked.connect(self.add_curated_server)
        self.refresh_status_button = QPushButton("Refresh status")
        self.refresh_status_button.setIcon(theme_icon("refresh"))
        self.refresh_status_button.clicked.connect(self.refresh_statuses)
        self.launch_button = QPushButton("Launch selected server")
        self.launch_button.setIcon(theme_icon("launch"))
        set_ui_role(self.launch_button, "primary")
        self.launch_button.clicked.connect(self.launch_selected)
        buttons.addStretch(1)
        buttons.addWidget(add_server)
        buttons.addWidget(self.refresh_status_button)
        buttons.addWidget(self.launch_button)
        layout.addLayout(buttons)
        self.update_curated_status_summary()
        self.refresh_curated_server_cards()
        return widget

    def _build_server_browser_tab(self) -> QWidget:
        widget = QWidget()
        set_ui_role(widget, "workspace")
        layout = QVBoxLayout(widget)

        filters = QHBoxLayout()
        self.browser_search = QLineEdit()
        self.browser_search.setPlaceholderText("Search discovered servers")
        self.browser_search.setClearButtonEnabled(True)
        self.browser_search.setMinimumWidth(280)
        self.browser_search.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.browser_search.textChanged.connect(self.refresh_server_browser)
        self.browser_search.textChanged.connect(self.schedule_remote_wolfapi_search)
        filters.addWidget(self.browser_search, 1)

        self.browser_modded = QComboBox()
        self.browser_modded.setFixedWidth(150)
        self.browser_modded.addItems(["Any mods", "Modded", "Vanilla"])
        self.browser_modded.currentTextChanged.connect(self.refresh_server_browser)
        filters.addWidget(self.browser_modded)

        self.browser_map = QComboBox()
        self.browser_map.setFixedWidth(180)
        self.browser_map.addItem("Any map")
        self.browser_map.currentTextChanged.connect(self.refresh_server_browser)
        self.browser_map.currentTextChanged.connect(
            lambda _text: self.schedule_remote_wolfapi_search(self.browser_search.text())
        )
        filters.addWidget(self.browser_map)

        self.browser_online_only = QCheckBox("Online only")
        self.browser_online_only.setFixedWidth(120)
        self.browser_online_only.stateChanged.connect(self.refresh_server_browser)
        filters.addWidget(self.browser_online_only)

        self.browser_summary = QLabel("Loading discovered servers…")
        set_ui_role(self.browser_summary, "metadata")

        self.browser_style = QComboBox()
        self.browser_style.setFixedWidth(150)
        self.browser_style.addItems(["Any game style", "PvE", "PvP"])
        self.browser_style.currentTextChanged.connect(self.refresh_server_browser)
        filters.insertWidget(2, self.browser_style)

        self.browser_version = QComboBox()
        self.browser_version.addItem("Any version")
        self.browser_version.currentTextChanged.connect(self.refresh_server_browser)
        self.browser_version.currentTextChanged.connect(
            lambda _text: self.schedule_remote_wolfapi_search(self.browser_search.text())
        )

        self.browser_source = QComboBox()
        self.browser_source.addItem("Any source")
        self.browser_source.currentTextChanged.connect(self.refresh_server_browser)

        self.browser_sort = QComboBox()
        self.browser_sort.addItems(
            ["Name", "Players", "Ping", "Map", "Version", "Last checked", "Last seen"]
        )
        self.browser_sort.currentTextChanged.connect(self.refresh_server_browser)

        self.browser_descending = QCheckBox("Desc")
        self.browser_descending.stateChanged.connect(self.refresh_server_browser)

        self.browser_limit = QComboBox()
        self.browser_limit.addItems(["200", "500", "1000"])
        self.browser_limit.currentTextChanged.connect(self.refresh_server_browser)
        layout.addLayout(filters)
        layout.addWidget(self.browser_summary)

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
        self.browser_hide_quality_flagged = QCheckBox("Hide quality warnings")
        self.browser_hide_quality_flagged.setToolTip(
            "Hide rows WolfAPI flags for suspicious provider telemetry or dense "
            "same-host populations. Off by default; exact/local data is retained."
        )
        self.browser_hide_quality_flagged.stateChanged.connect(self.refresh_server_browser)
        self.browser_hide_quality_flagged.stateChanged.connect(
            lambda _state: self.schedule_remote_wolfapi_search(self.browser_search.text())
        )
        advanced_filters.addWidget(self.browser_hide_quality_flagged)
        advanced_filters.addWidget(QLabel("Limit"))
        advanced_filters.addWidget(self.browser_limit)
        self.browser_detailed_columns = QCheckBox("Show detailed columns")
        self.browser_detailed_columns.toggled.connect(self.configure_browser_columns)
        advanced_filters.addWidget(self.browser_detailed_columns)
        advanced_filters.addStretch(1)
        advanced_layout.addLayout(advanced_filters)

        self.browser_table = QTableWidget(0, BROWSER_COLUMN_COUNT)
        self.browser_table.setHorizontalHeaderLabels(
            [
                "Server Name",
                "Live Name",
                "Host",
                "Game Port",
                "Query Port",
                "Status",
                "Map",
                "Players",
                "Ping",
                "Version",
                "Features",
                "Mods",
                "Last Checked",
                "Last Seen",
                "Source",
                "Region",
                "Game Time",
            ]
        )
        for column in (7, 8):
            self.browser_table.horizontalHeaderItem(column).setTextAlignment(
                Qt.AlignRight | Qt.AlignVCenter
            )
        self.browser_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.browser_table.setSelectionMode(QTableWidget.SingleSelection)
        self.browser_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.browser_table.setSortingEnabled(True)
        self.browser_table.setTabKeyNavigation(False)
        configure_data_table(self.browser_table)
        set_ui_role(self.browser_table, "browserTable")
        self.browser_table.verticalHeader().setDefaultSectionSize(34)
        self.configure_browser_columns(False)
        self.browser_table.itemActivated.connect(
            lambda item: self.handle_browser_double_clicked(item.row(), item.column())
        )
        self.browser_table.itemSelectionChanged.connect(self.update_browser_selection_context)
        self.browser_table.setContextMenuPolicy(Qt.CustomContextMenu)
        self.browser_table.customContextMenuRequested.connect(self.show_browser_context_menu)
        self.browser_detail_card = QFrame()
        set_ui_role(self.browser_detail_card, "browserDetail")
        self.browser_detail_card.setProperty("serverStatus", "warning")
        detail_layout = QVBoxLayout(self.browser_detail_card)
        detail_layout.setContentsMargins(0, 0, 0, 0)
        detail_layout.setSpacing(0)
        self.browser_detail_header = QFrame()
        set_ui_role(self.browser_detail_header, "browserDetailHeader")
        header_layout = QVBoxLayout(self.browser_detail_header)
        header_layout.setContentsMargins(16, 14, 16, 14)
        header_layout.setSpacing(6)
        header_top = QHBoxLayout()
        self.browser_detail_eyebrow = QLabel("SELECTED SERVER")
        set_ui_role(self.browser_detail_eyebrow, "inspectorLabel")
        self.browser_detail_status = QLabel("NO SELECTION")
        set_ui_role(self.browser_detail_status, "browserStatus")
        self.browser_detail_status.setProperty("serverStatus", "warning")
        self.browser_detail_mod_status = QLabel()
        set_ui_role(self.browser_detail_mod_status, "browserStatus")
        self.browser_detail_mod_status.setProperty("serverStatus", "warning")
        self.browser_detail_mod_status.hide()
        header_top.addWidget(self.browser_detail_eyebrow)
        header_top.addStretch(1)
        header_top.addWidget(self.browser_detail_status)
        header_top.addWidget(self.browser_detail_mod_status)
        header_layout.addLayout(header_top)
        self.browser_detail_title = QLabel("Select a server to inspect its details")
        self.browser_detail_title.setWordWrap(True)
        set_ui_role(self.browser_detail_title, "inspectorTitle")
        header_layout.addWidget(self.browser_detail_title)
        self.browser_detail_endpoint = QLabel("")
        set_monospace(self.browser_detail_endpoint)
        set_ui_role(self.browser_detail_endpoint, "browserEndpoint")
        header_layout.addWidget(self.browser_detail_endpoint)
        detail_layout.addWidget(self.browser_detail_header)

        facts = QFrame()
        set_ui_role(facts, "browserFacts")
        facts_layout = QGridLayout(facts)
        facts_layout.setContentsMargins(14, 12, 14, 12)
        facts_layout.setHorizontalSpacing(8)
        facts_layout.setVerticalSpacing(4)
        self.browser_detail_map = QLabel("—")
        self.browser_detail_players = QLabel("—")
        self.browser_detail_ping = QLabel("—")
        for column, (heading, value) in enumerate(
            (
                ("MAP", self.browser_detail_map),
                ("PLAYERS", self.browser_detail_players),
                ("PING", self.browser_detail_ping),
            )
        ):
            label = QLabel(heading)
            set_ui_role(label, "inspectorLabel")
            set_ui_role(value, "inspectorValue")
            facts_layout.addWidget(label, 0, column)
            facts_layout.addWidget(value, 1, column)
            facts_layout.setColumnStretch(column, 1)
        detail_layout.addWidget(facts)

        detail_body = QWidget()
        body_layout = QVBoxLayout(detail_body)
        body_layout.setContentsMargins(16, 14, 16, 14)
        body_layout.setSpacing(12)
        self.browser_detail_context = QLabel(
            "Selection-driven truth and mod readiness will appear here."
        )
        self.browser_detail_context.setWordWrap(True)
        set_ui_role(self.browser_detail_context, "metadata")
        self.browser_detail_truth = QLabel("")
        self.browser_detail_truth.setWordWrap(True)
        set_ui_role(self.browser_detail_truth, "metadata")
        self.browser_detail_features = QLabel("")
        self.browser_detail_features.setWordWrap(True)
        self.browser_detail_mods = QLabel("")
        self.browser_detail_mods.setWordWrap(True)
        self.browser_detail_diagnostics = QLabel("")
        self.browser_detail_diagnostics.setWordWrap(True)
        set_ui_role(self.browser_detail_diagnostics, "metadata")
        for child in (
            self.browser_detail_context,
            self.browser_detail_truth,
            self.browser_detail_features,
            self.browser_detail_mods,
            self.browser_detail_diagnostics,
        ):
            body_layout.addWidget(child)
        detail_layout.addWidget(detail_body)
        self.browser_detail_atmosphere = ServerMapAtmosphereFrame()
        set_ui_role(self.browser_detail_atmosphere, "browserAtmosphere")
        self.browser_detail_atmosphere.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        detail_layout.addWidget(self.browser_detail_atmosphere, 1)

        self.browser_splitter = QSplitter(Qt.Horizontal)
        self.browser_splitter.setObjectName("browserSplitter")
        self.browser_splitter.setHandleWidth(10)
        self.browser_splitter.setChildrenCollapsible(False)
        self.browser_splitter.addWidget(self.browser_table)
        self.browser_splitter.addWidget(self.browser_detail_card)
        self.browser_splitter.setStretchFactor(0, 3)
        self.browser_splitter.setStretchFactor(1, 1)
        self.browser_splitter.setSizes([990, 330])
        self.browser_splitter.splitterMoved.connect(
            lambda _position, _index: self.configure_browser_columns()
        )
        layout.addWidget(self.browser_splitter, 1)

        buttons = QHBoxLayout()
        self.refresh_database_button = QPushButton("Refresh server list")
        self.refresh_database_button.clicked.connect(self.refresh_from_configured_provider)
        self.browser_promote_button = QPushButton("Add to Favourite Servers")
        self.browser_promote_button.clicked.connect(self.promote_selected_discovered_server)
        self.browser_inspect_button = QPushButton("View mod details")
        self.browser_inspect_button.clicked.connect(self.inspect_selected_discovered_server)
        self.browser_launch_button = QPushButton("Launch server")
        self.browser_launch_button.setIcon(theme_icon("launch"))
        set_ui_role(self.browser_launch_button, "primary")
        self.browser_launch_button.clicked.connect(self.launch_selected_discovered_server)
        clear_filters = QPushButton("Reset filters")
        clear_filters.clicked.connect(self.reset_browser_filters)
        advanced_tools = QHBoxLayout()
        advanced_tools.addWidget(self.refresh_database_button)
        advanced_tools.addWidget(clear_filters)
        advanced_tools.addStretch(1)
        advanced_layout.addLayout(advanced_tools)

        buttons.addWidget(self.browser_advanced_toggle)
        buttons.addStretch(1)
        buttons.addWidget(self.browser_promote_button)
        buttons.addWidget(self.browser_inspect_button)
        buttons.addWidget(self.browser_launch_button)
        layout.addLayout(buttons)
        layout.addWidget(self.browser_advanced_panel)

        QWidget.setTabOrder(self.browser_search, self.browser_modded)
        QWidget.setTabOrder(self.browser_modded, self.browser_style)
        QWidget.setTabOrder(self.browser_style, self.browser_map)
        QWidget.setTabOrder(self.browser_map, self.browser_online_only)
        QWidget.setTabOrder(self.browser_online_only, self.browser_table)
        QWidget.setTabOrder(self.browser_table, self.browser_advanced_toggle)
        QWidget.setTabOrder(self.browser_advanced_toggle, self.browser_promote_button)
        QWidget.setTabOrder(self.browser_promote_button, self.browser_inspect_button)
        QWidget.setTabOrder(self.browser_inspect_button, self.browser_launch_button)

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
        self.update_browser_selection_context()
        return widget

    def _build_mods_tab(self) -> QWidget:
        widget = QWidget()
        set_ui_role(widget, "workspace")
        layout = QVBoxLayout(widget)

        self.mod_server_title = QLabel("No server selected")
        set_ui_role(self.mod_server_title, "summary")
        layout.addWidget(self.mod_server_title)
        self.mod_readiness = QLabel(
            "Choose a server from Favourite Servers or Server Browser to inspect its mods."
        )
        set_ui_role(self.mod_readiness, "metadata")
        layout.addWidget(self.mod_readiness)
        self.mod_summary = QLabel("")
        set_ui_role(self.mod_summary, "metadata")
        layout.addWidget(self.mod_summary)

        buttons = QHBoxLayout()
        check = QPushButton("Recheck selected server mods")
        check.setIcon(theme_icon("recheck"))
        set_ui_role(check, "accent")
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
        self.subscribe_missing_button = QPushButton("Install/update missing mods")
        self.subscribe_missing_button.clicked.connect(self.subscribe_missing_workshop_mods)
        self.subscribe_missing_button.setEnabled(False)
        buttons.addWidget(check)
        self.mod_filter = QComboBox()
        self.mod_filter.addItems(["All mods", "Missing only", "Installed only"])
        self.mod_filter.currentTextChanged.connect(self.apply_mod_filter)
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
        self.mods_back_to_browser_button = QPushButton("Back to Server Browser ←")
        self.mods_back_to_browser_button.clicked.connect(self.back_to_server_browser)
        advanced_toggle_row.addWidget(self.mods_back_to_browser_button)
        self.mods_launch_button = QPushButton("Launch selected server")
        self.mods_launch_button.setIcon(theme_icon("launch"))
        set_ui_role(self.mods_launch_button, "primary")
        self.mods_launch_button.clicked.connect(self.launch_selected)
        advanced_toggle_row.addWidget(self.mods_launch_button)

        self.mods_advanced_panel = QWidget()
        advanced_layout = QHBoxLayout(self.mods_advanced_panel)
        advanced_layout.setContentsMargins(0, 0, 0, 0)
        advanced_layout.addWidget(native_preview)
        advanced_layout.addWidget(copy_report)
        advanced_layout.addWidget(copy_missing)
        advanced_layout.addWidget(open_selected)
        advanced_layout.addWidget(open_missing)
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

        self.mods_table = QTableWidget(0, 4)
        self.mods_table.setHorizontalHeaderLabels(
            [
                "Status",
                "Name",
                "Workshop ID",
                "Size",
            ]
        )
        self.mods_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.mods_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.mods_table.setSortingEnabled(True)
        self.mods_table.setTabKeyNavigation(False)
        configure_data_table(self.mods_table)
        self.mods_table.itemActivated.connect(
            lambda item: self.handle_mod_double_clicked(item.row(), item.column())
        )
        self.mods_table.itemSelectionChanged.connect(self.update_mod_detail_card)
        self.mods_table.setContextMenuPolicy(Qt.CustomContextMenu)
        self.mods_table.customContextMenuRequested.connect(self.show_mod_context_menu)
        self.mod_detail_card = QFrame()
        set_ui_role(self.mod_detail_card, "modDetail")
        self.mod_detail_card.setProperty("modStatus", "warning")
        self.mod_detail_base_point_size = max(8.0, QApplication.font().pointSizeF())
        detail_layout = QVBoxLayout(self.mod_detail_card)
        detail_layout.setContentsMargins(14, 14, 14, 14)
        detail_layout.setSpacing(10)
        self.mod_detail_thumbnail = QLabel("No preview")
        self.mod_detail_thumbnail.setAlignment(Qt.AlignCenter)
        self.mod_detail_thumbnail.setFixedSize(320, 180)
        set_ui_role(self.mod_detail_thumbnail, "modThumbnail")
        thumbnail_row = QHBoxLayout()
        thumbnail_row.addStretch(1)
        thumbnail_row.addWidget(self.mod_detail_thumbnail)
        thumbnail_row.addStretch(1)
        detail_layout.addLayout(thumbnail_row)
        self.mod_detail_title = QLabel("Select a mod to see its Workshop details")
        set_ui_role(self.mod_detail_title, "cardTitle")
        self.mod_detail_description = QLabel(
            "Descriptions and preview images are supplied by the mod's Workshop page."
        )
        self.mod_detail_description.setWordWrap(True)
        set_ui_role(self.mod_detail_description, "metadata")
        self.mod_detail_metadata = QLabel("")
        set_ui_role(self.mod_detail_metadata, "metadata")
        detail_layout.addWidget(self.mod_detail_title)
        detail_layout.addWidget(self.mod_detail_description)
        detail_layout.addWidget(self.mod_detail_metadata)
        detail_layout.addStretch(1)
        self.mod_detail_open_button = QPushButton("Open Workshop page")
        self.mod_detail_open_button.setEnabled(False)
        self.mod_detail_open_button.clicked.connect(self.open_selected_workshop_page)
        open_row = QHBoxLayout()
        open_row.addStretch(1)
        open_row.addWidget(self.mod_detail_open_button)
        detail_layout.addLayout(open_row)

        self.mods_splitter = QSplitter(Qt.Horizontal)
        self.mods_splitter.setObjectName("modsSplitter")
        self.mods_splitter.setHandleWidth(10)
        self.mods_splitter.setChildrenCollapsible(False)
        self.mods_splitter.addWidget(self.mods_table)
        self.mods_splitter.addWidget(self.mod_detail_card)
        self.mods_splitter.setStretchFactor(0, 2)
        self.mods_splitter.setStretchFactor(1, 1)
        self.mods_splitter.setSizes([850, 450])
        self.mods_splitter.splitterMoved.connect(
            lambda _position, _index: self.resize_mod_detail_card()
        )
        layout.addWidget(self.mods_splitter, 1)
        self.mod_thumbnail_manager = QNetworkAccessManager(self)
        self.mod_thumbnail_manager.finished.connect(self.finish_mod_thumbnail_load)
        self.mod_thumbnail_url = ""
        self.resize_mod_detail_card()
        layout.addLayout(advanced_toggle_row)
        layout.addWidget(self.mods_advanced_panel)
        QWidget.setTabOrder(check, self.subscribe_missing_button)
        QWidget.setTabOrder(self.subscribe_missing_button, self.mod_filter)
        QWidget.setTabOrder(self.mod_filter, self.mods_table)
        QWidget.setTabOrder(self.mods_table, self.mods_advanced_toggle)
        QWidget.setTabOrder(self.mods_advanced_toggle, self.mods_back_to_browser_button)
        QWidget.setTabOrder(self.mods_back_to_browser_button, self.mods_launch_button)
        self.update_launch_button_text()
        return widget

    def _build_settings_tab(self) -> QWidget:
        widget = QWidget()
        set_ui_role(widget, "workspace")
        layout = QVBoxLayout(widget)

        self.system_summary = QLabel("Checking Steam and DayZ installation...")
        set_ui_role(self.system_summary, "summary")
        layout.addWidget(self.system_summary)

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
                "WolfAPI (legacy fallback)",
                "BattleMetrics",
                "Steam Web API",
                "Steam Master",
                "Disabled",
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
                "READY" if group.status == "OK" else "CHECK" if group.status == "WARN" else "ISSUE"
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
        self.schedule_results_freshness_check()
        if provider in ("wolfapi", "wolfapi_v1"):
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
        self.discovery_worker = SteamDiscoveryWorker(
            max_batches=1, master_addresses=master_addresses
        )
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
        inserted, removed = server_cache.sync_source_servers(
            self.server_cache, "steam_master", servers
        )
        self.refresh_server_browser()
        self.schedule_results_freshness_check()
        self.statusBar().showMessage(
            f"Steam discovery complete: added {inserted} candidate(s), removed {removed} stale row(s).",
            7000,
        )

    def refresh_from_steam_web_api(self):
        if self.web_api_worker and self.web_api_worker.isRunning():
            return
        api_key = self.steam_web_api_key.text().strip()
        if not api_key:
            QMessageBox.warning(
                self, "Steam Web API key required", "Enter a Steam Web API key first."
            )
            return
        self.browser_summary.setText("Cached discovered servers: querying Steam Web API...")
        self._set_database_refresh_enabled(False)
        self.web_api_worker = SteamWebApiDiscoveryWorker(
            api_key=api_key, limit=self.discovery_limit.value()
        )
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
        inserted, removed = server_cache.sync_source_servers(
            self.server_cache, "steam_web_api", servers
        )
        self.refresh_server_browser()
        self.schedule_results_freshness_check()
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
        if (
            self.wolfapi_refresh_process
            and self.wolfapi_refresh_process.state() != QProcess.NotRunning
        ):
            return
        use_v1 = self.discovery_provider_key() == "wolfapi_v1"
        self.start_wolfapi_refresh_process(automatic=False, use_v1=use_v1)

    def start_wolfapi_refresh_process(self, automatic: bool, use_v1: bool):
        label = "WolfAPI v1" if use_v1 else "WolfAPI legacy"
        self.browser_summary.setText(f"Cached discovered servers: querying {label}…")
        self._set_database_refresh_enabled(False)
        self.wolfapi_cache_context = (
            automatic,
            label,
            "wolfapi_v1" if use_v1 else "wolfapi",
        )
        process = QProcess(self)
        self.wolfapi_refresh_process = process
        process.setProgram(sys.executable)
        arguments = [
            "-m",
            "wolflauncher.wolfapi_refresh_process",
            "--cache",
            str(server_cache.SERVER_CACHE_PATH),
            "--limit",
            str(self.discovery_limit.value()),
        ]
        if use_v1:
            arguments.append("--v1")
        if use_v1 and self.browser_hide_quality_flagged.isChecked():
            arguments.append("--unflagged-only")
        process.setArguments(arguments)
        process.finished.connect(self.handle_wolfapi_refresh_process_finished)
        process.start()

    def handle_wolfapi_refresh_process_finished(self, _exit_code: int, _status):
        process = self.wolfapi_refresh_process
        automatic, label, provider = self.wolfapi_cache_context
        self._set_database_refresh_enabled(True)
        if process is None:
            return
        stdout = bytes(process.readAllStandardOutput()).decode("utf-8", errors="replace")
        stderr = bytes(process.readAllStandardError()).decode("utf-8", errors="replace").strip()
        try:
            payload = json.loads(stdout.strip())
            inserted = int(payload.get("inserted", 0))
            removed = int(payload.get("removed", 0))
            error = str(payload.get("error") or "")
        except (ValueError, TypeError, json.JSONDecodeError):
            inserted, removed = 0, 0
            error = stderr or "WolfAPI refresh helper returned an invalid response."
        if automatic:
            self.mark_auto_refresh(provider)
        self.handle_wolfapi_cache_ready(inserted, removed, error)

    def maybe_auto_refresh_configured_provider(self):
        if (
            not hasattr(self, "discovery_auto_refresh")
            or not self.discovery_auto_refresh.isChecked()
        ):
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
        if (
            self.wolfapi_refresh_process
            and self.wolfapi_refresh_process.state() != QProcess.NotRunning
        ):
            return
        if self.wolfapi_cache_worker and self.wolfapi_cache_worker.isRunning():
            return
        if not self.should_auto_refresh_provider(provider):
            return
        self.browser_summary.setText(
            "Cached discovered servers: quietly refreshing configured provider..."
        )
        self._set_database_refresh_enabled(False)
        if provider in ("wolfapi", "wolfapi_v1"):
            self.start_wolfapi_refresh_process(automatic=True, use_v1=provider == "wolfapi_v1")
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
            self.discovery_worker = SteamDiscoveryWorker(
                max_batches=1, master_addresses=master_addresses
            )
            self.discovery_worker.discovery_ready.connect(self.handle_auto_steam_discovery_ready)
            self.discovery_worker.start()

    def handle_main_tab_changed(self, index: int):
        if index != self.server_browser_tab_index:
            return
        self.schedule_selected_discovered_server_check()
        QTimer.singleShot(0, self.maybe_auto_refresh_configured_provider)

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
        inserted, removed = server_cache.sync_source_servers(
            self.server_cache, "steam_master", servers
        )
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
        inserted, removed = server_cache.sync_source_servers(
            self.server_cache, "steam_web_api", servers
        )
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
        inserted, removed = server_cache.sync_source_servers(
            self.server_cache, "battlemetrics", servers
        )
        self.refresh_server_browser()
        if not automatic:
            self.schedule_results_freshness_check()
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
        provider = "wolfapi_v1" if self.wolfapi_worker and self.wolfapi_worker.use_v1 else "wolfapi"
        label = self.wolfapi_worker.provider_label if self.wolfapi_worker else "WolfAPI"
        if automatic:
            self.mark_auto_refresh(provider)
        if error:
            self._set_database_refresh_enabled(True)
            self.refresh_server_browser()
            if automatic:
                self.statusBar().showMessage(
                    f"{label} auto-refresh failed; cached rows kept: {error}",
                    7000,
                )
                return
            QMessageBox.warning(
                self,
                f"{label} discovery failed",
                f"{error}\n\nExisting cached WolfAPI rows were kept.",
            )
            return
        self.browser_summary.setText(f"Cached discovered servers: updating {label} results…")
        self.wolfapi_cache_context = (automatic, label, provider)
        self.wolfapi_cache_worker = WolfApiCacheMergeWorker(
            server_cache.SERVER_CACHE_PATH,
            servers,
            bounded_v1=provider == "wolfapi_v1",
        )
        self.wolfapi_cache_worker.merge_ready.connect(self.handle_wolfapi_cache_ready)
        self.wolfapi_cache_worker.start()

    def handle_wolfapi_cache_ready(self, inserted: int, removed: int, error: str):
        automatic, label, _provider = self.wolfapi_cache_context
        self._set_database_refresh_enabled(True)
        if error:
            self.refresh_server_browser()
            if automatic:
                self.statusBar().showMessage(
                    f"{label} cache update failed; existing rows kept: {error}",
                    7000,
                )
                return
            QMessageBox.warning(
                self,
                f"{label} cache update failed",
                f"{error}\n\nExisting cached WolfAPI rows were kept.",
            )
            return
        self.refresh_server_browser()
        if not automatic:
            self.schedule_results_freshness_check()
        if automatic:
            self.statusBar().showMessage(
                f"{label} auto-refresh added {inserted} row(s), removed {removed}.",
                7000,
            )
            return
        self.statusBar().showMessage(
            f"{label} discovery complete: added {inserted} row(s), removed {removed} stale row(s).",
            7000,
        )

    def schedule_remote_wolfapi_search(self, text: str):
        self.remote_search_timer.stop()
        query = " ".join(text.split())
        if self.discovery_provider_key() != "wolfapi_v1" or len(query) < 3:
            self.pending_wolfapi_search = ""
            return
        self.pending_wolfapi_search = query
        self.remote_search_timer.start()

    def start_remote_wolfapi_search(self):
        query = " ".join(self.browser_search.text().split())
        if self.discovery_provider_key() != "wolfapi_v1" or len(query) < 3:
            self.pending_wolfapi_search = ""
            return
        if self.wolfapi_search_worker and self.wolfapi_search_worker.isRunning():
            self.pending_wolfapi_search = query
            return
        self.pending_wolfapi_search = ""
        map_name = self._combo_filter_value(self.browser_map, "Any map")
        version = self._combo_filter_value(self.browser_version, "Any version")
        self.wolfapi_search_worker = WolfApiSearchWorker(
            query,
            limit=min(100, int(self.browser_limit.currentText())),
            map_name=map_name,
            version=version,
            unflagged_only=self.browser_hide_quality_flagged.isChecked(),
        )
        self.wolfapi_search_worker.search_ready.connect(self.handle_remote_wolfapi_search)
        self.wolfapi_search_worker.finished.connect(self.finish_remote_wolfapi_search)
        self.statusBar().showMessage(f'Searching WolfAPI v1 for "{query}"…')
        self.wolfapi_search_worker.start()

    def handle_remote_wolfapi_search(self, query: str, servers, error: str):
        current_query = " ".join(self.browser_search.text().split())
        if error:
            if query == current_query:
                self.statusBar().showMessage(
                    f"WolfAPI v1 search unavailable; showing cached results: {error}",
                    7000,
                )
            return
        merged = server_cache.merge_source_servers(self.server_cache, "wolfapi", servers)
        if query == current_query and self.discovery_provider_key() == "wolfapi_v1":
            self.refresh_server_browser()
            self.statusBar().showMessage(
                f'WolfAPI v1 search merged {merged} result(s) for "{query}".',
                5000,
            )

    def finish_remote_wolfapi_search(self):
        self.wolfapi_search_worker = None
        query = " ".join(self.browser_search.text().split())
        if self.pending_wolfapi_search and self.pending_wolfapi_search == query:
            self.remote_search_timer.start()

        else:
            self.schedule_selected_discovered_server_check()
            self.schedule_results_freshness_check()

    def schedule_results_freshness_check(self):
        """Live-check only the small result set produced by an explicit user action."""
        if not hasattr(self, "browser_servers"):
            return
        if self.results_freshness_worker and self.results_freshness_worker.isRunning():
            self.pending_results_freshness = True
            return
        selected_workers = set(self.selection_enrichment_workers)
        servers = [
            server
            for server in self.browser_servers
            if server.cache_key not in selected_workers and local_enrichment_due(server)
        ][:MAX_RESULTS_FRESHNESS_BATCH]
        if not servers:
            return
        self.pending_results_freshness = False
        self.statusBar().showMessage(
            f"Checking live freshness for {len(servers)} matching server(s) in the background..."
        )
        worker = ServerEnrichmentWorker(servers)
        self.results_freshness_worker = worker
        worker.enrichment_progress.connect(self.handle_results_freshness_progress)
        worker.finished.connect(self.handle_results_freshness_finished)
        worker.start()

    def handle_results_freshness_progress(self, payload, _completed: int, _total: int):
        old_cache_key, server = payload
        server_cache.replace_server_key(self.server_cache, old_cache_key, server)
        update_browser_table_row(self.browser_table, old_cache_key, server)

    def handle_results_freshness_finished(self):
        self.results_freshness_worker = None
        self.refresh_server_browser()
        if self.pending_results_freshness:
            self.pending_results_freshness = False
            QTimer.singleShot(0, self.schedule_results_freshness_check)
        else:
            self.schedule_selected_discovered_server_check()

    def schedule_selected_discovered_server_check(self):
        if not hasattr(self, "browser_selection_timer"):
            return
        self.browser_selection_timer.stop()
        server = self.selected_discovered_server()
        if server is not None and local_enrichment_due(server):
            self.browser_selection_timer.start()
        elif server is not None and server.status_source == "local" and server.online:
            self.start_selected_server_mod_preview(server)

    def check_selected_discovered_server_status(self):
        server = self.selected_discovered_server()
        if server is None:
            return
        if not local_enrichment_due(server):
            if server.status_source == "local" and server.online:
                self.start_selected_server_mod_preview(server)
            return
        row = self.browser_table.currentRow()
        status_item = self.browser_table.item(row, 5) if row >= 0 else None
        if status_item is not None:
            status_item.setText("CHECKING…")
            status_item.setForeground(QColor(STATUS_COLOURS["warning"]))
        self.update_browser_detail_card(server, status_override="Checking")
        self.start_selected_discovered_enrichment(server)

    def start_selected_discovered_enrichment(self, server: DiscoveredServer):
        cache_key = server.cache_key
        if cache_key in self.selection_enrichment_workers:
            return
        if len(self.selection_enrichment_workers) >= MAX_SELECTED_STATUS_RUNNERS:
            self.pending_selection_checks.clear()
            self.pending_selection_checks[cache_key] = server
            return
        worker = ServerEnrichmentWorker([server])
        self.selection_enrichment_workers[cache_key] = worker
        worker.enrichment_progress.connect(self.handle_selected_enrichment_progress)
        worker.finished.connect(lambda key=cache_key: self.handle_selected_enrichment_finished(key))
        worker.start()

    def handle_selected_enrichment_progress(self, payload, _completed: int, _total: int):
        old_cache_key, server = payload
        server_cache.replace_server_key(self.server_cache, old_cache_key, server)
        update_browser_table_row(self.browser_table, old_cache_key, server)
        self.update_browser_selection_context()
        if server.online:
            self.start_selected_server_mod_preview(server)

    def handle_selected_enrichment_finished(self, cache_key: str):
        self.selection_enrichment_workers.pop(cache_key, None)
        while (
            self.pending_selection_checks
            and len(self.selection_enrichment_workers) < MAX_SELECTED_STATUS_RUNNERS
        ):
            pending_key = next(iter(self.pending_selection_checks))
            server = self.pending_selection_checks.pop(pending_key)
            if local_enrichment_due(server):
                self.start_selected_discovered_enrichment(server)
        self.schedule_selected_discovered_server_check()

    def start_selected_server_mod_preview(self, discovered: DiscoveredServer):
        cache_key = discovered.cache_key
        cached = self.browser_mod_results.get(cache_key)
        now = time.monotonic()
        if cached and now - cached[0] < (900 if cached[1].ok else 300):
            self.apply_browser_mod_preview(cache_key, cached[1])
            return
        if cache_key in self.browser_mod_workers:
            return
        if len(self.browser_mod_workers) >= MAX_SELECTED_BROWSER_RUNNERS:
            self.pending_browser_mod_previews[cache_key] = discovered
            return
        install = self.selected_browser_preview_install()
        if not install or not install.workshop_dir:
            return
        update_browser_mod_cell(
            self.browser_table,
            cache_key,
            "CHECKING…",
            "Comparing this server's required mods with the selected Steam Workshop installation.",
            STATUS_COLOURS["warning"],
        )
        self.update_browser_detail_card(
            discovered, mod_preview="Checking local Workshop readiness…"
        )
        worker = ModWorker(
            self.discovered_server_context(discovered),
            install.workshop_dir,
            self.mod_check_steam_context(install),
            workshop_install=install if install.running else None,
            include_metadata=False,
        )
        self.browser_mod_workers[cache_key] = worker
        worker.mods_ready.connect(
            lambda result, key=cache_key: self.finish_browser_mod_preview(key, result)
        )
        worker.finished.connect(lambda key=cache_key: self.handle_browser_mod_preview_finished(key))
        worker.start()

    def finish_browser_mod_preview(self, cache_key: str, result: ModCheckResult):
        self.browser_mod_results[cache_key] = (time.monotonic(), result)
        self.apply_browser_mod_preview(cache_key, result)

    def handle_browser_mod_preview_finished(self, cache_key: str):
        self.browser_mod_workers.pop(cache_key, None)
        while (
            self.pending_browser_mod_previews
            and len(self.browser_mod_workers) < MAX_SELECTED_BROWSER_RUNNERS
        ):
            pending_key = next(iter(self.pending_browser_mod_previews))
            server = self.pending_browser_mod_previews.pop(pending_key)
            self.start_selected_server_mod_preview(server)

    def apply_browser_mod_preview(self, cache_key: str, result: ModCheckResult):
        if not result.ok:
            update_browser_mod_cell(
                self.browser_table,
                cache_key,
                "UNAVAILABLE",
                result.error or "Required-mod readiness could not be checked.",
                STATUS_COLOURS["warning"],
            )
            self.update_browser_detail_for_key(cache_key, "Unavailable")
            return
        missing = len(result.missing_mods)
        if missing:
            update_browser_mod_cell(
                self.browser_table,
                cache_key,
                f"{missing} MISSING",
                "Launch will open pre-flight and offer to install or update the missing Workshop items.",
                STATUS_COLOURS["negative"],
            )
            self.update_browser_detail_for_key(cache_key, f"{missing} missing locally")
            return
        update_browser_mod_cell(
            self.browser_table,
            cache_key,
            "READY",
            "Local Workshop readiness preview. Launch pre-flight performs the final check.",
            STATUS_COLOURS["positive"],
        )
        self.update_browser_detail_for_key(cache_key, "Ready locally")

    def promote_selected_discovered_server(self):
        server = self.selected_discovered_server()
        if not server:
            QMessageBox.warning(
                self, "No discovered server selected", "Select a discovered server first."
            )
            return

        dialog = PromoteServerDialog(self, server.name)
        if dialog.exec() != QDialog.Accepted:
            return
        name = dialog.curated_name()
        if not name:
            QMessageBox.warning(self, "Name required", "Enter a favourite server name.")
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
            "Server added",
            f"{curated.name} was added to Favourite Servers.",
        )

    def selected_discovered_server(self):
        cache_key = selected_browser_cache_key(self.browser_table)
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
            QMessageBox.warning(
                self, "No discovered server selected", "Select a discovered server first."
            )
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

    def back_to_server_browser(self):
        self.tabs.setCurrentIndex(self.server_browser_tab_index)
        self.browser_table.setFocus()

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
            "wolfapi_v1": "WolfAPI",
            "wolfapi": "WolfAPI (legacy fallback)",
            "battlemetrics": "BattleMetrics",
            "steam_web_api": "Steam Web API",
            "steam_master": "Steam Master",
            "disabled": "Disabled",
        }
        return labels.get(key, labels[DEFAULT_DISCOVERY_PROVIDER])

    def _native_steam_mode_label(self, key: str) -> str:
        return steam_mode_label(key)

    def discovery_provider_key(self) -> str:
        if not hasattr(self, "discovery_provider"):
            return str(self.settings.get("discovery_provider") or DEFAULT_DISCOVERY_PROVIDER)
        keys = {
            "WolfAPI": "wolfapi_v1",
            "WolfAPI v1 (staged)": "wolfapi_v1",
            "WolfAPI (legacy fallback)": "wolfapi",
            "BattleMetrics": "battlemetrics",
            "Steam Web API": "steam_web_api",
            "Steam Master": "steam_master",
            "Disabled": "disabled",
        }
        return keys.get(self.discovery_provider.currentText(), DEFAULT_DISCOVERY_PROVIDER)

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

    def selected_browser_preview_install(self) -> SteamInstall | None:
        """Reuse the latest health snapshot so browsing never scans Steam on the UI thread."""
        installs = list(self.detected_steam_installs)
        if not installs:
            return None
        if self.launch_engine_key() == "native":
            return select_steam_install(self.native_steam_mode_key(), installs=installs)
        return best_install_from(installs)

    def check_startup_steam_state(self):
        """Surface Steam availability once the initial window has opened."""
        install = self.selected_steam_install()
        if install and install.running:
            return
        if install:
            detail = f"{install_label(install)} was detected, but it is not currently running."
        else:
            detail = "WolfLauncher could not detect the selected Steam installation."
        QMessageBox.warning(
            self,
            "Steam is not running",
            f"{detail}\n\n"
            "Start Steam and sign in for complete Workshop mod information, sizes and "
            "download operations. You can continue browsing servers in the meantime.",
        )

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
        MainWindow._recheck_after_mod_context_change(
            self, "Launch engine changed. Rechecking selected server mods..."
        )

    def handle_native_steam_mode_changed(self, *_args):
        MainWindow._recheck_after_mod_context_change(
            self, "Steam install changed. Rechecking selected server mods..."
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
            "steam_master_endpoints": self.steam_master_endpoints.text().strip()
            if hasattr(self, "steam_master_endpoints")
            else "",
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
            save_favourites(self.favourites)
        except OSError as exc:
            QMessageBox.warning(
                self,
                "Could not save favourites",
                f"WolfLauncher could not save the favourites index.\n\n{exc}",
            )
            return False
        return True

    def refresh_statuses(self):
        self.refresh_status_rows(list(range(len(self.servers))), "Last updated: refreshing...")

    def refresh_selected_status(self):
        row = self.table.currentRow()
        if row < 0 or row >= len(self.servers):
            QMessageBox.warning(self, "No server selected", "Select a favourite server first.")
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

        selected = self.selected_discovered_server()
        selected_key = selected.cache_key if selected else ""
        scroll_value = self.browser_table.verticalScrollBar().value()
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
                hide_quality_flagged=self.browser_hide_quality_flagged.isChecked(),
                sort_by=sort_key,
                descending=self.browser_descending.isChecked(),
                limit=limit,
            ),
        )
        servers = snapshot.servers
        self.browser_servers = servers

        populate_browser_table(self.browser_table, servers)
        if selected_key:
            for row in range(self.browser_table.rowCount()):
                item = self.browser_table.item(row, 0)
                if item and item.data(Qt.UserRole) == selected_key:
                    self.browser_table.selectRow(row)
                    break
        self.browser_table.verticalScrollBar().setValue(scroll_value)
        for server in servers:
            cached = self.browser_mod_results.get(server.cache_key)
            if cached and time.monotonic() - cached[0] < (900 if cached[1].ok else 300):
                self.apply_browser_mod_preview(server.cache_key, cached[1])
        self.configure_browser_columns()
        self.browser_summary.setText(
            browser_summary_text(snapshot.cache_summary, len(servers), snapshot.match_count, limit)
        )
        self.browser_summary.setToolTip(browser_summary_tooltip(snapshot.cache_summary))
        self.update_browser_selection_context()

    def update_browser_selection_context(self):
        if not hasattr(self, "browser_promote_button"):
            return
        selected = self.selected_discovered_server()
        enabled = selected is not None
        for button_name in (
            "browser_promote_button",
            "browser_inspect_button",
            "browser_launch_button",
        ):
            button = getattr(self, button_name, None)
            if button is not None:
                button.setEnabled(enabled)
        launch_button = getattr(self, "browser_launch_button", None)
        if launch_button is not None:
            launch_button.setText(
                f"Launch {display_server_name(selected)}" if selected else "Launch selected server"
            )
        if hasattr(self, "update_browser_detail_card"):
            self.update_browser_detail_card(selected)
        if hasattr(self, "schedule_selected_discovered_server_check"):
            self.schedule_selected_discovered_server_check()

    def update_browser_detail_for_key(self, cache_key: str, mod_preview: str):
        selected = self.selected_discovered_server()
        if selected is not None and selected.cache_key == cache_key:
            self.update_browser_detail_card(selected, mod_preview=mod_preview)

    def update_browser_detail_card(
        self,
        selected: DiscoveredServer | None,
        mod_preview: str = "",
        status_override: str = "",
    ):
        if not hasattr(self, "browser_detail_card"):
            return
        if selected is None:
            self.browser_detail_card.setProperty("serverStatus", "warning")
            self.browser_detail_title.setText("Select a server to inspect its details")
            self.browser_detail_status.setText("NO SELECTION")
            self.browser_detail_status.setProperty("serverStatus", "warning")
            self.browser_detail_mod_status.hide()
            self.browser_detail_endpoint.clear()
            self.browser_detail_atmosphere.set_map_name("")
            self.browser_detail_map.setText("—")
            self.browser_detail_players.setText("—")
            self.browser_detail_ping.setText("—")
            self.browser_detail_context.setText(
                "Selection-driven truth and mod readiness will appear here."
            )
            for label in (
                self.browser_detail_truth,
                self.browser_detail_features,
                self.browser_detail_mods,
                self.browser_detail_diagnostics,
            ):
                label.clear()
        else:
            cached = self.browser_mod_results.get(selected.cache_key)
            if not mod_preview and cached:
                result = cached[1]
                mod_preview = (
                    "Unavailable"
                    if not result.ok
                    else f"{len(result.missing_mods)} missing locally"
                    if result.missing_mods
                    else "Ready locally"
                )
            detail = browser_inspector(selected, mod_preview)
            detail_edge = detail.status_kind
            if status_override.casefold() == "checking":
                detail_edge = "warning"
            elif "missing" in mod_preview.casefold() or mod_preview.casefold() == "unavailable":
                detail_edge = "offline"
            status_pill = (
                "warning" if status_override.casefold() == "checking" else detail.status_kind
            )
            self.browser_detail_card.setProperty("serverStatus", detail_edge)
            self.browser_detail_title.setText(detail.title)
            self.browser_detail_status.setText((status_override or detail.status).upper())
            self.browser_detail_status.setProperty("serverStatus", status_pill)
            mod_pill_text, mod_pill_kind = browser_mod_pill(mod_preview)
            self.browser_detail_mod_status.setText(mod_pill_text)
            self.browser_detail_mod_status.setProperty("serverStatus", mod_pill_kind)
            self.browser_detail_mod_status.setVisible(bool(mod_pill_text))
            self.browser_detail_endpoint.setText(detail.endpoint)
            self.browser_detail_atmosphere.set_map_name(detail.map_name)
            self.browser_detail_map.setText(detail.map_name)
            self.browser_detail_players.setText(detail.players)
            self.browser_detail_ping.setText(detail.ping)
            self.browser_detail_context.setText(
                f"Region  {detail.region}\nGame time  {detail.game_time}"
            )
            self.browser_detail_truth.setText(f"Truth basis\n{detail.truth}")
            self.browser_detail_features.setText(f"Features\n{detail.features}")
            self.browser_detail_mods.setText(f"Mod readiness\n{detail.mods}")
            self.browser_detail_diagnostics.setText(detail.diagnostics)
        self.browser_detail_card.style().unpolish(self.browser_detail_card)
        self.browser_detail_card.style().polish(self.browser_detail_card)
        self.browser_detail_status.style().unpolish(self.browser_detail_status)
        self.browser_detail_status.style().polish(self.browser_detail_status)
        self.browser_detail_mod_status.style().unpolish(self.browser_detail_mod_status)
        self.browser_detail_mod_status.style().polish(self.browser_detail_mod_status)

    def configure_browser_columns(self, show_details: bool | None = None):
        if not hasattr(self, "browser_table"):
            return
        if show_details is None:
            show_details = (
                self.browser_detailed_columns.isChecked()
                if hasattr(self, "browser_detailed_columns")
                else False
            )
        configure_priority_columns(
            self.browser_table,
            (0, 5, 6, 16, 7, 15, 8, 10, 11),
            show_details=show_details,
            stretch_columns=(),
        )
        self.browser_table.setColumnHidden(1, True)
        if not show_details:
            header = self.browser_table.horizontalHeader()
            # Name flexes with the live viewport and yields when readiness text
            # makes Mods wider. This avoids stale startup widths and horizontal
            # overflow after background mod previews complete.
            header.setSectionResizeMode(0, QHeaderView.Stretch)

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
        self.browser_style.setCurrentText("Any game style")
        self.browser_map.setCurrentText("Any map")
        self.browser_version.setCurrentText("Any version")
        self.browser_source.setCurrentText("Any source")
        self.browser_sort.setCurrentText("Name")
        self.browser_descending.setChecked(False)
        self.browser_hide_quality_flagged.setChecked(False)
        self.browser_limit.setCurrentText("200")
        self.refresh_server_browser()

    def _set_item(self, row: int, column: int, text: str, colour: str | None = None):
        item = QTableWidgetItem(text)
        if column in {4, 5, 6, 7, 12, 15}:
            item.setFont(monospace_font())
        if column in {10, 12}:
            item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
        display_colour = colour or self._curated_cell_colour(column, text)
        if display_colour:
            item.setForeground(QColor(display_colour))
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
        if column in {4, 5, 6, 7, 12, 15}:
            item.setFont(monospace_font())
        if column in {10, 12}:
            item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
        colour = self._curated_cell_colour(column, value)
        if colour:
            item.setForeground(QColor(colour))
        if cached and column in {3, 5, 8, 9, 10, 11, 12, 13, 14, 15}:
            item.setToolTip("Last known status; refresh is checking for current data.")
        self.table.setItem(row, column, item)

    def _curated_cell_colour(self, column: int, text: str) -> str:
        if column == 0 and text == "★":
            return COLOURS["accent"]
        if column == 8:
            if text == "ONLINE":
                return STATUS_COLOURS["positive"]
            if text == "OFFLINE":
                return STATUS_COLOURS["negative"]
            return STATUS_COLOURS["warning"]
        if column == 12 and text.endswith("ms"):
            try:
                ping = int(text[:-2])
            except ValueError:
                return COLOURS["text_muted"]
            severity = ping_severity(ping)
            if severity == "warning":
                return STATUS_COLOURS["warning"]
            if severity == "critical":
                return STATUS_COLOURS["negative"]
            return COLOURS["text_muted"]
        if column == 15 and text:
            return COLOURS["accent"]
        return ""

    def update_curated_status_summary(self):
        if not hasattr(self, "curated_online_summary"):
            return
        statuses = [
            self.table.item(row, 8).text()
            for row in range(self.table.rowCount())
            if self.table.item(row, 8)
        ]
        online = statuses.count("ONLINE")
        offline = statuses.count("OFFLINE")
        self.curated_online_summary.setText(f"{online} online")
        self.curated_offline_summary.setText(f"{offline} offline")

    def refresh_curated_server_cards(self):
        if not hasattr(self, "server_cards"):
            return
        selected_row = self.table.currentRow()
        self.server_cards.blockSignals(True)
        self.server_cards.clear()
        for row in range(self.table.rowCount()):
            values = [self._server_cell(row, column) for column in range(16)]
            card = CuratedServerCard(row, values, self.server_cards)
            card.selected.connect(self._select_curated_card)
            card.activated.connect(self._launch_curated_card)
            card.favourite_requested.connect(self.toggle_favourite)
            card.context_requested.connect(self.show_server_card_context_menu)
            item = QListWidgetItem()
            item.setData(Qt.UserRole, row)
            item.setSizeHint(QSize(0, max(64, card.sizeHint().height() + 6)))
            self.server_cards.addItem(item)
            self.server_cards.setItemWidget(item, card)
        if 0 <= selected_row < self.server_cards.count():
            self.server_cards.setCurrentRow(selected_row)
        self.server_cards.blockSignals(False)
        self._sync_curated_card_selection()

    def _select_curated_table_row(self, row: int):
        if 0 <= row < self.table.rowCount() and self.table.currentRow() != row:
            self.table.selectRow(row)
        self._sync_curated_card_selection()

    def _select_curated_card(self, row: int):
        if 0 <= row < self.server_cards.count():
            self.server_cards.setCurrentRow(row)
        self._select_curated_table_row(row)

    def _launch_curated_card(self, row: int):
        self._select_curated_card(row)
        self.launch_selected()

    def _sync_curated_card_selection(self):
        if not hasattr(self, "server_cards"):
            return
        selected_row = self.table.currentRow()
        for row in range(self.server_cards.count()):
            card = self.server_cards.itemWidget(self.server_cards.item(row))
            if isinstance(card, CuratedServerCard):
                card.set_selected(row == selected_row)

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
            title="Add a favourite server",
        )
        if dialog.exec() != QDialog.Accepted:
            return

        server = dialog.curated_server()
        if not server.name or not server.host:
            QMessageBox.warning(self, "Server details required", "Enter a server name and host.")
            return

        try:
            add_curated_server(self.config_path, server)
        except (OSError, ValueError) as exc:
            QMessageBox.warning(self, "Could not add server", str(exc))
            return

        if server.favourite:
            self.favourites.add(server_key(server))
            self._save_favourites_index()
        self.add_curated_server_row(server)
        row = len(self.servers) - 1
        self.table.selectRow(row)
        self.update_launch_button_text()
        self.statusBar().showMessage(f"Added favourite server: {server.name}", 7000)
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
            if column in {4, 5, 6, 7, 12, 15}:
                item.setFont(monospace_font())
            if column in {10, 12}:
                item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            colour = self._curated_cell_colour(column, value)
            if colour:
                item.setForeground(QColor(colour))
            self.table.setItem(row, column, item)
        self.table.resizeColumnsToContents()
        self.update_curated_status_summary()
        self.refresh_curated_server_cards()

    def remove_curated_server_row(self, row: int, confirm: bool = True):
        if row < 0 or row >= len(self.servers):
            return
        server = self.servers[row]
        if confirm:
            answer = QMessageBox.question(
                self,
                "Remove favourite server",
                f"Remove {server.name} from Favourite Servers?",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No,
            )
            if answer != QMessageBox.Yes:
                return

        try:
            removed = remove_curated_server(self.config_path, server)
        except (OSError, ValueError) as exc:
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
        self._save_favourites_index()
        del self.servers[row]
        self.table.removeRow(row)
        self._reindex_server_rows()
        self.update_curated_status_summary()
        self.refresh_curated_server_cards()
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
        except (OSError, ValueError) as exc:
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
        self._save_favourites_index()
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
            self.statusBar().showMessage(
                "Favourite server already uses the live connect port.", 7000
            )
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
        except (OSError, ValueError) as exc:
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
        self.refresh_curated_server_cards()
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
        self.refresh_curated_server_cards()

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
            flags_text = display_server_flags(status.password, status.modded)
            ping_text = f"{status.ping}ms" if status.ping else ""
            self._set_item(row, 3, status.server_name or self.servers[row].name)
            self._set_item(row, 8, "ONLINE", STATUS_COLOURS["positive"])
            self._set_item(row, 9, display_map_name(status.map_name))
            self._set_item(row, 10, status.players)
            self._set_item(row, 11, status.time)
            self._set_item(row, 12, ping_text)
            self._set_item(row, 13, status.version)
            self._set_item(row, 14, flags_text)
            self._set_item(row, 15, status.connect)
        else:
            self._set_item(row, 3, self.servers[row].name)
            self._set_item(row, 8, "OFFLINE", STATUS_COLOURS["negative"])
            self._set_item(row, 9, status.error)
            for column in range(10, 16):
                self._set_item(row, column, "")
        self.update_curated_status_summary()
        self.refresh_curated_server_cards()

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
        becoming_favourite = not server.favourite
        if not becoming_favourite:
            reply = QMessageBox.question(
                self,
                "Remove from Favourite Servers?",
                f"Remove {server.name} from Favourite Servers?\n\n"
                "Choose No to keep the server in the list with its star turned off.",
                QMessageBox.Yes | QMessageBox.No | QMessageBox.Cancel,
                QMessageBox.No,
            )
            if reply == QMessageBox.Cancel:
                return
            if reply == QMessageBox.Yes:
                self.remove_curated_server_row(row, confirm=False)
                return

        updated = replace(server, favourite=becoming_favourite)
        try:
            changed = update_curated_server(self.config_path, server, updated)
        except (OSError, ValueError) as exc:
            QMessageBox.warning(self, "Could not update favourite", str(exc))
            return
        if not changed:
            QMessageBox.warning(
                self,
                "Could not update favourite",
                "This server was not found in servers.yaml.",
            )
            return

        self.servers[row] = updated
        key = server_key(updated)
        if updated.favourite:
            self.favourites.add(key)
        else:
            self.favourites.discard(key)
        favourite_item = QTableWidgetItem("★" if updated.favourite else "☆")
        favourite_item.setData(Qt.UserRole, row)
        if updated.favourite:
            favourite_item.setForeground(QColor(COLOURS["accent"]))
        self.table.setItem(row, 0, favourite_item)
        MainWindow._save_favourites_index(self)
        self.refresh_curated_server_cards()

    def handle_refresh_finished(self):
        self._set_status_refresh_enabled(True)
        self.table.resizeColumnsToContents()
        self.last_refresh_label.setText(f"Last updated: {datetime.now().strftime('%H:%M:%S')}")
        self.update_launch_button_text()

    def handle_refresh_seconds_changed(self):
        self.apply_refresh_timer()
        self.save_user_settings(silent=True)

    def update_launch_button_text(self):
        server = self.active_server_context()
        text = f"Launch {server.name}" if server else "Launch selected server"
        if hasattr(self, "launch_button"):
            self.launch_button.setText(text)
        if hasattr(self, "mods_launch_button"):
            self.mods_launch_button.setText(text)
            self.mods_launch_button.setEnabled(server is not None)
        if hasattr(self, "mods_back_to_browser_button"):
            self.mods_back_to_browser_button.setVisible(self.active_discovered_server is not None)

    def check_initial_server_mods(self):
        if self.servers and self.table.currentRow() < 0:
            last_row = self.saved_selected_row()
            row = last_row if 0 <= last_row < len(self.servers) else 0
            self.table.selectRow(row)
        self.check_selected_server_mods(silent=True)

    def handle_server_selection_changed(self):
        self.active_discovered_server = None
        self.active_discovered_cache_key = ""
        self._sync_curated_card_selection()
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
        self.mod_server_title.setText(
            f"Required mods for {server.name}  ·  {server.connect_target}"
        )
        self.mod_readiness.setText("Checking required-mod readiness…")
        self.subscribe_missing_button.setEnabled(False)
        install = (
            self.selected_steam_install()
            if self.launch_engine_key() == "native"
            else best_install()
        )
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
        workshop_install = install if install and install.running else None
        self.mod_worker = ModWorker(
            server, workshop_dir, steam_context, workshop_install=workshop_install
        )
        self.mod_worker.mods_ready.connect(self.update_mods_table)
        self.mod_worker.finished.connect(self.handle_mod_worker_finished)
        self.mod_worker.start()

    def update_mods_table(self, result: ModCheckResult):
        self.active_mod_server_key = ""
        current_server = self.active_server_context()
        install = (
            self.selected_steam_install()
            if self.launch_engine_key() == "native"
            else best_install()
        )
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
        server_cache.upsert_server(self.server_cache, replace(discovered, required_mod_count=count))
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
            self.mod_readiness.setText(
                f"Steam may still be downloading {count} required "
                f"Workshop {noun} from an earlier session. Check Steam Downloads; WolfLauncher "
                "will recheck when you use Recheck mods."
            )

    def display_mods_result(self, result: ModCheckResult):
        self.mods_table.setSortingEnabled(False)
        self.mod_server_title.setText(mod_server_heading(result))
        self.mod_readiness.setText(mod_readiness_text(result))
        self.mod_summary.setText(mod_summary_text(result))
        self.mod_summary.setToolTip("")
        missing_count = len(result.missing_mods) if result.ok else 0
        self.subscribe_missing_button.setEnabled(missing_count > 0)
        self.subscribe_missing_button.setText(
            f"Resolve {missing_count} required mod{'s' if missing_count != 1 else ''}"
            if missing_count
            else "Install/update required mods"
        )
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
                if column in {2, 3}:
                    item.setFont(monospace_font())
                if column in {0, 2, 3}:
                    item.setTextAlignment(Qt.AlignCenter)
                if column == 0:
                    item.setForeground(QColor(row_data.status_colour))
                self.mods_table.setItem(row, column, item)
        self.mods_table.resizeColumnsToContents()
        self.mods_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.mods_table.setSortingEnabled(True)
        self.mods_table.sortItems(0, Qt.DescendingOrder)
        self.apply_mod_filter()
        if self.mods_table.rowCount() > 0:
            self.mods_table.selectRow(0)

    def selected_required_mod(self):
        result = self.last_mod_result
        if not result or not result.ok:
            return None
        row = self.mods_table.currentRow()
        workshop_id = self._mods_cell(row, 2) if row >= 0 else ""
        return next(
            (mod for mod in result.required_mods if mod.workshop_id == workshop_id),
            None,
        )

    def update_mod_detail_card(self):
        if not hasattr(self, "mod_detail_card"):
            return
        mod = self.selected_required_mod()
        if mod is None:
            self._set_mod_detail_status("warning")
            self.mod_detail_title.setText("Select a mod to see its Workshop details")
            self.mod_detail_description.setText(
                "Descriptions and preview images are supplied by the mod's Workshop page."
            )
            self.mod_detail_metadata.setText("")
            self.mod_detail_open_button.setEnabled(False)
            self.mod_detail_thumbnail.setPixmap(QPixmap())
            self.mod_detail_thumbnail.setText("No preview")
            self.mod_thumbnail_url = ""
            return
        self._set_mod_detail_status(mod_detail_status(mod))
        self.mod_detail_title.setText(mod.name or mod.installed_name or "Unknown mod")
        self.mod_detail_description.setText(mod_description_preview(mod, limit=900))
        self.mod_detail_description.setToolTip("")
        status = mod_row(mod).values[0].lstrip("✓✗!↻… ")
        self.mod_detail_metadata.setText(
            f"Workshop {mod.workshop_id}  ·  {mod_file_size(mod)}  ·  {status}"
        )
        self.mod_detail_open_button.setEnabled(bool(mod.workshop_url))
        self.load_mod_thumbnail(mod.workshop_preview_url)

    def _set_mod_detail_status(self, status: str):
        self.mod_detail_card.setProperty("modStatus", status)
        self.mod_detail_card.style().unpolish(self.mod_detail_card)
        self.mod_detail_card.style().polish(self.mod_detail_card)

    def load_mod_thumbnail(self, url: str):
        self.mod_thumbnail_url = url
        self.mod_detail_thumbnail.setPixmap(QPixmap())
        if not url:
            self.mod_detail_thumbnail.setText("No preview")
            return
        self.mod_detail_thumbnail.setText("Loading…")
        self.mod_thumbnail_manager.get(QNetworkRequest(QUrl(url)))

    def resize_mod_detail_card(self):
        if not hasattr(self, "mod_detail_card"):
            return
        panel_width = self.mod_detail_card.width()
        if panel_width < 100:
            panel_width = round(self.width() * 0.34)
        media_scale = mod_inspector_scale(self.height())
        type_scale = mod_inspector_type_scale(self.height())
        thumbnail_width = max(220, min(round(360 * media_scale), panel_width - 28))
        thumbnail_height = round(thumbnail_width * 9 / 16)
        self.mod_detail_thumbnail.setFixedSize(thumbnail_width, thumbnail_height)
        base_size = self.mod_detail_base_point_size
        for widget, multiplier in (
            (self.mod_detail_title, 1.12),
            (self.mod_detail_description, 1.0),
            (self.mod_detail_metadata, 0.95),
            (self.mod_detail_open_button, 1.0),
        ):
            font = widget.font()
            font.setPointSizeF(base_size * type_scale * multiplier)
            widget.setFont(font)

    def finish_mod_thumbnail_load(self, reply: QNetworkReply):
        try:
            if reply.url().toString() != self.mod_thumbnail_url:
                return
            pixmap = QPixmap()
            if reply.error() == QNetworkReply.NoError:
                pixmap.loadFromData(bytes(reply.readAll()))
            if pixmap.isNull():
                self.mod_detail_thumbnail.setText("Preview unavailable")
                return
            self.mod_detail_thumbnail.setText("")
            self.mod_detail_thumbnail.setPixmap(
                pixmap.scaled(
                    self.mod_detail_thumbnail.size(),
                    Qt.KeepAspectRatio,
                    Qt.SmoothTransformation,
                )
            )
        finally:
            reply.deleteLater()

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
        mod = self.selected_required_mod()
        url = mod.workshop_url if mod else ""
        if not url:
            workshop_id = self._mods_cell(row, 2)
            if workshop_id:
                url = f"https://steamcommunity.com/sharedfiles/filedetails/?id={workshop_id}"
        if not url:
            QMessageBox.warning(
                self, "No Workshop URL", "This mod row does not have a Workshop URL."
            )
            return
        QDesktopServices.openUrl(QUrl(url))

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
        copy_id_action.triggered.connect(
            lambda: self.copy_to_clipboard(self._mods_cell(row, 2), "Workshop ID")
        )
        copy_name_action.triggered.connect(
            lambda: self.copy_to_clipboard(self._mods_cell(row, 1), "Mod name")
        )
        copy_url_action.triggered.connect(
            lambda: self.copy_to_clipboard(
                (self.selected_required_mod().workshop_url if self.selected_required_mod() else ""),
                "Workshop URL",
            )
        )
        check_update_action.triggered.connect(lambda: self.check_update_mod_row(row))
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
        promote_action = QAction("Add to Favourite Servers", self)
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
            add_action = QAction("Add a favourite server", self)
            add_action.triggered.connect(self.add_curated_server)
            menu.addAction(add_action)
            menu.exec(self.table.viewport().mapToGlobal(pos))
            return
        self.table.selectRow(row)
        menu = self._server_context_menu(row)
        menu.exec(self.table.viewport().mapToGlobal(pos))

    def show_server_card_context_menu(self, row: int, global_pos: QPoint):
        if row < 0 or row >= len(self.servers):
            return
        self._select_curated_card(row)
        self._server_context_menu(row).exec(global_pos)

    def _server_context_menu(self, row: int) -> QMenu:
        menu = QMenu(self)
        add_action = QAction("Add a favourite server", self)
        refresh_selected_action = QAction("Refresh selected status", self)
        apply_live_port_action = QAction("Apply live connect port", self)
        copy_connect_action = QAction("Copy connect address", self)
        copy_details_action = QAction("Copy server details", self)
        edit_action = QAction("Edit favourite server", self)
        toggle_fav_action = QAction("Toggle favourite", self)
        remove_action = QAction("Remove from favourites", self)
        add_action.triggered.connect(self.add_curated_server)
        refresh_selected_action.triggered.connect(self.refresh_selected_status)
        apply_live_port_action.triggered.connect(
            lambda: self.apply_live_connect_port_to_curated_server(row)
        )
        copy_connect_action.triggered.connect(
            lambda: self.copy_to_clipboard(self._server_cell(row, 15), "Connect address")
        )
        copy_details_action.triggered.connect(
            lambda: self.copy_to_clipboard(self.server_details_text(row), "Server details")
        )
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
        return menu

    def _server_cell(self, row: int, column: int) -> str:
        item = self.table.item(row, column)
        return item.text() if item else ""

    def _live_connect_port_for_row(self, row: int) -> int | None:
        return parse_connect_port(self._server_cell(row, 15))

    def server_details_text(self, row: int) -> str:
        return "\n".join(
            [
                self._server_cell(row, 3) or self._server_cell(row, 2),
                self._server_cell(row, 15),
                f"Map: {self._server_cell(row, 9)}",
                f"Players: {self._server_cell(row, 10)}",
                f"Version: {self._server_cell(row, 13)}",
            ]
        ).strip()

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
            QMessageBox.information(
                self, "No missing mods", "All required mods appear to be installed."
            )
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
            self.selected_steam_install()
            if self.launch_engine_key() == "native"
            else best_install(),
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

        install = (
            self.selected_steam_install()
            if self.launch_engine_key() == "native"
            else best_install()
        )
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
        unavailable = workshop_automation_unavailable_reason(install)
        if unavailable:
            QMessageBox.information(self, "Use Steam Workshop pages", unavailable)
            return
        names = "\n".join(
            f"- {mod.name or mod.workshop_id} — {mod_download_size(mod)}" for mod in missing[:12]
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
            f"{combined_download_estimate(missing)}\n\nContinue?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if reply != QMessageBox.Yes:
            return

        self.start_workshop_resolution(missing, result, install)

    def check_update_mod_row(self, row: int):
        result = self._selected_mod_result(successful=True)
        workshop_id = self._mods_cell(row, 2)
        mod = (
            next(
                (item for item in result.required_mods if item.workshop_id == workshop_id),
                None,
            )
            if result
            else None
        )
        if mod is None:
            QMessageBox.warning(
                self,
                "Mod check unavailable",
                "Recheck the selected server before updating this mod.",
            )
            return
        if mod.ready:
            QMessageBox.information(
                self,
                "Mod already ready",
                f"{mod.name or mod.workshop_id} is already reported ready.",
            )
            return
        if self.workshop_subscription_worker and self.workshop_subscription_worker.isRunning():
            self.subscribe_missing_workshop_mods()
            return
        install = (
            self.selected_steam_install()
            if self.launch_engine_key() == "native"
            else best_install()
        )
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
        self.workshop_subscription_dialog.setWindowTitle("Steam Workshop")
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
        self.workshop_subscription_worker.finished.connect(self.clear_workshop_subscription_worker)
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
            item_name = self.workshop_subscription_names.get(active.workshop_id, active.workshop_id)
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
            launch_button = box.addButton("Launch server", QMessageBox.ButtonRole.AcceptRole)
            set_ui_role(launch_button, "primary")
            box.addButton("Close", QMessageBox.ButtonRole.RejectRole)
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
        self.statusBar().showMessage("Steam Workshop helper finished; launch is available.", 5000)
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

        install = (
            self.selected_steam_install()
            if self.launch_engine_key() == "native"
            else best_install()
        )
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
        install = (
            self.selected_steam_install()
            if self.launch_engine_key() == "native"
            else best_install()
        )
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
            QMessageBox.warning(self, "No server selected", "Select a favourite server first.")
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
        self.detected_steam_installs = install_rows
        provider = self.discovery_provider_key()
        provider_detail = self.discovery_provider.currentText()
        if provider == "steam_web_api":
            provider_status = "OK" if self.steam_web_api_key.text().strip() else "MISSING"
            provider_detail = (
                "Steam Web API key saved"
                if provider_status == "OK"
                else "Steam Web API key required"
            )
        elif provider == "steam_master":
            try:
                addresses = self.steam_master_addresses()
            except (OSError, ValueError) as exc:
                provider_status = "WARN"
                provider_detail = str(exc)
            else:
                provider_status = "OK"
                provider_detail = (
                    ", ".join(address.address for address in addresses)
                    if addresses
                    else "Default Steam masters"
                )
        elif provider == "wolfapi_v1":
            provider_status = "OK"
            provider_detail = "WolfAPI server discovery"
        elif provider == "wolfapi":
            provider_status = "OK"
            provider_detail = "WolfAPI legacy hosted cache fallback"
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
        self.update_settings_health_groups(rows)

    def _health_colour(self, status: str) -> str:
        if status == "OK":
            return STATUS_COLOURS["positive"]
        if status == "WARN":
            return STATUS_COLOURS["warning"]
        return STATUS_COLOURS["negative"]

    def _set_health_item(self, row: int, column: int, text: str, colour: str | None = None):
        item = QTableWidgetItem(text)
        if colour:
            item.setForeground(QColor(colour))
        self.health_table.setItem(row, column, item)

    def launch_selected(self):
        workshop_block = self.workshop_launch_block_reason()
        if workshop_block:
            QMessageBox.information(self, "Steam Workshop in progress", workshop_block)
            return
        server = self.active_server_context()
        if not server:
            QMessageBox.warning(self, "No server selected", "Select a server first.")
            return

        self.save_user_settings(silent=True)
        self.start_connect_preflight(server)

    def start_connect_preflight(self, server: Server):
        """Run the user-facing Steam, Workshop, launcher and process checklist."""
        self.preflight_server = server
        self.preflight_dialog = PreflightLaunchDialog(self, server.name)
        self.preflight_dialog.finished.connect(self.cancel_connect_preflight)
        self.preflight_dialog.launch_report_ready.connect(self.persist_launch_report)
        self.preflight_dialog.show()
        self.launch_button.setEnabled(False)
        self.ensure_preflight_steam()

    def cancel_connect_preflight(self, *_args):
        worker = self.preflight_workshop_worker
        if worker and worker.isRunning():
            worker.cancel()
        self.launch_button.setEnabled(True)

    def fail_connect_preflight(self, key: str, detail: str):
        if self.preflight_dialog:
            self.preflight_dialog.set_failed(key, detail)
        self.launch_button.setEnabled(True)

    def ensure_preflight_steam(self):
        dialog = self.preflight_dialog
        if not dialog or not dialog.isVisible():
            return
        install = (
            self.selected_steam_install()
            if self.launch_engine_key() == "native"
            else best_install()
        )
        if not install or not install.dayz_dir:
            self.fail_connect_preflight(
                "steam",
                "The selected Steam/DayZ installation was not detected. Check Settings health.",
            )
            return
        if not install.workshop_dir:
            self.fail_connect_preflight(
                "mods", "The DayZ Workshop folder was not detected. Check Settings health."
            )
            return
        if install.running:
            dialog.set_complete(
                "steam", f"{install_label(install)} is running. Checking required mods…"
            )
            self.start_preflight_mod_check(install)
            return
        command = build_steam_start_command(install)
        if not command:
            self.fail_connect_preflight(
                "steam", "The selected Steam client has no runnable command."
            )
            return
        dialog.set_working("steam", f"Starting {install_label(install)}…")
        started, _pid = QProcess.startDetached(command[0], command[1:])
        if not started:
            self.fail_connect_preflight("steam", "Steam could not be started.")
            return
        self.preflight_steam_attempts = 0
        QTimer.singleShot(1000, self.poll_preflight_steam)

    def poll_preflight_steam(self):
        dialog = self.preflight_dialog
        if not dialog or not dialog.isVisible():
            return
        self.preflight_steam_attempts += 1
        install = (
            self.selected_steam_install()
            if self.launch_engine_key() == "native"
            else best_install()
        )
        if install and install.running:
            dialog.set_complete(
                "steam", f"{install_label(install)} is running. Checking required mods…"
            )
            self.start_preflight_mod_check(install)
            return
        if self.preflight_steam_attempts >= 60:
            self.fail_connect_preflight(
                "steam",
                "Steam was started, but did not become ready within 60 seconds. Sign in to Steam and try again.",
            )
            return
        QTimer.singleShot(1000, self.poll_preflight_steam)

    def start_preflight_mod_check(self, install: SteamInstall):
        dialog = self.preflight_dialog
        server = self.preflight_server
        if not dialog or not server:
            return
        dialog.set_working("mods", "Checking the server manifest and local Workshop state…")
        self.preflight_mod_worker = ModWorker(
            server,
            install.workshop_dir,
            self.mod_check_steam_context(install),
            workshop_install=install,
        )
        self.preflight_mod_worker.mods_ready.connect(self.finish_preflight_mod_check)
        self.preflight_mod_worker.start()

    def finish_preflight_mod_check(self, result: ModCheckResult):
        self.preflight_mod_worker = None
        dialog = self.preflight_dialog
        server = self.preflight_server
        if not dialog or not dialog.isVisible() or not server:
            return
        if server_key(result.server) != server_key(server) or not result.ok:
            self.fail_connect_preflight("mods", result.error or "The required-mod check failed.")
            return
        self.last_mod_result = result
        self.display_mods_result(result)
        if result.missing_mods:
            install = (
                self.selected_steam_install()
                if self.launch_engine_key() == "native"
                else best_install()
            )
            if not install or not install.running:
                self.fail_connect_preflight(
                    "mods", "Steam stopped before required mods could be installed."
                )
                return
            unavailable = workshop_automation_unavailable_reason(install)
            if unavailable:
                self.fail_connect_preflight("mods", unavailable)
                return
            dialog.set_working(
                "mods",
                f"Installing or updating {len(result.missing_mods)} required Workshop item(s)…",
            )
            self.preflight_workshop_worker = WorkshopSubscriptionWorker(
                [mod.workshop_id for mod in result.missing_mods], install
            )
            self.preflight_workshop_worker.progress_ready.connect(
                self.update_preflight_workshop_progress
            )
            self.preflight_workshop_worker.subscription_ready.connect(
                self.finish_preflight_workshop
            )
            self.preflight_workshop_worker.start()
            return
        dialog.set_complete("mods", f"All {len(result.required_mods)} required mod(s) are ready.")
        self.finish_connect_preflight()

    def update_preflight_workshop_progress(self, snapshots):
        dialog = self.preflight_dialog
        if not dialog or not snapshots:
            return
        installed = sum(1 for item in snapshots if item.installed)
        active = current_workshop_item(snapshots)
        suffix = (
            f"; current item {active.percent}%" if active and active.percent is not None else ""
        )
        dialog.set_working(
            "mods", f"Steam has prepared {installed} of {len(snapshots)} required item(s){suffix}."
        )

    def finish_preflight_workshop(self, result):
        self.preflight_workshop_worker = None
        if not result.ok:
            self.fail_connect_preflight(
                "mods", result.error or "Steam did not finish every required Workshop item."
            )
            return
        install = (
            self.selected_steam_install()
            if self.launch_engine_key() == "native"
            else best_install()
        )
        if not install:
            self.fail_connect_preflight(
                "mods", "The selected Steam installation is no longer available."
            )
            return
        self.start_preflight_mod_check(install)

    def finish_connect_preflight(self):
        dialog = self.preflight_dialog
        server = self.preflight_server
        if not dialog or not server:
            return
        dialog.set_working("launcher", "Building the Steam launch command…")
        try:
            command = self.build_selected_launch_command(server)
        except (NativeLaunchError, LaunchError) as exc:
            self.fail_connect_preflight("launcher", str(exc))
            return
        dialog.start_launch(command)

    def finish_prelaunch_workshop_check(self, server, result, state_result):
        current = self.active_server_context()
        if not current or server_key(current) != server_key(server):
            QMessageBox.warning(
                self,
                "Server selection changed",
                "Launch was cancelled because the active server changed.",
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

        handoff_label = (
            "native launch command" if self.launch_engine_key() == "native" else "external launcher"
        )
        dialog = LaunchDialog(self, command, f"Launching {server.name}", handoff_label)
        dialog.exec()
        try:
            save_last_launch_report(dialog.copyable_output_text())
        except OSError as exc:
            QMessageBox.warning(
                self,
                "Could not save launch report",
                f"The launch completed, but WolfLauncher could not save its support report.\n\n{exc}",
            )

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
        install = (
            self.selected_steam_install()
            if self.launch_engine_key() == "native"
            else best_install()
        )
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
                    install_button = box.addButton(
                        "Install/update mods", QMessageBox.ButtonRole.ActionRole
                    )
                    cancel_button = box.addButton("Cancel", QMessageBox.ButtonRole.RejectRole)
                    box.setDefaultButton(cancel_button)
                    box.exec()
                    clicked = box.clickedButton()
                    if clicked == open_button:
                        self.open_missing_workshop_pages()
                    elif clicked == install_button:
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
                install_button = box.addButton(
                    "Install/update mods", QMessageBox.ButtonRole.ActionRole
                )
                launch_button = box.addButton(
                    "Launch anyway", QMessageBox.ButtonRole.DestructiveRole
                )
                set_ui_role(launch_button, "destructive")
                cancel_button = box.addButton("Cancel", QMessageBox.ButtonRole.RejectRole)
                box.setDefaultButton(cancel_button)
                box.exec()
                clicked = box.clickedButton()
                if clicked == open_button:
                    self.open_missing_workshop_pages()
                    return False
                if clicked == install_button:
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
        if not self._shutdown_started:
            self._shutdown_started = True
            self.save_user_settings(silent=True)
            self._shutdown_deadline = time.monotonic() + 15
            begin_runtime_shutdown(self)
        if not runtime_shutdown_complete(self):
            event.ignore()
            if self._shutdown_dialog is None:
                self._shutdown_dialog = QProgressDialog(
                    "Finishing background checks before closing safely…",
                    "",
                    0,
                    0,
                    self,
                )
                self._shutdown_dialog.setCancelButton(None)
                self._shutdown_dialog.setWindowTitle("Closing WolfLauncher")
                self._shutdown_dialog.setWindowModality(Qt.WindowModal)
                self._shutdown_dialog.setMinimumDuration(0)
                self._shutdown_dialog.setAutoClose(False)
                self._shutdown_dialog.setMinimumWidth(420)
            self._shutdown_dialog.show()
            self._shutdown_dialog.raise_()
            self._shutdown_dialog.activateWindow()
            QTimer.singleShot(100, self._poll_shutdown)
            return
        if self._shutdown_dialog is not None:
            self._shutdown_dialog.close()
            self._shutdown_dialog = None
        self.server_cache.close()
        super().closeEvent(event)

    def _poll_shutdown(self):
        if runtime_shutdown_complete(self):
            self.close()
            return
        if self._shutdown_deadline is not None and time.monotonic() >= self._shutdown_deadline:
            kill_runtime_process(self)
            if self._shutdown_dialog is not None:
                self._shutdown_dialog.setLabelText(
                    "A background check is taking longer than expected. "
                    "WolfLauncher will close as soon as it stops safely…"
                )
        QTimer.singleShot(100, self._poll_shutdown)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.configure_browser_columns()
        self.resize_mod_detail_card()

    def showEvent(self, event):
        super().showEvent(event)
        # Window managers can apply maximized geometry after construction.
        QTimer.singleShot(0, self.configure_browser_columns)


def configure_packaged_smoke_test(app, window, environ=None) -> bool:
    environment = os.environ if environ is None else environ
    if environment.get("WOLFLAUNCHER_SMOKE_TEST") != "1":
        return False
    if (
        environment.get("WOLFLAUNCHER_SMOKE_REQUIRE_KEYRING") == "1"
        and not window.secret_store.available()
    ):
        QTimer.singleShot(0, lambda: app.exit(125))
        return True
    for delay in (1000, 5000, 10000):
        QTimer.singleShot(delay, window.close)
    QTimer.singleShot(30000, lambda: app.exit(124))
    return True


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("WolfLauncher")
    app.setApplicationVersion(__version__)
    app.setOrganizationName("WolfLauncher")
    apply_application_theme(app)
    window = MainWindow()
    window.show()
    configure_packaged_smoke_test(app, window)
    try:
        exit_code = app.exec()
    except KeyboardInterrupt:
        window.close()
        exit_code = 130
    sys.exit(exit_code)
