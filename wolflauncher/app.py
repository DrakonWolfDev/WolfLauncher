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
    QVBoxLayout,
    QWidget,
)

from . import __version__, server_cache
from .about_feature import AboutFeatureMixin
from .config import (
    CURATED_SERVERS_PATH,
    ensure_empty_servers_file,
    ensure_servers_file,
    find_default_launcher_path,
)
from .connect_preflight import ConnectPreflightCoordinator
from .curated_servers_controller import CuratedServersMixin
from .curated_status_cache import (
    load_status_cache,
)
from .dayz_product import STABLE
from .launch_dialogs import (
    LaunchDialog as LaunchDialog,
)
from .launch_dialogs import (
    NativeLaunchPreviewDialog as NativeLaunchPreviewDialog,
)
from .launch_dialogs import (
    PreflightLaunchDialog as PreflightLaunchDialog,
)
from .launch_execution import LaunchExecutionCoordinator
from .launch_feature import LaunchFeatureMixin
from .launcher import DEFAULT_PLAYER_NAME
from .lifecycle import (
    RuntimeShutdownCoordinator,
)
from .local_tools_feature import LocalToolsFeatureMixin
from .logging_setup import configure_local_logging, install_exception_hook
from .mods_feature import ModsFeatureMixin
from .platforms import current_platform
from .retention import run_local_retention
from .secret_store import (
    SecretStore,
    load_steam_api_key,
)
from .server_browser_feature import (
    ServerBrowserMixin,
)
from .server_browser_feature import (
    persist_enriched_server as persist_enriched_server,
)
from .settings import (
    curated_servers_path,
    load_settings,
    server_key,
)
from .settings_feature import SettingsFeatureMixin
from .settings_health_controller import SettingsHealthCoordinator
from .single_instance import SingleInstanceGuard, activate_window
from .theme import (
    WOLF_MARK_PATH,
    apply_application_theme,
    brand_wordmark,
    set_monospace,
    set_ui_role,
    theme_icon,
)
from .update_feature import UpdateFeatureMixin
from .workshop_resolution_controller import WorkshopResolutionCoordinator


class MainWindow(
    CuratedServersMixin,
    ServerBrowserMixin,
    ModsFeatureMixin,
    SettingsFeatureMixin,
    LocalToolsFeatureMixin,
    LaunchFeatureMixin,
    UpdateFeatureMixin,
    AboutFeatureMixin,
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
        from .server_launch_coordinator import ServerLaunchCoordinator

        self.server_launch = ServerLaunchCoordinator(self)
        self.settings_health = SettingsHealthCoordinator(self)
        self.workshop_resolution = WorkshopResolutionCoordinator(self)
        self._shutdown_dialog = None
        self.settings = load_settings()
        self.product = STABLE
        self.config_path = curated_servers_path(self.product.key)
        (ensure_empty_servers_file if self.product.experimental else ensure_servers_file)(
            self.config_path
        )
        from .saved_servers import SavedServerRepository

        self.saved_server_repository = SavedServerRepository(self.config_path.parent)
        self.servers = self.saved_server_repository.load()
        self.curated_status_cache = load_status_cache()
        self.secret_store = SecretStore()
        self.steam_api_key = load_steam_api_key(self.settings, self.secret_store)
        self.favourites = {server_key(s) for s in self.servers if s.favourite}
        self.detected_steam_installs = []
        self.worker = None
        self.mod_worker = None
        self.workshop_subscription_worker = None
        self.workshop_unsubscribe_worker = None
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
        self.wolfapi_map_worker = None
        self.wolfapi_map_catalog_worker = None
        self.wolfapi_map_catalog = []
        self.pending_wolfapi_search = ""
        self.pending_wolfapi_map = ""
        self.wolfapi_directory_total = self._saved_wolfapi_directory_total()
        self.wolfapi_filtered_total = self.settings.get("wolfapi_filtered_total_stable")
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

        if self.saved_server_repository.errors:
            QTimer.singleShot(
                0,
                lambda: QMessageBox.warning(
                    self,
                    "Saved servers need attention",
                    "Recoverable entries were loaded. Damaged files have been kept unchanged.\n\n"
                    + "\n".join(self.saved_server_repository.errors),
                ),
            )

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
        steam_modes = ["Auto", "Native Steam", "STEAM_ROOT Steam library"]
        self.native_steam_mode.addItems(steam_modes)
        if current_platform().capabilities.platform_id == "linux":
            self.native_steam_mode.setToolTip("This version supports native Steam only.")
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
        self.remote_map_timer = QTimer(self)
        self.remote_map_timer.setSingleShot(True)
        self.remote_map_timer.setInterval(450)
        self.remote_map_timer.timeout.connect(self.start_remote_wolfapi_map)
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
        self.tabs.addTab(
            self._scrollable_workspace(self._build_servers_tab()), theme_icon("servers"), "Servers"
        )
        self.server_browser_tab_index = self.tabs.addTab(
            self._scrollable_workspace(self._build_server_browser_tab()),
            theme_icon("browser"),
            "Server Browser",
        )
        self.mods_tab_index = self.tabs.addTab(
            self._scrollable_workspace(self._build_mods_tab()), theme_icon("mods"), "Mods"
        )
        self.local_tools_tab_index = self.tabs.addTab(
            self._scrollable_workspace(self._build_local_tools_tab()),
            theme_icon("mods"),
            "Editor / Local Tools",
        )
        self.tabs.addTab(
            self._scrollable_workspace(self._build_settings_tab()),
            theme_icon("settings"),
            "Settings",
        )
        self.tabs.addTab(
            self._scrollable_workspace(self._build_about_tab()),
            theme_icon("about"),
            "About",
        )
        for index in range(self.tabs.count()):
            self.tabs.setTabToolTip(index, f"Open {self.tabs.tabText(index)}")
        self.active_main_tab_index = self.tabs.currentIndex()
        self.tabs.currentChanged.connect(self.handle_main_tab_changed)
        central = QWidget()
        central_layout = QVBoxLayout(central)
        central_layout.setContentsMargins(0, 0, 0, 0)
        central_layout.setSpacing(0)
        self.update_banner = self._build_update_banner()
        central_layout.addWidget(self.update_banner)
        central_layout.addWidget(self.tabs)
        self.setCentralWidget(central)

        self.setup_update_feature()

        self.apply_refresh_timer()
        self.refresh_statuses(startup=True)
        self.refresh_server_browser()
        self.update_settings_health()
        QTimer.singleShot(0, self.show_server_cache_recovery_notice)
        QTimer.singleShot(0, self.check_startup_steam_state)
        QTimer.singleShot(0, self.check_initial_server_mods)
        QTimer.singleShot(1500, self.start_automatic_update_check)
        QTimer.singleShot(30000, self.maybe_auto_refresh_configured_provider)

    @staticmethod
    def _scrollable_workspace(content: QWidget) -> QScrollArea:
        """Keep every main-tab action reachable when desktop scaling is high."""
        scroll = QScrollArea()
        set_ui_role(scroll, "workspaceScroll")
        set_ui_role(scroll.viewport(), "workspaceViewport")
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        scroll.setWidget(content)
        return scroll

    def show_server_cache_recovery_notice(self):
        quarantined = self.recovered_server_cache_path
        if quarantined is None:
            return
        QMessageBox.information(
            self,
            "Discovered-server cache rebuilt",
            "WolfLauncher found a damaged discovered-server cache and rebuilt it. "
            "Your curated servers and settings were not changed.\n\n"
            f"A copy of the old disposable cache was saved at:\n{quarantined}",
        )

    def _build_brand_lockup(self) -> QWidget:
        lockup = QWidget()
        set_ui_role(lockup, "brandLockup")
        layout = QHBoxLayout(lockup)
        layout.setContentsMargins(8, 0, 10, 0)
        layout.setSpacing(7)
        mark = QLabel()
        mark.setPixmap(QIcon(str(WOLF_MARK_PATH)).pixmap(QSize(22, 22)))
        mark.setToolTip("WolfLauncher")
        wordmark = QLabel(brand_wordmark(" // "))
        wordmark.setAccessibleName("Wolf Launcher")
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
    # Exercise the bundled native TLS backend without requiring network access.
    from .tls import https_context

    https_context()
    for delay in (1000, 5000, 10000):
        QTimer.singleShot(delay, window.close)
    QTimer.singleShot(30000, lambda: app.exit(124))
    return True


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("WolfLauncher")
    app.setApplicationVersion(__version__)
    app.setOrganizationName("WolfLauncher")
    instance_guard = SingleInstanceGuard()
    if not instance_guard.start_or_notify():
        return
    run_local_retention()
    log_path = configure_local_logging()
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
    instance_guard.set_activation_handler(lambda: activate_window(window))
    window.show()
    configure_packaged_smoke_test(app, window)
    try:
        exit_code = app.exec()
    except KeyboardInterrupt:
        window.close()
        exit_code = 130
    instance_guard.close()
    sys.exit(exit_code)
