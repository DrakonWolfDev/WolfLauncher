import unittest

from wolflauncher.mod_presenter import (
    combined_download_estimate,
    mod_download_size,
    mod_result_context,
    mod_row,
    mod_summary_text,
)
from wolflauncher.models import Server
from wolflauncher.mods import ModCheckResult, RequiredMod
from wolflauncher.workshop_subscription import (
    ITEM_STATE_DOWNLOADING,
    ITEM_STATE_INSTALLED,
    ITEM_STATE_NEEDS_UPDATE,
)


def make_result(ok=True, required_mods=None, **kwargs):
    return ModCheckResult(
        ok=ok,
        server=Server("Test Server", "Community", "203.0.113.10", 2302, 27016),
        required_mods=required_mods or [],
        **kwargs,
    )


class ModPresenterTests(unittest.TestCase):
    def test_rows_distinguish_update_and_download_states(self):
        update = RequiredMod(
            "111", installed=True,
            workshop_state=ITEM_STATE_INSTALLED | ITEM_STATE_NEEDS_UPDATE,
        )
        downloading = RequiredMod(
            "222", installed=True,
            workshop_state=ITEM_STATE_DOWNLOADING | ITEM_STATE_NEEDS_UPDATE,
            workshop_downloaded=25,
            workshop_total=100,
        )

        self.assertEqual(mod_row(update).values[0], "! Update required")
        self.assertEqual(mod_row(downloading).values[0], "↻ Downloading")
        self.assertIn("25%", mod_row(downloading).values[6])

    def test_download_sizes_distinguish_known_partial_and_unavailable_totals(self):
        known = RequiredMod("111", workshop_downloaded=1024, workshop_total=3072)
        unknown = RequiredMod("222")

        self.assertEqual(mod_download_size(known), "2.0 KiB")
        self.assertEqual(mod_download_size(unknown), "Unavailable")
        estimate = combined_download_estimate([known, unknown])
        self.assertIn("Known remaining download: 2.0 KiB", estimate)
        self.assertIn("size unavailable for 1 item", estimate)

    def test_catalogue_file_size_is_used_before_download_starts(self):
        mod = RequiredMod("111", workshop_file_size=3 * 1024 * 1024)

        self.assertEqual(mod_download_size(mod), "3.0 MiB")
        self.assertEqual(
            combined_download_estimate([mod]),
            "Estimated remaining download: 3.0 MiB.",
        )

    def test_download_estimate_reports_complete_known_total(self):
        mods = [
            RequiredMod("111", workshop_total=1024),
            RequiredMod("222", workshop_total=1024),
        ]

        self.assertEqual(
            combined_download_estimate(mods),
            "Estimated remaining download: 2.0 KiB.",
        )

    def test_context_combines_steam_install_and_workshop_path(self):
        result = make_result(
            steam_context="Selected Steam install: Native Steam",
            workshop_dir="/steam/workshop/content/221100",
        )

        self.assertEqual(
            mod_result_context(result),
            " (Selected Steam install: Native Steam; Workshop: /steam/workshop/content/221100)",
        )

    def test_error_summary_includes_context(self):
        result = make_result(
            ok=False,
            error="API unavailable",
            steam_context="Steam install not detected",
        )

        self.assertEqual(
            mod_summary_text(result),
            "Could not check mods for Test Server: API unavailable (Steam install not detected)",
        )

    def test_empty_summary_reports_local_workshop_count(self):
        result = make_result(installed_count=3)

        self.assertIn("no required mods reported", mod_summary_text(result))
        self.assertIn("found locally: 3", mod_summary_text(result))

    def test_required_summary_reports_installed_and_missing_counts(self):
        result = make_result(
            required_mods=[RequiredMod("111", installed=True), RequiredMod("222")],
            installed_count=5,
        )

        summary = mod_summary_text(result)

        self.assertIn("Required 2 | Ready 1 | Missing 1 | Update/pending 0", summary)
        self.assertIn("Local Workshop mods found: 5", summary)

    def test_mod_rows_cover_installed_and_missing_metadata(self):
        installed = mod_row(
            RequiredMod(
                "111",
                name="Required Name",
                installed=True,
                installed_name="Local Name",
                workshop_url="https://example.test/111",
            )
        )
        missing = mod_row(RequiredMod("222"))

        self.assertEqual(installed.values, [
            "✓ Installed", "111", "Required Name", "Local Name",
            "https://example.test/111", "—", "Installed",
        ])
        self.assertEqual(installed.workshop_id, "111")
        self.assertEqual(installed.status_colour, "#6ee16e")
        self.assertEqual(missing.values[0:3], ["✗ Missing", "222", "Unknown"])
        self.assertEqual(missing.values[5], "Unavailable")
        self.assertIn("subscribe", missing.values[6])
        self.assertEqual(missing.status_colour, "#ff6b6b")


if __name__ == "__main__":
    unittest.main()
