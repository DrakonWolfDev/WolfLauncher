"""Shared visual tokens and application-level styling for WolfLauncher."""

from PySide6.QtGui import QFontDatabase
from PySide6.QtWidgets import QApplication, QAbstractItemView, QTableView, QWidget


COLOURS = {
    "background": "#15130f", "surface": "#1c1912", "surface_alt": "#201c15",
    "border": "#3a3326", "border_strong": "#5a4b32", "text": "#efe9db",
    "text_muted": "#a8a092", "accent": "#e8a33d", "accent_hover": "#f0b45a",
    "accent_pressed": "#c98528", "positive": "#6fcf97", "warning": "#e8a33d",
    "negative": "#e07a7a",
}
SPACING = {"compact": 4, "control_vertical": 6, "control_horizontal": 10,
           "table_vertical": 5, "table_horizontal": 8, "radius": 4}
STATUS_COLOURS = {key: COLOURS[key] for key in ("positive", "warning", "negative")}


def _build_stylesheet() -> str:
    c, s = COLOURS, SPACING
    return f"""
QWidget {{ background-color: {c['background']}; color: {c['text']}; selection-background-color: {c['accent']}; selection-color: {c['background']}; }}
QMainWindow, QDialog, QMessageBox {{ background-color: {c['background']}; }}
QLabel {{ background-color: transparent; }}
QLabel:disabled {{ color: {c['text_muted']}; }}
QLabel[uiRole="summary"] {{ color: {c['text']}; font-weight: 600; padding: 2px 0 4px 0; }}
QLabel[uiRole="metadata"] {{ color: {c['text_muted']}; }}
QToolTip {{ background-color: {c['surface_alt']}; color: {c['text']}; border: 1px solid {c['border_strong']}; padding: {s['compact']}px; }}
QLineEdit, QComboBox, QSpinBox, QTextEdit {{ background-color: {c['surface_alt']}; color: {c['text']}; border: 1px solid {c['border']}; border-radius: {s['radius']}px; padding: {s['control_vertical']}px {s['control_horizontal']}px; }}
QLineEdit:hover, QComboBox:hover, QSpinBox:hover, QTextEdit:hover {{ border-color: {c['border_strong']}; }}
QLineEdit:focus, QComboBox:focus, QSpinBox:focus, QTextEdit:focus {{ border: 1px solid {c['accent']}; }}
QLineEdit:disabled, QComboBox:disabled, QSpinBox:disabled, QTextEdit:disabled {{ background-color: {c['surface']}; color: {c['text_muted']}; }}
QComboBox::drop-down, QSpinBox::up-button, QSpinBox::down-button {{ border: 0; background-color: transparent; }}
QComboBox QAbstractItemView {{ background-color: {c['surface_alt']}; color: {c['text']}; border: 1px solid {c['border_strong']}; selection-background-color: {c['accent']}; selection-color: {c['background']}; }}
QPushButton {{ background-color: {c['surface_alt']}; color: {c['text']}; border: 1px solid {c['border']}; border-radius: {s['radius']}px; padding: {s['control_vertical']}px {s['control_horizontal']}px; }}
QPushButton:hover {{ background-color: {c['border']}; border-color: {c['border_strong']}; }}
QPushButton:pressed {{ background-color: {c['surface']}; }}
QPushButton:focus {{ border: 1px solid {c['accent']}; }}
QPushButton:disabled {{ color: {c['text_muted']}; background-color: {c['surface']}; }}
QPushButton[uiRole="primary"] {{ background-color: {c['accent']}; color: {c['background']}; border-color: {c['accent']}; font-weight: 600; }}
QPushButton[uiRole="primary"]:hover {{ background-color: {c['accent_hover']}; }}
QPushButton[uiRole="primary"]:pressed {{ background-color: {c['accent_pressed']}; }}
QPushButton[uiRole="primary"]:disabled {{ background-color: {c['surface']}; color: {c['text_muted']}; border-color: {c['border']}; }}
QPushButton[uiRole="disclosure"] {{ background-color: transparent; color: {c['text_muted']}; border-color: transparent; padding-left: 2px; }}
QPushButton[uiRole="disclosure"]:hover {{ color: {c['text']}; border-color: {c['border']}; }}
QTabWidget::pane {{ background-color: {c['background']}; border: 1px solid {c['border']}; top: -1px; }}
QTabBar::tab {{ background-color: {c['surface']}; color: {c['text_muted']}; border: 1px solid {c['border']}; padding: 9px 18px; }}
QTabBar::tab:hover {{ color: {c['text']}; background-color: {c['surface_alt']}; }}
QTabBar::tab:selected {{ color: {c['text']}; background-color: {c['surface_alt']}; border-bottom: 2px solid {c['accent']}; }}
QTableView {{ background-color: {c['surface']}; alternate-background-color: {c['surface_alt']}; color: {c['text']}; border: 1px solid {c['border']}; gridline-color: {c['border']}; selection-background-color: {c['accent']}; selection-color: {c['background']}; }}
QTableView::item {{ padding: {s['table_vertical']}px {s['table_horizontal']}px; }}
QTableView::item:focus {{ border: 1px solid {c['accent_hover']}; }}
QHeaderView::section {{ background-color: {c['surface_alt']}; color: {c['text_muted']}; border: 0; border-right: 1px solid {c['border']}; border-bottom: 1px solid {c['border']}; padding: {s['table_vertical']}px {s['table_horizontal']}px; font-weight: 600; }}
QCheckBox {{ spacing: 7px; background-color: transparent; }}
QCheckBox:focus {{ color: {c['accent_hover']}; }}
QProgressBar {{ background-color: {c['surface_alt']}; color: {c['text']}; border: 1px solid {c['border']}; border-radius: {s['radius']}px; text-align: center; }}
QProgressBar::chunk {{ background-color: {c['positive']}; border-radius: 3px; }}
QMenu {{ background-color: {c['surface_alt']}; color: {c['text']}; border: 1px solid {c['border_strong']}; }}
QMenu::item {{ padding: 6px 24px 6px 10px; }}
QMenu::item:selected {{ background-color: {c['accent']}; color: {c['background']}; }}
QScrollBar:vertical, QScrollBar:horizontal {{ background: {c['surface']}; border: 0; margin: 0; }}
QScrollBar::handle:vertical, QScrollBar::handle:horizontal {{ background: {c['border_strong']}; border-radius: 4px; min-height: 24px; min-width: 24px; }}
QScrollBar::handle:hover {{ background: {c['text_muted']}; }}
QScrollBar::add-line, QScrollBar::sub-line {{ width: 0; height: 0; }}
"""


APPLICATION_STYLESHEET = _build_stylesheet()


def apply_application_theme(app: QApplication) -> None:
    app.setStyleSheet(APPLICATION_STYLESHEET)


def set_ui_role(widget: QWidget, role: str) -> None:
    widget.setProperty("uiRole", role)


def set_monospace(widget: QWidget) -> None:
    """Use Qt's cross-platform system fixed font for technical values."""
    widget.setFont(QFontDatabase.systemFont(QFontDatabase.FixedFont))


def configure_data_table(table: QTableView) -> None:
    """Apply shared, data-dense table behaviour without custom painting."""
    table.setAlternatingRowColors(True)
    table.setShowGrid(False)
    table.verticalHeader().hide()
    table.horizontalHeader().setHighlightSections(False)
    table.setHorizontalScrollMode(QAbstractItemView.ScrollPerPixel)
    table.setVerticalScrollMode(QAbstractItemView.ScrollPerPixel)
