import json
import tempfile
import unittest
import urllib.error
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

from wolflauncher.models import Server
from wolflauncher.mods import (
    ModCheckResult,
    RequiredMod,
    apply_workshop_install_timestamps,
    apply_workshop_metadata,
    check_server_mods,
    fetch_required_mods,
    fetch_workshop_file_sizes,
    fetch_workshop_metadata,
    format_missing_workshop_links,
    format_mod_check_report,
    scan_experimental_local_mods,
    scan_installed_mods,
    workshop_install_timestamps,
)


class FakeResponse:
    def __init__(self, payload: dict):
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        return False

    def read(self, _size=-1) -> bytes:
        return json.dumps(self.payload).encode("utf-8")


class WorkshopFileSizeTests(unittest.TestCase):
    def test_remote_workshop_revision_blocks_stale_local_mod(self):
        result = ModCheckResult(True, make_server(), [RequiredMod("111", installed=True)])
        apply_workshop_metadata(result, {"111": {"time_updated": 200}})
        apply_workshop_install_timestamps(result, {"111": 100})
        self.assertTrue(result.required_mods[0].remote_update_available)
        self.assertFalse(result.required_mods[0].ready)

    def test_reads_local_workshop_revision_from_steam_manifest(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            steamapps = Path(tmpdir)
            manifest = steamapps / "workshop" / "appworkshop_221100.acf"
            manifest.parent.mkdir()
            manifest.write_text('"111" { "manifest" "abc" "timeupdated" "123" }', encoding="utf-8")
            install = type("Install", (), {"steamapps": steamapps, "library_steamapps": []})()
            self.assertEqual(workshop_install_timestamps(install), {"111": 123})

    def test_fetches_public_display_metadata_in_one_batch(self):
        payload = {
            "response": {
                "publishedfiledetails": [
                    {
                        "publishedfileid": "111",
                        "result": 1,
                        "title": "GameLabs-Experimental",
                        "file_size": "1048576",
                        "description": "A useful mod",
                        "preview_url": "https://cdn.example.test/preview.jpg",
                    }
                ]
            }
        }
        with patch(
            "wolflauncher.http_client.urllib.request.urlopen",
            return_value=FakeResponse(payload),
        ):
            metadata = fetch_workshop_metadata(["111"])

        self.assertEqual(metadata["111"]["file_size"], 1048576)
        self.assertEqual(metadata["111"]["title"], "GameLabs-Experimental")
        self.assertEqual(metadata["111"]["description"], "A useful mod")
        result = ModCheckResult(True, make_server(), [RequiredMod("111")])
        apply_workshop_metadata(result, metadata)
        self.assertEqual(result.required_mods[0].name, "GameLabs-Experimental")
        self.assertEqual(result.required_mods[0].workshop_file_size, 1048576)
        self.assertEqual(
            result.required_mods[0].workshop_preview_url,
            "https://cdn.example.test/preview.jpg",
        )

    def test_upgrades_an_installed_numeric_name_from_workshop_metadata(self):
        result = ModCheckResult(True, make_server(), [RequiredMod("111", "111", installed=True)])

        apply_workshop_metadata(result, {"111": {"title": "Community Framework"}})

        self.assertEqual(result.required_mods[0].name, "Community Framework")

    def test_keeps_server_name_for_installed_mod_metadata(self):
        result = ModCheckResult(
            True, make_server(), [RequiredMod("111", "Server GameLabs", installed=True)]
        )

        apply_workshop_metadata(result, {"111": {"title": "GameLabs-Experimental"}})

        self.assertEqual(result.required_mods[0].name, "Server GameLabs")

    def test_unavailable_metadata_preserves_installed_copy_readiness(self):
        payload = {
            "response": {
                "publishedfiledetails": [
                    {"publishedfileid": "3681415744", "result": 9},
                    {"publishedfileid": "111", "result": 1, "title": "Available mod"},
                    {"publishedfileid": "222", "result": "invalid"},
                ]
            }
        }
        with patch("wolflauncher.mods.post_form_json", return_value=payload):
            metadata = fetch_workshop_metadata(["3681415744", "111", "222"])
        self.assertEqual(metadata["3681415744"], {"result": 9})
        self.assertEqual(metadata["111"]["title"], "Available mod")
        self.assertNotIn("222", metadata)
        mod = RequiredMod("3681415744", "RaG_Expansion_Compatibility", installed=True)
        result = ModCheckResult(True, make_server(), [mod])
        apply_workshop_metadata(result, metadata)
        self.assertEqual(mod.workshop_metadata_result, 9)
        self.assertTrue(mod.ready)
        self.assertEqual(result.missing_mods, [])

    def test_metadata_outage_does_not_claim_item_unavailable(self):
        from wolflauncher.http_client import HttpClientError

        with patch(
            "wolflauncher.mods.post_form_json", side_effect=HttpClientError("connection", "offline")
        ):
            metadata = fetch_workshop_metadata(["111"])
        mod = RequiredMod("111")
        apply_workshop_metadata(ModCheckResult(True, make_server(), [mod]), metadata)
        self.assertIsNone(mod.workshop_metadata_result)

    def test_fetches_public_batch_file_sizes(self):
        payload = {
            "response": {
                "publishedfiledetails": [
                    {"publishedfileid": "111", "result": 1, "file_size": "1048576"},
                    {"publishedfileid": "222", "result": 9},
                ]
            }
        }
        with patch(
            "wolflauncher.http_client.urllib.request.urlopen",
            return_value=FakeResponse(payload),
        ) as urlopen:
            sizes = fetch_workshop_file_sizes(["111", "222", "111"])

        self.assertEqual(sizes, {"111": 1048576})
        request = urlopen.call_args.args[0]
        self.assertEqual(request.method, "POST")
        self.assertIn(b"itemcount=2", request.data)
        self.assertIn(b"publishedfileids%5B0%5D=111", request.data)

    def test_file_size_failure_is_advisory(self):
        with patch(
            "wolflauncher.http_client.urllib.request.urlopen",
            side_effect=urllib.error.URLError("offline"),
        ):
            self.assertEqual(fetch_workshop_file_sizes(["111"]), {})


def make_server() -> Server:
    return Server(
        name="Example",
        group="Tests",
        host="dayz.example.test",
        game_port=2302,
        query_port=27016,
    )


class ScanInstalledModsTests(unittest.TestCase):
    def test_scan_installed_mods_reads_numeric_workshop_dirs(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            workshop_dir = Path(tmpdir)
            first = workshop_dir / "111"
            first.mkdir()
            (first / "meta.cpp").write_text('name = "Community Framework";\n', encoding="utf-8")
            second = workshop_dir / "222"
            second.mkdir()
            ignored = workshop_dir / "not-a-mod"
            ignored.mkdir()

            self.assertEqual(
                scan_installed_mods(workshop_dir),
                {
                    "111": "Community Framework",
                    "222": "222",
                },
            )

    def test_scan_installed_mods_handles_missing_workshop_dir(self):
        self.assertEqual(scan_installed_mods(None), {})
        self.assertEqual(scan_installed_mods(Path("/definitely/not/wolflauncher/workshop")), {})

    def test_scan_experimental_local_mods_includes_official_workshop_local_source(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            stable = root / "DayZ"
            links = stable / "!Workshop"
            target = links / "2464526692"
            target.mkdir(parents=True)
            (target / "meta.cpp").write_text('name = "GameLabs";\n', encoding="utf-8")
            experimental = root / "DayZ Exp"
            experimental.mkdir()

            self.assertEqual(
                scan_experimental_local_mods(experimental, None),
                {"2464526692": "GameLabs"},
            )


class FetchRequiredModsTests(unittest.TestCase):
    @patch("wolflauncher.mods.resolve_host", return_value="203.0.113.10")
    @patch("wolflauncher.mods.query_dayz_required_mods")
    def test_fetch_required_mods_uses_direct_server_manifest(self, query_mods, resolve_host):
        from wolflauncher.dayz_mod_query import DayzRequiredMod

        query_mods.return_value = [
            DayzRequiredMod(111, "Community Framework"),
            DayzRequiredMod(222, "Namalsk Survival"),
        ]

        required = fetch_required_mods(make_server())

        self.assertEqual(
            required,
            [
                RequiredMod(
                    workshop_id="111",
                    name="Community Framework",
                    workshop_url="https://steamcommunity.com/sharedfiles/filedetails/?id=111",
                ),
                RequiredMod(
                    workshop_id="222",
                    name="Namalsk Survival",
                    workshop_url="https://steamcommunity.com/sharedfiles/filedetails/?id=222",
                ),
            ],
        )
        resolve_host.assert_called_once_with("dayz.example.test")
        query_mods.assert_called_once_with("203.0.113.10", 27016)


class CheckServerModsTests(unittest.TestCase):
    @patch(
        "wolflauncher.mods.fetch_required_mods",
        return_value=[
            RequiredMod("111", "Community Framework", workshop_url="url-111"),
            RequiredMod("222", "", workshop_url="url-222"),
        ],
    )
    def test_check_server_mods_marks_installed_and_missing_mods(self, fetch_required):
        with tempfile.TemporaryDirectory() as tmpdir:
            workshop_dir = Path(tmpdir)
            installed = workshop_dir / "111"
            installed.mkdir()
            (installed / "meta.cpp").write_text('name = "CF Local";\n', encoding="utf-8")

            result = check_server_mods(make_server(), workshop_dir)

        self.assertTrue(result.ok)
        self.assertEqual(result.installed_count, 1)
        self.assertEqual([mod.workshop_id for mod in result.missing_mods], ["222"])
        self.assertTrue(result.required_mods[0].installed)
        self.assertEqual(result.required_mods[0].installed_name, "CF Local")
        self.assertEqual(result.required_mods[1].name, "")

    @patch(
        "wolflauncher.mods.fetch_required_mods",
        return_value=[RequiredMod("2464526692", "GameLabs")],
    )
    def test_check_server_mods_accepts_experimental_local_source(self, fetch_required):
        result = check_server_mods(
            make_server(),
            None,
            installed_mods={"2464526692": "GameLabs"},
        )

        self.assertTrue(result.ok)
        self.assertTrue(result.required_mods[0].installed)
        self.assertEqual(result.required_mods[0].installed_name, "GameLabs")

    @patch("wolflauncher.mods.fetch_required_mods", return_value=[])
    def test_check_server_mods_records_selected_steam_context(self, fetch_required):
        with tempfile.TemporaryDirectory() as tmpdir:
            workshop_dir = Path(tmpdir)

            result = check_server_mods(
                make_server(),
                workshop_dir,
                steam_context="Selected Steam install: Flatpak Steam",
            )

        self.assertTrue(result.ok)
        self.assertEqual(result.steam_context, "Selected Steam install: Flatpak Steam")
        self.assertEqual(result.workshop_dir, str(workshop_dir))

    @patch("wolflauncher.mods.fetch_required_mods", side_effect=RuntimeError("api failed"))
    def test_check_server_mods_returns_error_result(self, fetch_required):
        result = check_server_mods(make_server(), None)

        self.assertFalse(result.ok)
        self.assertEqual(result.required_mods, [])
        self.assertEqual(result.installed_count, 0)
        self.assertEqual(result.error, "api failed")

    @patch("wolflauncher.mods.fetch_required_mods", side_effect=RuntimeError("api failed"))
    def test_check_server_mods_keeps_context_on_error_result(self, fetch_required):
        with tempfile.TemporaryDirectory() as tmpdir:
            workshop_dir = Path(tmpdir)

            result = check_server_mods(
                make_server(),
                workshop_dir,
                steam_context="Selected Steam install: STEAM_ROOT Steam library",
            )

        self.assertFalse(result.ok)
        self.assertEqual(result.error, "api failed")
        self.assertEqual(result.steam_context, "Selected Steam install: STEAM_ROOT Steam library")
        self.assertEqual(result.workshop_dir, str(workshop_dir))


class FormatModCheckReportTests(unittest.TestCase):
    def test_format_mod_check_report_includes_counts_and_missing_ids(self):
        result = ModCheckResult(
            True,
            make_server(),
            [
                RequiredMod(
                    "111",
                    "Community Framework",
                    installed=True,
                    installed_name="CF Local",
                    workshop_url="https://steamcommunity.com/sharedfiles/filedetails/?id=111",
                ),
                RequiredMod(
                    "222",
                    "Missing Mod",
                    installed=False,
                    workshop_url="https://steamcommunity.com/sharedfiles/filedetails/?id=222",
                ),
            ],
            installed_count=7,
            steam_context="Selected Steam install: Flatpak Steam",
            workshop_dir="/home/user/.var/app/com.valvesoftware.Steam/data/Steam/steamapps/workshop/content/221100",
        )

        report = format_mod_check_report(
            result,
            generated_at=datetime(2026, 6, 22, 12, 34, 56, tzinfo=timezone.utc),
        )

        self.assertIn("WolfLauncher mod check report", report)
        self.assertIn("Generated at: 2026-06-22T12:34:56+00:00", report)
        self.assertIn("Server: Example", report)
        self.assertIn("Connect target: dayz.example.test:2302", report)
        self.assertIn("Query port: 27016", report)
        self.assertIn("Result: OK", report)
        self.assertIn("Local Workshop mods found: 7", report)
        self.assertIn("Steam install context: Selected Steam install: Flatpak Steam", report)
        self.assertIn(
            "Workshop path checked: /home/user/.var/app/com.valvesoftware.Steam/data/Steam/steamapps/workshop/content/221100",
            report,
        )
        self.assertIn("Required mod count: 2", report)
        self.assertIn("Installed required mods: 1", report)
        self.assertIn("Missing required mods: 1", report)
        self.assertIn("- Community Framework (111) [installed]", report)
        self.assertIn("local name: CF Local", report)
        self.assertIn("- Missing Mod (222) [missing]", report)
        self.assertIn("Missing Workshop IDs:\n- 222", report)

    def test_format_mod_check_report_handles_unmodded_server(self):
        result = ModCheckResult(True, make_server(), [], installed_count=3)

        report = format_mod_check_report(result)

        self.assertIn("Required mod count: 0", report)
        self.assertIn("Required Workshop mods: none reported by the game server", report)
        self.assertNotIn("Missing Workshop IDs:", report)

    def test_format_mod_check_report_includes_error(self):
        result = ModCheckResult(False, make_server(), [], installed_count=0, error="api failed")

        report = format_mod_check_report(result)

        self.assertIn("Result: ERROR", report)
        self.assertIn("Error: api failed", report)
        self.assertNotIn("Required mod count:", report)


class FormatMissingWorkshopLinksTests(unittest.TestCase):
    def test_format_missing_workshop_links_includes_only_missing_mods(self):
        result = ModCheckResult(
            True,
            make_server(),
            [
                RequiredMod(
                    "111",
                    "Community Framework",
                    installed=True,
                    workshop_url="https://steamcommunity.com/sharedfiles/filedetails/?id=111",
                ),
                RequiredMod(
                    "222",
                    "Missing Mod",
                    installed=False,
                    workshop_url="https://steamcommunity.com/sharedfiles/filedetails/?id=222",
                ),
                RequiredMod("333", installed=False),
            ],
        )

        links = format_missing_workshop_links(result)

        self.assertEqual(
            links,
            "\n".join(
                [
                    "Missing Mod (222): https://steamcommunity.com/sharedfiles/filedetails/?id=222",
                    "333: https://steamcommunity.com/sharedfiles/filedetails/?id=333",
                ]
            ),
        )

    def test_format_missing_workshop_links_returns_empty_when_none_missing(self):
        result = ModCheckResult(True, make_server(), [RequiredMod("111", installed=True)])

        self.assertEqual(format_missing_workshop_links(result), "")

    def test_format_missing_workshop_links_returns_empty_for_failed_check(self):
        result = ModCheckResult(False, make_server(), [RequiredMod("111")], error="api failed")

        self.assertEqual(format_missing_workshop_links(result), "")


if __name__ == "__main__":
    unittest.main()
