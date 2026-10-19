"""Qt coordination for the curated-server card list and its selection state."""

from PySide6.QtCore import QSize, Qt
from PySide6.QtWidgets import QListWidgetItem

from .curated_server_cards import CuratedServerCard
from .curated_server_presenter import curated_status_counts


class CuratedServerCardsCoordinator:
    """Keep the compact card view synchronized with the curated-server table."""

    def __init__(self, window):
        self.window = window

    def update_status_summary(self):
        window = self.window
        if not hasattr(window, "curated_online_summary"):
            return
        statuses = [
            window.table.item(row, 8).text()
            for row in range(window.table.rowCount())
            if window.table.item(row, 8)
        ]
        online, offline, unknown = curated_status_counts(statuses)
        window.curated_online_summary.setText(f"{online} online")
        window.curated_offline_summary.setText(f"{offline} offline")
        if hasattr(window, "curated_unknown_summary"):
            window.curated_unknown_summary.setText(f"{unknown} unknown")

    def refresh_cards(self):
        window = self.window
        if not hasattr(window, "server_cards"):
            return
        selected_row = window.table.currentRow()
        window.server_cards.blockSignals(True)
        window.server_cards.clear()
        for row in range(window.table.rowCount()):
            values = [window._server_cell(row, column) for column in range(16)]
            card = CuratedServerCard(row, values, window.server_cards)
            card.selected.connect(self.select_card)
            card.activated.connect(self.launch_card)
            card.favourite_requested.connect(window.toggle_favourite)
            card.context_requested.connect(window.show_server_card_context_menu)
            item = QListWidgetItem()
            item.setData(Qt.UserRole, row)
            item.setSizeHint(QSize(0, max(64, card.sizeHint().height() + 6)))
            window.server_cards.addItem(item)
            window.server_cards.setItemWidget(item, card)
        if 0 <= selected_row < window.server_cards.count():
            window.server_cards.setCurrentRow(selected_row)
        window.server_cards.blockSignals(False)
        self.sync_selection()

    def select_table_row(self, row: int):
        window = self.window
        if 0 <= row < window.table.rowCount():
            if window.table.currentRow() != row:
                window.table.selectRow(row)
            elif getattr(window, "active_discovered_server", None) is not None:
                window.handle_server_selection_changed()
        self.sync_selection()

    def select_card(self, row: int):
        window = self.window
        if 0 <= row < window.server_cards.count():
            window.server_cards.setCurrentRow(row)
        self.select_table_row(row)

    def launch_card(self, row: int):
        self.select_card(row)
        self.window.launch_selected()

    def sync_selection(self):
        window = self.window
        if not hasattr(window, "server_cards"):
            return
        selected_row = window.table.currentRow()
        for row in range(window.server_cards.count()):
            card = window.server_cards.itemWidget(window.server_cards.item(row))
            if isinstance(card, CuratedServerCard):
                card.set_selected(row == selected_row)
