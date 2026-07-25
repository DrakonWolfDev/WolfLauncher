import os
import sys

from PySide6.QtCore import QSize, Qt, QTimer
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QProgressDialog,
    QScrollArea,
    QSpinBox,
    QTabWidget,
    QWidget,
)

from . import __version__, server_cache
from .logging_setup import configure_local_logging, install_exception_hook
from .config import (
    CURATED_SERVERS_PATH,
    ensure_servers_file,
    find_default_launcher_path,
    load_servers,
)
from .curated_status_cache import (
    load_status_cache,
)
from .connect_preflight import ConnectPreflightCoordinator
from .launch_execution import LaunchExecutionCoordinator
from .launch_dialogs import (
    LaunchDialog as LaunchDialog,
    NativeLaunchPreviewDialog as NativeLaunchPreviewDialog,
    PreflightLaunchDialog as PreflightLaunchDialog,
)
from .settings_health_controller import SettingsHealthCoordinator
from .workshop_resolution_controller import WorkshopResolutionCoordinator
from .launcher import DEFAULT_PLAYER_NAME
from .lifecycle import (
    RuntimeShutdownCoordinator,
)
from .platforms import current_platform
from .retention import run_local_retention
from .secret_store import (
    SecretStore,
    load_steam_api_key,
)
from .settings import (
    load_favourites,
    load_settings,
    server_key,
)
from .theme import (
    WOLF_MARK_PATH,
    apply_application_theme,
    set_monospace,
    set_ui_role,
    theme_icon,
)
from .curated_servers_controller import CuratedServersMixin
from .launch_feature import LaunchFeatureMixin
from .mods_feature import ModsFeatureMixin
from .server_browser_feature import (
    ServerBrowserMixin,
    persist_enriched_server as persist_enriched_server,
)
from .settings_feature import SettingsFeatureMixin


class MainWindow(
    CuratedServersMixin,
    ServerBrowserMixin,
    ModsFeatureMixin,
    SettingsFeatureMixin,
    LaunchFeatureMixin,
    QMainWindow,
):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("WolfLauncher")
        self.resize(1350, 720)

        self.config_path = CURATED_SERVERS_PATH
        self._shutting_down = False
        self.shutdown_coordinator = RuntimeShutdownCoordinator(self)
        self.connect_preflight = ConnectPreflightCoordinator(self)
        self.launch_execution = LaunchExecutionCoordinator(self)
        self.settings_health = SettingsHealthCoordinator(self)
        self.workshop_resolution = WorkshopResolutionCoordinator(self)
        self._shutdown_dialog = None
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
        self.wolfapi_directory_total = self._saved_wolfapi_directory_total()
        self.selection_enrichment_workers = {}
        self.pending_selection_checks = {}
        self.results_freshness_worker = None
        self.pending_results_freshness = False
        self.pending_provider_refresh = False
        self.initial_results_freshness_batches_remaining = 0
        self.results_freshness_visible_only = False
        self.results_freshness_context = ""
        self.results_freshness_attempted_keys = set()
        self.browser_mod_workers = {}
        self.pending_browser_mod_previews = {}
        self.browser_mod_results = {}
        self.last_mod_result = None
        self.active_mod_server_key = ""
        self.pending_mod_check_row = None
        self.pending_mod_server = None
        self.browser_servers = []
        self.server_cache, self.recovered_server_cache_path = server_cache.connect_recovering()

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
        self.browser_filter_timer = QTimer(self)
        self.browser_filter_timer.setSingleShot(True)
        self.browser_filter_timer.setInterval(250)
        self.browser_filter_timer.timeout.connect(self.refresh_server_browser)
        self.browser_selection_timer = QTimer(self)
        self.browser_selection_timer.setSingleShot(True)
        self.browser_selection_timer.setInterval(450)
        self.browser_selection_timer.timeout.connect(self.check_selected_discovered_server_status)
        self.browser_scroll_timer = QTimer(self)
        self.browser_scroll_timer.setSingleShot(True)
        self.browser_scroll_timer.setInterval(350)
        self.browser_scroll_timer.timeout.connect(self.start_browser_scroll_freshness_check)

        self.tabs = QTabWidget()
        self.tabs.setObjectName("mainTabs")
        self.tabs.setAccessibleName("WolfLauncher main sections")
        self.tabs.tabBar().setAccessibleName("WolfLauncher main sections")
        self.tabs.setCornerWidget(self._build_brand_lockup(), Qt.TopRightCorner)
        self.tabs.addTab(self._scrollable_workspace(self._build_servers_tab()), theme_icon("servers"), "Servers")
        self.server_browser_tab_index = self.tabs.addTab(
            self._scrollable_workspace(self._build_server_browser_tab()),
            theme_icon("browser"),
            "Server Browser",
        )
        self.mods_tab_index = self.tabs.addTab(
            self._scrollable_workspace(self._build_mods_tab()), theme_icon("mods"), "Mods"
        )
        self.tabs.addTab(
            self._scrollable_workspace(self._build_settings_tab()), theme_icon("settings"), "Settings"
        )
        for index in range(self.tabs.count()):
            self.tabs.setTabToolTip(index, f"Open {self.tabs.tabText(index)}")
        self.active_main_tab_index = self.tabs.currentIndex()
        self.tabs.currentChanged.connect(self.handle_main_tab_changed)
        self.setCentralWidget(self.tabs)

        self.apply_refresh_timer()
        self.refresh_statuses()
        self.refresh_server_browser()
        self.update_settings_health()
        QTimer.singleShot(0, self.check_startup_steam_state)
        QTimer.singleShot(0, self.check_initial_server_mods)
        QTimer.singleShot(30000, self.maybe_auto_refresh_configured_provider)

    @staticmethod
    def _scrollable_workspace(content: QWidget) -> QScrollArea:
        """Keep every main-tab action reachable when desktop scaling is high."""
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        scroll.setWidget(content)
        return scroll

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

    def closeEvent(self, event):
        if not self.shutdown_coordinator.started:
            self.save_user_settings(silent=True)
        if not self.shutdown_coordinator.begin():
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
        if self.shutdown_coordinator.poll():
            self.close()
            return
        if self.shutdown_coordinator.overdue():
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
    run_local_retention()
    log_path = configure_local_logging()
    app = QApplication(sys.argv)
    app.setApplicationName("WolfLauncher")
    app.setApplicationVersion(__version__)
    app.setOrganizationName("WolfLauncher")
    apply_application_theme(app)
    install_exception_hook(
        log_path,
        lambda report_name: QMessageBox.critical(
            None,
            "WolfLauncher encountered an error",
            "The application can remain open, but the current action may not have completed. "
            f"A redacted local report was saved as {report_name} in WolfLauncher application data.",
        ),
    )
    window = MainWindow()
    window.show()
    configure_packaged_smoke_test(app, window)
    try:
        exit_code = app.exec()
    except KeyboardInterrupt:
        window.close()
        exit_code = 130
    sys.exit(exit_code)
