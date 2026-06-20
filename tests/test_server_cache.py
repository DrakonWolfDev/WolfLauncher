import tempfile
import unittest
from pathlib import Path

from wolflauncher.models import DiscoveredServer
from wolflauncher import server_cache


class ServerCacheTests(unittest.TestCase):
    def open_cache(self):
        tmpdir = tempfile.TemporaryDirectory()
        path = Path(tmpdir.name) / "server_cache.sqlite3"
        connection = server_cache.connect(path)
        self.addCleanup(connection.close)
        self.addCleanup(tmpdir.cleanup)
        return connection

    def test_connect_initializes_schema_version(self):
        connection = self.open_cache()

        version = connection.execute("PRAGMA user_version").fetchone()[0]
        tables = connection.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table'"
        ).fetchall()

        self.assertEqual(version, server_cache.SCHEMA_VERSION)
        self.assertIn("discovered_servers", {row["name"] for row in tables})

    def test_upsert_and_get_server_round_trips_discovered_server(self):
        connection = self.open_cache()
        server = DiscoveredServer(
            name="Example Vanilla",
            source="scrape",
            server_name="Example Live Name",
            host="203.0.113.10",
            game_port=2302,
            query_port=27016,
            map_name="chernarusplus",
            players_current=12,
            players_max=60,
            ping_ms=41,
            version="1.26",
            password=True,
            modded=False,
            online=True,
            last_checked="2026-06-20T12:00:00Z",
            last_seen="2026-06-20T12:00:00Z",
        )

        server_cache.upsert_server(connection, server)

        self.assertEqual(server_cache.get_server(connection, server.cache_key), server)

    def test_upsert_replaces_existing_cache_entry(self):
        connection = self.open_cache()
        original = DiscoveredServer(
            name="Old Name",
            host="203.0.113.10",
            game_port=2302,
            query_port=27016,
            players_current=2,
        )
        updated = DiscoveredServer(
            name="New Name",
            host="203.0.113.10",
            game_port=2302,
            query_port=27016,
            players_current=28,
            online=True,
        )

        server_cache.upsert_server(connection, original)
        server_cache.upsert_server(connection, updated)

        cached = server_cache.get_server(connection, updated.cache_key)
        self.assertEqual(cached.name, "New Name")
        self.assertEqual(cached.players_current, 28)
        self.assertTrue(cached.online)

    def test_search_filters_and_sorts_cached_servers(self):
        connection = self.open_cache()
        servers = [
            DiscoveredServer(
                name="Quiet Chernarus",
                host="203.0.113.10",
                game_port=2302,
                query_port=27016,
                map_name="chernarusplus",
                players_current=3,
                ping_ms=90,
                version="1.26",
                online=True,
            ),
            DiscoveredServer(
                name="Busy Namalsk",
                host="203.0.113.20",
                game_port=2302,
                query_port=27016,
                map_name="namalsk",
                players_current=52,
                ping_ms=44,
                version="1.26",
                modded=True,
                online=True,
            ),
            DiscoveredServer(
                name="Offline Namalsk",
                host="203.0.113.30",
                game_port=2302,
                query_port=27016,
                map_name="namalsk",
                players_current=0,
                ping_ms=None,
                version="1.25",
                modded=True,
                online=False,
            ),
        ]
        for item in servers:
            server_cache.upsert_server(connection, item)

        results = server_cache.search_servers(
            connection,
            text="namalsk",
            online_only=True,
            modded=True,
            sort_by="players",
            descending=True,
        )

        self.assertEqual([server.name for server in results], ["Busy Namalsk"])

    def test_search_treats_sql_wildcards_as_literal_text(self):
        connection = self.open_cache()
        server_cache.upsert_server(
            connection,
            DiscoveredServer(
                name="100% Survival",
                host="203.0.113.40",
                game_port=2302,
                query_port=27016,
            ),
        )
        server_cache.upsert_server(
            connection,
            DiscoveredServer(
                name="1000 Survival",
                host="203.0.113.50",
                game_port=2302,
                query_port=27016,
            ),
        )

        results = server_cache.search_servers(connection, text="100%")

        self.assertEqual([server.name for server in results], ["100% Survival"])


if __name__ == "__main__":
    unittest.main()
