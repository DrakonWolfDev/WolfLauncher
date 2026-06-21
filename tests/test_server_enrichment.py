import unittest

from wolflauncher.models import DiscoveredServer
from wolflauncher.server_enrichment import enrich_discovered_server, parse_connect_port, parse_players
from wolflauncher.status import ServerStatus


class ServerEnrichmentTests(unittest.TestCase):
    def make_candidate(self) -> DiscoveredServer:
        return DiscoveredServer(
            name="203.0.113.10:27016",
            source="steam_master",
            host="203.0.113.10",
            game_port=27016,
            query_port=27016,
            last_seen="2026-06-20T12:00:00Z",
        )

    def test_parse_players_reads_current_and_maximum(self):
        self.assertEqual(parse_players("12/60"), (12, 60))

    def test_parse_players_tolerates_unknown_values(self):
        self.assertEqual(parse_players("0/?"), (0, None))
        self.assertEqual(parse_players(""), (None, None))

    def test_online_status_updates_browser_fields_without_renaming_display_name(self):
        enriched = enrich_discovered_server(
            self.make_candidate(),
            ServerStatus(
                online=True,
                server_name="Live Server",
                map_name="namalsk",
                players="12/60",
                version="1.26",
                ping="42",
                password=True,
                modded=True,
                connect="203.0.113.10:2302",
            ),
            "2026-06-20T14:00:00+00:00",
        )

        self.assertEqual(enriched.name, "203.0.113.10:27016")
        self.assertEqual(enriched.server_name, "Live Server")
        self.assertEqual(enriched.game_port, 2302)
        self.assertEqual(enriched.query_port, 27016)
        self.assertEqual(enriched.map_name, "namalsk")
        self.assertEqual(enriched.players_current, 12)
        self.assertEqual(enriched.players_max, 60)
        self.assertEqual(enriched.ping_ms, 42)
        self.assertTrue(enriched.password)
        self.assertTrue(enriched.modded)
        self.assertTrue(enriched.online)
        self.assertEqual(enriched.last_checked, "2026-06-20T14:00:00+00:00")
        self.assertEqual(enriched.last_seen, "2026-06-20T14:00:00+00:00")

    def test_offline_status_only_marks_checked_and_offline(self):
        enriched = enrich_discovered_server(
            self.make_candidate(),
            ServerStatus(False, error="timed out"),
            "2026-06-20T14:00:00+00:00",
        )

        self.assertFalse(enriched.online)
        self.assertEqual(enriched.last_checked, "2026-06-20T14:00:00+00:00")
        self.assertEqual(enriched.last_seen, "2026-06-20T12:00:00Z")

    def test_parse_connect_port_reads_port_from_gamedig_connect_address(self):
        self.assertEqual(parse_connect_port("203.0.113.10:2302"), 2302)
        self.assertEqual(parse_connect_port("example.test:3302"), 3302)
        self.assertIsNone(parse_connect_port(""))
        self.assertIsNone(parse_connect_port("203.0.113.10"))
        self.assertIsNone(parse_connect_port("203.0.113.10:not-a-port"))
        self.assertIsNone(parse_connect_port("203.0.113.10:70000"))


if __name__ == "__main__":
    unittest.main()
