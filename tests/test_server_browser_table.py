import os
import unittest
from types import SimpleNamespace

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QCheckBox, QPushButton, QTableWidget

from wolflauncher.app import MainWindow
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
        self.assertIn("Locally validated live name", table.item(0, 0).toolTip())
        self.assertEqual(
            table.item(0, 5).foreground().color().name(),
            STATUS_COLOURS["positive"],
        )
        self.assertTrue(table.isSortingEnabled())

    def test_name_width_is_responsive_but_bounded_on_wide_displays(self):
        self.assertEqual(browser_name_column_width(800), 300)
        self.assertEqual(browser_name_column_width(1388), 416)
        self.assertEqual(browser_name_column_width(1920), 576)

    def test_browser_next_actions_require_a_selected_server(self):
        buttons = [QPushButton(), QPushButton(), QPushButton()]
        window = SimpleNamespace(
            browser_promote_button=buttons[0],
            browser_inspect_button=buttons[1],
            browser_launch_button=buttons[2],
            selected_discovered_server=lambda: None,
        )

        MainWindow.update_browser_selection_context(window)

        self.assertFalse(any(button.isEnabled() for button in buttons))

    def test_required_mods_sort_handles_known_and_unknown_counts(self):
        table = QTableWidget(0, 15)
        unknown = DiscoveredServer(
            name="Unknown mods", host="203.0.113.11", game_port=2302, query_port=27016
        )
        known = DiscoveredServer(
            name="Known mods",
            host="203.0.113.12",
            game_port=2302,
            query_port=27016,
            required_mod_count=17,
        )

        populate_browser_table(table, [unknown, known])
        table.sortItems(11, Qt.AscendingOrder)

        self.assertEqual(table.item(0, 11).text(), "17")
        self.assertEqual(table.item(1, 11).text(), "–")

    def test_detailed_view_keeps_internal_live_name_hidden(self):
        table = QTableWidget(0, 15)
        checkbox = QCheckBox()
        checkbox.setChecked(True)
        window = SimpleNamespace(
            browser_table=table,
            browser_detailed_columns=checkbox,
        )

        MainWindow.configure_browser_columns(window, True)

        self.assertTrue(table.isColumnHidden(1))
        self.assertFalse(table.isColumnHidden(3))

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

    def test_ping_colours_follow_dayz_warning_thresholds(self):
        table = QTableWidget(0, 15)
        servers = [
            DiscoveredServer(
                name="Warning", host="one", game_port=2302, query_port=27016, ping_ms=200
            ),
            DiscoveredServer(
                name="Critical", host="two", game_port=2302, query_port=27016, ping_ms=250
            ),
        ]

        populate_browser_table(table, servers)

        self.assertEqual(
            table.item(0, 8).foreground().color().name(),
            STATUS_COLOURS["warning"],
        )
        self.assertEqual(
            table.item(1, 8).foreground().color().name(),
            STATUS_COLOURS["negative"],
        )


if __name__ == "__main__":
    unittest.main()
