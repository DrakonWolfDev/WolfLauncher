import os
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QCheckBox, QPushButton, QTableWidget

from wolflauncher.app import MainWindow
from wolflauncher.models import DiscoveredServer
from wolflauncher.server_browser_table import (
    browser_name_column_width,
    populate_browser_table,
    update_browser_mod_cell,
    update_browser_table_row,
)
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
        self.assertEqual(buttons[2].text(), "Launch selected server")

    def test_browser_primary_action_names_the_selected_server(self):
        buttons = [QPushButton(), QPushButton(), QPushButton()]
        selected = DiscoveredServer(
            name="Namalsk Adventure",
            host="203.0.113.10",
            game_port=2302,
            query_port=27016,
        )
        window = SimpleNamespace(
            browser_promote_button=buttons[0],
            browser_inspect_button=buttons[1],
            browser_launch_button=buttons[2],
            selected_discovered_server=lambda: selected,
        )

        MainWindow.update_browser_selection_context(window)

        self.assertTrue(all(button.isEnabled() for button in buttons))
        self.assertEqual(buttons[2].text(), "Launch Namalsk Adventure")

    @patch("wolflauncher.app.local_enrichment_due", return_value=True)
    def test_selected_server_check_is_debounced_when_local_data_is_due(self, _due):
        timer = Mock()
        server = DiscoveredServer(
            name="Selected", host="203.0.113.10", game_port=2302, query_port=27016
        )
        window = SimpleNamespace(
            browser_selection_timer=timer,
            selected_discovered_server=lambda: server,
        )

        MainWindow.schedule_selected_discovered_server_check(window)

        timer.stop.assert_called_once_with()
        timer.start.assert_called_once_with()

    @patch("wolflauncher.app.local_enrichment_due", return_value=False)
    def test_selected_server_check_reuses_recent_local_data(self, _due):
        timer = Mock()
        server = DiscoveredServer(
            name="Selected", host="203.0.113.10", game_port=2302, query_port=27016
        )
        window = SimpleNamespace(
            browser_selection_timer=timer,
            selected_discovered_server=lambda: server,
        )

        MainWindow.schedule_selected_discovered_server_check(window)

        timer.stop.assert_called_once_with()
        timer.start.assert_not_called()

    def test_bulk_check_progress_only_updates_lightweight_summary(self):
        window = SimpleNamespace(
            enrichment_mode="bulk",
            browser_summary=Mock(),
        )

        MainWindow.handle_enrichment_progress(window, ("old", object()), 10, 200)

        window.browser_summary.setText.assert_called_once_with(
            "Checked 10 of 200 visible server(s) locally..."
        )

    @patch("wolflauncher.app.server_cache.upsert_servers", return_value=200)
    def test_bulk_check_persists_and_refreshes_once_at_completion(self, upsert):
        servers = [object(), object()]
        window = SimpleNamespace(
            enrichment_mode="bulk",
            enrich_visible_button=Mock(),
            server_cache=object(),
            refresh_server_browser=Mock(),
            statusBar=Mock(return_value=Mock()),
        )

        MainWindow.handle_enrichment_ready(window, servers, "")

        upsert.assert_called_once_with(window.server_cache, servers)
        window.refresh_server_browser.assert_called_once_with()

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
        self.assertIn("when you select", table.item(0, 8).toolTip())
        self.assertEqual(
            table.item(0, 5).foreground().color().name(),
            STATUS_COLOURS["negative"],
        )

    def test_single_enrichment_updates_only_the_selected_table_row(self):
        table = QTableWidget(0, 15)
        original = DiscoveredServer(
            name="Selected", host="203.0.113.11", game_port=2302, query_port=27016
        )
        neighbour = DiscoveredServer(
            name="Neighbour", host="203.0.113.12", game_port=2302, query_port=27016
        )
        populate_browser_table(table, [original, neighbour])
        neighbour_item = table.item(0, 0) if table.item(0, 0).text() == "Neighbour" else table.item(1, 0)
        enriched = DiscoveredServer(
            name="Selected",
            host="203.0.113.11",
            game_port=2302,
            query_port=27016,
            online=True,
            status_source="local",
            ping_ms=42,
        )

        self.assertTrue(update_browser_table_row(table, original.cache_key, enriched))

        self.assertEqual(table.rowCount(), 2)
        self.assertEqual(neighbour_item.text(), "Neighbour")
        selected_items = [
            table.item(row, 0)
            for row in range(table.rowCount())
            if table.item(row, 0).data(Qt.UserRole) == enriched.cache_key
        ]
        self.assertEqual(len(selected_items), 1)
        selected_row = selected_items[0].row()
        self.assertEqual(table.item(selected_row, 5).text(), "ONLINE")
        self.assertEqual(table.item(selected_row, 8).text(), "42ms")

    def test_local_mod_preview_replaces_only_the_matching_mods_cell(self):
        table = QTableWidget(0, 15)
        selected = DiscoveredServer(
            name="Selected", host="203.0.113.11", game_port=2302, query_port=27016
        )
        populate_browser_table(table, [selected])

        self.assertTrue(
            update_browser_mod_cell(
                table,
                selected.cache_key,
                "3 MISSING",
                "Launch will run pre-flight.",
                STATUS_COLOURS["negative"],
            )
        )

        self.assertEqual(table.item(0, 11).text(), "3 MISSING")
        self.assertIn("pre-flight", table.item(0, 11).toolTip())

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
