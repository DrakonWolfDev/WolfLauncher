"""Qt helpers for stable Server Browser filter options."""

from PySide6.QtWidgets import QComboBox


def set_combo_filter_options(combo: QComboBox, any_label: str, values: list[str]) -> None:
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


def combo_filter_value(combo: QComboBox, any_label: str) -> str:
    value = combo.currentText().strip()
    return "" if value == any_label else value
