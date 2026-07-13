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
        self.assertIn("discovered_server_aliases", {row["name"] for row in tables})
        columns = {
            row["name"]
            for row in connection.execute("PRAGMA table_info(discovered_servers)")
        }
        self.assertIn("stable_server_id", columns)
        self.assertIn("endpoint_aliases", columns)
        self.assertIn("validation_status", columns)
        self.assertIn("mod_metadata_status", columns)
        self.assertIn("mod_manifest_hash", columns)

    def test_schema_v1_migrates_to_v3_without_losing_rows(self):
        tmpdir = tempfile.TemporaryDirectory()
        path = Path(tmpdir.name) / "server_cache.sqlite3"
        self.addCleanup(tmpdir.cleanup)
        connection = server_cache.sqlite3.connect(path)
        connection.execute(
            """
            CREATE TABLE discovered_servers (
                cache_key TEXT PRIMARY KEY,
                source TEXT NOT NULL DEFAULT 'discovered',
                display_name TEXT NOT NULL,
                server_name TEXT NOT NULL DEFAULT '',
                host TEXT NOT NULL,
                game_port INTEGER NOT NULL,
                query_port INTEGER NOT NULL,
                map_name TEXT NOT NULL DEFAULT '',
                players_current INTEGER,
                players_max INTEGER,
                ping_ms INTEGER,
                version TEXT NOT NULL DEFAULT '',
                password INTEGER NOT NULL DEFAULT 0,
                modded INTEGER NOT NULL DEFAULT 0,
                online INTEGER NOT NULL DEFAULT 0,
                last_checked TEXT NOT NULL DEFAULT '',
                last_seen TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        connection.execute(
            """
            INSERT INTO discovered_servers (
                cache_key, display_name, host, game_port, query_port
            ) VALUES ('203.0.113.10:2302:27016', 'Existing', '203.0.113.10', 2302, 27016)
            """
        )
        connection.execute("PRAGMA user_version = 1")
        connection.commit()
        connection.close()

        migrated = server_cache.connect(path)
        self.addCleanup(migrated.close)

        self.assertEqual(
            migrated.execute("PRAGMA user_version").fetchone()[0],
            server_cache.SCHEMA_VERSION,
        )
        cached = server_cache.get_server(migrated, "203.0.113.10:2302:27016")
        self.assertEqual(cached.name, "Existing")
        self.assertEqual(cached.stable_server_id, "")

    def test_initialize_rejects_newer_schema_version(self):
        tmpdir = tempfile.TemporaryDirectory()
        path = Path(tmpdir.name) / "server_cache.sqlite3"
        self.addCleanup(tmpdir.cleanup)
        connection = server_cache.sqlite3.connect(path)
        connection.execute(f"PRAGMA user_version = {server_cache.SCHEMA_VERSION + 1}")
        connection.close()

        with self.assertRaisesRegex(RuntimeError, "newer"):
            server_cache.connect(path)

    def test_schema_v1_migrates_required_count_and_status_source(self):
        connection = server_cache.sqlite3.connect(":memory:")
        self.addCleanup(connection.close)
        connection.execute("CREATE TABLE discovered_servers (cache_key TEXT PRIMARY KEY)")
        connection.execute("PRAGMA user_version = 1")

        server_cache.initialize(connection)

        columns = {
            row[1] for row in connection.execute("PRAGMA table_info(discovered_servers)")
        }
        self.assertEqual(
            connection.execute("PRAGMA user_version").fetchone()[0],
            server_cache.SCHEMA_VERSION,
        )
        self.assertIn("required_mod_count", columns)
        self.assertIn("status_source", columns)

    def test_hardening_schema_v2_adds_wolfapi_columns(self):
        connection = server_cache.sqlite3.connect(":memory:")
        self.addCleanup(connection.close)
        connection.execute(
            """
            CREATE TABLE discovered_servers (
                cache_key TEXT PRIMARY KEY,
                required_mod_count INTEGER,
                status_source TEXT NOT NULL DEFAULT 'provider'
            )
            """
        )
        connection.execute("PRAGMA user_version = 2")

        server_cache.initialize(connection)

        columns = {
            row[1] for row in connection.execute("PRAGMA table_info(discovered_servers)")
        }
        self.assertEqual(
            connection.execute("PRAGMA user_version").fetchone()[0],
            server_cache.SCHEMA_VERSION,
        )
        self.assertIn("stable_server_id", columns)
        self.assertIn("validation_status", columns)

    def test_wolfapi_schema_v2_adds_hardening_columns(self):
        connection = server_cache.sqlite3.connect(":memory:")
        self.addCleanup(connection.close)
        connection.execute(
            """
            CREATE TABLE discovered_servers (
                cache_key TEXT PRIMARY KEY,
                stable_server_id TEXT NOT NULL DEFAULT '',
                endpoint_aliases TEXT NOT NULL DEFAULT '[]'
            )
            """
        )
        connection.execute("PRAGMA user_version = 2")

        server_cache.initialize(connection)

        columns = {
            row[1] for row in connection.execute("PRAGMA table_info(discovered_servers)")
        }
        self.assertEqual(
            connection.execute("PRAGMA user_version").fetchone()[0],
            server_cache.SCHEMA_VERSION,
        )
        self.assertIn("required_mod_count", columns)
        self.assertIn("status_source", columns)

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
            required_mod_count=12,
            status_source="local",
            mod_metadata_status="ready",
            mod_metadata_checked_at="2026-06-20T12:00:00Z",
            mod_metadata_expires_at="2026-06-20T18:00:00Z",
            mod_manifest_hash="sha256:example",
        )

        server_cache.upsert_server(connection, server)

        self.assertEqual(server_cache.get_server(connection, server.cache_key), server)

    def test_stable_wolfapi_id_moves_corrected_endpoint_without_duplicate(self):
        connection = self.open_cache()
        stable_id = "11111111-1111-1111-1111-111111111111"
        original = DiscoveredServer(
            name="Stable Server",
            source="wolfapi",
            host="203.0.113.10",
            game_port=2302,
            query_port=27016,
            stable_server_id=stable_id,
            endpoint_aliases=("203.0.113.10:2302:27016",),
            freshness="recent",
            validation_status="online",
        )
        corrected = DiscoveredServer(
            name="Stable Server",
            source="wolfapi",
            host="203.0.113.10",
            game_port=2402,
            query_port=28016,
            stable_server_id=stable_id,
            endpoint_aliases=(
                "203.0.113.10:2402:28016",
                "203.0.113.10:2302:27016",
            ),
            freshness="live",
            validation_status="online",
        )

        self.assertEqual(
            server_cache.sync_source_servers(connection, "wolfapi", [original]),
            (1, 0),
        )
        self.assertEqual(
            server_cache.sync_source_servers(connection, "wolfapi", [corrected]),
            (0, 0),
        )

        self.assertIsNone(server_cache.get_server(connection, original.cache_key))
        cached = server_cache.get_server(connection, corrected.cache_key)
        self.assertEqual(cached.stable_server_id, stable_id)
        self.assertEqual(cached.endpoint_aliases, corrected.endpoint_aliases)
        self.assertEqual(cached.freshness, "live")
        old_alias = server_cache.get_server_by_endpoint_alias(
            connection,
            "203.0.113.10:2302:27016",
        )
        self.assertEqual(old_alias.cache_key, corrected.cache_key)
        self.assertEqual(len(server_cache.search_servers(connection)), 1)

    def test_bounded_provider_page_merges_without_deleting_other_cached_rows(self):
        connection = self.open_cache()
        first = DiscoveredServer(
            name="First",
            source="wolfapi",
            host="203.0.113.10",
            game_port=2302,
            query_port=27016,
            stable_server_id="11111111-1111-1111-1111-111111111111",
        )
        second = DiscoveredServer(
            name="Second",
            source="wolfapi",
            host="203.0.113.11",
            game_port=2302,
            query_port=27016,
            stable_server_id="22222222-2222-2222-2222-222222222222",
        )
        updated_first = DiscoveredServer(
            name="First Updated",
            source="remote-page",
            host=first.host,
            game_port=first.game_port,
            query_port=first.query_port,
            stable_server_id=first.stable_server_id,
        )
        server_cache.sync_source_servers(connection, "wolfapi", [first, second])

        merged = server_cache.merge_source_servers(
            connection, "wolfapi", [updated_first]
        )

        self.assertEqual(merged, 1)
        self.assertEqual(len(server_cache.search_servers(connection)), 2)
        cached_first = server_cache.get_server(connection, first.cache_key)
        self.assertEqual(cached_first.name, "First Updated")
        self.assertEqual(cached_first.source, "wolfapi")
        self.assertIsNotNone(server_cache.get_server(connection, second.cache_key))

    def test_search_matches_current_and_historical_endpoint_text(self):
        connection = self.open_cache()
        server = DiscoveredServer(
            name="Endpoint Search",
            source="wolfapi",
            host="203.0.113.10",
            game_port=2402,
            query_port=28016,
            stable_server_id="33333333-3333-3333-3333-333333333333",
            endpoint_aliases=("203.0.113.10:2302:27016",),
        )
        server_cache.merge_source_servers(connection, "wolfapi", [server])

        current = server_cache.search_servers(connection, text="203.0.113.10:2402")
        historical = server_cache.search_servers(connection, text="203.0.113.10:2302")

        self.assertEqual([item.stable_server_id for item in current], [server.stable_server_id])
        self.assertEqual(
            [item.stable_server_id for item in historical],
            [server.stable_server_id],
        )

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

    def test_replace_server_key_removes_obsolete_provider_row(self):
        connection = self.open_cache()
        original = DiscoveredServer("Example", "203.0.113.10", 27018, 27018)
        corrected = DiscoveredServer(
            "Example", "203.0.113.10", 37017, 27018, status_source="local"
        )
        server_cache.upsert_server(connection, original)

        server_cache.replace_server_key(connection, original.cache_key, corrected)

        self.assertIsNone(server_cache.get_server(connection, original.cache_key))
        self.assertEqual(
            server_cache.get_server(connection, corrected.cache_key), corrected
        )

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

    def test_sync_source_servers_clears_source_when_provider_returns_no_rows(self):
        connection = self.open_cache()
        server_cache.upsert_server(
            connection,
            DiscoveredServer(
                name="API Server",
                source="battlemetrics",
                host="203.0.113.10",
                game_port=2302,
                query_port=27016,
            ),
        )
        server_cache.upsert_server(
            connection,
            DiscoveredServer(
                name="Imported Server",
                source="import",
                host="203.0.113.20",
                game_port=2302,
                query_port=27016,
            ),
        )

        inserted, removed = server_cache.sync_source_servers(connection, "battlemetrics", [])

        self.assertEqual((inserted, removed), (0, 1))
        self.assertIsNone(server_cache.get_server(connection, "203.0.113.10:2302:27016"))
        self.assertIsNotNone(server_cache.get_server(connection, "203.0.113.20:2302:27016"))

    def test_clear_source_servers_removes_only_that_source(self):
        connection = self.open_cache()
        server_cache.upsert_server(
            connection,
            DiscoveredServer(
                name="API Server",
                source="battlemetrics",
                host="203.0.113.10",
                game_port=2302,
                query_port=27016,
            ),
        )
        server_cache.upsert_server(
            connection,
            DiscoveredServer(
                name="Imported Server",
                source="import",
                host="203.0.113.20",
                game_port=2302,
                query_port=27016,
            ),
        )

        removed = server_cache.clear_source_servers(connection, "battlemetrics")

        self.assertEqual(removed, 1)
        self.assertIsNone(server_cache.get_server(connection, "203.0.113.10:2302:27016"))
        self.assertIsNotNone(server_cache.get_server(connection, "203.0.113.20:2302:27016"))

    def test_sync_source_servers_inserts_only_new_cache_keys(self):
        connection = self.open_cache()
        known = DiscoveredServer(
            name="Known Enriched Name",
            source="steam_web_api",
            host="203.0.113.30",
            game_port=2302,
            query_port=27016,
            players_current=12,
            online=True,
        )
        server_cache.upsert_server(connection, known)

        inserted, removed = server_cache.sync_source_servers(
            connection,
            "steam_web_api",
            [
                DiscoveredServer(
                    name="Provider Renamed Known",
                    source="steam_web_api",
                    host="203.0.113.30",
                    game_port=2302,
                    query_port=27016,
                    players_current=0,
                    online=False,
                ),
                DiscoveredServer(
                    name="New API Server",
                    source="steam_web_api",
                    host="203.0.113.40",
                    game_port=2302,
                    query_port=27016,
                ),
            ],
        )

        self.assertEqual((inserted, removed), (1, 0))
        cached_known = server_cache.get_server(connection, known.cache_key)
        self.assertEqual(cached_known.name, "Known Enriched Name")
        self.assertEqual(cached_known.players_current, 12)
        self.assertTrue(cached_known.online)
        self.assertIsNotNone(server_cache.get_server(connection, "203.0.113.40:2302:27016"))

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

    def test_search_sorts_numeric_values_with_unknowns_last(self):
        connection = self.open_cache()
        for server in [
            DiscoveredServer(
                name="Unknown Ping",
                host="203.0.113.10",
                game_port=2302,
                query_port=27016,
                players_current=None,
                ping_ms=None,
            ),
            DiscoveredServer(
                name="Low Ping",
                host="203.0.113.20",
                game_port=2302,
                query_port=27016,
                players_current=12,
                ping_ms=12,
            ),
            DiscoveredServer(
                name="High Ping",
                host="203.0.113.30",
                game_port=2302,
                query_port=27016,
                players_current=48,
                ping_ms=90,
            ),
        ]:
            server_cache.upsert_server(connection, server)

        ping_ascending = server_cache.search_servers(connection, sort_by="ping")
        players_descending = server_cache.search_servers(
            connection,
            sort_by="players",
            descending=True,
        )

        self.assertEqual(
            [server.name for server in ping_ascending],
            ["Low Ping", "High Ping", "Unknown Ping"],
        )
        self.assertEqual(
            [server.name for server in players_descending],
            ["High Ping", "Low Ping", "Unknown Ping"],
        )

    def test_search_sorts_checked_dates_with_unknowns_last(self):
        connection = self.open_cache()
        for server in [
            DiscoveredServer(
                name="Never Checked",
                host="203.0.113.10",
                game_port=2302,
                query_port=27016,
            ),
            DiscoveredServer(
                name="Old Checked",
                host="203.0.113.20",
                game_port=2302,
                query_port=27016,
                last_checked="2026-06-20T12:00:00+00:00",
            ),
            DiscoveredServer(
                name="Fresh Checked",
                host="203.0.113.30",
                game_port=2302,
                query_port=27016,
                last_checked="2026-06-21T12:00:00+00:00",
            ),
        ]:
            server_cache.upsert_server(connection, server)

        results = server_cache.search_servers(
            connection,
            sort_by="last_checked",
            descending=True,
        )

        self.assertEqual(
            [server.name for server in results],
            ["Fresh Checked", "Old Checked", "Never Checked"],
        )

    def test_search_filters_by_source(self):
        connection = self.open_cache()
        server_cache.upsert_server(
            connection,
            DiscoveredServer(
                name="BattleMetrics Server",
                source="battlemetrics",
                host="203.0.113.10",
                game_port=2302,
                query_port=27016,
            ),
        )
        server_cache.upsert_server(
            connection,
            DiscoveredServer(
                name="Imported Server",
                source="import",
                host="203.0.113.20",
                game_port=2302,
                query_port=27016,
            ),
        )

        results = server_cache.search_servers(connection, source="import")

        self.assertEqual([server.name for server in results], ["Imported Server"])

    def test_search_filters_by_style_terms(self):
        connection = self.open_cache()
        server_cache.upsert_server(
            connection,
            DiscoveredServer(
                name="Quiet Chernarus PvE",
                host="203.0.113.10",
                game_port=2302,
                query_port=27016,
            ),
        )
        server_cache.upsert_server(
            connection,
            DiscoveredServer(
                name="Coastal Combat",
                server_name="Weekend PvP",
                host="203.0.113.20",
                game_port=2302,
                query_port=27016,
            ),
        )

        pve_results = server_cache.search_servers(connection, style_terms=["pve"])
        pvp_results = server_cache.search_servers(connection, style_terms=["pvp"])

        self.assertEqual([server.name for server in pve_results], ["Quiet Chernarus PvE"])
        self.assertEqual([server.name for server in pvp_results], ["Coastal Combat"])

    def test_count_search_servers_uses_same_filters_without_result_limit(self):
        connection = self.open_cache()
        for index in range(3):
            server_cache.upsert_server(
                connection,
                DiscoveredServer(
                    name=f"PvE Server {index}",
                    host=f"203.0.113.{index}",
                    game_port=2302,
                    query_port=27016,
                    online=True,
                ),
            )

        results = server_cache.search_servers(
            connection,
            online_only=True,
            style_terms=["pve"],
            limit=2,
        )
        count = server_cache.count_search_servers(
            connection,
            online_only=True,
            style_terms=["pve"],
        )

        self.assertEqual(len(results), 2)
        self.assertEqual(count, 3)

    def test_cache_summary_counts_total_online_checked_and_seen(self):
        connection = self.open_cache()
        server_cache.upsert_server(
            connection,
            DiscoveredServer(
                name="Online Checked",
                host="203.0.113.10",
                game_port=2302,
                query_port=27016,
                online=True,
                last_checked="2026-06-20T12:00:00Z",
                last_seen="2026-06-20T12:00:00Z",
            ),
        )
        server_cache.upsert_server(
            connection,
            DiscoveredServer(
                name="Offline Unchecked",
                host="203.0.113.20",
                game_port=2302,
                query_port=27016,
            ),
        )

        self.assertEqual(
            server_cache.cache_summary(connection),
            {"total": 2, "online": 1, "checked": 1, "seen": 1},
        )

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

    def test_search_matches_display_name_and_live_server_name(self):
        connection = self.open_cache()
        server_cache.upsert_server(
            connection,
            DiscoveredServer(
                name="Imported Alias",
                server_name="Live Community Server",
                host="203.0.113.40",
                game_port=2302,
                query_port=27016,
            ),
        )

        display_results = server_cache.search_servers(connection, text="Imported")
        live_results = server_cache.search_servers(connection, text="Community")

        self.assertEqual([server.name for server in display_results], ["Imported Alias"])
        self.assertEqual([server.name for server in live_results], ["Imported Alias"])
        self.assertEqual(live_results[0].server_name, "Live Community Server")

    def test_distinct_values_returns_sorted_non_empty_filter_values(self):
        connection = self.open_cache()
        for server in [
            DiscoveredServer(
                name="One",
                host="203.0.113.40",
                game_port=2302,
                query_port=27016,
                map_name="namalsk",
                version="1.26",
            ),
            DiscoveredServer(
                name="Two",
                host="203.0.113.50",
                game_port=2302,
                query_port=27016,
                map_name="chernarusplus",
                version="",
            ),
            DiscoveredServer(
                name="Three",
                host="203.0.113.60",
                game_port=2302,
                query_port=27016,
                map_name="namalsk",
                version="1.25",
            ),
        ]:
            server_cache.upsert_server(connection, server)

        self.assertEqual(
            server_cache.distinct_values(connection, "map"),
            ["chernarusplus", "namalsk"],
        )
        self.assertEqual(server_cache.distinct_values(connection, "version"), ["1.25", "1.26"])

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
