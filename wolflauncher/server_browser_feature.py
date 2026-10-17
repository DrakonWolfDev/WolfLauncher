import sqlite3
import time
from pathlib import Path

from PySide6.QtCore import QPoint, Qt, QTimer
from PySide6.QtGui import QAction, QColor
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QFileDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMenu,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QSplitter,
    QTableWidget,
    QVBoxLayout,
    QWidget,
)

from . import server_cache
from .browser_filter_options import combo_filter_value, set_combo_filter_options
from .config import (
    add_curated_server,
)
from .curated_dialogs import PromoteServerDialog
from .discovery_refresh import (
    auto_refresh_due,
    auto_refresh_timestamp,
)
from .models import DiscoveredServer, Server
from .mods import (
    ModCheckResult,
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
    BROWSER_FAVOURITE_COLUMN,
    BROWSER_NAME_COLUMN,
    BROWSER_PASSWORD_COLUMN,
    populate_browser_table,
    selected_browser_cache_key,
    set_browser_favourite_marker,
    update_browser_mod_cell,
    update_browser_table_row,
)
from .server_discovery import parse_master_address
from .server_enrichment import (
    local_enrichment_due,
)
from .server_identity import saved_server_fields
from .server_map_atmosphere import ServerMapAtmosphereFrame
from .settings import (
    DEFAULT_DISCOVERY_PROVIDER,
    server_key,
)
from .theme import (
    STATUS_COLOURS,
    configure_data_table,
    configure_priority_columns,
    set_monospace,
    set_ui_role,
    theme_icon,
)
from .ui_sections import set_disclosure_state
from .workers import (
    BattleMetricsDiscoveryWorker,
    ModWorker,
    ServerEnrichmentWorker,
    SteamDiscoveryWorker,
    SteamWebApiDiscoveryWorker,
    WolfApiCacheMergeWorker,
    WolfApiDiscoveryWorker,
    WolfApiMapCatalogWorker,
    WolfApiMapWorker,
    WolfApiSearchWorker,
)

MAX_SELECTED_BROWSER_RUNNERS = 3
MAX_SELECTED_STATUS_RUNNERS = 1
MAX_RESULTS_FRESHNESS_BATCH = 6
INITIAL_RESULTS_FRESHNESS_BATCHES = 4
MIN_BROWSER_SEARCH_LENGTH = 3


def persist_enriched_server(connection, old_cache_key: str, server: DiscoveredServer) -> bool:
    """Persist a live correction unless it conflicts with another stable server."""
    try:
        server_cache.replace_server_key(connection, old_cache_key, server)
    except ValueError:
        connection.rollback()
        return False
    except sqlite3.OperationalError as exc:
        # Provider cache merges use a separate SQLite connection and can briefly
        # own the single writer slot.  A live enrichment result is disposable;
        # do not turn expected write contention into a modal application error,
        # and leave this connection ready for the next result.
        # Error-code attributes/constants were added in Python 3.11. SQLite's
        # stable primary codes are BUSY=5 and LOCKED=6; extended codes retain
        # their primary code in the low byte. Python 3.10 needs the text fallback.
        code = getattr(exc, "sqlite_errorcode", None)
        locked = code is not None and (code & 0xFF) in {5, 6}
        if not locked and str(exc).lower() not in {
            "database is locked",
            "database table is locked",
            "database schema is locked",
        }:
            raise
        connection.rollback()
        return False
    except sqlite3.ProgrammingError:
        return False
    return True


class ServerBrowserMixin:
    def browser_product_key(self) -> str:
        selector = getattr(self, "browser_edition", None)
        return str(selector.currentData() or "stable") if selector is not None else "stable"

    def browser_product(self):
        from .dayz_product import product_from_key

        return product_from_key(ServerBrowserMixin.browser_product_key(self))

    def _browser_callback(self, callback):
        generation = getattr(self, "browser_generation", 0)
        scoped_query = getattr(callback, "__name__", "") in {
            "handle_remote_wolfapi_search",
            "handle_remote_wolfapi_map",
        }
        signature = ServerBrowserMixin._browser_filter_signature(self) if scoped_query else None
        return lambda *args: (
            callback(*args)
            if (
                generation == getattr(self, "browser_generation", 0)
                and not getattr(self, "_shutting_down", False)
                and (
                    not scoped_query
                    or signature == ServerBrowserMixin._browser_filter_signature(self)
                )
            )
            else None
        )

    def _browser_filter_signature(self):
        return (
            self.browser_search.text(),
            self.browser_map.currentText(),
            self.browser_version.currentText(),
            self.browser_hide_quality_flagged.isChecked(),
        )

    def change_browser_edition(self, *_args):
        self.browser_generation = getattr(self, "browser_generation", 0) + 1
        if hasattr(self, "server_launch"):
            self.server_launch.invalidate()
        self.active_discovered_server = None
        self.active_discovered_cache_key = ""
        self.browser_table.clearSelection()
        self.pending_wolfapi_search = ""
        self.pending_wolfapi_map = ""
        self.browser_mod_results.clear()
        for name in ("remote_search_timer", "remote_map_timer", "browser_selection_timer"):
            getattr(self, name).stop()
        self.wolfapi_map_catalog = []
        self.wolfapi_directory_total = self._saved_wolfapi_directory_total()
        self.wolfapi_filtered_total = self.settings.get(
            f"wolfapi_filtered_total_{ServerBrowserMixin.browser_product_key(self)}"
        )
        self.refresh_server_browser()
        self.update_browser_edition_notice()
        self._set_database_refresh_enabled(True)
        # A previous edition's worker may still occupy the discovery slot.
        # Once it exits, retry the current edition without accepting its result.
        for name in (
            "discovery_worker",
            "web_api_worker",
            "battlemetrics_worker",
            "wolfapi_worker",
            "wolfapi_cache_worker",
        ):
            worker = getattr(self, name, None)
            if worker is not None and worker.isRunning():
                worker.finished.connect(
                    ServerBrowserMixin._browser_callback(
                        self, self.maybe_auto_refresh_configured_provider
                    )
                )
        self.maybe_auto_refresh_configured_provider()
        self.schedule_remote_wolfapi_search(self.browser_search.text())

    def update_browser_edition_notice(self):
        if not hasattr(self, "browser_edition_notice"):
            return
        product = ServerBrowserMixin.browser_product(self)
        state = getattr(self, "product_availability", {}).get(product.key)
        detail = f"Showing {product.label} servers only."
        if state is not None and not state.detected:
            detail += (
                " Installation required to join."
                if state.state != "error"
                else " Installation check unavailable; rescan in Settings."
            )
        self.browser_edition_notice.setText(detail)

    def discovery_source_name(self, source: str) -> str:
        """Keep disposable discovered-server cache rows isolated by game product."""
        return (
            source
            if ServerBrowserMixin.browser_product_key(self) == "stable"
            else f"{source}_{ServerBrowserMixin.browser_product_key(self)}"
        )

    def _build_server_browser_tab(self) -> QWidget:
        widget = QWidget()
        set_ui_role(widget, "workspace")
        layout = QVBoxLayout(widget)

        self.browser_generation = 0
        self.browser_edition = QComboBox()
        self.browser_edition.setFixedWidth(150)
        self.browser_edition.addItem("Version", "stable")
        self.browser_edition.addItem("Stable", "stable")
        self.browser_edition.addItem("Experimental", "experimental")
        self.browser_edition.setAccessibleName("Server browser version")
        self.browser_edition.setToolTip(
            "Browse one edition at a time. Favourites and joining select their own edition."
        )
        self.browser_edition.currentIndexChanged.connect(self.change_browser_edition)
        self.browser_edition_notice = QLabel("Showing DayZ Stable servers only.")
        self.browser_edition_notice.setWordWrap(True)
        set_ui_role(self.browser_edition_notice, "metadata")

        filters = QHBoxLayout()
        self.browser_search = QLineEdit()
        self.browser_search.setAccessibleName("Search discovered servers")
        self.browser_search.setPlaceholderText("Search discovered servers")
        self.browser_search.setClearButtonEnabled(True)
        self.browser_search.setMinimumWidth(280)
        self.browser_search.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.browser_search.textChanged.connect(self.schedule_browser_search_refresh)
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
        self.browser_map.currentTextChanged.connect(self.schedule_remote_wolfapi_map)
        filters.addWidget(self.browser_map)
        QTimer.singleShot(0, self.refresh_wolfapi_map_catalog)

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
        filters.insertWidget(1, self.browser_edition)

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
        layout.addWidget(self.browser_edition_notice)
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
        self.browser_hide_quality_flagged = QCheckBox("Hide listing data warnings")
        self.browser_hide_quality_flagged.setToolTip(
            "Hide rows WolfAPI flags for suspicious provider telemetry or dense "
            "same-host populations. Enabled by default; exact/local data is retained."
        )
        self.browser_hide_quality_flagged.setChecked(
            bool(self.settings.get("hide_quality_flagged", True))
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
        self.browser_table.setAccessibleName("Discovered servers")
        self.browser_table.setAccessibleDescription(
            "Read-only discovered DayZ servers. Select a row to inspect or launch it."
        )
        self.browser_table.setHorizontalHeaderLabels(
            [
                "Fav",
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
                "Game Time",
                "",
            ]
        )
        for column in (8, 9):
            self.browser_table.horizontalHeaderItem(column).setTextAlignment(
                Qt.AlignRight | Qt.AlignVCenter
            )
        self.browser_table.horizontalHeaderItem(BROWSER_PASSWORD_COLUMN).setToolTip(
            "Password required"
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
        self.browser_table.cellClicked.connect(self.handle_browser_cell_clicked)
        self.browser_table.itemSelectionChanged.connect(self.update_browser_selection_context)
        self.browser_table.verticalScrollBar().valueChanged.connect(
            self.schedule_browser_scroll_freshness_check
        )
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
        if getattr(self, "pending_provider_refresh", False):
            return
        if self.results_freshness_worker is not None:
            self.pending_provider_refresh = True
            self.pending_results_freshness = False
            self.initial_results_freshness_batches_remaining = 0
            self.results_freshness_visible_only = False
            self._set_database_refresh_enabled(False)
            self.statusBar().showMessage(
                "Finishing the current live check before refreshing the server list…"
            )
            self.results_freshness_worker.cancel()
            return
        self._start_configured_provider_refresh(provider)

    def _start_configured_provider_refresh(self, provider: str):
        if provider == "wolfapi_v1":
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

    def _run_pending_configured_provider_refresh(self):
        if not self.pending_provider_refresh or getattr(self, "_shutting_down", False):
            return
        self.pending_provider_refresh = False
        self._start_configured_provider_refresh(self.discovery_provider_key())

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
            max_batches=1,
            master_addresses=master_addresses,
            app_id=ServerBrowserMixin.browser_product(self).client_app_id,
        )
        self.discovery_worker.discovery_ready.connect(
            ServerBrowserMixin._browser_callback(self, self.handle_steam_discovery_ready)
        )
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
            self.server_cache, self.discovery_source_name("steam_master"), servers
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
            api_key=api_key,
            limit=self.discovery_limit.value(),
            app_id=ServerBrowserMixin.browser_product(self).client_app_id,
        )
        self.web_api_worker.discovery_ready.connect(
            ServerBrowserMixin._browser_callback(self, self.handle_steam_web_api_ready)
        )
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
            self.server_cache, self.discovery_source_name("steam_web_api"), servers
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
        self.battlemetrics_worker.discovery_ready.connect(
            ServerBrowserMixin._browser_callback(self, self.handle_battlemetrics_ready)
        )
        self.battlemetrics_worker.start()

    def refresh_from_wolfapi(self):
        if self.wolfapi_worker and self.wolfapi_worker.isRunning():
            return
        self.start_wolfapi_refresh_process(automatic=False)

    def start_wolfapi_refresh_process(self, automatic: bool):
        label = "WolfAPI"
        self.browser_summary.setText(f"Cached discovered servers: querying {label}…")
        self._set_database_refresh_enabled(False)
        self.wolfapi_cache_context = (
            automatic,
            label,
            "wolfapi_v1",
        )
        self.wolfapi_worker = WolfApiDiscoveryWorker(
            limit=self.discovery_limit.value(),
            automatic=automatic,
            unflagged_only=self.browser_hide_quality_flagged.isChecked(),
            product=ServerBrowserMixin.browser_product_key(self),
        )
        self.wolfapi_worker.discovery_ready.connect(
            ServerBrowserMixin._browser_callback(self, self.handle_wolfapi_ready)
        )
        self.wolfapi_worker.start()

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
        if self.wolfapi_cache_worker and self.wolfapi_cache_worker.isRunning():
            return
        if not self.should_auto_refresh_provider(provider):
            return
        self.browser_summary.setText(
            "Cached discovered servers: quietly refreshing configured provider..."
        )
        self._set_database_refresh_enabled(False)
        if provider == "wolfapi_v1":
            self.start_wolfapi_refresh_process(automatic=True)
        elif provider == "battlemetrics":
            self.battlemetrics_worker = BattleMetricsDiscoveryWorker(
                limit=self.discovery_limit.value(),
                page_delay=2.0,
                automatic=True,
            )
            self.battlemetrics_worker.discovery_ready.connect(
                ServerBrowserMixin._browser_callback(self, self.handle_battlemetrics_ready)
            )
            self.battlemetrics_worker.start()
        elif provider == "steam_web_api":
            api_key = self.steam_web_api_key.text().strip()
            if not api_key:
                self._set_database_refresh_enabled(True)
                return
            self.web_api_worker = SteamWebApiDiscoveryWorker(
                api_key=api_key,
                limit=self.discovery_limit.value(),
                app_id=ServerBrowserMixin.browser_product(self).client_app_id,
            )
            self.web_api_worker.discovery_ready.connect(
                ServerBrowserMixin._browser_callback(self, self.handle_auto_web_api_ready)
            )
            self.web_api_worker.start()
        elif provider == "steam_master":
            try:
                master_addresses = self.steam_master_addresses()
            except ValueError as exc:
                self._set_database_refresh_enabled(True)
                self.statusBar().showMessage(f"Steam master auto-refresh skipped: {exc}", 7000)
                return
            self.discovery_worker = SteamDiscoveryWorker(
                max_batches=1,
                master_addresses=master_addresses,
                app_id=ServerBrowserMixin.browser_product(self).client_app_id,
            )
            self.discovery_worker.discovery_ready.connect(
                ServerBrowserMixin._browser_callback(self, self.handle_auto_steam_discovery_ready)
            )
            self.discovery_worker.start()

    def handle_main_tab_changed(self, index: int):
        previous_index = getattr(self, "active_main_tab_index", None)
        self.active_main_tab_index = index
        if index == getattr(self, "mods_tab_index", -1):
            if previous_index == self.server_browser_tab_index:
                self.follow_browser_selection_to_mods()
            return
        if index != self.server_browser_tab_index:
            return
        self.schedule_selected_discovered_server_check()
        QTimer.singleShot(0, self.schedule_initial_results_freshness_check)
        QTimer.singleShot(0, self.maybe_auto_refresh_configured_provider)

    def should_auto_refresh_provider(self, provider: str) -> bool:
        return auto_refresh_due(
            self.settings.get(
                f"last_{provider}_{ServerBrowserMixin.browser_product_key(self)}_auto_refresh_at"
            )
        )

    def mark_auto_refresh(self, provider: str):
        self.settings[
            f"last_{provider}_{ServerBrowserMixin.browser_product_key(self)}_auto_refresh_at"
        ] = auto_refresh_timestamp()
        self.save_user_settings(silent=True)

    def _saved_wolfapi_directory_total(self) -> int | None:
        try:
            total = int(
                self.settings.get(
                    f"wolfapi_directory_total_{ServerBrowserMixin.browser_product_key(self)}"
                )
            )
        except (TypeError, ValueError):
            return None
        return total if total >= 0 else None

    def record_wolfapi_directory_total(self, value) -> None:
        if value is None:
            return
        try:
            total = int(value)
        except (TypeError, ValueError):
            return
        if total < 0 or total == self.wolfapi_directory_total:
            return
        self.wolfapi_directory_total = total
        self.settings[f"wolfapi_directory_total_{ServerBrowserMixin.browser_product_key(self)}"] = (
            total
        )
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
            self.server_cache, self.discovery_source_name("steam_master"), servers
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
            self.server_cache, self.discovery_source_name("steam_web_api"), servers
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
        provider = "wolfapi_v1"
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
        self.record_wolfapi_directory_total(getattr(servers, "directory_total", None))
        self.wolfapi_filtered_total = getattr(servers, "filtered_total", None)
        self.settings[f"wolfapi_filtered_total_{ServerBrowserMixin.browser_product_key(self)}"] = (
            self.wolfapi_filtered_total
        )
        self.browser_summary.setText(f"Cached discovered servers: updating {label} results…")
        self.wolfapi_cache_context = (automatic, label, provider)
        self.wolfapi_cache_worker = WolfApiCacheMergeWorker(
            server_cache.SERVER_CACHE_PATH,
            servers,
            bounded_v1=provider == "wolfapi_v1",
            source=self.discovery_source_name("wolfapi"),
        )
        self.wolfapi_cache_worker.merge_ready.connect(
            ServerBrowserMixin._browser_callback(self, self.handle_wolfapi_cache_ready)
        )
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

    def schedule_remote_wolfapi_map(self, map_name: str):
        self.remote_map_timer.stop()
        map_name = " ".join(map_name.split())
        if self.discovery_provider_key() != "wolfapi_v1" or not map_name or map_name == "Any map":
            self.pending_wolfapi_map = ""
            return
        self.pending_wolfapi_map = map_name
        self.remote_map_timer.start()

    def refresh_wolfapi_map_catalog(self):
        if self.discovery_provider_key() != "wolfapi_v1":
            return
        if self.wolfapi_map_catalog_worker and self.wolfapi_map_catalog_worker.isRunning():
            return
        self.wolfapi_map_catalog_worker = WolfApiMapCatalogWorker()
        self.wolfapi_map_catalog_worker.catalog_ready.connect(
            ServerBrowserMixin._browser_callback(self, self.handle_wolfapi_map_catalog)
        )
        self.wolfapi_map_catalog_worker.finished.connect(self.finish_wolfapi_map_catalog)
        self.wolfapi_map_catalog_worker.start()

    def handle_wolfapi_map_catalog(self, maps, _error: str):
        if not isinstance(maps, list):
            return
        self.wolfapi_map_catalog = [str(map_name) for map_name in maps if str(map_name).strip()]
        self._refresh_browser_filter_options()

    def finish_wolfapi_map_catalog(self):
        self.wolfapi_map_catalog_worker = None

    def start_remote_wolfapi_map(self):
        map_name = self.pending_wolfapi_map
        if not map_name or self.discovery_provider_key() != "wolfapi_v1":
            return
        if self.wolfapi_map_worker and self.wolfapi_map_worker.isRunning():
            return
        self.pending_wolfapi_map = ""
        self.wolfapi_map_worker = WolfApiMapWorker(
            map_name,
            limit=500,
            unflagged_only=self.browser_hide_quality_flagged.isChecked(),
            product=ServerBrowserMixin.browser_product_key(self),
        )
        self.wolfapi_map_worker.map_ready.connect(
            ServerBrowserMixin._browser_callback(self, self.handle_remote_wolfapi_map)
        )
        self.wolfapi_map_worker.finished.connect(self.finish_remote_wolfapi_map)
        self.statusBar().showMessage(f'Loading WolfAPI map "{map_name}"…')
        self.wolfapi_map_worker.start()

    def handle_remote_wolfapi_map(self, map_name: str, servers, error: str):
        if error:
            self.statusBar().showMessage(
                f"WolfAPI map lookup unavailable; showing cached results: {error}", 7000
            )
            return
        merged = server_cache.merge_source_servers(
            self.server_cache, self.discovery_source_name("wolfapi"), servers
        )
        if self._combo_filter_value(self.browser_map, "Any map").casefold() == map_name.casefold():
            self.refresh_server_browser()
            self.statusBar().showMessage(
                f'WolfAPI map lookup merged {merged} result(s) for "{map_name}".', 5000
            )

    def finish_remote_wolfapi_map(self):
        self.wolfapi_map_worker = None
        if self.pending_wolfapi_map:
            self.remote_map_timer.start()

    def schedule_browser_search_refresh(self, text: str):
        self.browser_filter_timer.stop()
        query = " ".join(text.split())
        if query and len(query) < MIN_BROWSER_SEARCH_LENGTH:
            self.browser_summary.setText(
                f"Type at least {MIN_BROWSER_SEARCH_LENGTH} characters to search servers."
            )
            return
        self.browser_filter_timer.start()

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
            product=ServerBrowserMixin.browser_product_key(self),
        )
        self.wolfapi_search_worker.search_ready.connect(
            ServerBrowserMixin._browser_callback(self, self.handle_remote_wolfapi_search)
        )
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
        if query != current_query:
            return
        merged = server_cache.merge_source_servers(
            self.server_cache, self.discovery_source_name("wolfapi"), servers
        )
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
        """Live-check a bounded sample after an explicit discovery refresh."""
        self.initial_results_freshness_batches_remaining = INITIAL_RESULTS_FRESHNESS_BATCHES
        self.results_freshness_visible_only = False
        ServerBrowserMixin._schedule_results_freshness_check(self)

    def schedule_initial_results_freshness_check(self):
        """Live-check four visible-order batches when the browser is first opened."""
        self.initial_results_freshness_batches_remaining = INITIAL_RESULTS_FRESHNESS_BATCHES
        self.results_freshness_visible_only = False
        ServerBrowserMixin._schedule_results_freshness_check(self)

    def continue_initial_results_freshness_check(self):
        ServerBrowserMixin._schedule_results_freshness_check(self)

    def schedule_browser_scroll_freshness_check(self, _value: int):
        """Debounce viewport freshness until the user has stopped scrolling."""
        self.browser_scroll_timer.stop()
        self.browser_scroll_timer.start()

    def start_browser_scroll_freshness_check(self):
        """Live-check up to four batches drawn only from currently visible rows."""
        self.initial_results_freshness_batches_remaining = INITIAL_RESULTS_FRESHNESS_BATCHES
        self.results_freshness_visible_only = True
        ServerBrowserMixin._schedule_results_freshness_check(self)

    def _schedule_results_freshness_check(self):
        if not hasattr(self, "browser_servers"):
            return
        context = (
            " ".join(self.browser_search.text().split()) if hasattr(self, "browser_search") else ""
        )
        context_changed = context != self.results_freshness_context
        if context_changed:
            self.results_freshness_context = context
            self.results_freshness_attempted_keys.clear()
        # A stopped thread can still have its finished signal queued. Keep its
        # slot reserved until that callback runs, otherwise it can clear the
        # replacement worker's last reference while the replacement is running.
        if self.results_freshness_worker is not None:
            self.pending_results_freshness = True
            if context_changed:
                self.results_freshness_worker.cancel()
            return
        selected_workers = set(self.selection_enrichment_workers)
        servers_by_key = {server.cache_key: server for server in self.browser_servers}
        row_count = self.browser_table.rowCount()
        viewport = self.browser_table.viewport()
        top_row = self.browser_table.rowAt(0)
        bottom_row = self.browser_table.rowAt(max(0, viewport.height() - 1))
        if top_row < 0:
            top_row = 0
        if bottom_row < top_row:
            bottom_row = min(row_count - 1, top_row + MAX_RESULTS_FRESHNESS_BATCH - 1)
        visible_rows = range(top_row, bottom_row + 1)
        remaining_rows = (
            ()
            if getattr(self, "results_freshness_visible_only", False)
            else (*range(0, top_row), *range(bottom_row + 1, row_count))
        )
        ordered_servers = []
        for row in (*visible_rows, *remaining_rows):
            item = self.browser_table.item(row, BROWSER_NAME_COLUMN)
            cache_key = item.data(Qt.UserRole) if item is not None else ""
            server = servers_by_key.get(cache_key)
            if server is not None:
                ordered_servers.append(server)
        servers = [
            server
            for server in ordered_servers
            if server.cache_key not in selected_workers
            and server.cache_key not in self.results_freshness_attempted_keys
            and local_enrichment_due(server)
        ][:MAX_RESULTS_FRESHNESS_BATCH]
        if not servers:
            self.pending_results_freshness = False
            self.initial_results_freshness_batches_remaining = 0
            self.results_freshness_visible_only = False
            completed_pass = bool(self.results_freshness_attempted_keys)
            self.results_freshness_attempted_keys.clear()
            message = (
                "Live freshness check complete."
                if completed_pass
                else "Matching servers already have recent live status."
            )
            self.statusBar().showMessage(message, 5000)
            self.schedule_selected_discovered_server_check()
            return
        self.results_freshness_attempted_keys.update(server.cache_key for server in servers)
        self.pending_results_freshness = False
        self.statusBar().showMessage(
            f"Checking live freshness for {len(servers)} matching server(s) in the background..."
        )
        worker = ServerEnrichmentWorker(servers, probe_fallbacks=False)
        self.results_freshness_worker = worker
        worker.enrichment_progress.connect(self.handle_results_freshness_progress)
        worker.finished.connect(self.handle_results_freshness_finished)
        worker.start()

    def handle_results_freshness_progress(self, payload, _completed: int, _total: int):
        if getattr(self, "_shutting_down", False):
            return
        old_cache_key, server = payload
        if not persist_enriched_server(self.server_cache, old_cache_key, server):
            return
        update_browser_table_row(self.browser_table, old_cache_key, server)

    def handle_results_freshness_finished(self):
        self.results_freshness_worker = None
        if getattr(self, "pending_provider_refresh", False):
            self.pending_results_freshness = False
            self.initial_results_freshness_batches_remaining = 0
            self.results_freshness_visible_only = False
            self.results_freshness_attempted_keys.clear()
            QTimer.singleShot(0, self._run_pending_configured_provider_refresh)
            return
        if self.pending_results_freshness:
            self.pending_results_freshness = False
        if self.initial_results_freshness_batches_remaining:
            self.initial_results_freshness_batches_remaining -= 1
            if self.initial_results_freshness_batches_remaining:
                QTimer.singleShot(0, self.continue_initial_results_freshness_check)
                return
            message = (
                "Visible server freshness check complete."
                if getattr(self, "results_freshness_visible_only", False)
                else "Initial live freshness check complete."
            )
            self.results_freshness_visible_only = False
            self.results_freshness_attempted_keys.clear()
            self.statusBar().showMessage(message, 5000)
            self.schedule_selected_discovered_server_check()
            return
        QTimer.singleShot(0, self.schedule_results_freshness_check)

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
        if not persist_enriched_server(self.server_cache, old_cache_key, server):
            self.statusBar().showMessage(
                "Live result matched another stable server; the cached identity was kept.",
                7000,
            )
            return
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
        if hasattr(self, "server_launch"):
            # Browsing uses provider mod counts. Local readiness requires the
            # live identity/context path invoked by Join or Check mods.
            return
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
            workshop_install=install,
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
            **saved_server_fields(server),
            name=name,
            group=dialog.curated_group(),
            host=server.host,
            game_port=server.game_port,
            query_port=server.query_port,
            favourite=True,
        )
        try:
            add_curated_server(getattr(self, "saved_server_repository", self.config_path), curated)
        except ValueError as exc:
            QMessageBox.warning(self, "Could not promote server", str(exc))
            return

        self.favourites.add(server_key(curated))
        self._save_favourites_index()
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
            **saved_server_fields(server),
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
        return self.activate_discovered_server(discovered)

    def activate_discovered_server(self, discovered: DiscoveredServer) -> Server:
        if hasattr(self, "server_launch") and not self.server_launch.current(
            self.server_launch.context, require_fresh=False
        ):
            self.server_launch.invalidate()
        self.active_discovered_server = self.discovered_server_context(discovered)
        self.active_discovered_cache_key = discovered.cache_key
        self.update_launch_button_text()
        return self.active_discovered_server

    def follow_browser_selection_to_mods(self):
        discovered = self.selected_discovered_server()
        if discovered is None:
            return
        context_changed = discovered.cache_key != self.active_discovered_cache_key
        server = self.activate_discovered_server(discovered)
        if context_changed:
            self.last_mod_result = None
            self.mods_table.setRowCount(0)
            self.update_mod_detail_card()
        self.check_server_mods(server, silent=True)

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

    def _provider_label(self, key: str) -> str:
        labels = {
            "wolfapi_v1": "WolfAPI",
            "steam_master": "Steam Master",
        }
        return labels.get(key, labels[DEFAULT_DISCOVERY_PROVIDER])

    def discovery_provider_key(self) -> str:
        if not hasattr(self, "discovery_provider"):
            return str(self.settings.get("discovery_provider") or DEFAULT_DISCOVERY_PROVIDER)
        keys = {
            "WolfAPI": "wolfapi_v1",
            "WolfAPI v1 (staged)": "wolfapi_v1",
            "Steam Master": "steam_master",
        }
        return keys.get(self.discovery_provider.currentText(), DEFAULT_DISCOVERY_PROVIDER)

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
        source_namespace = ""
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
                source_namespace=source_namespace,
                products=(ServerBrowserMixin.browser_product_key(self),),
                style_terms=tuple(style_terms),
                modded=modded,
                hide_quality_flagged=self.browser_hide_quality_flagged.isChecked(),
                sort_by=sort_key,
                descending=self.browser_descending.isChecked(),
                limit=limit,
            ),
        )
        servers = snapshot.servers
        if selected_key and selected_key not in {server.cache_key for server in servers}:
            if hasattr(self, "server_launch"):
                self.server_launch.invalidate()
            self.active_discovered_server = None
            self.active_discovered_cache_key = ""
        self.browser_servers = servers

        populate_browser_table(
            self.browser_table,
            servers,
            {
                (server.host, server.game_port, server.query_port)
                for server in self.servers
                if server.favourite
            },
        )
        if selected_key:
            for row in range(self.browser_table.rowCount()):
                item = self.browser_table.item(row, BROWSER_NAME_COLUMN)
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
            browser_summary_text(
                snapshot.cache_summary,
                len(servers),
                snapshot.match_count,
                limit,
                self.wolfapi_directory_total
                if self.discovery_provider_key() == "wolfapi_v1"
                else None,
            )
        )
        if getattr(self, "wolfapi_filtered_total", None) is not None:
            self.browser_summary.setText(
                self.browser_summary.text()
                + f" · {self.wolfapi_filtered_total:,} in selected edition directory"
            )
        self.browser_summary.setToolTip(browser_summary_tooltip(snapshot.cache_summary))
        self.update_browser_selection_context()

    def update_browser_selection_context(self):
        if not hasattr(self, "browser_promote_button"):
            return
        selected = self.selected_discovered_server()
        if getattr(self, "active_discovered_cache_key", "") and (
            selected is None or selected.cache_key != self.active_discovered_cache_key
        ):
            if hasattr(self, "server_launch"):
                self.server_launch.invalidate()
            self.active_discovered_server = None
            self.active_discovered_cache_key = ""
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
            availability = getattr(self, "product_availability", {}).get(
                ServerBrowserMixin.browser_product_key(self)
            )
            if availability is not None and availability.state in {
                "missing",
                "steam_missing",
                "incomplete",
            }:
                launch_button.setEnabled(False)
                launch_button.setToolTip(
                    "Install this DayZ edition, launch it once through Steam, then rescan in Settings."
                )
            else:
                launch_button.setToolTip("")
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
            self.browser_detail_context.setText(f"Game time  {detail.game_time}")
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
            (BROWSER_FAVOURITE_COLUMN, 1, BROWSER_PASSWORD_COLUMN, 6, 7, 16, 8, 9, 11, 12),
            show_details=show_details,
            stretch_columns=(),
        )
        header = self.browser_table.horizontalHeader()
        # Some Qt styles default to a minimum wider than the 32px lock column.
        header.setMinimumSectionSize(32)
        header.setSectionResizeMode(BROWSER_FAVOURITE_COLUMN, QHeaderView.Fixed)
        self.browser_table.setColumnWidth(BROWSER_FAVOURITE_COLUMN, 48)
        header.setSectionResizeMode(BROWSER_PASSWORD_COLUMN, QHeaderView.Fixed)
        self.browser_table.setColumnWidth(BROWSER_PASSWORD_COLUMN, 32)
        self.browser_table.setColumnHidden(BROWSER_PASSWORD_COLUMN, False)
        self.browser_table.setColumnHidden(2, True)
        if not show_details:
            # Name flexes with the live viewport and yields when readiness text
            # makes Mods wider. This avoids stale startup widths and horizontal
            # overflow after background mod previews complete.
            header.setSectionResizeMode(BROWSER_NAME_COLUMN, QHeaderView.Stretch)

    def _refresh_browser_filter_options(self):
        source_namespace = (
            f"_{ServerBrowserMixin.browser_product_key(self)}"
            if ServerBrowserMixin.browser_product(self).experimental
            else ""
        )
        options = browser_filter_options(
            self.server_cache,
            source_namespace,
            products=(ServerBrowserMixin.browser_product_key(self),),
        )
        self._set_combo_filter_options(
            self.browser_map,
            "Any map",
            sorted(set(options["map"]) | set(self.wolfapi_map_catalog), key=str.casefold),
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
        set_combo_filter_options(combo, any_label, values)

    def _combo_filter_value(self, combo: QComboBox, any_label: str) -> str:
        return combo_filter_value(combo, any_label)

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
        self.browser_hide_quality_flagged.setChecked(True)
        self.browser_limit.setCurrentText("200")
        self.refresh_server_browser()

    def handle_browser_double_clicked(self, row: int, column: int):
        if column == BROWSER_FAVOURITE_COLUMN:
            return
        self.browser_table.selectRow(row)
        self.inspect_selected_discovered_server()

    def handle_browser_cell_clicked(self, row: int, column: int):
        if column != BROWSER_FAVOURITE_COLUMN:
            return
        item = self.browser_table.item(row, BROWSER_NAME_COLUMN)
        cache_key = item.data(Qt.UserRole) if item else ""
        discovered = (
            server_cache.get_server(self.server_cache, str(cache_key)) if cache_key else None
        )
        if not discovered:
            return
        endpoint = (discovered.host, discovered.game_port, discovered.query_port)
        for index, curated in enumerate(self.servers):
            if (curated.host, curated.game_port, curated.query_port) == endpoint:
                if curated.favourite:
                    self.remove_curated_server_row(index, confirm=False)
                else:
                    self.toggle_favourite(index)
                return
        curated = Server(
            **saved_server_fields(discovered),
            name=discovered.server_name or discovered.name or discovered.connect_target,
            group="Favourites",
            host=discovered.host,
            game_port=discovered.game_port,
            query_port=discovered.query_port,
            favourite=True,
        )
        try:
            add_curated_server(getattr(self, "saved_server_repository", self.config_path), curated)
        except ValueError as exc:
            QMessageBox.warning(self, "Could not add favourite", str(exc))
            return
        self.favourites.add(server_key(curated))
        self._save_favourites_index()
        self.add_curated_server_row(curated)

    def sync_browser_favourite_endpoint(
        self,
        host: str,
        game_port: int,
        query_port: int,
        *,
        is_favourite: bool,
    ):
        """Reflect a curated change in the Browser without a cache reload."""
        matching_keys = {
            server.cache_key
            for server in self.browser_servers
            if (server.host, server.game_port, server.query_port) == (host, game_port, query_port)
        }
        for row in range(self.browser_table.rowCount()):
            item = self.browser_table.item(row, BROWSER_NAME_COLUMN)
            if item and item.data(Qt.UserRole) in matching_keys:
                self._set_browser_favourite_cell(row, is_favourite=is_favourite)

    def _set_browser_favourite_cell(self, row: int, *, is_favourite: bool):
        set_browser_favourite_marker(self.browser_table, row, is_favourite)

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
