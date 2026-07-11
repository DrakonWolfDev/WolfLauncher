import unittest

from wolflauncher.server_browser_presenter import (
    browser_style_terms,
    browser_summary_text,
    players_text,
)


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


if __name__ == "__main__":
    unittest.main()
