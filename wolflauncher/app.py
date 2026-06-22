import os
import shutil
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from datetime import datetime, timedelta, timezone
import sys

from PySide6.QtCore import QTimer, QThread, Signal, QUrl, Qt, QPoint, QProcess
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
    QDialogButtonBox,
    QComboBox,
    QMenu,
    QPushButton,
    QSpinBox,
    QTabWidget,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)
from PySide6.QtGui import QColor, QDesktopServices, QAction, QTextCursor

from .config import (
    DEFAULT_LAUNCHER_PATHS,
    add_curated_server,
    find_default_launcher_path,
    load_servers,
    remove_curated_server,
    update_curated_server,
)
from .diagnostics import (
    format_launch_output_report,
    format_settings_health_report,
    launch_troubleshooting_report,
    post_handoff_launch_option_guidance,
    prime_environment_report,
    prime_helper_report,
    run_diagnostics,
    steam_launch_options_report,
)
from .launcher import DEFAULT_PLAYER_NAME, LaunchError, build_launch_command
from .models import Server
from .native_launcher import (
    NativeLaunchError,
    format_native_launch_parity_report,
    prepare_native_launch,
    prepare_native_launch_parity_report,
)
from .platform_detection import (
    SteamInstall,
    best_install,
    dayz_process_check,
    detect_steam,
    proton_compatdata_detail,
    select_steam_install,
    selected_install_summary,
    steam_install_summary,
    steam_mode_label,
    steam_selection_candidates_detail,
    steam_selection_report,
)
from .mods import ModCheckResult, check_server_mods
from . import server_cache
from .server_discovery import (
    discover_dayz_servers,
    discover_dayz_servers_battlemetrics,
    discover_dayz_servers_web_api,
    discover_dayz_servers_wolfapi,
    parse_master_address,
)
from .server_enrichment import (
    enrich_discovered_server,
    enrichment_probe_servers,
    parse_connect_port,
)
from .settings import (
    load_favourites,
    load_settings,
    save_favourites,
    save_settings,
    server_key,
)
from .status import ServerStatus, check_server


MAX_STATUS_WORKERS = 8


def _checked_server_status(server: Server) -> ServerStatus:
    try:
        return check_server(server)
    except Exception as exc:
        return ServerStatus(False, error=f"status check failed: {exc}")


class StatusWorker(QThread):
    status_ready = Signal(int, object)
    finished_all = Signal()

    def __init__(self, servers: list[Server]):
        super().__init__()
        self.servers = list(servers)

    def run(self):
        if not self.servers:
            self.finished_all.emit()
            return

        max_workers = min(MAX_STATUS_WORKERS, len(self.servers))
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {
                executor.submit(_checked_server_status, server): index
                for index, server in enumerate(self.servers)
            }
            for future in as_completed(futures):
                self.status_ready.emit(futures[future], future.result())
        self.finished_all.emit()


class ModWorker(QThread):
    mods_ready = Signal(object)

    def __init__(self, server: Server, workshop_dir):
        super().__init__()
        self.server = server
        self.workshop_dir = workshop_dir

    def run(self):
        self.mods_ready.emit(check_server_mods(self.server, self.workshop_dir))


class SteamDiscoveryWorker(QThread):
    discovery_ready = Signal(object, str)

    def __init__(self, max_batches: int = 1, master_addresses=None):
        super().__init__()
        self.max_batches = max_batches
        self.master_addresses = master_addresses

    def run(self):
        try:
            servers = discover_dayz_servers(
                max_batches=self.max_batches,
                master_addresses=self.master_addresses,
            )
        except OSError as exc:
            self.discovery_ready.emit([], str(exc))
        except ValueError as exc:
            self.discovery_ready.emit([], str(exc))
        else:
            self.discovery_ready.emit(servers, "")


class SteamWebApiDiscoveryWorker(QThread):
    discovery_ready = Signal(object, str)

    def __init__(self, api_key: str, limit: int = 5000):
        super().__init__()
        self.api_key = api_key
        self.limit = limit

    def run(self):
        try:
            servers = discover_dayz_servers_web_api(api_key=self.api_key, limit=self.limit)
        except Exception as exc:
            self.discovery_ready.emit([], str(exc))
        else:
            self.discovery_ready.emit(servers, "")


class BattleMetricsDiscoveryWorker(QThread):
    discovery_ready = Signal(object, str)

    def __init__(self, limit: int = 500, page_delay: float = 0.0, automatic: bool = False):
        super().__init__()
        self.limit = limit
        self.page_delay = page_delay
        self.automatic = automatic

    def run(self):
        try:
            servers = discover_dayz_servers_battlemetrics(
                limit=self.limit,
                page_delay=self.page_delay,
            )
        except Exception as exc:
            self.discovery_ready.emit([], str(exc))
        else:
            self.discovery_ready.emit(servers, "")


class WolfApiDiscoveryWorker(QThread):
    discovery_ready = Signal(object, str)

    def __init__(self, limit: int = 10000, automatic: bool = False):
        super().__init__()
        self.limit = limit
        self.automatic = automatic

    def run(self):
        try:
            servers = discover_dayz_servers_wolfapi(limit=self.limit)
        except Exception as exc:
            self.discovery_ready.emit([], str(exc))
        else:
            self.discovery_ready.emit(servers, "")


class ServerEnrichmentWorker(QThread):
    enrichment_ready = Signal(object, str)

    def __init__(self, servers):
        super().__init__()
        self.servers = servers

    def run(self):
        checked_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
        enriched = []
        try:
            for server in self.servers:
                status = ServerStatus(False, error="No valid query ports to probe.")
                for probe in enrichment_probe_servers(server):
                    status = check_server(probe)
                    if status.online:
                        break
                enriched.append(enrich_discovered_server(server, status, checked_at))
        except Exception as exc:
            self.enrichment_ready.emit(enriched, str(exc))
        else:
            self.enrichment_ready.emit(enriched, "")


class SortableTableWidgetItem(QTableWidgetItem):
    def __init__(self, text: str, sort_value=None):
        super().__init__(text)
        self.sort_value = sort_value if sort_value is not None else text.casefold()

    def __lt__(self, other):
        if isinstance(other, SortableTableWidgetItem):
            return self._normalized_sort_value() < other._normalized_sort_value()
        return super().__lt__(other)

    def _normalized_sort_value(self):
        value = self.sort_value
        if value is None or value == "":
            return (1, "")
        if isinstance(value, str):
            return (0, value.casefold())
        return (0, value)


POST_HANDOFF_PROCESS_CHECK_INTERVAL_MS = 5000
POST_HANDOFF_PROCESS_CHECK_ATTEMPTS = 9


class PostHandoffProcessCheckMixin:
    def start_post_handoff_process_checks(self):
        self.post_handoff_check_attempt = 0
        self.output.append("Watching for known DayZ processes for up to 45 seconds...")
        QTimer.singleShot(POST_HANDOFF_PROCESS_CHECK_INTERVAL_MS, self.append_dayz_process_check)

    def append_dayz_process_check(self):
        self.post_handoff_check_attempt += 1
        check = dayz_process_check()
        elapsed_seconds = (
            self.post_handoff_check_attempt * POST_HANDOFF_PROCESS_CHECK_INTERVAL_MS // 1000
        )
        if check.running:
            self.output.append(
                f"\nPost-handoff process check: {check.detail} after about {elapsed_seconds} seconds."
            )
            return

        if self.post_handoff_check_attempt < POST_HANDOFF_PROCESS_CHECK_ATTEMPTS:
            QTimer.singleShot(POST_HANDOFF_PROCESS_CHECK_INTERVAL_MS, self.append_dayz_process_check)
            return

        self.output.append(
            f"\nPost-handoff process check: no known DayZ process detected after about {elapsed_seconds} seconds. "
            "Steam may still be preparing Proton, but if there is no Steam activity, check downloads, Proton/BattlEye prompts, "
            "and the selected Steam install in Settings health. "
            f"{post_handoff_launch_option_guidance()}"
        )


class LaunchDialog(PostHandoffProcessCheckMixin, QDialog):
    def __init__(self, parent, command: list[str], title: str, handoff_label: str = "launch command"):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.resize(820, 460)
        self.handoff_label = handoff_label
        self.command_text = " ".join(command)
        self.process = QProcess(self)
        self.process.setProcessChannelMode(QProcess.MergedChannels)

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Launch command:"))
        command_box = QLineEdit(self.command_text)
        command_box.setReadOnly(True)
        layout.addWidget(command_box)

        self.output = QTextEdit()
        self.output.setReadOnly(True)
        layout.addWidget(self.output)

        button_row = QHBoxLayout()
        self.close_button = QPushButton("Close")
        self.close_button.clicked.connect(self.close)
        self.close_button.setEnabled(False)
        copy_button = QPushButton("Copy")
        copy_button.clicked.connect(self.copy_output)
        button_row.addStretch(1)
        button_row.addWidget(copy_button)
        button_row.addWidget(self.close_button)
        layout.addLayout(button_row)

        self.process.readyReadStandardOutput.connect(self.read_output)
        self.process.finished.connect(self.handle_finished)
        self.process.errorOccurred.connect(self.handle_process_error)
        self.output.append("Starting launcher...\n")
        self.process.start(command[0], command[1:])

    def copy_output(self):
        QApplication.clipboard().setText(self.copyable_output_text())
        self.output.append("\nLaunch command and output copied to clipboard.")

    def copyable_output_text(self) -> str:
        return format_launch_output_report(self.command_text, self.output.toPlainText())

    def read_output(self):
        data = bytes(self.process.readAllStandardOutput()).decode("utf-8", errors="replace")
        if data:
            self.output.moveCursor(QTextCursor.End)
            self.output.insertPlainText(data)
            self.output.moveCursor(QTextCursor.End)

    def handle_finished(self, exit_code: int, exit_status):
        self.read_output()
        if exit_code == 0:
            self.output.append(
                f"\n{self.handoff_label.title()} exited successfully, which means WolfLauncher handed control "
                "to Steam. Steam may still need time to start, update, initialize Proton or show a BattlEye prompt."
            )
            self.start_post_handoff_process_checks()
        else:
            self.output.append(
                f"\nLauncher exited with code {exit_code}. "
                "Check the messages above for the script or Steam error."
            )
        self.close_button.setEnabled(True)

    def handle_process_error(self, error):
        if error == QProcess.ProcessError.FailedToStart:
            self.output.append(
                "\nLaunch command could not start. Check that the configured launcher or Steam command exists."
            )
            self.close_button.setEnabled(True)

class NativeLaunchPreviewDialog(PostHandoffProcessCheckMixin, QDialog):
    def __init__(self, parent, title: str, preview_text: str, command: list[str]):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.resize(860, 540)
        self.command = command
        self.process = QProcess(self)
        self.process.setProcessChannelMode(QProcess.MergedChannels)

        layout = QVBoxLayout(self)
        self.output = QTextEdit()
        self.output.setReadOnly(True)
        self.output.setPlainText(preview_text)
        layout.addWidget(self.output)

        button_row = QHBoxLayout()
        copy = QPushButton("Copy")
        copy.clicked.connect(self.copy_preview)
        self.launch_button = QPushButton("Launch native experimental")
        self.launch_button.setEnabled(bool(command))
        self.launch_button.clicked.connect(self.launch_native_experimental)
        close = QPushButton("Close")
        close.clicked.connect(self.close)
        button_row.addStretch(1)
        button_row.addWidget(copy)
        button_row.addWidget(self.launch_button)
        button_row.addWidget(close)
        layout.addLayout(button_row)

        self.process.readyReadStandardOutput.connect(self.read_output)
        self.process.finished.connect(self.handle_finished)
        self.process.errorOccurred.connect(self.handle_process_error)

    def copy_preview(self):
        QApplication.clipboard().setText(self.output.toPlainText())

    def launch_native_experimental(self):
        reply = QMessageBox.warning(
            self,
            "Experimental native launch",
            "This bypasses the external dayz-launcher.sh script and hands the previewed command directly to Steam.\n\n"
            "Use it only for testing the new native launcher path. Continue?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if reply != QMessageBox.Yes:
            return
        if not self.command:
            return

        self.launch_button.setEnabled(False)
        self.output.moveCursor(QTextCursor.End)
        self.output.append("\n\nStarting experimental native launch...\n")
        self.process.start(self.command[0], self.command[1:])

    def read_output(self):
        data = bytes(self.process.readAllStandardOutput()).decode("utf-8", errors="replace")
        if data:
            self.output.moveCursor(QTextCursor.End)
            self.output.insertPlainText(data)
            self.output.moveCursor(QTextCursor.End)

    def handle_finished(self, exit_code: int, exit_status):
        self.read_output()
        if exit_code == 0:
            self.output.append(
                "\nExperimental native command handed off to Steam successfully. "
                "Steam may still need time to start, update, initialize Proton or show a BattlEye prompt."
            )
            self.start_post_handoff_process_checks()
        else:
            self.output.append(
                f"\nExperimental native command exited with code {exit_code}. "
                "Check the messages above for the Steam error."
            )
        self.launch_button.setEnabled(bool(self.command))

    def handle_process_error(self, error):
        if error == QProcess.ProcessError.FailedToStart:
            self.output.append(
                "\nExperimental native command could not start. Check Steam detection in Settings health."
            )
            self.launch_button.setEnabled(bool(self.command))


class PromoteServerDialog(QDialog):
    def __init__(self, parent, name: str, group: str = "Discovered"):
        super().__init__(parent)
        self.setWindowTitle("Promote to curated")
        self.resize(420, 140)

        layout = QVBoxLayout(self)
        form = QFormLayout()
        self.name = QLineEdit(name)
        self.group = QLineEdit(group)
        form.addRow("Name", self.name)
        form.addRow("Group", self.group)
        layout.addLayout(form)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def curated_name(self) -> str:
        return self.name.text().strip()

    def curated_group(self) -> str:
        return self.group.text().strip() or "Discovered"


class EditCuratedServerDialog(QDialog):
    def __init__(self, parent, server: Server, title: str = "Edit curated server"):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.resize(440, 240)

        layout = QVBoxLayout(self)
        form = QFormLayout()
        self.name = QLineEdit(server.name)
        self.group = QLineEdit(server.group)
        self.host = QLineEdit(server.host)
        self.game_port = QSpinBox()
        self.game_port.setRange(1, 65535)
        self.game_port.setValue(server.game_port)
        self.query_port = QSpinBox()
        self.query_port.setRange(1, 65535)
        self.query_port.setValue(server.query_port)
        self.favourite = QCheckBox("Favourite")
        self.favourite.setChecked(server.favourite)
        form.addRow("Name", self.name)
        form.addRow("Group", self.group)
        form.addRow("Host", self.host)
        form.addRow("Game port", self.game_port)
        form.addRow("Query port", self.query_port)
        form.addRow("", self.favourite)
        layout.addLayout(form)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def curated_server(self) -> Server:
        return Server(
            name=self.name.text().strip(),
            group=self.group.text().strip() or "Community",
            host=self.host.text().strip(),
            game_port=self.game_port.value(),
            query_port=self.query_port.value(),
            favourite=self.favourite.isChecked(),
        )


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("WolfLauncher")
        self.resize(1350, 720)

        self.config_path = Path(__file__).resolve().parent.parent / "servers.yaml"
        self.servers = load_servers(self.config_path)
        self.settings = load_settings()
        self.favourites = load_favourites()
        self.worker = None
        self.mod_worker = None
        self.discovery_worker = None
        self.web_api_worker = None
        self.battlemetrics_worker = None
        self.wolfapi_worker = None
        self.enrichment_worker = None
        self.last_mod_result = None
        self.active_mod_server_key = ""
        self.pending_mod_check_row = None
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
        self.launch_engine.addItems(["External launcher", "Native experimental"])
        self.launch_engine.setCurrentText(
            "Native experimental"
            if str(self.settings.get("launch_engine") or "external") == "native"
            else "External launcher"
        )
        self.launch_engine.currentTextChanged.connect(self.handle_settings_changed)
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

        tabs = QTabWidget()
        tabs.addTab(self._build_servers_tab(), "Servers")
        tabs.addTab(self._build_server_browser_tab(), "Server Browser")
        tabs.addTab(self._build_mods_tab(), "Mods")
        tabs.addTab(self._build_settings_tab(), "Settings")
        self.setCentralWidget(tabs)

        self.apply_refresh_timer()
        self.refresh_statuses()
        self.refresh_server_browser()
        self.update_settings_health()
        QTimer.singleShot(0, self.check_initial_server_mods)
        QTimer.singleShot(30000, self.maybe_auto_refresh_configured_provider)

    def _build_servers_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)

        settings = QFormLayout()
        launcher_row = QHBoxLayout()
        launcher_row.addWidget(self.launcher_path)
        browse = QPushButton("Browse")
        browse.clicked.connect(self.browse_launcher)
        launcher_row.addWidget(browse)
        settings.addRow("Launcher script", launcher_row)
        player_name_row = QHBoxLayout()
        player_name_row.addWidget(self.player_name)
        self.player_name.returnPressed.connect(self.save_player_name)
        set_player_name = QPushButton("Set name")
        set_player_name.clicked.connect(self.save_player_name)
        player_name_row.addWidget(set_player_name)
        settings.addRow("Player name", player_name_row)
        settings.addRow("Auto refresh", self.refresh_seconds)
        settings.addRow("Status", self.last_refresh_label)
        layout.addLayout(settings)

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
            values = [
                "★" if server.favourite else "☆",
                server.group,
                server.name,
                "",
                server.host,
                "Checking...",
                str(server.game_port),
                str(server.query_port),
                "Checking...",
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
        save = QPushButton("Save settings")
        save.clicked.connect(self.save_user_settings)
        buttons.addWidget(add_server)
        buttons.addWidget(self.refresh_status_button)
        buttons.addWidget(self.launch_button)
        buttons.addWidget(save)
        layout.addLayout(buttons)
        return widget

    def _build_server_browser_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)

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
        filters.addWidget(QLabel("Map"))
        filters.addWidget(self.browser_map)

        self.browser_version = QComboBox()
        self.browser_version.addItem("Any version")
        self.browser_version.currentTextChanged.connect(self.refresh_server_browser)
        filters.addWidget(QLabel("Version"))
        filters.addWidget(self.browser_version)

        self.browser_source = QComboBox()
        self.browser_source.addItem("Any source")
        self.browser_source.currentTextChanged.connect(self.refresh_server_browser)
        filters.addWidget(QLabel("Source"))
        filters.addWidget(self.browser_source)

        self.browser_sort = QComboBox()
        self.browser_sort.addItems(["Name", "Players", "Ping", "Map", "Version", "Last checked", "Last seen"])
        self.browser_sort.currentTextChanged.connect(self.refresh_server_browser)
        filters.addWidget(QLabel("Sort"))
        filters.addWidget(self.browser_sort)

        self.browser_descending = QCheckBox("Desc")
        self.browser_descending.stateChanged.connect(self.refresh_server_browser)
        filters.addWidget(self.browser_descending)

        self.browser_limit = QComboBox()
        self.browser_limit.addItems(["200", "500", "1000"])
        self.browser_limit.currentTextChanged.connect(self.refresh_server_browser)
        filters.addWidget(QLabel("Limit"))
        filters.addWidget(self.browser_limit)
        layout.addLayout(filters)

        self.browser_summary = QLabel("Cached discovered servers: loading")
        layout.addWidget(self.browser_summary)

        self.browser_table = QTableWidget(0, 14)
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
        clear_filters = QPushButton("Reset filters")
        clear_filters.clicked.connect(self.reset_browser_filters)
        refresh = QPushButton("Refresh cache view")
        refresh.clicked.connect(self.refresh_server_browser)
        buttons.addStretch(1)
        buttons.addWidget(self.refresh_database_button)
        buttons.addWidget(self.enrich_visible_button)
        buttons.addWidget(promote)
        buttons.addWidget(clear_filters)
        buttons.addWidget(refresh)
        layout.addLayout(buttons)
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
        open_selected = QPushButton("Open selected Workshop page")
        open_selected.clicked.connect(self.open_selected_workshop_page)
        open_missing = QPushButton("Open missing Workshop pages")
        open_missing.clicked.connect(self.open_missing_workshop_pages)
        buttons.addWidget(check)
        buttons.addWidget(native_preview)
        self.mod_filter = QComboBox()
        self.mod_filter.addItems(["All mods", "Missing only", "Installed only"])
        self.mod_filter.currentTextChanged.connect(self.apply_mod_filter)
        buttons.addWidget(open_selected)
        buttons.addWidget(open_missing)
        buttons.addWidget(QLabel("Filter"))
        buttons.addWidget(self.mod_filter)
        layout.addLayout(buttons)

        self.mods_table = QTableWidget(0, 6)
        self.mods_table.setHorizontalHeaderLabels([
            "Installed",
            "Workshop ID",
            "Required Name",
            "Installed Name",
            "Workshop URL",
            "Notes",
        ])
        self.mods_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.mods_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.mods_table.setSortingEnabled(True)
        self.mods_table.cellDoubleClicked.connect(self.handle_mod_double_clicked)
        self.mods_table.setContextMenuPolicy(Qt.CustomContextMenu)
        self.mods_table.customContextMenuRequested.connect(self.show_mod_context_menu)
        layout.addWidget(self.mods_table)
        return widget

    def _build_settings_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)

        launcher_settings = QFormLayout()
        launcher_settings.addRow("Launch engine", self.launch_engine)
        launcher_settings.addRow("Steam install mode", self.native_steam_mode)

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
        launcher_settings.addRow("Server API provider", self.discovery_provider)

        self.discovery_limit = QSpinBox()
        self.discovery_limit.setRange(1, 10000)
        self.discovery_limit.setValue(int(self.settings.get("discovery_limit", 500)))
        self.discovery_limit.valueChanged.connect(self.handle_settings_changed)
        launcher_settings.addRow("Refresh limit", self.discovery_limit)

        self.discovery_auto_refresh = QCheckBox("Refresh selected provider quietly after startup")
        self.discovery_auto_refresh.setChecked(bool(self.settings.get("discovery_auto_refresh", False)))
        self.discovery_auto_refresh.stateChanged.connect(self.handle_settings_changed)
        launcher_settings.addRow("Automatic refresh", self.discovery_auto_refresh)

        self.steam_web_api_key = QLineEdit(
            str(self.settings.get("steam_web_api_key") or "")
            or os.environ.get("WOLFLAUNCHER_STEAM_WEB_API_KEY")
            or os.environ.get("STEAM_WEB_API_KEY")
            or ""
        )
        self.steam_web_api_key.setEchoMode(QLineEdit.Password)
        self.steam_web_api_key.setPlaceholderText("Steam Web API key")
        self.steam_web_api_key.editingFinished.connect(self.handle_settings_changed)
        launcher_settings.addRow("Steam API key", self.steam_web_api_key)

        self.steam_master_endpoints = QLineEdit(str(self.settings.get("steam_master_endpoints") or ""))
        self.steam_master_endpoints.setPlaceholderText("Comma separated host[:port]")
        self.steam_master_endpoints.editingFinished.connect(self.handle_settings_changed)
        launcher_settings.addRow("Steam masters", self.steam_master_endpoints)
        layout.addLayout(launcher_settings)

        row = QHBoxLayout()
        health = QPushButton("Check health")
        health.clicked.connect(self.update_settings_health)
        copy_health = QPushButton("Copy health")
        copy_health.clicked.connect(self.copy_settings_health)
        copy_diagnostics = QPushButton("Copy diagnostics")
        copy_diagnostics.clicked.connect(self.copy_diagnostics_report)
        import_file = QPushButton("Import server list")
        import_file.clicked.connect(self.import_server_cache_file)
        save = QPushButton("Save settings")
        save.clicked.connect(self.save_user_settings)
        row.addStretch(1)
        row.addWidget(health)
        row.addWidget(copy_health)
        row.addWidget(copy_diagnostics)
        row.addWidget(import_file)
        row.addWidget(save)
        layout.addLayout(row)

        self.system_summary = QLabel("Checking Steam and DayZ installation...")
        layout.addWidget(self.system_summary)

        self.health_table = QTableWidget(0, 3)
        self.health_table.setHorizontalHeaderLabels(["Check", "Status", "Details"])
        self.health_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.health_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.health_table.setContextMenuPolicy(Qt.CustomContextMenu)
        self.health_table.customContextMenuRequested.connect(self.show_health_context_menu)
        layout.addWidget(self.health_table)
        return widget

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
        value = str(self.settings.get(f"last_{provider}_auto_refresh_at") or "")
        if not value:
            return True
        try:
            last_refresh = datetime.fromisoformat(value)
        except ValueError:
            return True
        if last_refresh.tzinfo is None:
            last_refresh = last_refresh.replace(tzinfo=timezone.utc)
        return datetime.now(timezone.utc) - last_refresh >= timedelta(hours=24)

    def mark_auto_refresh(self, provider: str):
        self.settings[f"last_{provider}_auto_refresh_at"] = (
            datetime.now(timezone.utc).replace(microsecond=0).isoformat()
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
        self.enrichment_worker.enrichment_ready.connect(self.handle_enrichment_ready)
        self.enrichment_worker.start()

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
            return str(self.settings.get("launch_engine") or "external")
        return "native" if self.launch_engine.currentText() == "Native experimental" else "external"

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

    def handle_native_steam_mode_changed(self, *_args):
        self.last_mod_result = None
        if hasattr(self, "mod_summary"):
            self.mod_summary.setText("Steam install changed. Recheck selected server mods.")
        if hasattr(self, "mods_table"):
            self.mods_table.setRowCount(0)
        self.handle_settings_changed()

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
        if self.worker and self.worker.isRunning():
            return
        self._set_status_refresh_enabled(False)
        self.last_refresh_label.setText("Last updated: refreshing...")
        self.worker = StatusWorker(self.servers)
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
        style_terms = self._browser_style_terms()
        limit = int(self.browser_limit.currentText())

        servers = server_cache.search_servers(
            self.server_cache,
            text=self.browser_search.text(),
            online_only=self.browser_online_only.isChecked(),
            map_name=map_name,
            version=version,
            source=source,
            style_terms=style_terms,
            modded=modded,
            sort_by=sort_key,
            descending=self.browser_descending.isChecked(),
            limit=limit,
        )
        match_count = server_cache.count_search_servers(
            self.server_cache,
            text=self.browser_search.text(),
            online_only=self.browser_online_only.isChecked(),
            map_name=map_name,
            version=version,
            source=source,
            style_terms=style_terms,
            modded=modded,
        )
        self.browser_servers = servers

        self.browser_table.setSortingEnabled(False)
        self.browser_table.setRowCount(len(servers))
        for row, server in enumerate(servers):
            flags = []
            if server.password:
                flags.append("Password")
            if server.modded:
                flags.append("Mods")
            live_name = self._browser_live_name_text(server)
            values = [
                server.name,
                live_name,
                server.host,
                str(server.game_port),
                str(server.query_port),
                "ONLINE" if server.online else "OFFLINE",
                server.map_name,
                self._players_text(server.players_current, server.players_max),
                f"{server.ping_ms}ms" if server.ping_ms is not None else "",
                server.version,
                ", ".join(flags) if flags else "Vanilla/unknown",
                server.last_checked,
                server.last_seen,
                server.source,
            ]
            sort_values = [
                server.name,
                live_name or server.name,
                server.host,
                server.game_port,
                server.query_port,
                0 if server.online else 1,
                server.map_name,
                server.players_current,
                server.ping_ms,
                server.version,
                ", ".join(flags) if flags else "Vanilla/unknown",
                server.last_checked,
                server.last_seen,
                server.source,
            ]
            for column, value in enumerate(values):
                item = SortableTableWidgetItem(value, sort_values[column])
                item.setData(Qt.UserRole, server.cache_key)
                if column == 0 and live_name:
                    item.setToolTip(f"Live name: {server.server_name}")
                elif column == 1 and not live_name:
                    item.setToolTip("Same as display name, or not reported yet.")
                elif column == 11 and not server.last_checked:
                    item.setToolTip("This row has not been live-checked yet.")
                elif column == 12 and not server.last_seen:
                    item.setToolTip("This row has not been seen online yet.")
                if column == 5:
                    item.setForeground(QColor("#6ee16e" if server.online else "#ff6b6b"))
                self.browser_table.setItem(row, column, item)

        self.browser_table.resizeColumnsToContents()
        self.browser_table.setSortingEnabled(True)
        self.browser_summary.setText(self._browser_summary_text(servers, match_count, limit))

    def _refresh_browser_filter_options(self):
        self._set_combo_filter_options(
            self.browser_map,
            "Any map",
            server_cache.distinct_values(self.server_cache, "map"),
        )
        self._set_combo_filter_options(
            self.browser_version,
            "Any version",
            server_cache.distinct_values(self.server_cache, "version"),
        )
        self._set_combo_filter_options(
            self.browser_source,
            "Any source",
            server_cache.distinct_values(self.server_cache, "source"),
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

    def _browser_style_terms(self) -> list[str]:
        style = self.browser_style.currentText()
        if style == "PvE":
            return ["pve", "p.v.e", "no pvp", "no kos", "no-kos", "no kill on sight"]
        if style == "PvP":
            return ["pvp", "p.v.p"]
        return []

    def _browser_summary_text(self, servers, match_count: int, limit: int) -> str:
        summary = server_cache.cache_summary(self.server_cache)
        shown = len(servers)
        total = summary["total"]
        if total == 0:
            return "Cached discovered servers: empty"

        parts = [
            f"Showing {shown} of {match_count} matching",
            f"{total} cached",
            f"{summary['online']} online",
            f"{summary['checked']} checked",
            f"{summary['seen']} seen online",
        ]
        if shown == limit and match_count > shown:
            parts[0] = f"Showing first {shown} of {match_count} matching"
        elif shown == 0:
            parts[0] = f"No matches from {total} cached"
        return "Cached discovered servers: " + " | ".join(parts)

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

    def _players_text(self, current: int | None, maximum: int | None) -> str:
        if current is None and maximum is None:
            return ""
        if maximum is None:
            return str(current)
        if current is None:
            return f"?/{maximum}"
        return f"{current}/{maximum}"

    def _set_item(self, row: int, column: int, text: str, colour: str | None = None):
        item = QTableWidgetItem(text)
        if colour:
            item.setForeground(QColor(colour))
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
        self.table.selectRow(len(self.servers) - 1)
        self.update_launch_button_text()
        self.statusBar().showMessage(f"Added curated server: {server.name}", 7000)

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
        values = {
            0: "★" if server.favourite else "☆",
            1: server.group,
            2: server.name,
            3: "",
            4: server.host,
            5: "Not checked",
            6: str(server.game_port),
            7: str(server.query_port),
            8: "Not checked",
            9: "",
            10: "",
            11: "",
            12: "",
            13: "",
            14: "",
            15: "",
        }
        for column, value in values.items():
            item = QTableWidgetItem(value)
            item.setData(Qt.UserRole, row)
            self.table.setItem(row, column, item)
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
        row = self.table.currentRow()
        if row >= 0 and row < len(self.servers):
            self.launch_button.setText(f"Launch {self.servers[row].name}")
        else:
            self.launch_button.setText("Launch selected server")

    def check_initial_server_mods(self):
        if self.servers and self.table.currentRow() < 0:
            last_row = self.saved_selected_row()
            row = last_row if 0 <= last_row < len(self.servers) else 0
            self.table.selectRow(row)
        self.check_selected_server_mods(silent=True)

    def handle_server_selection_changed(self):
        self.update_launch_button_text()
        if not hasattr(self, "mod_summary"):
            return
        self.check_selected_server_mods(silent=True)

    def check_selected_server_mods(self, silent: bool = False, force: bool = False):
        row = self.table.currentRow()
        if row < 0:
            if not silent:
                QMessageBox.warning(self, "No server selected", "Select a server first.")
            return

        self.check_server_mods_for_row(row, silent=silent, force=force)

    def check_server_mods_for_row(self, row: int, silent: bool = False, force: bool = False):
        if row < 0 or row >= len(self.servers):
            return

        server = self.servers[row]
        if not hasattr(self, "mod_summary") or not hasattr(self, "mods_table"):
            return
        selected_key = server_key(server)
        if (
            not force
            and self.last_mod_result
            and server_key(self.last_mod_result.server) == selected_key
        ):
            if self.mods_table.rowCount() == 0:
                self.display_mods_result(self.last_mod_result)
            return

        if self.mod_worker and self.mod_worker.isRunning():
            if self.active_mod_server_key != selected_key:
                self.pending_mod_check_row = row
            return

        install = self.selected_steam_install() if self.launch_engine_key() == "native" else best_install()
        workshop_dir = install.workshop_dir if install else None
        if not workshop_dir:
            self.last_mod_result = None
            self.mod_summary.setText(
                "Workshop folder not detected for the current launch mode. "
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

        self.mod_summary.setText(f"Checking required mods for {server.name}...")
        self.mods_table.setRowCount(0)
        self.active_mod_server_key = selected_key
        self.pending_mod_check_row = None
        self.mod_worker = ModWorker(server, workshop_dir)
        self.mod_worker.mods_ready.connect(self.update_mods_table)
        self.mod_worker.start()

    def update_mods_table(self, result: ModCheckResult):
        self.active_mod_server_key = ""
        current_row = self.table.currentRow()
        current_server = self.servers[current_row] if 0 <= current_row < len(self.servers) else None
        if current_server and server_key(current_server) != server_key(result.server):
            pending_row = self.pending_mod_check_row if self.pending_mod_check_row is not None else current_row
            self.pending_mod_check_row = pending_row
            self._check_pending_server_mods()
            return

        self.last_mod_result = result
        self.display_mods_result(result)
        self._check_pending_server_mods()

    def display_mods_result(self, result: ModCheckResult):
        self.mods_table.setSortingEnabled(False)
        if not result.ok:
            self.mod_summary.setText(f"Could not check mods for {result.server.name}: {result.error}")
            self.mods_table.setRowCount(0)
            self.mods_table.setSortingEnabled(True)
            return

        required = result.required_mods
        missing = result.missing_mods
        if not required:
            self.mod_summary.setText(
                f"{result.server.name}: no required mods reported by the server API. "
                f"Installed Workshop mods found locally: {result.installed_count}."
            )
        else:
            self.mod_summary.setText(
                f"{result.server.name}: Required {len(required)} | "
                f"Installed {len(required) - len(missing)} | Missing {len(missing)} | "
                f"Local Workshop mods found: {result.installed_count}"
            )

        self.mods_table.setRowCount(len(required))
        for row, mod in enumerate(required):
            status_text = "✓ Installed" if mod.installed else "✗ Missing"
            note = "Installed" if mod.installed else "Missing - subscribe in Steam Workshop"
            values = [
                status_text,
                mod.workshop_id,
                mod.name or "Unknown",
                mod.installed_name or "",
                mod.workshop_url,
                note,
            ]
            for column, value in enumerate(values):
                item = QTableWidgetItem(value)
                item.setData(Qt.UserRole, mod.workshop_id)
                if column == 0:
                    item.setForeground(QColor("#6ee16e" if mod.installed else "#ff6b6b"))
                self.mods_table.setItem(row, column, item)
        self.mods_table.resizeColumnsToContents()
        self.mods_table.setSortingEnabled(True)
        self.mods_table.sortItems(0, Qt.DescendingOrder)
        self.apply_mod_filter()

    def _check_pending_server_mods(self):
        if self.pending_mod_check_row is None:
            return
        if self.mod_worker and self.mod_worker.isRunning():
            QTimer.singleShot(50, self._check_pending_server_mods)
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
        self.promote_selected_discovered_server()

    def open_workshop_page_for_mod_row(self, row: int):
        if row < 0:
            return
        url = self._mods_cell(row, 4)
        if not url:
            workshop_id = self._mods_cell(row, 1)
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
        open_action.triggered.connect(lambda: self.open_workshop_page_for_mod_row(row))
        copy_id_action.triggered.connect(lambda: self.copy_to_clipboard(self._mods_cell(row, 1), "Workshop ID"))
        copy_name_action.triggered.connect(lambda: self.copy_to_clipboard(self._mods_cell(row, 2) or self._mods_cell(row, 3), "Mod name"))
        copy_url_action.triggered.connect(lambda: self.copy_to_clipboard(self._mods_cell(row, 4), "Workshop URL"))
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
        promote_action = QAction("Promote to curated", self)
        copy_connect_action = QAction("Copy connect address", self)
        copy_host_action = QAction("Copy host", self)
        copy_details_action = QAction("Copy server details", self)
        promote_action.triggered.connect(self.promote_selected_discovered_server)
        copy_connect_action.triggered.connect(
            lambda: self.copy_to_clipboard(server.connect_target, "Connect address")
        )
        copy_host_action.triggered.connect(
            lambda: self.copy_to_clipboard(server.host, "Server host")
        )
        copy_details_action.triggered.connect(
            lambda: self.copy_to_clipboard(self.discovered_server_details_text(server), "Server details")
        )
        menu.addAction(promote_action)
        menu.addSeparator()
        menu.addAction(copy_connect_action)
        menu.addAction(copy_host_action)
        menu.addAction(copy_details_action)
        menu.exec(self.browser_table.viewport().mapToGlobal(pos))

    def discovered_server_details_text(self, server) -> str:
        flags = []
        if server.password:
            flags.append("Password")
        if server.modded:
            flags.append("Mods")
        lines = [
            server.name,
        ]
        if self._browser_live_name_text(server):
            lines.append(f"Live name: {server.server_name}")
        lines.extend([
            server.connect_target,
            f"Query port: {server.query_port}",
            f"Map: {server.map_name}",
            f"Players: {self._players_text(server.players_current, server.players_max)}",
            f"Version: {server.version}",
            f"Flags: {', '.join(flags) if flags else 'Vanilla/unknown'}",
            f"Last checked: {server.last_checked or 'Never'}",
            f"Last seen: {server.last_seen or 'Never'}",
            f"Source: {server.source}",
        ])
        return "\n".join(lines).strip()

    def _browser_live_name_text(self, server) -> str:
        live_name = (server.server_name or "").strip()
        display_name = (server.name or "").strip()
        if not live_name or live_name.casefold() == display_name.casefold():
            return ""
        return live_name

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
        apply_live_port_action = QAction("Apply live connect port", self)
        copy_connect_action = QAction("Copy connect address", self)
        copy_details_action = QAction("Copy server details", self)
        edit_action = QAction("Edit curated server", self)
        toggle_fav_action = QAction("Toggle favourite", self)
        remove_action = QAction("Remove from curated list", self)
        add_action.triggered.connect(self.add_curated_server)
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
        if not self.last_mod_result:
            QMessageBox.warning(self, "No mod check yet", "Check selected server mods first.")
            return
        missing = self.last_mod_result.missing_mods
        if not missing:
            QMessageBox.information(self, "No missing mods", "All required mods appear to be installed.")
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

    def preview_native_launch(self):
        if not self.last_mod_result or not self.last_mod_result.ok:
            QMessageBox.warning(
                self,
                "No mod check yet",
                "Check selected server mods successfully before preparing a native launch preview.",
            )
            return

        row = self.table.currentRow()
        if row < 0:
            QMessageBox.warning(self, "No server selected", "Select a curated server first.")
            return
        server = self.servers[row]
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
            )
        except NativeLaunchError as exc:
            QMessageBox.critical(self, "Native preview failed", exc.user_message())
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
        selected_install = select_steam_install(self.native_steam_mode_key(), install_rows)
        self.system_summary.setText(selected_install_summary(selected_install))

        path = Path(self.launcher_path.text()).expanduser()
        launch_engine = self.launch_engine_key()
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

        steam = selected_install
        auto_steam_report = steam_selection_report("auto", install_rows)
        steam_report = steam_selection_report(self.native_steam_mode_key(), install_rows)
        steam_status, steam_detail = steam_report.status, steam_report.detail
        tools = ["python3", "gamedig", "node", "npm", "dig", "curl", "jq", "gawk"]
        missing_tools = [command for command in tools if not shutil.which(command)]
        launcher_candidates = [str(candidate) for candidate in DEFAULT_LAUNCHER_PATHS if candidate.exists()]
        prime_report = prime_environment_report()
        prime_helpers = prime_helper_report()
        launch_options = steam_launch_options_report()
        process_check = dayz_process_check()
        launch_report = launch_troubleshooting_report(
            self.native_steam_mode_key(),
            install_rows,
            process_check,
        )

        rows = [
            (
                "Launch engine",
                "WARN" if launch_engine == "native" else "OK",
                "Native experimental" if launch_engine == "native" else "External launcher",
            ),
            (
                "Launcher script",
                "OK" if launch_engine == "native" or (path.exists() and path.is_file()) else "MISSING",
                "Not required for native experimental mode" if launch_engine == "native" else str(path),
            ),
            (
                "Server API",
                provider_status,
                provider_detail,
            ),
            (
                "Required tools",
                "OK" if not missing_tools else "WARN",
                "All found" if not missing_tools else "Missing: " + ", ".join(missing_tools),
            ),
            (
                "PRIME environment",
                prime_report.status,
                prime_report.summary,
            ),
            (
                "PRIME helpers",
                prime_helpers.status,
                prime_helpers.summary,
            ),
            (
                "Steam launch options",
                launch_options.status,
                launch_options.summary,
            ),
            (
                "Selected Steam",
                steam_status,
                steam_detail,
            ),
            (
                "Auto Steam",
                auto_steam_report.status,
                auto_steam_report.detail,
            ),
            (
                "Launch troubleshooting",
                launch_report.status,
                "; ".join(launch_report.next_steps),
            ),
            (
                "Steam candidates",
                "OK" if steam_report.candidates else "WARN",
                steam_selection_candidates_detail(steam_report),
            ),
            (
                "DayZ process",
                "OK",
                process_check.detail,
            ),
            (
                "DayZ",
                "OK" if steam and steam.dayz_dir else "MISSING",
                str(steam.dayz_dir) if steam and steam.dayz_dir else "Not detected",
            ),
            (
                "Workshop",
                "OK" if steam and steam.workshop_dir else "MISSING",
                str(steam.workshop_dir) if steam and steam.workshop_dir else "Not detected",
            ),
            (
                "Proton compatdata",
                "OK",
                proton_compatdata_detail(steam),
            ),
            (
                "Configured Steam installs",
                "OK" if any(item.root or item.executable for item in install_rows) else "WARN",
                ", ".join(self._install_summary(item) for item in install_rows if item.root or item.executable)
                or "No native or Flatpak Steam roots found",
            ),
            (
                "Launcher candidates",
                "OK" if launcher_candidates else "WARN",
                ", ".join(launcher_candidates) or "No default candidate exists",
            ),
        ]

        self.health_table.setRowCount(len(rows))
        for row, (name, status, details) in enumerate(rows):
            self._set_health_item(row, 0, name)
            self._set_health_item(row, 1, status, self._health_colour(status))
            self._set_health_item(row, 2, details)
        self.health_table.resizeColumnsToContents()

    def _install_summary(self, install) -> str:
        return steam_install_summary(install)

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
        row = self.table.currentRow()
        if row < 0:
            QMessageBox.warning(self, "No server selected", "Select a server first.")
            return

        server = self.servers[row]
        self.save_user_settings(silent=True)

        if not self.confirm_launch_preflight(server):
            return

        try:
            command = self.build_selected_launch_command(server, row)
        except NativeLaunchError as exc:
            self.show_native_launch_error(exc)
            return
        except LaunchError as exc:
            QMessageBox.critical(self, "Launch failed", str(exc))
            return

        handoff_label = "native launch command" if self.launch_engine_key() == "native" else "external launcher"
        dialog = LaunchDialog(self, command, f"Launching {server.name}", handoff_label)
        dialog.exec()

    def build_selected_launch_command(self, server: Server, row: int) -> list[str]:
        # Launch with the resolved IP address when available. This mirrors the
        # original terminal menu and avoids DayZSA API failures with some DNS
        # hostnames.
        launch_server = server
        resolved_item = self.table.item(row, 5)
        resolved_ip = resolved_item.text().strip() if resolved_item else ""
        if resolved_ip:
            launch_server = Server(
                name=server.name,
                group=server.group,
                host=resolved_ip,
                game_port=server.game_port,
                query_port=server.query_port,
                favourite=server.favourite,
            )

        player_name = self.player_name.text().strip() or DEFAULT_PLAYER_NAME
        if self.launch_engine_key() == "native":
            install = self.selected_steam_install()
            if not install:
                raise NativeLaunchError(
                    "Selected Steam installation not detected",
                    stage="Steam detection",
                    guidance="Open Settings health and confirm the selected native or Flatpak Steam install can be detected.",
                )
            required_mods = None
            if self.last_mod_result and server_key(self.last_mod_result.server) == server_key(server):
                required_mods = self.last_mod_result.required_mods
            try:
                prepared = prepare_native_launch(install, launch_server, player_name, required_mods)
            except NativeLaunchError as exc:
                raise exc.with_details(
                    self.native_launch_failure_details(
                        install,
                        launch_server,
                        player_name,
                        required_mods,
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

    def native_launch_failure_details(
        self,
        install: SteamInstall,
        server: Server,
        player_name: str,
        required_mods,
    ) -> str:
        if required_mods is None:
            return (
                "Native launch parity report unavailable.\n\n"
                "Run Check selected server mods successfully before launching to include required Workshop IDs "
                "and prepared mod-link details in launch failure reports."
            )
        try:
            report = prepare_native_launch_parity_report(
                install,
                self.launcher_path.text(),
                server,
                player_name,
                required_mods,
            )
        except NativeLaunchError as detail_error:
            return (
                "Native launch parity report unavailable.\n\n"
                f"Report generation failed during {detail_error.stage}: {detail_error.user_message()}"
            )
        return format_native_launch_parity_report(report)

    def confirm_launch_preflight(self, server: Server) -> bool:
        install = self.selected_steam_install() if self.launch_engine_key() == "native" else best_install()
        if not install or not install.dayz_dir:
            QMessageBox.critical(
                self,
                "DayZ not detected",
                "WolfLauncher could not detect a DayZ installation. Check Settings health before launching.",
            )
            return False

        if not install.workshop_dir:
            QMessageBox.critical(
                self,
                "Workshop folder not detected",
                "WolfLauncher could not detect the DayZ Workshop folder. Check Settings health before launching.",
            )
            return False

        if not install.running:
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

        if self.last_mod_result and server_key(self.last_mod_result.server) == server_key(server):
            missing = self.last_mod_result.missing_mods
            if missing:
                names = "\n".join(f"- {mod.name or mod.workshop_id}" for mod in missing[:12])
                if len(missing) > 12:
                    names += f"\n- ...and {len(missing) - 12} more"
                if self.launch_engine_key() == "native":
                    box = QMessageBox(self)
                    box.setIcon(QMessageBox.Warning)
                    box.setWindowTitle("Missing required mods")
                    box.setText(f"{server.name} is missing {len(missing)} required mod(s).")
                    box.setInformativeText(
                        f"{names}\n\n"
                        "The native experimental engine needs every required Workshop directory before it can "
                        "build the DayZ mod command."
                    )
                    open_button = box.addButton("Open Workshop", QMessageBox.ButtonRole.ActionRole)
                    cancel_button = box.addButton("Cancel", QMessageBox.ButtonRole.RejectRole)
                    box.setDefaultButton(cancel_button)
                    box.exec()
                    if box.clickedButton() == open_button:
                        self.open_missing_workshop_pages()
                    return False

                box = QMessageBox(self)
                box.setIcon(QMessageBox.Warning)
                box.setWindowTitle("Missing required mods")
                box.setText(f"{server.name} is missing {len(missing)} required mod(s).")
                box.setInformativeText(
                    f"{names}\n\nOpen the missing Workshop page(s), launch anyway, or cancel?"
                )
                open_button = box.addButton("Open Workshop", QMessageBox.ButtonRole.ActionRole)
                launch_button = box.addButton("Launch anyway", QMessageBox.ButtonRole.DestructiveRole)
                cancel_button = box.addButton("Cancel", QMessageBox.ButtonRole.RejectRole)
                box.setDefaultButton(cancel_button)
                box.exec()
                clicked = box.clickedButton()
                if clicked == open_button:
                    self.open_missing_workshop_pages()
                    return False
                if clicked != launch_button:
                    return False
        else:
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
        self.save_user_settings(silent=True)
        self.server_cache.close()
        super().closeEvent(event)


def main():
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
