import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QTableWidget

from wolflauncher.models import DiscoveredServer
from wolflauncher.server_browser_table import browser_name_column_width, populate_browser_table
from wolflauncher.theme import STATUS_COLOURS
from wolflauncher.table_items import SortableTableWidgetItem


class ServerBrowserTableTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_population_preserves_display_sort_key_tooltip_and_status_colour(self):
        table = QTableWidget(0, 15)
        server = DiscoveredServer(
            name="Cached Name",
            server_name="Live Name",
            host="203.0.113.10",
            game_port=2302,
            query_port=27016,
            players_current=12,
            players_max=60,
            ping_ms=42,
            online=True,
            status_source="local",
        )

        populate_browser_table(table, [server])

        self.assertEqual(table.rowCount(), 1)
        self.assertEqual(table.item(0, 1).text(), "Live Name")
        self.assertEqual(table.item(0, 7).text(), "12/60")
        self.assertIsInstance(table.item(0, 7), SortableTableWidgetItem)
        self.assertEqual(table.item(0, 7).sort_value, 12)
        self.assertEqual(table.item(0, 0).data(Qt.UserRole), server.cache_key)
        self.assertEqual(table.item(0, 0).toolTip(), "Live name: Live Name")
        self.assertEqual(
            table.item(0, 5).foreground().color().name(),
            STATUS_COLOURS["positive"],
        )
        self.assertTrue(table.isSortingEnabled())

    def test_name_width_is_responsive_but_bounded_on_wide_displays(self):
        self.assertEqual(browser_name_column_width(800), 360)
        self.assertEqual(browser_name_column_width(1388), 582)
        self.assertEqual(browser_name_column_width(1920), 600)

    def test_population_replaces_existing_rows_and_keeps_missing_ping_guidance(self):
        table = QTableWidget(3, 15)
        server = DiscoveredServer(
            name="Offline Server",
            host="203.0.113.11",
            game_port=2302,
            query_port=27016,
            status_source="local",
        )

        populate_browser_table(table, [server])

        self.assertEqual(table.rowCount(), 1)
        self.assertIn("Enrich visible", table.item(0, 8).toolTip())
        self.assertEqual(
            table.item(0, 5).foreground().color().name(),
            STATUS_COLOURS["negative"],
        )


if __name__ == "__main__":
    unittest.main()
