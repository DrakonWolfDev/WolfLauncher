import json
import sqlite3
import subprocess
import tempfile
import unittest
from contextlib import closing
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QLabel, QTableWidget

from wolflauncher import server_cache
from wolflauncher.curated_server_presenter import curated_server_row
from wolflauncher.curated_servers_controller import CuratedServersMixin
from wolflauncher.curated_status_cache import load_status_cache, save_status_cache
from wolflauncher.models import DiscoveredServer, Server
from wolflauncher.server_browser_presenter import browser_inspector, browser_row
from wolflauncher.server_browser_table import populate_browser_table, update_browser_table_row
from wolflauncher.server_enrichment import enrich_discovered_server
from wolflauncher.server_queue import players_queue_tooltip, players_with_queue, queue_text
from wolflauncher.settings import server_key
from wolflauncher.status import ServerStatus, check_server, dayz_queue_count


class QueueTests(unittest.TestCase):
    def candidate(self, **kwargs):
        return DiscoveredServer("Example", "203.0.113.10", 2302, 2303, **kwargs)

    def test_decoder_rejects_missing_malformed_and_ambiguous_queue_evidence(self):
        for value in (None, True, False, -1, 65536, 1.5, "12", {}, []):
            with self.subTest(value=value):
                self.assertIsNone(dayz_queue_count({"queue": value}))
        for tag in (
            "lqs",
            "lqs-1",
            "lqs12bad",
            "lqs1.5",
            "lqs 2",
            "lqs１２",
            "lqs65536",
            "lqs000000",
        ):
            with self.subTest(tag=tag):
                self.assertIsNone(dayz_queue_count({"tags": [tag], "queue": 12}))
        self.assertIsNone(dayz_queue_count({"tags": ["lqs0", "lqs12"], "queue": 12}))
        for count in (0, 12, 65535):
            self.assertEqual(dayz_queue_count({"tags": [f"lqs{count}"]}), count)
            self.assertEqual(dayz_queue_count({"queue": count}), count)

    def test_live_fixture_and_positive_queue_pass_through_actual_status_decoder(self):
        fixture = json.loads((Path(__file__).parent / "fixtures/dayz_queue_live.json").read_text())
        saved = Server("Example", "Tests", "203.0.113.10", 2302, 2303)
        samples = fixture["responses"] + [
            {
                "name": "Full example",
                "numplayers": 60,
                "maxplayers": 60,
                "raw": {"tags": ["lqs12"], "queue": 12},
            },
            {"name": "Full without queue", "numplayers": 60, "maxplayers": 60},
        ]
        for data, expected in zip(samples, (0, 0, 12, None), strict=True):
            with (
                self.subTest(data=data["name"]),
                patch("wolflauncher.status.gamedig_command", return_value=["gamedig"]),
                patch(
                    "wolflauncher.status.subprocess.run",
                    return_value=subprocess.CompletedProcess([], 0, json.dumps(data), ""),
                ),
            ):
                status = check_server(saved)
                self.assertTrue(status.online)
                self.assertEqual(status.queue_count, expected)
                enriched = enrich_discovered_server(
                    self.candidate(), status, status.query_started_at
                )
                self.assertEqual(enriched.queue_count, expected)
                label = f"{enriched.players_current} / {enriched.players_max}"
                if expected:
                    label += f" +{expected}"
                self.assertEqual(label, browser_row(enriched).values[7])
                self.assertEqual(label, browser_inspector(enriched).players)
                self.assertEqual(label.replace(" ", ""), curated_server_row(saved, status)[10])

    def test_zero_unknown_stale_and_future_measurements_are_distinct(self):
        now = datetime(2026, 11, 3, tzinfo=timezone.utc)
        self.assertEqual(queue_text(0, now.isoformat(), now=now), "Queue: 0")
        self.assertEqual(queue_text(None, now.isoformat(), now=now), "Queue: unknown")
        for checked in (
            "",
            "bad",
            "2026-11-03T00:00:00",
            (now - timedelta(seconds=120)).isoformat(),
            (now + timedelta(seconds=1)).isoformat(),
        ):
            with self.subTest(checked=checked):
                self.assertEqual(queue_text(0, checked, now=now), "Queue: 0 (stale)")

    def test_counts_show_only_a_fresh_positive_queue(self):
        now = datetime.now(timezone.utc)
        fresh = now.isoformat()
        self.assertEqual(players_with_queue("10/20", 0, fresh), "10 / 20")
        self.assertEqual(players_with_queue("20/20", 5, fresh), "20 / 20 +5")
        self.assertEqual(players_with_queue("2/60", 0, fresh), "2 / 60")
        self.assertEqual(players_with_queue("20/20", 2, fresh), "20 / 20 +2")
        self.assertEqual(players_with_queue("2 / 60", 0, fresh, compact=True), "2/60")
        self.assertEqual(players_with_queue("20 / 20", 2, fresh, compact=True), "20/20+2")
        self.assertIn("Queue: 5", players_queue_tooltip(5, fresh))
        for count, checked in (
            (None, fresh),
            (True, fresh),
            (-1, fresh),
            (0, (now - timedelta(seconds=121)).isoformat()),
            (5, (now + timedelta(seconds=60)).isoformat()),
            (0, "bad"),
        ):
            with self.subTest(count=count, checked=checked):
                self.assertEqual(players_with_queue("10/20", count, checked), "10 / 20")
        self.assertIn("not available", players_queue_tooltip(None, fresh))
        self.assertIn("expired", players_queue_tooltip(0, "bad"))

    def test_failed_or_missing_live_queue_clears_previous_observation(self):
        previous = self.candidate(queue_count=12, queue_checked_at="2026-11-03T00:00:00Z")
        for status in (ServerStatus(False), ServerStatus(True, players="60/60")):
            result = enrich_discovered_server(previous, status, "2026-11-03T00:01:00Z")
            self.assertIsNone(result.queue_count)
            self.assertEqual(result.queue_checked_at, "")
            self.assertNotIn("+", browser_row(result).values[7])

    def test_old_and_invalid_curated_cache_dont_invent_zero(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "status.json"
            save_status_cache(
                {
                    "known": ServerStatus(
                        True, queue_count=0, query_started_at="2026-11-03T00:00:00Z"
                    )
                },
                path,
            )
            self.assertEqual(load_status_cache(path)["known"].queue_count, 0)
            self.assertEqual(
                load_status_cache(path)["known"].query_started_at, "2026-11-03T00:00:00Z"
            )
            path.write_text(json.dumps({"old": {"online": True}, "bad": {"queue_count": True}}))
            self.assertIsNone(load_status_cache(path)["old"].queue_count)
            self.assertIsNone(load_status_cache(path)["bad"].queue_count)

    def test_schema_nine_migration_preserves_rows_and_adds_unknown_queue(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "cache.sqlite3"
            connection = server_cache.connect(path)
            server_cache.upsert_server(connection, self.candidate())
            connection.execute("ALTER TABLE discovered_servers DROP COLUMN queue_count")
            connection.execute("ALTER TABLE discovered_servers DROP COLUMN queue_checked_at")
            connection.execute("PRAGMA user_version = 9")
            connection.commit()
            connection.close()
            with closing(server_cache.connect(path)) as connection:
                result = server_cache.get_server(connection, self.candidate().cache_key)
                self.assertEqual(result.name, "Example")
                self.assertIsNone(result.queue_count)
                self.assertEqual(result.queue_checked_at, "")

    def test_provider_refresh_cannot_refresh_move_or_resurrect_queue(self):
        connection = sqlite3.connect(":memory:")
        connection.row_factory = sqlite3.Row
        self.addCleanup(connection.close)
        server_cache.initialize(connection)
        measured = self.candidate(
            status_source="local",
            stable_server_id="id1",
            queue_count=12,
            queue_checked_at="2026-11-03T00:00:00Z",
        )
        server_cache.upsert_server(connection, measured)
        provider = replace(
            measured,
            status_source="provider",
            queue_count=None,
            queue_checked_at="",
            last_checked="2026-11-03T01:00:00Z",
        )
        server_cache.upsert_server(connection, provider)
        result = server_cache.get_server(connection, measured.cache_key)
        self.assertEqual(
            (result.queue_count, result.queue_checked_at), (12, measured.queue_checked_at)
        )
        failed = enrich_discovered_server(result, ServerStatus(False), "2026-11-03T02:00:00Z")
        server_cache.upsert_server(connection, failed)
        server_cache.upsert_server(connection, provider)
        self.assertIsNone(server_cache.get_server(connection, measured.cache_key).queue_count)
        server_cache.upsert_server(connection, measured)
        moved = replace(provider, host="203.0.113.11")
        server_cache.upsert_server(connection, moved)
        self.assertIsNone(server_cache.get_server(connection, moved.cache_key).queue_count)


class QueueDisplayTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_incremental_live_update_and_expiry_preserve_selection_and_player_sort(self):
        browser = QTableWidget(0, 18)
        curated = QTableWidget(1, 16)
        self.addCleanup(browser.close)
        self.addCleanup(curated.close)
        now = datetime.now(timezone.utc).isoformat()
        first = DiscoveredServer(
            "Example", "203.0.113.10", 2302, 2303, players_current=60, players_max=60
        )
        populate_browser_table(browser, [first])
        browser.selectRow(0)
        live = replace(first, queue_count=12, queue_checked_at=now)
        self.assertTrue(update_browser_table_row(browser, first.cache_key, live))
        self.assertEqual(browser.item(0, 8).text(), "60 / 60 +12")
        self.assertEqual(browser.item(0, 8).sort_value, 60)
        self.assertEqual(browser.item(0, 8).data(Qt.UserRole), first.cache_key)
        saved = Server("Example", "Test", first.host, first.game_port, first.query_port)
        status = ServerStatus(True, players="60/60", queue_count=12, query_started_at=now)
        from PySide6.QtWidgets import QTableWidgetItem

        curated.setItem(0, 10, QTableWidgetItem("60/60+12"))
        window = SimpleNamespace(
            servers=[saved],
            table=curated,
            browser_table=browser,
            curated_status_cache={server_key(saved): status},
            refresh_curated_server_cards=Mock(),
            selected_discovered_server=Mock(return_value=live),
            browser_detail_players=QLabel(),
        )
        with patch("wolflauncher.server_queue.datetime") as clock:
            clock.fromisoformat = datetime.fromisoformat
            clock.now.return_value = datetime.now(timezone.utc) + timedelta(seconds=121)
            CuratedServersMixin.refresh_queue_displays(window)
        self.assertEqual(browser.currentRow(), 0)
        self.assertEqual(browser.item(0, 8).text(), "60 / 60")
        self.assertEqual(curated.item(0, 10).text(), "60/60")
        self.assertEqual(window.browser_detail_players.text(), "60 / 60")
        self.assertIn("expired", browser.item(0, 8).toolTip())
        self.assertIn("expired", curated.item(0, 10).toolTip())
        window.refresh_curated_server_cards.assert_called_once()
