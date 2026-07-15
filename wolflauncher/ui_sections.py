from PySide6.QtWidgets import QPushButton, QWidget

from .theme import set_ui_role


def set_disclosure_state(
    button: QPushButton,
    panel: QWidget,
    label: str,
    expanded: bool,
) -> None:
    """Keep a disclosure button and its secondary-control panel in sync."""
    set_ui_role(button, "disclosure")
    panel.setVisible(expanded)
    button.setChecked(expanded)
    marker = "▾" if expanded else "▸"
    button.setText(f"{marker} {'Hide' if expanded else 'Show'} {label}")
