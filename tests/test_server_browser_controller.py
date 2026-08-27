import tempfile
import unittest
from pathlib import Path

from wolflauncher import server_cache
from wolflauncher.models import DiscoveredServer
from wolflauncher.server_browser_controller import (
    BrowserQuery,
    browser_filter_options,
    load_browser_snapshot,
)


class ServerBrowserControllerTests(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmpdir.cleanup)
        self.connection = server_cache.connect(Path(self.tmpdir.name) / "cache.sqlite3")
        self.addCleanup(self.connection.close)
        server_cache.upsert_servers(
            self.connection,
            [
                DiscoveredServer(
                    name="Quiet PvE Chernarus",
                    host="203.0.113.10",
                    game_port=2302,
                    query_port=27016,
                    map_name="chernarusplus",
                    players_current=5,
                    version="1.26",
                    source="wolfapi",
                    online=True,
                ),
                DiscoveredServer(
                    name="Busy PvP Namalsk",
                    host="203.0.113.20",
                    game_port=2302,
                    query_port=27016,
                    map_name="namalsk",
                    players_current=45,
                    version="1.25",
                    source="battlemetrics",
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
                    version="1.25",
                    source="battlemetrics",
                    modded=True,
                    quality_flags=("suspicious_bots",),
                ),
                DiscoveredServer(
                    name="Lower Bitterroot",
                    host="203.0.113.40",
                    game_port=2302,
                    query_port=27016,
                    map_name="bitterroot",
                    source="wolfapi",
                ),
                DiscoveredServer(
                    name="Upper Bitterroot",
                    host="203.0.113.41",
                    game_port=2302,
                    query_port=27016,
                    map_name="Bitterroot",
                    source="wolfapi",
                ),
                DiscoveredServer(
                    name="Livonia alias",
                    host="203.0.113.42",
                    game_port=2302,
                    query_port=27016,
                    map_name="enoch",
                    source="wolfapi",
                ),
                DiscoveredServer(
                    name="\ufffd\ufffd\ufffd",
                    host="203.0.113.43",
                    game_port=2302,
                    query_port=27016,
                    source="wolfapi",
                    online=True,
                ),
                DiscoveredServer(
                    name="Experimental Chernarus",
                    host="203.0.113.11",
                    game_port=2302,
                    query_port=27016,
                    map_name="chernarusplus",
                    source="wolfapi_experimental",
                    online=True,
                ),
                DiscoveredServer(
                    name="\x01" * 63,
                    host="203.0.113.44",
                    game_port=2302,
                    query_port=27016,
                    source="wolfapi",
                    online=True,
                ),
            ],
        )

    def test_snapshot_applies_filters_sorting_count_and_summary(self):
        snapshot = load_browser_snapshot(
            self.connection,
            BrowserQuery(
                online_only=True,
                style_terms=("pvp",),
                modded=True,
                sort_by="players",
                descending=True,
                limit=200,
            ),
        )

        self.assertEqual([server.name for server in snapshot.servers], ["Busy PvP Namalsk"])
        self.assertEqual(snapshot.match_count, 1)
        self.assertEqual(snapshot.cache_summary["total"], 9)
        self.assertEqual(snapshot.cache_summary["online"], 5)

    def test_snapshot_count_is_not_limited_to_visible_rows(self):
        snapshot = load_browser_snapshot(self.connection, BrowserQuery(limit=1))

        self.assertEqual(len(snapshot.servers), 1)
        self.assertEqual(snapshot.match_count, 7)

    def test_snapshot_quietly_hides_malformed_names(self):
        snapshot = load_browser_snapshot(self.connection, BrowserQuery(limit=200))

        self.assertNotIn("\ufffd\ufffd\ufffd", [server.name for server in snapshot.servers])
        self.assertNotIn("\x01" * 63, [server.name for server in snapshot.servers])
        self.assertEqual(snapshot.match_count, 7)

    def test_snapshot_optionally_hides_quality_flagged_rows(self):
        snapshot = load_browser_snapshot(
            self.connection,
            BrowserQuery(hide_quality_flagged=True),
        )

        self.assertNotIn("Offline Namalsk", [server.name for server in snapshot.servers])
        self.assertEqual(snapshot.match_count, 6)

    def test_filter_options_are_distinct_and_sorted(self):
        options = browser_filter_options(self.connection)

        self.assertEqual(
            options["map"],
            ["Bitterroot", "ChernarusPlus", "Livonia", "Namalsk"],
        )
        self.assertEqual(options["version"], ["1.25", "1.26"])
        self.assertEqual(options["source"], ["battlemetrics", "wolfapi", "wolfapi_experimental"])

    def test_experimental_namespace_excludes_stable_cached_servers(self):
        snapshot = load_browser_snapshot(
            self.connection,
            BrowserQuery(source_namespace="_experimental"),
        )

        self.assertEqual([server.name for server in snapshot.servers], ["Experimental Chernarus"])
        self.assertEqual(snapshot.match_count, 1)
        self.assertEqual(
            browser_filter_options(self.connection, "_experimental")["source"],
            ["wolfapi_experimental"],
        )

    def test_canonical_map_filter_matches_all_cached_casing_and_aliases(self):
        bitterroot = load_browser_snapshot(self.connection, BrowserQuery(map_name="Bitterroot"))
        livonia = load_browser_snapshot(self.connection, BrowserQuery(map_name="Livonia"))

        self.assertEqual(bitterroot.match_count, 2)
        self.assertEqual(livonia.match_count, 1)
        self.assertEqual(livonia.servers[0].map_name, "enoch")


if __name__ == "__main__":
    unittest.main()
