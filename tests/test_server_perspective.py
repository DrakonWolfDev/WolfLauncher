import sqlite3
import unittest

from wolflauncher import server_cache
from wolflauncher.models import DiscoveredServer
from wolflauncher.server_browser_controller import BrowserQuery, load_browser_snapshot
from wolflauncher.server_perspective import perspective_from_keywords


class PerspectiveTests(unittest.TestCase):
    def test_advertised_keywords(self):
        for value, expected in (
            ("battleye,no3rd,external,12:30", "first_person"),
            (["battleye", "no3rd"], "first_person"),
            ("battleye,external,12:30", "third_person"),
            ("mod", "unknown"),
            ("firstperson", "unknown"),
            ("", "unknown"),
            (None, "unknown"),
            ([], "unknown"),
            ("notno3rd,mod", "unknown"),
        ):
            with self.subTest(value=value):
                self.assertEqual(perspective_from_keywords(value), expected)

    def test_discovery_and_local_enrichment(self):
        from wolflauncher.server_discovery import discovered_server_from_wolfapi_row
        from wolflauncher.server_enrichment import enrich_discovered_server
        from wolflauncher.status import ServerStatus

        server = discovered_server_from_wolfapi_row(
            {
                "name": "Example",
                "host": "203.0.113.1",
                "game_port": 2302,
                "query_port": 27016,
                "gametype": "battleye,no3rd,external",
            }
        )
        self.assertEqual(server.perspective, "first_person")
        refreshed = enrich_discovered_server(
            server, ServerStatus(online=True, perspective="third_person"), "2026-10-18"
        )
        self.assertEqual(refreshed.perspective, "third_person")
        offline = enrich_discovered_server(server, ServerStatus(online=False), "2026-10-18")
        self.assertEqual(offline.perspective, "first_person")

    def test_cache_and_browser_filters(self):
        connection = sqlite3.connect(":memory:")
        self.addCleanup(connection.close)
        connection.row_factory = sqlite3.Row
        server_cache.initialize(connection)
        for index, perspective in enumerate(("first_person", "third_person", "unknown")):
            server_cache.upsert_server(
                connection,
                DiscoveredServer(
                    name=f"Server {index}",
                    host=f"203.0.113.{index + 1}",
                    game_port=2302,
                    query_port=27016,
                    perspective=perspective,
                ),
            )
        for perspective in ("first_person", "third_person", "unknown"):
            snapshot = load_browser_snapshot(connection, BrowserQuery(perspective=perspective))
            self.assertEqual(snapshot.match_count, 1)
            self.assertEqual([s.perspective for s in snapshot.servers], [perspective])
        self.assertEqual(load_browser_snapshot(connection, BrowserQuery()).match_count, 3)

    def test_v8_migration_preserves_unknown(self):
        connection = sqlite3.connect(":memory:")
        self.addCleanup(connection.close)
        connection.row_factory = sqlite3.Row
        server_cache.initialize(connection)
        server_cache.upsert_server(
            connection,
            DiscoveredServer(
                name="Existing",
                host="203.0.113.1",
                game_port=2302,
                query_port=27016,
            ),
        )
        connection.execute("ALTER TABLE discovered_servers DROP COLUMN perspective")
        connection.execute("PRAGMA user_version = 8")
        server_cache.initialize(connection)
        self.assertEqual(server_cache.search_servers(connection)[0].perspective, "unknown")
        self.assertEqual(connection.execute("PRAGMA user_version").fetchone()[0], 9)
