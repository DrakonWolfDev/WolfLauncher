import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from wolflauncher.platform_detection import ProcessCheck, SteamInstall
from wolflauncher.settings_health import build_settings_health_snapshot


class SettingsHealthSnapshotTests(unittest.TestCase):
    def setUp(self):
        self.report_patches = (
            patch(
                "wolflauncher.settings_health.prime_environment_report",
                return_value=SimpleNamespace(status="OK", summary="PRIME clear"),
            ),
            patch(
                "wolflauncher.settings_health.prime_helper_report",
                return_value=SimpleNamespace(status="OK", summary="Helpers checked"),
            ),
            patch(
                "wolflauncher.settings_health.steam_launch_options_report",
                return_value=SimpleNamespace(status="OK", summary="Options external"),
            ),
            patch(
                "wolflauncher.settings_health.dayz_process_check",
                return_value=ProcessCheck(False, "No DayZ process visible"),
            ),
            patch(
                "wolflauncher.settings_health.launch_troubleshooting_report",
                return_value=SimpleNamespace(status="OK", next_steps=["No action required"]),
            ),
        )
        for report_patch in self.report_patches:
            report_patch.start()
            self.addCleanup(report_patch.stop)

    def test_native_snapshot_reports_ready_install_and_ignores_launcher_script(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            install = SteamInstall(
                mode="native",
                executable="steam",
                running=True,
                root=root,
                steamapps=root / "steamapps",
                dayz_dir=root / "DayZ",
                workshop_dir=root / "workshop",
                compatdata_dir=root / "compatdata",
            )
            snapshot = build_settings_health_snapshot(
                str(root / "missing-launcher.sh"),
                "native",
                "auto",
                "OK",
                "WolfAPI hosted cache",
                [install],
                command_lookup=lambda command: f"/usr/bin/{command}",
                launcher_candidates=(),
            )

        rows = {name: (status, detail) for name, status, detail in snapshot.rows}
        self.assertEqual(rows["Launch engine"], ("OK", "Native launcher"))
        self.assertEqual(rows["Launcher script"], ("OK", "Not required for native mode"))
        self.assertEqual(rows["Required tools"], ("OK", "All found"))
        self.assertEqual(rows["DayZ"][0], "OK")
        self.assertEqual(rows["Workshop"][0], "OK")
        self.assertIn("Selected Native Steam", snapshot.summary)
        self.assertIn("DayZ OK", snapshot.summary)

    def test_external_snapshot_reports_missing_launcher_tools_and_steam(self):
        snapshot = build_settings_health_snapshot(
            "/missing/dayz-launcher.sh",
            "external",
            "auto",
            "WARN",
            "Database refresh is disabled",
            [],
            command_lookup=lambda command: None,
            launcher_candidates=(),
        )

        rows = {name: (status, detail) for name, status, detail in snapshot.rows}
        self.assertEqual(rows["Launch engine"], ("OK", "External launcher (fallback)"))
        self.assertEqual(rows["Launcher script"][0], "MISSING")
        self.assertEqual(rows["Server API"], ("WARN", "Database refresh is disabled"))
        self.assertEqual(rows["Required tools"][0], "WARN")
        self.assertEqual(rows["Configured Steam installs"][0], "WARN")
        self.assertEqual(snapshot.summary, "Selected Steam/DayZ not detected")

    def test_stopped_selected_steam_is_an_actionable_warning(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            install = SteamInstall(
                mode="flatpak",
                executable="com.valvesoftware.Steam",
                running=False,
                root=root,
                steamapps=root / "steamapps",
                dayz_dir=root / "DayZ",
                workshop_dir=root / "workshop",
            )
            snapshot = build_settings_health_snapshot(
                "",
                "native",
                "flatpak",
                "OK",
                "WolfAPI hosted cache",
                [install],
                command_lookup=lambda command: f"/usr/bin/{command}",
                launcher_candidates=(),
            )

        rows = {name: (status, detail) for name, status, detail in snapshot.rows}
        self.assertEqual(rows["Selected Steam"][0], "WARN")
        self.assertIn("not running", rows["Selected Steam"][1])
        self.assertIn("Connect will start Steam", rows["Selected Steam"][1])
