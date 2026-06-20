from pathlib import Path
from datetime import datetime
import sys

from PySide6.QtCore import QTimer, QThread, Signal, QUrl, Qt, QPoint, QProcess
from PySide6.QtWidgets import (
    QApplication,
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
    QSpinBox,
    QTabWidget,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)
from PySide6.QtGui import QColor, QDesktopServices, QAction, QTextCursor

from .config import find_default_launcher_path, load_servers
from .diagnostics import run_diagnostics
from .launcher import LaunchError, build_launch_command
from .models import Server
from .platform_detection import best_install
from .mods import ModCheckResult, check_server_mods
from .settings import (
    load_favourites,
    load_settings,
    save_favourites,
    save_settings,
    server_key,
)
from .status import ServerStatus, check_server


class StatusWorker(QThread):
    status_ready = Signal(int, object)
    finished_all = Signal()

    def __init__(self, servers: list[Server]):
        super().__init__()
        self.servers = servers

    def run(self):
        for index, server in enumerate(self.servers):
            self.status_ready.emit(index, check_server(server))
        self.finished_all.emit()


class ModWorker(QThread):
    mods_ready = Signal(object)

    def __init__(self, server: Server, workshop_dir):
        super().__init__()
        self.server = server
        self.workshop_dir = workshop_dir

    def run(self):
        self.mods_ready.emit(check_server_mods(self.server, self.workshop_dir))


class LaunchDialog(QDialog):
    def __init__(self, parent, command: list[str], title: str):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.resize(820, 460)
        self.process = QProcess(self)
        self.process.setProcessChannelMode(QProcess.MergedChannels)

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Launch command:"))
        command_box = QLineEdit(" ".join(command))
        command_box.setReadOnly(True)
        layout.addWidget(command_box)

        self.output = QTextEdit()
        self.output.setReadOnly(True)
        layout.addWidget(self.output)

        button_row = QHBoxLayout()
        self.close_button = QPushButton("Close")
        self.close_button.clicked.connect(self.close)
        self.close_button.setEnabled(False)
        button_row.addStretch(1)
        button_row.addWidget(self.close_button)
        layout.addLayout(button_row)

        self.process.readyReadStandardOutput.connect(self.read_output)
        self.process.finished.connect(self.handle_finished)
        self.output.append("Starting launcher...\n")
        self.process.start(command[0], command[1:])

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
                "\nLaunch command handed off to Steam successfully. "
                "If DayZ does not appear, check Steam/Proton or existing DayZ processes."
            )
        else:
            self.output.append(
                f"\nLauncher exited with code {exit_code}. "
                "Check the messages above for the script or Steam error."
            )
        self.close_button.setEnabled(True)


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
        self.last_mod_result = None

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
        self.player_name = QLineEdit(str(self.settings.get("player_name") or "Andi"))
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
        tabs.addTab(self._build_mods_tab(), "Mods")
        tabs.addTab(self._build_diagnostics_tab(), "Diagnostics")
        self.setCentralWidget(tabs)

        self.apply_refresh_timer()
        self.refresh_statuses()
        self.update_diagnostics()

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
        settings.addRow("Player name", self.player_name)
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
        self.table.itemSelectionChanged.connect(self.update_launch_button_text)
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
        last_row = int(self.settings.get("last_selected_row", -1))
        if 0 <= last_row < len(self.servers):
            self.table.selectRow(last_row)
        layout.addWidget(self.table)

        buttons = QHBoxLayout()
        refresh = QPushButton("Refresh status")
        refresh.clicked.connect(self.refresh_statuses)
        self.launch_button = QPushButton("Launch selected server")
        self.launch_button.clicked.connect(self.launch_selected)
        save = QPushButton("Save settings")
        save.clicked.connect(self.save_user_settings)
        buttons.addWidget(refresh)
        buttons.addWidget(self.launch_button)
        buttons.addWidget(save)
        layout.addLayout(buttons)
        return widget


    def _build_mods_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)

        self.mod_summary = QLabel("Select a server, then click Check selected server mods.")
        layout.addWidget(self.mod_summary)

        buttons = QHBoxLayout()
        check = QPushButton("Check selected server mods")
        check.clicked.connect(self.check_selected_server_mods)
        open_selected = QPushButton("Open selected Workshop page")
        open_selected.clicked.connect(self.open_selected_workshop_page)
        open_missing = QPushButton("Open missing Workshop pages")
        open_missing.clicked.connect(self.open_missing_workshop_pages)
        buttons.addWidget(check)
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

    def _build_diagnostics_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        row = QHBoxLayout()
        refresh = QPushButton("Run diagnostics")
        refresh.clicked.connect(self.update_diagnostics)
        row.addWidget(QLabel("Diagnostics"))
        row.addWidget(refresh)
        layout.addLayout(row)
        self.system_summary = QLabel("Checking Steam and DayZ installation...")
        layout.addWidget(self.system_summary)
        self.diagnostics = QTextEdit()
        self.diagnostics.setReadOnly(True)
        layout.addWidget(self.diagnostics)
        return widget

    def browse_launcher(self):
        path, _ = QFileDialog.getOpenFileName(self, "Select dayz-launcher.sh")
        if path:
            self.launcher_path.setText(path)
            self.save_user_settings(silent=True)
            self.update_diagnostics()

    def apply_refresh_timer(self):
        seconds = self.refresh_seconds.value()
        if seconds <= 0:
            self.timer.stop()
        else:
            self.timer.start(seconds * 1000)

    def save_user_settings(self, silent: bool = False):
        self.settings = {
            "launcher_path": self.launcher_path.text(),
            "player_name": self.player_name.text(),
            "refresh_seconds": self.refresh_seconds.value(),
            "last_selected_row": self.table.currentRow(),
        }
        save_settings(self.settings)
        save_favourites(self.favourites)
        self.apply_refresh_timer()
        if not silent:
            QMessageBox.information(self, "Settings saved", "WolfLauncher settings were saved.")

    def refresh_statuses(self):
        if self.worker and self.worker.isRunning():
            return
        for row in range(len(self.servers)):
            self.table.setItem(row, 8, QTableWidgetItem("Checking..."))
        self.worker = StatusWorker(self.servers)
        self.worker.status_ready.connect(self.update_status_row)
        self.worker.finished_all.connect(self.handle_refresh_finished)
        self.worker.start()

    def _set_item(self, row: int, column: int, text: str, colour: str | None = None):
        item = QTableWidgetItem(text)
        if colour:
            item.setForeground(QColor(colour))
        self.table.setItem(row, column, item)

    def update_status_row(self, row: int, status: ServerStatus):
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
        self.table.resizeColumnsToContents()

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


    def check_selected_server_mods(self):
        row = self.table.currentRow()
        if row < 0:
            QMessageBox.warning(self, "No server selected", "Select a server first.")
            return

        if self.mod_worker and self.mod_worker.isRunning():
            return

        install = best_install()
        workshop_dir = install.workshop_dir if install else None
        if not workshop_dir:
            QMessageBox.warning(
                self,
                "Workshop folder not found",
                "WolfLauncher could not find the DayZ Workshop folder. Check Diagnostics.",
            )
            return

        server = self.servers[row]
        self.mod_summary.setText(f"Checking required mods for {server.name}...")
        self.mods_table.setRowCount(0)
        self.mod_worker = ModWorker(server, workshop_dir)
        self.mod_worker.mods_ready.connect(self.update_mods_table)
        self.mod_worker.start()

    def update_mods_table(self, result: ModCheckResult):
        self.last_mod_result = result
        self.mods_table.setSortingEnabled(False)
        if not result.ok:
            self.mod_summary.setText(f"Could not check mods for {result.server.name}: {result.error}")
            self.mods_table.setRowCount(0)
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

    def _mods_cell(self, row: int, column: int) -> str:
        item = self.mods_table.item(row, column)
        return item.text() if item else ""

    def show_server_context_menu(self, pos: QPoint):
        row = self.table.rowAt(pos.y())
        if row < 0:
            return
        self.table.selectRow(row)
        menu = QMenu(self)
        copy_connect_action = QAction("Copy connect address", self)
        copy_details_action = QAction("Copy server details", self)
        toggle_fav_action = QAction("Toggle favourite", self)
        copy_connect_action.triggered.connect(lambda: self.copy_to_clipboard(self._server_cell(row, 15), "Connect address"))
        copy_details_action.triggered.connect(lambda: self.copy_to_clipboard(self.server_details_text(row), "Server details"))
        toggle_fav_action.triggered.connect(lambda: self.toggle_favourite(row))
        menu.addAction(copy_connect_action)
        menu.addAction(copy_details_action)
        menu.addAction(toggle_fav_action)
        menu.exec(self.table.viewport().mapToGlobal(pos))

    def _server_cell(self, row: int, column: int) -> str:
        item = self.table.item(row, column)
        return item.text() if item else ""

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

    def update_diagnostics(self):
        install = best_install()
        if install and install.dayz_dir and install.workshop_dir:
            self.system_summary.setText(f"Detected {install.mode} Steam | DayZ OK | Workshop OK")
        elif install and install.dayz_dir:
            self.system_summary.setText(f"Detected {install.mode} Steam | DayZ OK | Workshop missing")
        elif install and (install.root or install.executable):
            self.system_summary.setText(f"Detected {install.mode} Steam | DayZ not found yet")
        else:
            self.system_summary.setText("Steam/DayZ not detected")
        self.diagnostics.setPlainText(run_diagnostics(self.launcher_path.text(), self.servers))

    def launch_selected(self):
        row = self.table.currentRow()
        if row < 0:
            QMessageBox.warning(self, "No server selected", "Select a server first.")
            return

        server = self.servers[row]
        self.save_user_settings(silent=True)

        if not self.confirm_launch_preflight(server):
            return

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

        try:
            command = build_launch_command(
                self.launcher_path.text(),
                self.player_name.text().strip() or "Survivor",
                launch_server,
            )
        except LaunchError as exc:
            QMessageBox.critical(self, "Launch failed", str(exc))
            return

        dialog = LaunchDialog(self, command, f"Launching {server.name}")
        dialog.exec()

    def confirm_launch_preflight(self, server: Server) -> bool:
        install = best_install()
        if not install or not install.dayz_dir:
            QMessageBox.critical(
                self,
                "DayZ not detected",
                "WolfLauncher could not detect a DayZ installation. Check the Diagnostics tab before launching.",
            )
            return False

        if not install.workshop_dir:
            QMessageBox.critical(
                self,
                "Workshop folder not detected",
                "WolfLauncher could not detect the DayZ Workshop folder. Check the Diagnostics tab before launching.",
            )
            return False

        if not install.running:
            reply = QMessageBox.question(
                self,
                "Steam is not running",
                f"{install.mode.title()} Steam was detected, but it does not appear to be running.\n\n"
                "The external launcher may still be able to start Steam, but starting Steam first is recommended.\n\n"
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
        super().closeEvent(event)


def main():
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
