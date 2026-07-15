from collections.abc import Sequence

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QTableWidget

from .models import DiscoveredServer
from .server_browser_presenter import browser_row
from .table_items import SortableTableWidgetItem
from .theme import monospace_font


def populate_browser_table(table: QTableWidget, servers: Sequence[DiscoveredServer]) -> None:
    """Replace the discovered-server table rows while preserving sortable metadata."""
    table.setSortingEnabled(False)
    table.setRowCount(len(servers))
    for row, server in enumerate(servers):
        row_data = browser_row(server)
        for column, value in enumerate(row_data.values):
            item = SortableTableWidgetItem(value, row_data.sort_values[column])
            item.setData(Qt.UserRole, server.cache_key)
            if column in row_data.tooltips:
                item.setToolTip(row_data.tooltips[column])
            if column == 5:
                item.setForeground(QColor(row_data.status_colour))
            if column in {7, 8}:
                item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            if column in {2, 3, 4, 8, 9, 11}:
                item.setFont(monospace_font())
            table.setItem(row, column, item)

    table.resizeColumnsToContents()
    table.setSortingEnabled(True)
