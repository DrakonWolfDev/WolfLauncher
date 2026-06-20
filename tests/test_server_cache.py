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

    def test_upsert_servers_returns_inserted_count(self):
        connection = self.open_cache()

        count = server_cache.upsert_servers(
            connection,
            [
                DiscoveredServer(
                    name="Candidate One",
                    host="203.0.113.10",
                    game_port=27016,
                    query_port=27016,
                ),
                DiscoveredServer(
                    name="Candidate Two",
                    host="203.0.113.20",
                    game_port=27016,
                    query_port=27016,
                ),
            ],
        )

        self.assertEqual(count, 2)
        self.assertEqual(len(server_cache.search_servers(connection)), 2)

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

    def test_import_servers_from_yaml_file_populates_cache(self):
        connection = self.open_cache()
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "discovered.yaml"
            path.write_text(
                """
servers:
  - name: Imported Namalsk
    source: sample
    server_name: Live Imported Namalsk
    host: 203.0.113.60
    game_port: "2302"
    query_port: "27016"
    map: namalsk
    players_current: "14"
    players_max: 40
    ping: "51"
    version: "1.26"
    password: "false"
    modded: "true"
    online: "true"
    last_seen: "2026-06-20T13:30:00Z"
""",
                encoding="utf-8",
            )

            count = server_cache.import_servers_from_file(connection, path)

        imported = server_cache.get_server(connection, "203.0.113.60:2302:27016")
        self.assertEqual(count, 1)
        self.assertEqual(imported.name, "Imported Namalsk")
        self.assertEqual(imported.source, "sample")
        self.assertEqual(imported.server_name, "Live Imported Namalsk")
        self.assertEqual(imported.map_name, "namalsk")
        self.assertEqual(imported.players_current, 14)
        self.assertEqual(imported.players_max, 40)
        self.assertEqual(imported.ping_ms, 51)
        self.assertFalse(imported.password)
        self.assertTrue(imported.modded)
        self.assertTrue(imported.online)

    def test_import_servers_from_json_file_accepts_top_level_list(self):
        connection = self.open_cache()
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "discovered.json"
            path.write_text(
                """
[
  {
    "display_name": "JSON Chernarus",
    "host": "203.0.113.70",
    "game_port": 2302,
    "query_port": 27016
  }
]
""",
                encoding="utf-8",
            )

            count = server_cache.import_servers_from_file(connection, path)

        imported = server_cache.get_server(connection, "203.0.113.70:2302:27016")
        self.assertEqual(count, 1)
        self.assertEqual(imported.name, "JSON Chernarus")
        self.assertEqual(imported.source, "import")

    def test_import_rejects_rows_without_required_ports(self):
        connection = self.open_cache()
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "bad.yaml"
            path.write_text(
                """
servers:
  - name: Broken
    host: 203.0.113.80
    game_port: 2302
""",
                encoding="utf-8",
            )

            with self.assertRaisesRegex(ValueError, "query_port"):
                server_cache.import_servers_from_file(connection, path)


if __name__ == "__main__":
    unittest.main()
