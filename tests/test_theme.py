import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtGui import QFontDatabase
from PySide6.QtWidgets import QApplication, QPushButton, QTableWidget

from wolflauncher.theme import (
    APPLICATION_STYLESHEET,
    COLOURS,
    apply_application_theme,
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
