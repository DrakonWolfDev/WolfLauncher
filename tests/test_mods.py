import json
import tempfile
import unittest
import urllib.error
from pathlib import Path
from unittest.mock import patch

from wolflauncher.models import Server
from wolflauncher.mods import (
    RequiredMod,
    check_server_mods,
    fetch_required_mods,
    scan_installed_mods,
)


class FakeResponse:
    def __init__(self, payload: dict):
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        return False

    def read(self) -> bytes:
        return json.dumps(self.payload).encode("utf-8")


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


class FetchRequiredModsTests(unittest.TestCase):
    @patch("wolflauncher.mods.resolve_host", return_value="203.0.113.10")
    @patch("wolflauncher.mods.urllib.request.urlopen")
    def test_fetch_required_mods_parses_api_response_and_deduplicates(self, urlopen, resolve_host):
        urlopen.return_value = FakeResponse(
            {
                "result": {
                    "mods": [
                        {"steamWorkshopId": "111", "name": "Community Framework"},
                        {"workshopId": 222, "title": "Namalsk Survival"},
                        {"id": "111", "name": "Duplicate"},
                        {"name": "Missing ID"},
                        "not a dict",
                    ]
                }
            }
        )

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
        request = urlopen.call_args.args[0]
        self.assertEqual(request.full_url, "https://dayzsalauncher.com/api/v1/query/203.0.113.10/27016")
        self.assertEqual(request.headers["User-agent"], "WolfLauncher/0.4")

    @patch("wolflauncher.mods.resolve_host", return_value="203.0.113.10")
    @patch("wolflauncher.mods.urllib.request.urlopen")
    def test_fetch_required_mods_accepts_unmodded_response(self, urlopen, resolve_host):
        urlopen.return_value = FakeResponse({"result": {"mods": None}})

        self.assertEqual(fetch_required_mods(make_server()), [])

    @patch("wolflauncher.mods.resolve_host", return_value="203.0.113.10")
    @patch("wolflauncher.mods.urllib.request.urlopen")
    def test_fetch_required_mods_rejects_invalid_mods_shape(self, urlopen, resolve_host):
        urlopen.return_value = FakeResponse({"result": {"mods": {"bad": "shape"}}})

        with self.assertRaisesRegex(RuntimeError, "mods list"):
            fetch_required_mods(make_server())

    @patch("wolflauncher.mods.resolve_host", return_value="203.0.113.10")
    @patch("wolflauncher.mods.urllib.request.urlopen", side_effect=urllib.error.URLError("offline"))
    def test_fetch_required_mods_wraps_url_errors(self, urlopen, resolve_host):
        with self.assertRaisesRegex(RuntimeError, "mod API connection failed"):
            fetch_required_mods(make_server())


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

    @patch("wolflauncher.mods.fetch_required_mods", side_effect=RuntimeError("api failed"))
    def test_check_server_mods_returns_error_result(self, fetch_required):
        result = check_server_mods(make_server(), None)

        self.assertFalse(result.ok)
        self.assertEqual(result.required_mods, [])
        self.assertEqual(result.installed_count, 0)
        self.assertEqual(result.error, "api failed")


if __name__ == "__main__":
    unittest.main()
