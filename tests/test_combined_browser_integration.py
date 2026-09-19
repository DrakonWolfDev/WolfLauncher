import os
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication, QComboBox, QTableWidget

from wolflauncher import server_cache
from wolflauncher.dayz_product import STABLE
from wolflauncher.local_tools_feature import LocalToolsFeatureMixin
from wolflauncher.models import DiscoveredServer
from wolflauncher.server_browser_controller import BrowserQuery, load_browser_snapshot
from wolflauncher.server_browser_feature import ServerBrowserMixin
from wolflauncher.server_browser_table import BROWSER_COLUMN_COUNT, populate_browser_table


class CombinedBrowserIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_edition_queries_count_before_limit_and_rows_have_no_edition_badge(self):
        with tempfile.TemporaryDirectory() as directory:
            connection = server_cache.connect(Path(directory) / "cache.db")
            self.addCleanup(connection.close)
            rows = [
                DiscoveredServer(
                    f"Community {index}",
                    f"host{index}.test",
                    2302,
                    27016,
                    product=product,
                    source="same-provider",
                    map_name="chernarusplus",
                )
                for product in ("stable", "experimental")
                for index in range(12)
            ]
            server_cache.upsert_servers(connection, rows)
            table = QTableWidget(0, BROWSER_COLUMN_COUNT)
            for product in ("stable", "experimental", "stable"):
                snapshot = load_browser_snapshot(
                    connection, BrowserQuery(products=(product,), text="Community", limit=5)
                )
                self.assertEqual(snapshot.match_count, 12)
                self.assertEqual(len(snapshot.servers), 5)
                self.assertEqual({row.product for row in snapshot.servers}, {product})
                populate_browser_table(table, snapshot.servers)
                self.assertTrue(
                    all(table.item(row, 1).text().startswith("Community ") for row in range(5))
                )
                self.assertTrue(all("EXP" not in table.item(row, 1).text() for row in range(5)))

    def test_edition_switch_invalidates_join_and_late_directory_response(self):
        selector = QComboBox()
        selector.addItem("Stable", "stable")
        selector.addItem("Experimental", "experimental")
        window = SimpleNamespace(
            browser_edition=selector,
            browser_generation=0,
            server_launch=Mock(),
            browser_table=QTableWidget(),
            browser_mod_results={"old": object()},
            remote_search_timer=Mock(),
            remote_map_timer=Mock(),
            browser_selection_timer=Mock(),
            _saved_wolfapi_directory_total=lambda: None,
            settings={},
            refresh_server_browser=Mock(),
            update_browser_edition_notice=Mock(),
            _set_database_refresh_enabled=Mock(),
            maybe_auto_refresh_configured_provider=Mock(),
            schedule_remote_wolfapi_search=Mock(),
            browser_search=Mock(),
        )
        self.assertEqual(ServerBrowserMixin.browser_product_key(window), "stable")
        callback = Mock()
        late_response = ServerBrowserMixin._browser_callback(window, callback)
        selector.setCurrentIndex(1)
        ServerBrowserMixin.change_browser_edition(window)
        late_response(["old stable rows"])
        callback.assert_not_called()
        self.assertIsNone(window.active_discovered_server)
        self.assertEqual(window.browser_mod_results, {})
        window.server_launch.invalidate.assert_called_once()
        self.assertEqual(ServerBrowserMixin.browser_product_key(window), "experimental")
        selector.setCurrentIndex(0)
        ServerBrowserMixin.change_browser_edition(window)
        self.assertEqual(ServerBrowserMixin.browser_product_key(window), "stable")

    def test_local_tools_stay_stable_with_legacy_experimental_selection(self):
        window = SimpleNamespace(
            settings={"local_tool_product": "experimental"},
            mod_selection_target="profile",
            native_steam_mode_key=lambda: "auto",
        )
        with patch("wolflauncher.platform_detection.detect_steam", return_value=[]) as detect:
            LocalToolsFeatureMixin.selected_local_tool_install(window, editor=True)
            detect.assert_called_with(STABLE)
            LocalToolsFeatureMixin.selected_local_tool_install(window, editor=False)
            detect.assert_called_with(STABLE)
            LocalToolsFeatureMixin.selected_local_tool_install(window)
            detect.assert_called_with(STABLE)
