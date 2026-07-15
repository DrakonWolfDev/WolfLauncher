import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtGui import QFontDatabase, QPalette
from PySide6.QtWidgets import QApplication, QPushButton, QTableWidget

from wolflauncher.theme import (
    APPLICATION_STYLESHEET,
    COLOURS,
    apply_application_theme,
    build_palette,
    configure_data_table,
    set_monospace,
    set_ui_role,
)


class ThemeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_application_theme_uses_shared_palette(self):
        apply_application_theme(self.app)
        self.assertEqual(self.app.styleSheet(), APPLICATION_STYLESHEET)
        self.assertIn(COLOURS["background"], APPLICATION_STYLESHEET)
        self.assertIn(COLOURS["accent"], APPLICATION_STYLESHEET)
        self.assertEqual(
            self.app.palette().color(QPalette.Window).name(),
            COLOURS["background"],
        )

    def test_palette_covers_selection_placeholder_and_disabled_text(self):
        palette = build_palette()
        self.assertEqual(palette.color(QPalette.Highlight).name(), COLOURS["accent"])
        self.assertEqual(
            palette.color(QPalette.PlaceholderText).name(), COLOURS["text_muted"]
        )
        self.assertEqual(
            palette.color(QPalette.Disabled, QPalette.Text).name(),
            COLOURS["text_muted"],
        )

    def test_widget_role_is_semantic_dynamic_property(self):
        button = QPushButton("Launch")
        set_ui_role(button, "primary")
        self.assertEqual(button.property("uiRole"), "primary")

    def test_data_table_configuration_preserves_dense_shared_behaviour(self):
        table = QTableWidget()
        configure_data_table(table)
        self.assertTrue(table.alternatingRowColors())
        self.assertFalse(table.showGrid())
        self.assertTrue(table.verticalHeader().isHidden())
        self.assertFalse(table.horizontalHeader().highlightSections())

    def test_monospace_uses_the_platform_fixed_font(self):
        button = QPushButton("technical value")
        set_monospace(button)
        self.assertEqual(
            button.font().family(),
            QFontDatabase.systemFont(QFontDatabase.FixedFont).family(),
        )


if __name__ == "__main__":
    unittest.main()
