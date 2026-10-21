import unittest
from datetime import datetime, timezone

from wolflauncher.models import DiscoveredServer
from wolflauncher.server_enrichment import (
    candidate_query_ports,
    enrich_discovered_server,
    enrichment_probe_servers,
    local_enrichment_due,
    parse_connect_port,
    parse_players,
)
from wolflauncher.status import ServerStatus, ServerStatusOutcome


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
                time="14:30",
                day_acceleration=6,
                night_acceleration=4,
            ),
            "2026-06-20T14:00:00+00:00",
        )

        self.assertEqual(enriched.name, "203.0.113.10:27016")
        self.assertEqual(enriched.server_name, "Live Server")
        self.assertEqual(enriched.game_port, 2302)
        self.assertEqual(enriched.query_port, 27016)
        self.assertEqual(enriched.map_name, "namalsk")
        self.assertEqual(enriched.game_time, "14:30")
        self.assertEqual(enriched.day_acceleration, 6)
        self.assertEqual(enriched.night_acceleration, 4)
        self.assertEqual(enriched.players_current, 12)
        self.assertEqual(enriched.players_max, 60)
        self.assertEqual(enriched.ping_ms, 42)
        self.assertTrue(enriched.password)
        self.assertTrue(enriched.modded)
        self.assertTrue(enriched.online)
        self.assertEqual(enriched.last_checked, "2026-06-20T14:00:00+00:00")
        self.assertEqual(enriched.last_seen, "2026-06-20T14:00:00+00:00")
        self.assertEqual(enriched.status_source, "local")

    def test_enrichment_preserves_api_metadata_it_did_not_measure(self):
        candidate = self.make_candidate()
        candidate.stable_server_id = "stable-1"
        candidate.freshness = "recent"
        candidate.quality_flags = ("advisory",)

        enriched = enrich_discovered_server(
            candidate,
            ServerStatus(True, players="1/10", connect="203.0.113.10:2302"),
            "2026-06-20T14:00:00+00:00",
        )

        self.assertEqual(enriched.stable_server_id, "stable-1")
        self.assertEqual(enriched.freshness, "recent")
        self.assertEqual(enriched.quality_flags, ("advisory",))

    def test_recent_local_success_is_not_rechecked_until_ttl(self):
        candidate = self.make_candidate()
        candidate.status_source = "local"
        candidate.online = True
        candidate.last_checked = "2026-06-20T14:00:00+00:00"
        now = datetime(2026, 6, 20, 14, 1, tzinfo=timezone.utc)

        self.assertFalse(local_enrichment_due(candidate, now=now))
        self.assertTrue(
            local_enrichment_due(
                candidate,
                now=datetime(2026, 6, 20, 14, 2, tzinfo=timezone.utc),
            )
        )

    def test_failed_local_check_uses_longer_retry_cooldown(self):
        candidate = self.make_candidate()
        candidate.status_source = "local"
        candidate.online = False
        candidate.last_checked = "2026-06-20T14:00:00+00:00"

        self.assertFalse(
            local_enrichment_due(
                candidate,
                now=datetime(2026, 6, 20, 14, 4, tzinfo=timezone.utc),
            )
        )
        self.assertTrue(
            local_enrichment_due(
                candidate,
                now=datetime(2026, 6, 20, 14, 5, tzinfo=timezone.utc),
            )
        )

    def test_offline_status_only_marks_checked_and_offline(self):
        enriched = enrich_discovered_server(
            self.make_candidate(),
            ServerStatus(False, error="timed out"),
            "2026-06-20T14:00:00+00:00",
        )

        self.assertFalse(enriched.online)
        self.assertEqual(enriched.last_checked, "2026-06-20T14:00:00+00:00")
        self.assertEqual(enriched.last_seen, "2026-06-20T12:00:00Z")
        self.assertEqual(enriched.status_source, "local")

    def test_unsuccessful_checks_are_unknown_and_retain_retry_cooldown(self):
        from wolflauncher.server_browser_presenter import browser_inspector, browser_status

        for outcome in (
            ServerStatusOutcome.TIMEOUT,
            ServerStatusOutcome.NETWORK_ERROR,
            ServerStatusOutcome.CHECK_ERROR,
            ServerStatusOutcome.INVALID_RESPONSE,
            ServerStatusOutcome.CANCELLED,
        ):
            with self.subTest(outcome=outcome):
                candidate = self.make_candidate()
                candidate.ping_ms = 42
                enriched = enrich_discovered_server(
                    candidate,
                    ServerStatus(False, outcome=outcome),
                    "2026-06-20T14:00:00+00:00",
                )
                self.assertEqual(browser_status(enriched)[0], "UNKNOWN")
                self.assertIn("Local check unsuccessful", browser_inspector(enriched).truth)
                self.assertIsNone(enriched.ping_ms)
                self.assertFalse(
                    local_enrichment_due(
                        enriched, now=datetime(2026, 6, 20, 14, 4, tzinfo=timezone.utc)
                    )
                )
                self.assertTrue(
                    local_enrichment_due(
                        enriched, now=datetime(2026, 6, 20, 14, 5, tzinfo=timezone.utc)
                    )
                )

    def test_parse_connect_port_reads_port_from_gamedig_connect_address(self):
        self.assertEqual(parse_connect_port("203.0.113.10:2302"), 2302)
        self.assertEqual(parse_connect_port("example.test:3302"), 3302)
        self.assertIsNone(parse_connect_port(""))
        self.assertIsNone(parse_connect_port("203.0.113.10"))
        self.assertIsNone(parse_connect_port("203.0.113.10:not-a-port"))
        self.assertIsNone(parse_connect_port("203.0.113.10:70000"))

    def test_candidate_query_ports_prefers_cached_query_port(self):
        self.assertEqual(
            candidate_query_ports(
                DiscoveredServer(
                    name="BattleMetrics",
                    host="203.0.113.10",
                    game_port=2302,
                    query_port=27016,
                )
            ),
            [27016, 2302],
        )

    def test_candidate_query_ports_adds_bounded_dayz_fallbacks_when_ports_are_uncertain(self):
        self.assertEqual(
            candidate_query_ports(
                DiscoveredServer(
                    name="Candidate",
                    host="203.0.113.10",
                    game_port=2302,
                    query_port=2302,
                )
            ),
            [2302, 2303, 2312, 27016],
        )

    def test_enrichment_probe_servers_keeps_game_port_while_varying_query_port(self):
        probes = enrichment_probe_servers(self.make_candidate())

        self.assertEqual([probe.query_port for probe in probes], [27016, 27017, 27026])
        self.assertTrue(all(probe.game_port == 27016 for probe in probes))


if __name__ == "__main__":
    unittest.main()
