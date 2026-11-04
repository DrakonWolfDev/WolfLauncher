"""Incremental mod presentation using native sortable table items."""

from collections import Counter

from PySide6.QtCore import QSignalBlocker, Qt
from PySide6.QtGui import QColor, QFontMetrics
from PySide6.QtWidgets import QHeaderView, QTableWidgetItem

from .mod_presenter import mod_row
from .theme import monospace_font
from .workshop_subscription import ITEM_STATE_DOWNLOADING

KEY_ROLE = Qt.UserRole + 4
SIGNATURE_ROLE = Qt.UserRole + 5


def populate_mod_table(table, mods, *, preserve_position=False):
    counts = Counter()
    rows = []
    for mod in mods:
        data = mod_row(mod)
        identity = mod.workshop_id or f"local:{mod.name}"
        key = (identity, counts[identity])
        counts[identity] += 1
        downloading = bool(
            mod.workshop_state is not None
            and mod.workshop_state & ITEM_STATE_DOWNLOADING
            and not mod.checking
            and not mod.workshop_completion_pending
        )
        rows.append((key, data, downloading))
    selected = table.item(table.currentRow(), 1)
    selected_key = selected.data(KEY_ROLE) if selected and preserve_position else None
    scroll = table.verticalScrollBar().value()
    sorting = table.isSortingEnabled()
    current = {}
    for row in range(table.rowCount()):
        item = table.item(row, 1)
        if item and item.data(KEY_ROLE) is not None:
            current[tuple(item.data(KEY_ROLE))] = row
    reuse_order = (
        sorting and len(current) == len(rows) and set(current) == {key for key, _, _ in rows}
    )
    changes = []
    for index, (key, data, downloading) in enumerate(rows):
        row = current[key] if reuse_order else index
        signature = (key, tuple(data.values), data.status_colour)
        existing = table.item(row, 1)
        if (
            existing is None
            or existing.data(SIGNATURE_ROLE) != signature
            or (not downloading and table.cellWidget(row, 0) is not None)
        ):
            changes.append((row, key, data, signature, downloading))
    if changes or table.rowCount() != len(rows):
        updates = table.updatesEnabled()
        with QSignalBlocker(table):
            table.setUpdatesEnabled(False)
            table.setSortingEnabled(False)
            try:
                table.setRowCount(len(rows))
                font = monospace_font()
                for row, key, data, signature, downloading in changes:
                    old = table.item(row, 1)
                    same_row = old is not None and old.data(KEY_ROLE) == key
                    if (not same_row or not downloading) and table.cellWidget(row, 0) is not None:
                        table.removeCellWidget(row, 0)
                    for column, value in enumerate(data.values):
                        item = table.item(row, column)
                        if item is None:
                            item = QTableWidgetItem()
                            table.setItem(row, column, item)
                            if column in {2, 3}:
                                item.setFont(font)
                            if column in {0, 2, 3}:
                                item.setTextAlignment(Qt.AlignCenter)
                        if item.text() != value:
                            item.setText(value)
                        if item.toolTip() != value:
                            item.setToolTip(value)
                        item.setData(Qt.UserRole, data.workshop_id)
                        item.setData(KEY_ROLE, key)
                        if column == 0:
                            item.setForeground(QColor(data.status_colour))
                    table.item(row, 1).setData(SIGNATURE_ROLE, signature)
            finally:
                table.setSortingEnabled(sorting if preserve_position else False)
                table.setUpdatesEnabled(updates)
        if updates:
            table.viewport().update()
    # Measure representative text only, never every cell. Respect user widths
    # after initial setup; Qt's stretch name column handles window resizing.
    if not table.property("modColumnSizingSet"):
        for column, text in (
            (0, "Waiting for Steam completion"),
            (2, "00000000000000000000"),
            (3, "Unavailable"),
        ):
            metrics = QFontMetrics(monospace_font()) if column in {2, 3} else table.fontMetrics()
            width = max(metrics.horizontalAdvance(text), metrics.horizontalAdvance("000.0 GiB"))
            table.setColumnWidth(column, width + 28)
        table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        table.setProperty("modColumnSizingSet", True)
    with QSignalBlocker(table):
        if table.rowCount():
            row = next(
                (
                    row
                    for row in range(table.rowCount())
                    if table.item(row, 1).data(KEY_ROLE) == selected_key
                ),
                0,
            )
            table.selectRow(row)
        if preserve_position:
            table.verticalScrollBar().setValue(scroll)
