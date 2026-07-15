import unittest
from datetime import datetime, timezone

from wolflauncher.server_browser_presenter import (
    browser_row,
    browser_style_terms,
    browser_summary_text,
    browser_summary_tooltip,
    api_freshness_text,
    discovered_server_details,
    players_text,
)
from wolflauncher.theme import STATUS_COLOURS
from wolflauncher.models import DiscoveredServer


class ServerBrowserPresenterTests(unittest.TestCase):
    def test_style_terms_cover_pve_pvp_and_unfiltered_modes(self):
        self.assertIn("no kos", browser_style_terms("PvE"))
        self.assertEqual(browser_style_terms("PvP"), ["pvp", "p.v.p"])
        self.assertEqual(browser_style_terms("Any style"), [])

    def test_players_text_handles_partial_and_missing_counts(self):
        self.assertEqual(players_text(None, None), "")
        self.assertEqual(players_text(12, None), "12")
        self.assertEqual(players_text(None, 60), "?/60")
        self.assertEqual(players_text(12, 60), "12/60")

    def test_summary_reports_empty_cache(self):
        summary = {"total": 0, "online": 0, "checked": 0, "seen": 0}

        self.assertEqual(
            browser_summary_text(summary, shown=0, match_count=0, limit=200),
            "No discovered servers cached",
        )

    def test_summary_marks_truncated_and_no_match_results(self):
        summary = {"total": 500, "online": 100, "checked": 200, "seen": 150}

        truncated = browser_summary_text(summary, shown=200, match_count=350, limit=200)
        no_matches = browser_summary_text(summary, shown=0, match_count=0, limit=200)

        self.assertIn("Showing first 200 of 350 matching", truncated)
        self.assertIn("No matches from 500 cached", no_matches)
        self.assertNotIn("Cached discovered servers:", truncated)
        self.assertEqual(truncated, "Showing first 200 of 350 matching · 100 online")
        self.assertIn("500 cached", browser_summary_tooltip(summary))
        self.assertIn("200 checked", browser_summary_tooltip(summary))

    def test_browser_row_builds_display_sort_tooltip_and_colour_metadata(self):
        server = DiscoveredServer(
            name="Cached Name",
            server_name="Live Name",
            host="203.0.113.10",
            game_port=2302,
            query_port=27016,
            players_current=12,
            players_max=60,
            ping_ms=42,
            password=True,
            modded=True,
            online=True,
            status_source="local",
        )

        row = browser_row(server)

        self.assertEqual(row.values[1], "Live Name")
        self.assertEqual(row.values[7], "12/60")
        self.assertEqual(row.values[10], "Password, Mods")
        self.assertEqual(row.sort_values[7], 12)
        self.assertEqual(row.tooltips[0], "Live name: Live Name")
        self.assertIn(12, row.tooltips)
        self.assertEqual(row.status_colour, STATUS_COLOURS["positive"])

    def test_browser_row_hides_duplicate_live_name(self):
        server = DiscoveredServer(
            name="Same Name",
            server_name="same name",
            host="203.0.113.10",
            game_port=2302,
            query_port=27016,
            status_source="local",
        )

        row = browser_row(server)

        self.assertEqual(row.values[1], "")
        self.assertIn(1, row.tooltips)
        self.assertIn("Enrich visible", row.tooltips[8])
        self.assertIn("Inspect mods", row.tooltips[11])
        self.assertEqual(row.status_colour, STATUS_COLOURS["negative"])

    def test_provider_status_and_required_mod_count_are_explicit(self):
        server = DiscoveredServer(
            name="Provider Row",
            host="203.0.113.20",
            game_port=2302,
            query_port=27016,
            online=True,
            source="wolfapi",
            required_mod_count=23,
            last_checked="2026-07-12T12:00:00+00:00",
        )

        row = browser_row(server)

        self.assertEqual(row.values[5], "PROVIDER ONLINE")
        self.assertEqual(row.values[11], "23")
        self.assertEqual(row.status_colour, STATUS_COLOURS["warning"])
        self.assertIn("not yet validated", row.tooltips[5])

    def test_quality_warning_is_advisory_and_visible_when_not_hidden(self):
        server = DiscoveredServer(
            name="Provider Row",
            host="203.0.113.20",
            game_port=2302,
            query_port=27016,
            quality_flags=("suspicious_bots", "high_population_cluster"),
        )

        row = browser_row(server)
        details = discovered_server_details(server)

        self.assertEqual(row.values[10], "Quality warning")
        self.assertIn("not proof the server is unsafe", row.tooltips[10])
        self.assertIn("suspicious bots", details)

    def test_api_freshness_marks_expired_cached_labels_without_guessing_next_state(self):
        server = DiscoveredServer(
            name="Freshness",
            host="203.0.113.10",
            game_port=2302,
            query_port=27016,
            freshness="live",
            freshness_expires_at="2026-07-13T12:30:00+00:00",
        )

        self.assertEqual(
            api_freshness_text(
                server,
                now=datetime(2026, 7, 13, 12, 29, tzinfo=timezone.utc),
            ),
            "Live",
        )
        self.assertEqual(
            api_freshness_text(
                server,
                now=datetime(2026, 7, 13, 12, 31, tzinfo=timezone.utc),
            ),
            "Live (expired; refresh pending)",
        )

    def test_required_mod_tooltip_preserves_api_preview_and_direct_truth(self):
        server = DiscoveredServer(
            name="Modded",
            host="203.0.113.10",
            game_port=2302,
            query_port=27016,
            required_mod_count=17,
            mod_metadata_status="ready",
            mod_metadata_checked_at="2026-07-13T12:00:00+00:00",
        )

        row = browser_row(server)
        details = discovered_server_details(server)

        self.assertIn("WolfAPI found 17 required mod(s)", row.tooltips[11])
        self.assertIn("Inspect mods remains final truth", row.tooltips[11])
        self.assertIn("API mod metadata: Ready", details)

    def test_browser_status_tooltip_explains_api_and_local_truth_boundary(self):
        server = DiscoveredServer(
            name="Freshness",
            host="203.0.113.10",
            game_port=2302,
            query_port=27016,
            freshness="recent",
            validation_status="online",
            validation_checked_at="2026-07-13T12:00:00+00:00",
            provider_last_seen="2026-07-13T11:55:00+00:00",
        )

        tooltip = browser_row(server).tooltips[5]

        self.assertIn("WolfAPI freshness: Recent", tooltip)
        self.assertIn("WolfAPI validation: Online", tooltip)
        self.assertIn("Local ping and launch-time checks remain separate", tooltip)

    def test_discovered_details_use_shared_player_and_live_name_formatting(self):
        server = DiscoveredServer(
            name="Cached Name",
            server_name="Live Name",
            host="203.0.113.10",
            game_port=2302,
            query_port=27016,
            players_current=12,
            players_max=60,
        )

        details = discovered_server_details(server)

        self.assertIn("Live name: Live Name", details)
        self.assertIn("Players: 12/60", details)

    def test_discovered_details_include_flags_dates_and_source_fallbacks(self):
        server = DiscoveredServer(
            name="Cached Name",
            host="203.0.113.10",
            game_port=2302,
            query_port=27016,
            password=True,
            modded=True,
            source="wolfapi",
        )

        details = discovered_server_details(server)

        self.assertNotIn("Live name:", details)
        self.assertIn("Flags: Password, Mods", details)
        self.assertIn("Last checked: Never", details)
        self.assertIn("Last seen: Never", details)
        self.assertTrue(details.endswith("Source: wolfapi"))

    def test_discovered_details_include_api_freshness_and_validation(self):
        server = DiscoveredServer(
            name="API Truth",
            host="203.0.113.10",
            game_port=2302,
            query_port=27016,
            source="wolfapi",
            freshness="recent",
            freshness_expires_at="2026-07-14T12:00:00+00:00",
            validation_status="online",
            validation_checked_at="2026-07-13T12:00:00+00:00",
            provider_last_checked="2026-07-13T11:55:00+00:00",
        )

        details = discovered_server_details(server)

        self.assertIn("API freshness: Recent", details)
        self.assertIn("Freshness expires: 2026-07-14T12:00:00+00:00", details)
        self.assertIn("API validation: Online", details)
        self.assertIn("Provider checked: 2026-07-13T11:55:00+00:00", details)


if __name__ == "__main__":
    unittest.main()
