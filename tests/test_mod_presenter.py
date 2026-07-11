import unittest

from wolflauncher.mod_presenter import mod_result_context, mod_row, mod_summary_text
from wolflauncher.models import Server
from wolflauncher.mods import ModCheckResult, RequiredMod


def make_result(ok=True, required_mods=None, **kwargs):
    return ModCheckResult(
        ok=ok,
        server=Server("Test Server", "Community", "203.0.113.10", 2302, 27016),
        required_mods=required_mods or [],
        **kwargs,
    )


class ModPresenterTests(unittest.TestCase):
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

        self.assertIn("Required 2 | Installed 1 | Missing 1", summary)
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
            "https://example.test/111", "Installed",
        ])
        self.assertEqual(installed.workshop_id, "111")
        self.assertEqual(installed.status_colour, "#6ee16e")
        self.assertEqual(missing.values[0:3], ["✗ Missing", "222", "Unknown"])
        self.assertIn("subscribe", missing.values[5])
        self.assertEqual(missing.status_colour, "#ff6b6b")


if __name__ == "__main__":
    unittest.main()
