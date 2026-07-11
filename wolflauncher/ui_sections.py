from PySide6.QtWidgets import QPushButton, QWidget


def set_disclosure_state(
    button: QPushButton,
    panel: QWidget,
    label: str,
    expanded: bool,
) -> None:
    """Keep a disclosure button and its secondary-control panel in sync."""
    panel.setVisible(expanded)
    button.setChecked(expanded)
    button.setText(f"{'Hide' if expanded else 'Show'} {label}")
