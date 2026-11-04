import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from wolflauncher.dayz_product import EXPERIMENTAL
from wolflauncher.platform_detection import SteamInstall
from wolflauncher.settings_health import build_settings_health_snapshot


class SettingsHealthSnapshotTests(unittest.TestCase):
    def setUp(self):
        self.report_patches = (
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
        self.assertEqual(rows["DayZ Stable"][0], "OK")
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

    def test_experimental_snapshot_labels_the_missing_install_explicitly(self):
        root = Path("/steam")
        install = SteamInstall(
            mode="native",
            executable="steam",
            running=True,
            root=root,
            steamapps=root / "steamapps",
            dayz_dir=None,
            workshop_dir=None,
            product=EXPERIMENTAL,
        )

        snapshot = build_settings_health_snapshot(
            "",
            "native",
            "auto",
            "OK",
            "WolfAPI hosted cache",
            [install],
            product=EXPERIMENTAL,
            command_lookup=lambda command: f"/usr/bin/{command}",
            launcher_candidates=(),
        )

        rows = {name: (status, detail) for name, status, detail in snapshot.rows}
        self.assertNotIn("DayZ", rows)
        self.assertEqual(rows["DayZ Experimental"], ("MISSING", "Not detected"))


class LinuxMemoryMapHealthTests(unittest.TestCase):
    def test_read_only_check_distinguishes_low_recommended_and_high_values(self):
        from wolflauncher.settings_health import linux_memory_map_health

        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "max_map_count"
            for value, status in ((65530, "WARN"), (1048576, "OK"), (2147483642, "OK")):
                with self.subTest(value=value):
                    original = f"{value}\n"
                    path.write_text(original)
                    row = linux_memory_map_health(path)
                    self.assertEqual(row[1], status)
                    self.assertIn(f"{value:,}", row[2])
                    self.assertEqual(path.read_text(), original)

    def test_unavailable_or_malformed_limit_is_unknown_never_ok(self):
        from wolflauncher.settings_health import linux_memory_map_health

        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "max_map_count"
            self.assertEqual(linux_memory_map_health(path)[1], "WARN")
            for value in ("", "bad", "-1", "0", "1.5", "１２", "1" * 80):
                path.write_text(value)
                with self.subTest(value=value):
                    row = linux_memory_map_health(path)
                    self.assertEqual(row[1], "WARN")
                    self.assertIn("unknown", row[2])

    def test_snapshot_adds_linux_only_check_to_compatibility_group(self):
        from wolflauncher.settings_health_presenter import settings_health_groups

        for uses_proton in (False, True):
            with (
                self.subTest(uses_proton=uses_proton),
                patch("wolflauncher.settings_health.current_platform") as platform,
                patch(
                    "wolflauncher.settings_health.linux_memory_map_health",
                    return_value=("Linux memory maps", "WARN", "Low limit"),
                ) as read,
            ):
                platform.return_value.capabilities = SimpleNamespace(
                    uses_proton=uses_proton, diagnostic_tools=(), supports_external_launcher=False
                )
                snapshot = build_settings_health_snapshot(
                    "", "native", "auto", "OK", "API", [], launcher_candidates=()
                )
                groups = {group.key: group for group in settings_health_groups(snapshot.rows)}
                if uses_proton:
                    read.assert_called_once_with()
                    self.assertEqual(groups["graphics"].status, "WARN")
                    self.assertIn(
                        ("Linux memory maps", "WARN", "Low limit"), groups["graphics"].rows
                    )
                else:
                    read.assert_not_called()
