"""Shared visual tokens and application-level styling for WolfLauncher."""

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QFontDatabase, QPalette
from PySide6.QtWidgets import (
    QApplication,
    QAbstractItemView,
    QHeaderView,
    QTableView,
    QWidget,
)


COLOURS = {
    "background": "#15130f", "surface": "#1c1912", "surface_alt": "#201c15",
    "border": "#3a3326", "border_strong": "#5a4b32", "text": "#efe9db",
    "text_muted": "#a8a092", "accent": "#e8a33d", "accent_hover": "#f0b45a",
    "accent_pressed": "#c98528", "positive": "#6fcf97", "warning": "#e8a33d",
    "negative": "#e07a7a",
    "table_selection": "#4a351b",
}
SPACING = {"compact": 4, "control_vertical": 6, "control_horizontal": 10,
           "table_vertical": 5, "table_horizontal": 8, "radius": 4}
STATUS_COLOURS = {key: COLOURS[key] for key in ("positive", "warning", "negative")}


def _build_stylesheet() -> str:
    c, s = COLOURS, SPACING
    check_icon = (Path(__file__).resolve().parent / "assets" / "check.svg").as_posix()
    return f"""
QWidget {{ background-color: {c['background']}; color: {c['text']}; selection-background-color: {c['accent']}; selection-color: {c['background']}; }}
QMainWindow, QDialog, QMessageBox {{ background-color: {c['background']}; }}
QLabel {{ background-color: transparent; }}
QLabel:disabled {{ color: {c['text_muted']}; }}
QLabel[uiRole="summary"] {{ color: {c['text']}; font-weight: 600; padding: 2px 0 4px 0; }}
QLabel[uiRole="metadata"] {{ color: {c['text_muted']}; }}
QLabel[uiRole="statusPositive"] {{ color: {c['positive']}; background-color: #1e3a2e; border-radius: 9px; padding: 3px 9px; }}
QLabel[uiRole="statusNegative"] {{ color: {c['negative']}; background-color: #3a1e1e; border-radius: 9px; padding: 3px 9px; }}
QLabel[uiRole="cardTitle"] {{ color: {c['text']}; font-weight: 600; }}
QLabel[uiRole="cardMetadata"], QLabel[uiRole="cardStats"] {{ color: {c['text_muted']}; }}
QLabel[uiRole="pingWarning"] {{ color: {c['warning']}; }}
QLabel[uiRole="pingCritical"] {{ color: {c['negative']}; }}
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
QPushButton:default {{ border: 1px solid {c['accent']}; }}
QPushButton:disabled {{ color: {c['text_muted']}; background-color: {c['surface']}; }}
QPushButton[uiRole="primary"] {{ background-color: {c['accent']}; color: {c['background']}; border-color: {c['accent']}; font-weight: 600; }}
QPushButton[uiRole="primary"]:hover {{ background-color: {c['accent_hover']}; }}
QPushButton[uiRole="primary"]:pressed {{ background-color: {c['accent_pressed']}; }}
QPushButton[uiRole="primary"]:disabled {{ background-color: {c['surface']}; color: {c['text_muted']}; border-color: {c['border']}; }}
QPushButton[uiRole="accent"] {{ color: {c['accent']}; border-color: {c['border_strong']}; background-color: transparent; }}
QPushButton[uiRole="accent"]:hover {{ color: {c['background']}; border-color: {c['accent']}; background-color: {c['accent']}; }}
QPushButton[uiRole="accent"]:disabled {{ color: {c['text_muted']}; border-color: {c['border']}; background-color: {c['surface']}; }}
QPushButton[uiRole="disclosure"] {{ background-color: transparent; color: {c['text_muted']}; border-color: transparent; padding-left: 2px; }}
QPushButton[uiRole="disclosure"]:hover {{ color: {c['text']}; border-color: {c['border']}; }}
QPushButton[uiRole="destructive"] {{ color: {c['negative']}; border-color: {c['negative']}; background-color: transparent; }}
QPushButton[uiRole="destructive"]:hover {{ color: {c['background']}; background-color: {c['negative']}; }}
QPushButton[uiRole="star"] {{ color: {c['text_muted']}; background-color: transparent; border-color: transparent; padding: 4px; font-size: 15px; }}
QPushButton[uiRole="star"]:hover {{ color: {c['accent']}; border-color: {c['border']}; }}
QPushButton[uiRole="star"][favourite="true"] {{ color: {c['accent']}; }}
QFrame[uiRole="serverCard"] {{ background-color: {c['surface']}; border: 1px solid {c['border']}; border-left: 3px solid {c['warning']}; border-radius: 7px; }}
QFrame[uiRole="serverCard"][onlineState="online"] {{ border-left-color: {c['positive']}; }}
QFrame[uiRole="serverCard"][onlineState="offline"] {{ border-left-color: {c['negative']}; }}
QFrame[uiRole="serverCard"][selected="true"] {{ background-color: {c['table_selection']}; border-color: {c['accent']}; }}
QListWidget[uiRole="serverCards"] {{ background-color: {c['background']}; border: 0; outline: 0; }}
QListWidget[uiRole="serverCards"]::item {{ background-color: transparent; border: 0; padding: 3px 0; }}
QListWidget[uiRole="serverCards"]::item:selected {{ background-color: transparent; }}
QTabWidget::pane {{ background-color: {c['background']}; border: 1px solid {c['border']}; top: -1px; }}
QTabBar::tab {{ background-color: {c['surface']}; color: {c['text_muted']}; border: 1px solid {c['border']}; padding: 9px 18px; }}
QTabBar::tab:hover {{ color: {c['text']}; background-color: {c['surface_alt']}; }}
QTabBar::tab:selected {{ color: {c['text']}; background-color: {c['surface_alt']}; border-bottom: 2px solid {c['accent']}; }}
QTableView {{ background-color: {c['surface']}; alternate-background-color: {c['surface_alt']}; color: {c['text']}; border: 1px solid {c['border']}; gridline-color: {c['border']}; selection-background-color: {c['table_selection']}; selection-color: {c['text']}; }}
QTableView::item {{ padding: {s['table_vertical']}px {s['table_horizontal']}px; }}
QTableView::item:hover {{ background-color: {c['surface_alt']}; }}
QTableView::item:focus {{ border: 1px solid {c['accent_hover']}; }}
QTableView:focus {{ border-color: {c['accent']}; }}
QHeaderView::section {{ background-color: {c['surface_alt']}; color: {c['text_muted']}; border: 0; border-right: 1px solid {c['border']}; border-bottom: 1px solid {c['border']}; padding: {s['table_vertical']}px {s['table_horizontal']}px; font-weight: 600; }}
QTableCornerButton::section {{ background-color: {c['surface_alt']}; border: 0; border-right: 1px solid {c['border']}; border-bottom: 1px solid {c['border']}; }}
QCheckBox {{ spacing: 7px; background-color: transparent; }}
QCheckBox:focus {{ color: {c['accent_hover']}; }}
QCheckBox::indicator {{ width: 15px; height: 15px; border: 1px solid {c['border_strong']}; border-radius: 3px; background-color: {c['surface_alt']}; }}
QCheckBox::indicator:hover {{ border-color: {c['accent']}; }}
QCheckBox::indicator:checked {{ background-color: {c['accent']}; border-color: {c['accent']}; image: url("{check_icon}"); }}
QCheckBox::indicator:disabled {{ background-color: {c['surface']}; border-color: {c['border']}; }}
QProgressBar {{ background-color: {c['surface_alt']}; color: {c['text']}; border: 1px solid {c['border']}; border-radius: {s['radius']}px; text-align: center; }}
QProgressBar::chunk {{ background-color: {c['positive']}; border-radius: 3px; }}
QMenu {{ background-color: {c['surface_alt']}; color: {c['text']}; border: 1px solid {c['border_strong']}; }}
QMenu::item {{ padding: 6px 24px 6px 10px; }}
QMenu::item:selected {{ background-color: {c['accent']}; color: {c['background']}; }}
QMenu::separator {{ height: 1px; background-color: {c['border']}; margin: 4px 8px; }}
QStatusBar {{ background-color: {c['surface']}; color: {c['text_muted']}; border-top: 1px solid {c['border']}; }}
QStatusBar::item {{ border: 0; }}
QScrollBar:vertical, QScrollBar:horizontal {{ background: {c['surface']}; border: 0; margin: 0; }}
QScrollBar::handle:vertical, QScrollBar::handle:horizontal {{ background: {c['border_strong']}; border-radius: 4px; min-height: 24px; min-width: 24px; }}
QScrollBar::handle:hover {{ background: {c['text_muted']}; }}
QScrollBar::add-line, QScrollBar::sub-line {{ width: 0; height: 0; }}
QScrollBar::add-page, QScrollBar::sub-page {{ background: transparent; }}
"""


APPLICATION_STYLESHEET = _build_stylesheet()


def build_palette() -> QPalette:
    """Build a complete palette for Qt-owned and partially styled controls."""
    c = COLOURS
    palette = QPalette()
    roles = {
        QPalette.Window: c["background"],
        QPalette.WindowText: c["text"],
        QPalette.Base: c["surface"],
        QPalette.AlternateBase: c["surface_alt"],
        QPalette.ToolTipBase: c["surface_alt"],
        QPalette.ToolTipText: c["text"],
        QPalette.Text: c["text"],
        QPalette.Button: c["surface_alt"],
        QPalette.ButtonText: c["text"],
        QPalette.BrightText: c["accent_hover"],
        QPalette.Highlight: c["accent"],
        QPalette.HighlightedText: c["background"],
        QPalette.Link: c["accent"],
        QPalette.LinkVisited: c["accent_hover"],
        QPalette.PlaceholderText: c["text_muted"],
    }
    for role, colour in roles.items():
        palette.setColor(role, QColor(colour))
    for role in (QPalette.WindowText, QPalette.Text, QPalette.ButtonText):
        palette.setColor(QPalette.Disabled, role, QColor(c["text_muted"]))
    palette.setColor(QPalette.Disabled, QPalette.Highlight, QColor(c["border_strong"]))
    palette.setColor(QPalette.Disabled, QPalette.HighlightedText, QColor(c["text_muted"]))
    return palette


def apply_application_theme(app: QApplication) -> None:
    app.setPalette(build_palette())
    app.setStyleSheet(APPLICATION_STYLESHEET)


def set_ui_role(widget: QWidget, role: str) -> None:
    widget.setProperty("uiRole", role)


def set_monospace(widget: QWidget) -> None:
    """Use Qt's cross-platform system fixed font for technical values."""
    widget.setFont(monospace_font())


def monospace_font():
    """Return Qt's portable system fixed font."""
    return QFontDatabase.systemFont(QFontDatabase.FixedFont)


def configure_data_table(table: QTableView) -> None:
    """Apply shared, data-dense table behaviour without custom painting."""
    table.setAlternatingRowColors(True)
    table.setShowGrid(False)
    table.verticalHeader().hide()
    table.verticalHeader().setMinimumSectionSize(28)
    table.verticalHeader().setDefaultSectionSize(30)
    table.horizontalHeader().setHighlightSections(False)
    table.horizontalHeader().setDefaultAlignment(Qt.AlignLeft | Qt.AlignVCenter)
    table.setHorizontalScrollMode(QAbstractItemView.ScrollPerPixel)
    table.setVerticalScrollMode(QAbstractItemView.ScrollPerPixel)


def configure_priority_columns(
    table: QTableView,
    primary_columns: tuple[int, ...],
    show_details: bool,
    stretch_columns: tuple[int, ...] = (),
) -> None:
    """Put task-critical columns first while retaining optional detail columns."""
    header = table.horizontalHeader()
    all_columns = tuple(range(table.model().columnCount()))
    ordered = primary_columns + tuple(column for column in all_columns if column not in primary_columns)
    for visual_index, logical_index in enumerate(ordered):
        current_visual_index = header.visualIndex(logical_index)
        if current_visual_index != visual_index:
            header.moveSection(current_visual_index, visual_index)
    for column in all_columns:
        table.setColumnHidden(column, not show_details and column not in primary_columns)
        mode = QHeaderView.Stretch if column in stretch_columns else QHeaderView.ResizeToContents
        header.setSectionResizeMode(column, mode)
    header.setStretchLastSection(False)
