import unittest

from wolflauncher.server_browser_presenter import (
    browser_row,
    browser_style_terms,
    browser_summary_text,
    players_text,
)
from wolflauncher.models import DiscoveredServer
from wolflauncher.app import MainWindow


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
            "Cached discovered servers: empty",
        )

    def test_summary_marks_truncated_and_no_match_results(self):
        summary = {"total": 500, "online": 100, "checked": 200, "seen": 150}

        truncated = browser_summary_text(summary, shown=200, match_count=350, limit=200)
        no_matches = browser_summary_text(summary, shown=0, match_count=0, limit=200)

        self.assertIn("Showing first 200 of 350 matching", truncated)
        self.assertIn("No matches from 500 cached", no_matches)

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
        )

        row = browser_row(server)

        self.assertEqual(row.values[1], "Live Name")
        self.assertEqual(row.values[7], "12/60")
        self.assertEqual(row.values[10], "Password, Mods")
        self.assertEqual(row.sort_values[7], 12)
        self.assertEqual(row.tooltips[0], "Live name: Live Name")
        self.assertIn(11, row.tooltips)
        self.assertEqual(row.status_colour, "#6ee16e")

    def test_browser_row_hides_duplicate_live_name(self):
        server = DiscoveredServer(
            name="Same Name",
            server_name="same name",
            host="203.0.113.10",
            game_port=2302,
            query_port=27016,
        )

        row = browser_row(server)

        self.assertEqual(row.values[1], "")
        self.assertIn(1, row.tooltips)
        self.assertEqual(row.status_colour, "#ff6b6b")

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

        details = MainWindow.discovered_server_details_text(None, server)

        self.assertIn("Live name: Live Name", details)
        self.assertIn("Players: 12/60", details)


if __name__ == "__main__":
    unittest.main()
