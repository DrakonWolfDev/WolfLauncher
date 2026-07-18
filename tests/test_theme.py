import os
from pathlib import Path
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
    configure_priority_columns,
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
        self.assertIn("check.svg", APPLICATION_STYLESHEET)
        self.assertIn('QTableView[uiRole="browserTable"]', APPLICATION_STYLESHEET)
        self.assertTrue(
            (Path(__file__).resolve().parents[1] / "wolflauncher" / "assets" / "check.svg").is_file()
        )

    def test_atmosphere_asset_is_packaged_with_theme(self):
        self.assertTrue(
            (
                Path(__file__).resolve().parents[1]
                / "wolflauncher"
                / "assets"
                / "wolf-atmosphere-v1.png"
            ).is_file()
        )
        self.assertIn("wolf-atmosphere-v1.png", APPLICATION_STYLESHEET)
        self.assertIn("QTabWidget#mainTabs::pane", APPLICATION_STYLESHEET)

    def test_wolf_mark_is_packaged_with_theme(self):
        mark = (
            Path(__file__).resolve().parents[1]
            / "wolflauncher"
            / "assets"
            / "wolf-mark.svg"
        )
        self.assertTrue(mark.is_file())
        self.assertIn("#e8a33d", mark.read_text())

    def test_restrained_icon_set_is_packaged_as_native_svg(self):
        assets = Path(__file__).resolve().parents[1] / "wolflauncher" / "assets"
        for name in (
            "servers", "browser", "mods", "settings", "add", "refresh", "launch", "recheck"
        ):
            self.assertTrue((assets / f"icon-{name}.svg").is_file())
        for name in ("time-sun.svg", "time-moon.svg"):
            self.assertTrue((assets / name).is_file())
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

    def test_priority_columns_reorder_and_retain_optional_details(self):
        table = QTableWidget(0, 5)
        configure_priority_columns(table, (0, 3, 4), show_details=False, stretch_columns=(0,))
        header = table.horizontalHeader()
        self.assertEqual([header.logicalIndex(index) for index in range(3)], [0, 3, 4])
        self.assertTrue(table.isColumnHidden(1))
        self.assertTrue(table.isColumnHidden(2))

        configure_priority_columns(table, (0, 3, 4), show_details=True, stretch_columns=(0,))
        self.assertFalse(any(table.isColumnHidden(column) for column in range(5)))

    def test_monospace_uses_the_platform_fixed_font(self):
        button = QPushButton("technical value")
        set_monospace(button)
        self.assertEqual(
            button.font().family(),
            QFontDatabase.systemFont(QFontDatabase.FixedFont).family(),
        )


if __name__ == "__main__":
    unittest.main()
