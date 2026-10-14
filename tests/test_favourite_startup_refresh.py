import os
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication, QTableWidget, QTableWidgetItem

from wolflauncher.curated_server_cards import CuratedServerCard
from wolflauncher.curated_servers_controller import CuratedServersMixin
from wolflauncher.models import Server
from wolflauncher.settings import server_key
from wolflauncher.status import ServerStatus


class FavouriteStartupRefreshTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_startup_keeps_last_known_details_without_claiming_live_status(self):
        server = Server("Favourite", "Tests", "dayz.test", 2302, 27016)
        previous = ServerStatus(
            True, server_name="Live name", map_name="chernarusplus", players="12/60", ping="42"
        )
        table = QTableWidget(1, 16)
        self.addCleanup(table.close)
        window = SimpleNamespace(
            servers=[server],
            table=table,
            curated_status_cache={server_key(server): previous},
            _set_curated_server_table_item=lambda row, col, text, cached=False: table.setItem(
                row, col, QTableWidgetItem(text)
            ),
            update_curated_status_summary=Mock(),
            refresh_curated_server_cards=Mock(),
        )
        CuratedServersMixin._mark_startup_status_rows_checking(window, [0])
        values = [table.item(0, col).text() for col in range(16)]
        self.assertEqual(values[8], "Rechecking…")
        self.assertEqual(values[10], "12/60")
        self.assertEqual(values[12], "42ms")
        card = CuratedServerCard(0, values)
        self.addCleanup(card.close)
        self.assertIn("Rechecking", card.metadata_label.text())
        self.assertIn("Last known", card.metadata_label.text())
        self.assertFalse(card.connect_button.isEnabled())
        self.assertIs(window.curated_status_cache[server_key(server)], previous)

    @patch("wolflauncher.curated_servers_controller.StatusWorker")
    def test_only_startup_enables_retry_and_pending_display(self, worker_type):
        for startup in (False, True):
            with self.subTest(startup=startup):
                worker_type.reset_mock()
                window = SimpleNamespace(
                    worker=None,
                    servers=[Mock()],
                    _set_status_refresh_enabled=Mock(),
                    last_refresh_label=Mock(),
                    _mark_startup_status_rows_checking=Mock(),
                    update_status_row=Mock(),
                    handle_refresh_finished=Mock(),
                )
                CuratedServersMixin.refresh_status_rows(window, [0], "Refreshing", startup=startup)
                if startup:
                    worker_type.assert_called_once_with(window.servers, [0], retry_failed=True)
                    window._mark_startup_status_rows_checking.assert_called_once_with([0])
                else:
                    worker_type.assert_called_once_with(window.servers, [0])
                    window._mark_startup_status_rows_checking.assert_not_called()

    def test_startup_does_not_reuse_cached_failure_as_current_status(self):
        server = Server("Favourite", "Tests", "dayz.test", 2302, 27016)
        for cached in (None, ServerStatus(False, error="Previous timeout")):
            with self.subTest(cached=cached):
                cells = {}
                window = SimpleNamespace(
                    servers=[server],
                    table=Mock(),
                    curated_status_cache={server_key(server): cached} if cached else {},
                    _set_curated_server_table_item=lambda row, col, text, **kwargs: cells.update(
                        {col: text}
                    ),
                    update_curated_status_summary=Mock(),
                    refresh_curated_server_cards=Mock(),
                )
                window.table.rowCount.return_value = 1
                CuratedServersMixin._mark_startup_status_rows_checking(window, [0])
                self.assertEqual(cells[8], "Checking…")
                self.assertEqual(cells[9], "")
