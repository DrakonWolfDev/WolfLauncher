import unittest

from wolflauncher.mod_presenter import (
    combined_download_estimate,
    mod_description_preview,
    mod_detail_status,
    mod_download_size,
    mod_file_size,
    mod_inspector_scale,
    mod_inspector_type_scale,
    mod_readiness_text,
    mod_result_context,
    mod_row,
    mod_server_heading,
    mod_summary_text,
)
from wolflauncher.models import Server
from wolflauncher.mods import ModCheckResult, RequiredMod
from wolflauncher.theme import STATUS_COLOURS
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
    def test_mod_detail_status_drives_semantic_inspector_edge(self):
        self.assertEqual(mod_detail_status(RequiredMod("1", installed=True)), "ready")
        self.assertEqual(mod_detail_status(RequiredMod("2")), "missing")
        self.assertEqual(
            mod_detail_status(
                RequiredMod("3", installed=True, workshop_state=ITEM_STATE_NEEDS_UPDATE)
            ),
            "warning",
        )

    def test_inspector_scale_grows_from_720p_and_is_bounded(self):
        self.assertEqual(mod_inspector_scale(600), 1.0)
        self.assertEqual(mod_inspector_scale(720), 1.0)
        self.assertEqual(mod_inspector_scale(900), 1.25)
        self.assertEqual(mod_inspector_scale(1080), 1.4)
        self.assertEqual(mod_inspector_type_scale(720), 1.0)
        self.assertEqual(mod_inspector_type_scale(900), 1.1)
        self.assertEqual(mod_inspector_type_scale(1080), 1.2)
        self.assertEqual(mod_inspector_type_scale(2000), 1.22)

    def test_mod_flow_heading_and_readiness_make_next_state_explicit(self):
        server = Server("Example", "Tests", "dayz.test", 2302, 27016)
        ready = ModCheckResult(
            True,
            server,
            [RequiredMod("111", installed=True)],
        )
        blocked = ModCheckResult(True, server, [RequiredMod("222")])

        self.assertIn("Example", mod_server_heading(ready))
        self.assertIn("dayz.test:2302", mod_server_heading(ready))
        self.assertIn("Ready to launch", mod_readiness_text(ready))
        self.assertIn("Action required", mod_readiness_text(blocked))

    def test_rows_distinguish_update_and_download_states(self):
        update = RequiredMod(
            "111",
            installed=True,
            workshop_state=ITEM_STATE_INSTALLED | ITEM_STATE_NEEDS_UPDATE,
        )
        downloading = RequiredMod(
            "222",
            installed=True,
            workshop_state=ITEM_STATE_DOWNLOADING | ITEM_STATE_NEEDS_UPDATE,
            workshop_downloaded=25,
            workshop_total=100,
        )

        self.assertEqual(mod_row(update).values[0], "! Update required")
        self.assertEqual(mod_row(downloading).values[0], "↻ Downloading (25%)")

    def test_steam_installed_state_waits_for_local_verification(self):
        mod = RequiredMod("111", installed=False, workshop_state=ITEM_STATE_INSTALLED)

        self.assertEqual(mod_row(mod).values[0], "… Verifying install")

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
        self.assertEqual(mod_file_size(mod), "3.0 MiB")
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

    def test_error_summary_stays_concise(self):
        result = make_result(
            ok=False,
            error="API unavailable",
            steam_context="Steam install not detected",
        )

        self.assertEqual(
            mod_summary_text(result),
            "Check failed: API unavailable",
        )

    def test_empty_summary_reports_zero_required_counts(self):
        result = make_result(installed_count=3)

        self.assertEqual(
            mod_summary_text(result),
            "Required 0  ·  Ready 0  ·  Missing 0  ·  Update/pending 0",
        )

    def test_required_summary_reports_installed_and_missing_counts(self):
        result = make_result(
            required_mods=[RequiredMod("111", installed=True), RequiredMod("222")],
            installed_count=5,
        )

        summary = mod_summary_text(result)

        self.assertIn(
            "Required 2  ·  Ready 1  ·  Missing 1  ·  Update/pending 0",
            summary,
        )

    def test_mod_rows_cover_installed_and_missing_metadata(self):
        installed = mod_row(
            RequiredMod(
                "111",
                name="Required Name",
                installed=True,
                installed_name="Local Name",
                workshop_url="https://example.test/111",
                workshop_description="A useful Workshop mod.",
            )
        )
        missing = mod_row(RequiredMod("222"))

        self.assertEqual(
            installed.values,
            [
                "✓ Installed",
                "Required Name",
                "111",
                "Unavailable",
            ],
        )
        self.assertEqual(installed.workshop_id, "111")
        self.assertEqual(installed.status_colour, STATUS_COLOURS["positive"])
        self.assertEqual(missing.values[0:4], ["✗ Missing", "Unknown", "222", "Unavailable"])
        self.assertEqual(missing.status_colour, STATUS_COLOURS["negative"])

    def test_description_preview_strips_workshop_markup_and_truncates(self):
        mod = RequiredMod(
            "111",
            workshop_description=(
                "[h1]Features[/h1]\nhttps://img.example.test/preview.png " + "Useful text " * 20
            ),
        )

        preview = mod_description_preview(mod, limit=40)

        self.assertNotIn("[h1]", preview)
        self.assertNotIn("https://", preview)
        self.assertTrue(preview.endswith("…"))
        self.assertLessEqual(len(preview), 40)

    def test_mod_row_uses_installed_name_as_fallback(self):
        row = mod_row(RequiredMod("111", installed=True, installed_name="Local Name"))

        self.assertEqual(row.values[1], "Local Name")


if __name__ == "__main__":
    unittest.main()
