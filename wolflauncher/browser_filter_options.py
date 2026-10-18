"""Qt helpers for stable Server Browser filter options."""

from PySide6.QtWidgets import QComboBox

from .server_display import display_map_name, map_filter_key


def set_combo_filter_options(combo: QComboBox, any_label: str, values: list[str]) -> None:
    if any_label == "Any map":
        official = ["ChernarusPlus", "Livonia", "Sakhal", "Nasdara"]
        official_keys = {map_filter_key(name) for name in official}
        community = sorted(
            {
                display_map_name(value)
                for value in values
                if map_filter_key(value) not in official_keys
            },
            key=str.casefold,
        )
        choices = [any_label, *official, *(["", *community] if community else [])]
    else:
        choices = [any_label, *values]
    existing = [combo.itemText(index) for index in range(combo.count())]
    if existing == choices:
        return
    current = combo.currentText()
    if any_label == "Any map" and current != any_label:
        current = display_map_name(current)
    combo.blockSignals(True)
    combo.clear()
    for choice in choices:
        if choice:
            combo.addItem(choice)
        else:
            combo.insertSeparator(combo.count())
    combo.setCurrentText(current if current in choices else any_label)
    combo.blockSignals(False)


def combo_filter_value(combo: QComboBox, any_label: str) -> str:
    value = combo.currentText().strip()
    return "" if value == any_label else value
