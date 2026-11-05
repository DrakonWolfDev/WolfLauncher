from collections.abc import Sequence

from PySide6.QtCore import QSignalBlocker, QSize, Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QTableWidget

from .models import DiscoveredServer
from .server_browser_presenter import browser_row, game_time_is_day, players_text
from .server_display import ping_severity
from .table_items import SortableTableWidgetItem
from .theme import (
    COLOURS,
    STATUS_COLOURS,
    monospace_font,
    theme_icon,
    time_icon,
)

BROWSER_COLUMN_COUNT = 18
BROWSER_FAVOURITE_COLUMN = 0
BROWSER_NAME_COLUMN = 1
BROWSER_MODS_COLUMN = 12
BROWSER_GAME_TIME_COLUMN = 16
BROWSER_PASSWORD_COLUMN = 17
BROWSER_FAVOURITE_ROLE = Qt.UserRole + 1


def configure_browser_sorting(table: QTableWidget) -> None:
    """Sort when requested, without moving rows as background replies arrive."""
    table.setSortingEnabled(False)
    header = table.horizontalHeader()
    header.setSectionsClickable(True)
    header.setSortIndicatorShown(True)
    if not getattr(table, "_browser_sort_connected", False):
        header.sortIndicatorChanged.connect(table.sortItems)
        table._browser_sort_connected = True


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
    *,
    preserve_order: bool = False,
    mod_previews: dict[str, tuple[str, str, str]] | None = None,
) -> None:
    """Replace the discovered-server table rows while preserving sortable metadata."""
    # A provider refresh can replace hundreds of rows at once. Repainting after
    # every inserted cell makes the GUI appear to hang while the background
    # WolfAPI work is finishing. Column sizing is owned by
    # ServerBrowserMixin.configure_browser_columns(); resizeColumnsToContents()
    # would synchronously scan the whole table a second time here.
    table.setUpdatesEnabled(False)
    try:
        configure_browser_sorting(table)
        table.setIconSize(QSize(20, 20))
        table.setRowCount(len(servers))
        favourites = favourite_endpoints or set()
        for row, server in enumerate(servers):
            _set_browser_table_row(
                table, row, server, favourites, (mod_previews or {}).get(server.cache_key)
            )
        if not preserve_order:
            header = table.horizontalHeader()
            table.sortItems(header.sortIndicatorSection(), header.sortIndicatorOrder())
    finally:
        table.setUpdatesEnabled(True)
        table.viewport().update()


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
            scroll_value = table.verticalScrollBar().value()
            with QSignalBlocker(table):
                favourite = table.item(row, BROWSER_FAVOURITE_COLUMN)
                favourite_endpoints = (
                    {(server.host, server.game_port, server.query_port)}
                    if favourite and favourite.data(BROWSER_FAVOURITE_ROLE)
                    else set()
                )
                _set_browser_table_row(table, row, server, favourite_endpoints)
                if selected_key == old_cache_key:
                    selected_key = server.cache_key
                _restore_selection(table, selected_key)
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
        scroll_value = table.verticalScrollBar().value()
        with QSignalBlocker(table):
            item = SortableTableWidgetItem(text, text)
            item.setData(Qt.UserRole, cache_key)
            item.setToolTip(tooltip)
            item.setFont(monospace_font())
            if colour:
                item.setForeground(QColor(colour))
            table.setItem(row, BROWSER_MODS_COLUMN, item)
            _restore_selection(table, selected_key)
        table.verticalScrollBar().setValue(scroll_value)
        return True
    return False


def set_browser_favourite_marker(table: QTableWidget, row: int, is_favourite: bool) -> None:
    """Paint a single star through Qt's item delegate, without a child widget."""
    item = table.item(row, BROWSER_FAVOURITE_COLUMN)
    if item is None:
        return
    _style_browser_favourite(table, item, is_favourite)


def _style_browser_favourite(table, item, is_favourite):
    item.setText("\u2605" if is_favourite else "\u2606")
    item.setData(BROWSER_FAVOURITE_ROLE, is_favourite)
    item.setToolTip("Remove from Favourite Servers" if is_favourite else "Add to Favourite Servers")
    item.setForeground(QColor(COLOURS["accent" if is_favourite else "text_muted"]))
    item.setTextAlignment(Qt.AlignCenter)
    font = table.font()
    font.setPixelSize(15)
    item.setFont(font)


def _set_browser_table_row(
    table: QTableWidget,
    row: int,
    server: DiscoveredServer,
    favourite_endpoints: set[tuple[str, int, int]] | None = None,
    mod_preview: tuple[str, str, str] | None = None,
) -> None:
    row_data = browser_row(server)
    cache_key = server.cache_key
    mono_font = monospace_font()
    items = []
    for data_column, value in enumerate(row_data.values):
        column = data_column + 1
        item = SortableTableWidgetItem(value, row_data.sort_values[data_column])
        if column == BROWSER_MODS_COLUMN and mod_preview:
            item = SortableTableWidgetItem(mod_preview[0], mod_preview[0])
        item.setData(Qt.UserRole, cache_key)
        if data_column in row_data.tooltips:
            item.setToolTip(row_data.tooltips[data_column])
        if column == BROWSER_MODS_COLUMN and mod_preview:
            item.setToolTip(mod_preview[1])
            item.setForeground(QColor(mod_preview[2]))
        if data_column == 7 and row_data.values[7] != "—":
            item.setData(
                Qt.UserRole + 2,
                (
                    players_text(server.players_current, server.players_max),
                    server.queue_count,
                    server.queue_checked_at,
                ),
            )
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
            item.setFont(mono_font)
        if data_column == 15:
            is_day = game_time_is_day(server)
            if is_day is not None:
                item.setIcon(time_icon(is_day))
        items.append((column, item))
    is_favourite = (server.host, server.game_port, server.query_port) in (
        favourite_endpoints or set()
    )
    favourite = SortableTableWidgetItem("", 0)
    favourite.setData(Qt.UserRole, cache_key)
    _style_browser_favourite(table, favourite, is_favourite)
    items.append((BROWSER_FAVOURITE_COLUMN, favourite))
    password = SortableTableWidgetItem("", int(server.password))
    password.setData(Qt.UserRole, cache_key)
    password.setTextAlignment(Qt.AlignCenter)
    if server.password:
        password.setIcon(theme_icon("lock-table"))
        password.setToolTip("Password required to join this server")
    items.append((BROWSER_PASSWORD_COLUMN, password))
    for column, item in items:
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
