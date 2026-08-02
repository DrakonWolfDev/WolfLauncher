from collections.abc import Sequence

from PySide6.QtCore import QSignalBlocker, QSize, Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QHBoxLayout, QLabel, QTableWidget, QWidget

from .models import DiscoveredServer
from .server_browser_presenter import browser_row, game_time_is_day
from .server_display import ping_severity
from .table_items import SortableTableWidgetItem
from .theme import STATUS_COLOURS, monospace_font, set_ui_role, theme_icon, time_icon

BROWSER_COLUMN_COUNT = 18
BROWSER_FAVOURITE_COLUMN = 0
BROWSER_NAME_COLUMN = 1
BROWSER_MODS_COLUMN = 12
BROWSER_GAME_TIME_COLUMN = 16
BROWSER_PASSWORD_COLUMN = 17


def selected_browser_cache_key(table: QTableWidget) -> str:
    """Return identity from the visibly selected row, never a stale current index."""
    selection_model = table.selectionModel()
    selected_rows = selection_model.selectedRows(0) if selection_model else []
    if not selected_rows:
        return ""
    item = table.item(selected_rows[0].row(), BROWSER_NAME_COLUMN)
    return str(item.data(Qt.UserRole) or "") if item else ""


def populate_browser_table(
    table: QTableWidget,
    servers: Sequence[DiscoveredServer],
    favourite_endpoints: set[tuple[str, int, int]] | None = None,
) -> None:
    """Replace the discovered-server table rows while preserving sortable metadata."""
    table.setSortingEnabled(False)
    table.setIconSize(QSize(20, 20))
    table.setRowCount(len(servers))
    for row, server in enumerate(servers):
        _set_browser_table_row(table, row, server, favourite_endpoints or set())

    table.resizeColumnsToContents()
    table.setSortingEnabled(True)


def update_browser_table_row(
    table: QTableWidget,
    old_cache_key: str,
    server: DiscoveredServer,
) -> bool:
    """Update one enriched result without rebuilding or scrolling the table."""
    for row in range(table.rowCount()):
        item = table.item(row, BROWSER_NAME_COLUMN)
        if item and item.data(Qt.UserRole) == old_cache_key:
            selected_key = _selected_cache_key(table)
            sorting = table.isSortingEnabled()
            scroll_value = table.verticalScrollBar().value()
            with QSignalBlocker(table):
                table.setSortingEnabled(False)
                favourite = table.item(row, BROWSER_FAVOURITE_COLUMN)
                favourite_endpoints = (
                    {(server.host, server.game_port, server.query_port)}
                    if favourite and favourite.text() == "★"
                    else set()
                )
                _set_browser_table_row(table, row, server, favourite_endpoints)
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
        name_item = table.item(row, BROWSER_NAME_COLUMN)
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
            table.setItem(row, BROWSER_MODS_COLUMN, item)
            table.setSortingEnabled(sorting)
            _restore_selection(table, selected_key)
        table.verticalScrollBar().setValue(scroll_value)
        return True
    return False


def set_browser_favourite_marker(table: QTableWidget, row: int, is_favourite: bool) -> None:
    """Update the star widget without duplicating its glyph in the table item."""
    item = table.item(row, BROWSER_FAVOURITE_COLUMN)
    if item is None:
        return
    item.setText("")
    item.setToolTip(
        "Remove from Favourite Servers" if is_favourite else "Add to Favourite Servers"
    )
    table.setCellWidget(row, BROWSER_FAVOURITE_COLUMN, _browser_marker(is_favourite))


def _set_browser_table_row(
    table: QTableWidget,
    row: int,
    server: DiscoveredServer,
    favourite_endpoints: set[tuple[str, int, int]] | None = None,
) -> None:
    row_data = browser_row(server)
    for data_column, value in enumerate(row_data.values):
        column = data_column + 1
        item = SortableTableWidgetItem(value, row_data.sort_values[data_column])
        item.setData(Qt.UserRole, server.cache_key)
        if data_column in row_data.tooltips:
            item.setToolTip(row_data.tooltips[data_column])
        if data_column == 5:
            item.setForeground(QColor(row_data.status_colour))
        if data_column == 8:
            severity = ping_severity(server.ping_ms)
            if severity == "warning":
                item.setForeground(QColor(STATUS_COLOURS["warning"]))
            elif severity == "critical":
                item.setForeground(QColor(STATUS_COLOURS["negative"]))
        if data_column in {7, 8}:
            item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
        if data_column in {2, 3, 4, 8, 9, 11, 15}:
            item.setFont(monospace_font())
        if data_column == 15:
            is_day = game_time_is_day(server)
            if is_day is not None:
                item.setIcon(time_icon(is_day))
        table.setItem(row, column, item)
    is_favourite = (server.host, server.game_port, server.query_port) in (favourite_endpoints or set())
    favourite = SortableTableWidgetItem("", 0)
    favourite.setData(Qt.UserRole, server.cache_key)
    favourite.setToolTip("Remove from Favourite Servers" if is_favourite else "Add to Favourite Servers")
    table.setItem(row, BROWSER_FAVOURITE_COLUMN, favourite)
    table.setCellWidget(row, BROWSER_FAVOURITE_COLUMN, _browser_marker(is_favourite))
    password = SortableTableWidgetItem("", int(server.password))
    password.setData(Qt.UserRole, server.cache_key)
    password.setTextAlignment(Qt.AlignCenter)
    if server.password:
        password.setIcon(theme_icon("lock-table"))
        password.setToolTip("Password required to join this server")
    table.setItem(row, BROWSER_PASSWORD_COLUMN, password)


def _browser_marker(is_favourite: bool) -> QWidget:
    marker = QWidget()
    marker.setAttribute(Qt.WA_TransparentForMouseEvents)
    layout = QHBoxLayout(marker)
    layout.setContentsMargins(10, 0, 0, 0)
    layout.setSpacing(4)
    star = QLabel("★" if is_favourite else "☆")
    set_ui_role(star, "browserStar")
    star.setProperty("favourite", is_favourite)
    star.setFixedWidth(28)
    star.setAlignment(Qt.AlignCenter)
    layout.addWidget(star)
    layout.addStretch(1)
    return marker


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
