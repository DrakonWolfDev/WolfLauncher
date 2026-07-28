from dataclasses import replace
from datetime import datetime

from PySide6.QtCore import QPoint, QSize, Qt
from PySide6.QtGui import QAction, QColor
from PySide6.QtWidgets import (
    QDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMenu,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from .config import (
    add_curated_server,
    remove_curated_server,
    reorder_curated_servers,
    update_curated_server,
)
from .curated_dialogs import EditCuratedServerDialog
from .curated_server_cards import CuratedServerCard
from .launch_history import load_recent_launches
from .curated_server_presenter import curated_server_row
from .curated_status_cache import (
    cached_status_for_server,
    update_status_cache,
)
from .models import Server
from .server_display import display_map_name, display_server_flags, ping_severity
from .server_enrichment import (
    parse_connect_port,
)
from .settings import (
    server_key,
)
from .settings_feature import SettingsFeatureMixin
from .status import ServerStatus
from .theme import (
    COLOURS,
    STATUS_COLOURS,
    configure_data_table,
    configure_priority_columns,
    monospace_font,
    set_ui_role,
    theme_icon,
)
from .workers import (
    StatusWorker,
)


class CuratedServersMixin:
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
        self.table.setAccessibleName("Favourite servers")
        self.table.setAccessibleDescription("Saved DayZ servers and their latest known status.")
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
        self.server_cards.setAccessibleName("Favourite servers")
        self.server_cards.setAccessibleDescription(
            "Saved DayZ servers. Each card includes its status and a Connect action."
        )
        set_ui_role(self.server_cards, "serverCards")
        self.server_cards.currentRowChanged.connect(self._select_curated_table_row)
        layout.addWidget(self.server_cards)
        layout.addWidget(self.table)
        self.table.hide()

        self.recent_servers_panel = QWidget()
        recent_layout = QVBoxLayout(self.recent_servers_panel)
        recent_layout.setContentsMargins(0, 8, 0, 0)
        recent_layout.addWidget(QLabel("Recent servers"))
        self.recent_servers_list = QVBoxLayout()
        recent_layout.addLayout(self.recent_servers_list)
        layout.addWidget(self.recent_servers_panel)

        buttons = QHBoxLayout()
        add_server = QPushButton("Add a favourite server")
        add_server.setIcon(theme_icon("add"))
        add_server.clicked.connect(self.add_curated_server)
        self.refresh_status_button = QPushButton("Refresh status")
        self.refresh_status_button.setIcon(theme_icon("refresh"))
        self.refresh_status_button.clicked.connect(self.refresh_statuses)
        self.move_server_up_button = QPushButton("Move up")
        self.move_server_up_button.clicked.connect(lambda: self.move_selected_curated_server(-1))
        self.move_server_down_button = QPushButton("Move down")
        self.move_server_down_button.clicked.connect(lambda: self.move_selected_curated_server(1))
        self.launch_button = QPushButton("Launch selected server")
        self.launch_button.setIcon(theme_icon("launch"))
        set_ui_role(self.launch_button, "primary")
        self.launch_button.clicked.connect(self.launch_selected)
        buttons.addStretch(1)
        buttons.addWidget(add_server)
        buttons.addWidget(self.move_server_up_button)
        buttons.addWidget(self.move_server_down_button)
        buttons.addWidget(self.refresh_status_button)
        buttons.addWidget(self.launch_button)
        layout.addLayout(buttons)
        self.update_curated_status_summary()
        self.refresh_curated_server_cards()
        self.refresh_recent_servers()
        return widget

    def refresh_recent_servers(self):
        if not hasattr(self, "recent_servers_panel"):
            return
        while self.recent_servers_list.count():
            item = self.recent_servers_list.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        favourite_keys = {server_key(server) for server in self.servers}
        rows = [row for row in load_recent_launches() if row.get("key") not in favourite_keys][:3]
        self.recent_servers_panel.setVisible(bool(rows))
        for row in rows:
            try:
                server = Server(row["name"], row.get("group", "Recent"), row["host"], int(row["game_port"]), int(row["query_port"]))
            except (KeyError, TypeError, ValueError):
                continue
            line = QHBoxLayout()
            line.addWidget(QLabel(f"{server.name}  ·  {server.connect_target}"), 1)
            launch = QPushButton("Launch")
            launch.clicked.connect(lambda _checked=False, target=server: self.launch_recent_server(target))
            line.addWidget(launch)
            self.recent_servers_list.addLayout(line)

    def launch_recent_server(self, server: Server):
        self.active_discovered_server = server
        self.active_discovered_cache_key = ""
        self.update_launch_button_text()
        self.launch_selected()

    def move_selected_curated_server(self, direction: int):
        row = self.table.currentRow()
        target = row + direction
        if row < 0 or target < 0 or target >= len(self.servers):
            return
        reordered = list(self.servers)
        reordered[row], reordered[target] = reordered[target], reordered[row]
        try:
            reorder_curated_servers(self.config_path, reordered)
        except (OSError, ValueError) as exc:
            QMessageBox.warning(self, "Could not reorder favourite servers", str(exc))
            return
        self.servers = reordered
        self._rebuild_curated_server_table(target)
        self.statusBar().showMessage("Favourite-server order saved.", 5000)

    def _rebuild_curated_server_table(self, selected_row: int):
        self.table.blockSignals(True)
        self.table.setRowCount(len(self.servers))
        for row, server in enumerate(self.servers):
            cached = cached_status_for_server(self.curated_status_cache, server)
            for column, value in enumerate(curated_server_row(server, cached)):
                self._set_curated_server_table_item(row, column, value, cached=bool(cached))
        self.table.resizeColumnsToContents()
        self.table.selectRow(selected_row)
        self.table.blockSignals(False)
        self._reindex_server_rows()
        self.refresh_curated_server_cards()
        self.update_launch_button_text()

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
            item.setText(card.accessibleName())
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
            SettingsFeatureMixin._save_favourites_index(self)
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
        if server.favourite and hasattr(self, "sync_browser_favourite_endpoint"):
            self.sync_browser_favourite_endpoint(
                server.host,
                server.game_port,
                server.query_port,
                is_favourite=True,
            )

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
        SettingsFeatureMixin._save_favourites_index(self)
        if hasattr(self, "sync_browser_favourite_endpoint"):
            self.sync_browser_favourite_endpoint(
                server.host,
                server.game_port,
                server.query_port,
                is_favourite=False,
            )
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
        SettingsFeatureMixin._save_favourites_index(self)
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
        SettingsFeatureMixin._save_favourites_index(self)
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
