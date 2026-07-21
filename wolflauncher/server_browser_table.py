from collections.abc import Sequence

from PySide6.QtCore import QSignalBlocker, QSize, Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QTableWidget

from .models import DiscoveredServer
from .server_browser_presenter import browser_row, game_time_is_day
from .server_display import ping_severity
from .table_items import SortableTableWidgetItem
from .theme import STATUS_COLOURS, monospace_font, time_icon

BROWSER_COLUMN_COUNT = 16
BROWSER_GAME_TIME_COLUMN = 15


def selected_browser_cache_key(table: QTableWidget) -> str:
    """Return identity from the visibly selected row, never a stale current index."""
    selection_model = table.selectionModel()
    selected_rows = selection_model.selectedRows(0) if selection_model else []
    if not selected_rows:
        return ""
    item = table.item(selected_rows[0].row(), 0)
    return str(item.data(Qt.UserRole) or "") if item else ""


def populate_browser_table(table: QTableWidget, servers: Sequence[DiscoveredServer]) -> None:
    """Replace the discovered-server table rows while preserving sortable metadata."""
    table.setSortingEnabled(False)
    table.setIconSize(QSize(20, 20))
    table.setRowCount(len(servers))
    for row, server in enumerate(servers):
        _set_browser_table_row(table, row, server)

    table.resizeColumnsToContents()
    table.setSortingEnabled(True)


def update_browser_table_row(
    table: QTableWidget,
    old_cache_key: str,
    server: DiscoveredServer,
) -> bool:
    """Update one enriched result without rebuilding or scrolling the table."""
    for row in range(table.rowCount()):
        item = table.item(row, 0)
        if item and item.data(Qt.UserRole) == old_cache_key:
            selected_key = _selected_cache_key(table)
            sorting = table.isSortingEnabled()
            scroll_value = table.verticalScrollBar().value()
            with QSignalBlocker(table):
                table.setSortingEnabled(False)
                _set_browser_table_row(table, row, server)
                table.setSortingEnabled(sorting)
                _restore_selection(table, selected_key or server.cache_key)
            table.verticalScrollBar().setValue(scroll_value)
            return True
    return False


def update_browser_mod_cell(
    table: QTableWidget,
    cache_key: str,
    text: str,
    tooltip: str,
    colour: str | None = None,
) -> bool:
    """Apply transient local readiness to the Mods cell for one cached row."""
    for row in range(table.rowCount()):
        name_item = table.item(row, 0)
        if not name_item or name_item.data(Qt.UserRole) != cache_key:
            continue
        selected_key = _selected_cache_key(table)
        sorting = table.isSortingEnabled()
        scroll_value = table.verticalScrollBar().value()
        with QSignalBlocker(table):
            table.setSortingEnabled(False)
            item = SortableTableWidgetItem(text, text)
            item.setData(Qt.UserRole, cache_key)
            item.setToolTip(tooltip)
            item.setFont(monospace_font())
            if colour:
                item.setForeground(QColor(colour))
            table.setItem(row, 11, item)
            table.setSortingEnabled(sorting)
            _restore_selection(table, selected_key)
        table.verticalScrollBar().setValue(scroll_value)
        return True
    return False


def _set_browser_table_row(
    table: QTableWidget,
    row: int,
    server: DiscoveredServer,
) -> None:
    row_data = browser_row(server)
    for column, value in enumerate(row_data.values):
        item = SortableTableWidgetItem(value, row_data.sort_values[column])
        item.setData(Qt.UserRole, server.cache_key)
        if column in row_data.tooltips:
            item.setToolTip(row_data.tooltips[column])
        if column == 5:
            item.setForeground(QColor(row_data.status_colour))
        if column == 8:
            severity = ping_severity(server.ping_ms)
            if severity == "warning":
                item.setForeground(QColor(STATUS_COLOURS["warning"]))
            elif severity == "critical":
                item.setForeground(QColor(STATUS_COLOURS["negative"]))
        if column in {7, 8}:
            item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
        if column in {2, 3, 4, 8, 9, 11, BROWSER_GAME_TIME_COLUMN}:
            item.setFont(monospace_font())
        if column == BROWSER_GAME_TIME_COLUMN:
            is_day = game_time_is_day(server)
            if is_day is not None:
                item.setIcon(time_icon(is_day))
        table.setItem(row, column, item)


def _selected_cache_key(table: QTableWidget) -> str:
    return selected_browser_cache_key(table)


def _restore_selection(table: QTableWidget, cache_key: str) -> None:
    if not cache_key:
        table.clearSelection()
        return
    for row in range(table.rowCount()):
        item = table.item(row, 0)
        if item and item.data(Qt.UserRole) == cache_key:
            table.selectRow(row)
            return
