import os
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

from wolflauncher.diagnostics import (
    format_launch_output_report,
    format_settings_health_report,
    launch_troubleshooting_report,
    run_diagnostics,
)
from wolflauncher.models import Server
from wolflauncher.platform_detection import ProcessCheck, SteamInstall


class DiagnosticsTests(unittest.TestCase):
    def test_format_settings_health_report_is_copyable(self):
        report = format_settings_health_report(
            "Selected Flatpak Steam | DayZ OK | Workshop OK",
            [["Selected Steam", "OK", "Flatpak Steam ready (not running)"]],
            generated_at=datetime(2026, 6, 21, 15, 16, 59, tzinfo=timezone.utc),
        )
        self.assertIn("WolfLauncher Settings Health", report)
        self.assertIn("Selected Steam | OK | Flatpak Steam ready", report)

    def test_format_launch_output_report_redacts_home_path(self):
        report = format_launch_output_report(
            f"bash {Path.home() / 'dayz-launcher.sh'} --launch", "Starting launcher..."
        )
        self.assertIn(f"bash ~{os.sep}dayz-launcher.sh --launch", report)

    def test_diagnostics_do_not_inspect_prime_environment(self):
        with tempfile.NamedTemporaryFile() as launcher:
            with patch("wolflauncher.diagnostics.detect_steam", return_value=[]):
                with patch("wolflauncher.diagnostics.resolve_host", return_value="203.0.113.10"):
                    report = run_diagnostics(
                        launcher.name,
                        [Server("Example", "Tests", "example.test", 2302, 27016)],
                        generated_at=datetime(2026, 6, 21, 15, 16, 59, tzinfo=timezone.utc),
                    )
        self.assertIn("Launch troubleshooting:", report)
        self.assertNotIn("PRIME status:", report)
        self.assertNotIn("Launch option environment:", report)

    def test_launch_troubleshooting_reports_ready_native_install(self):
        install = SteamInstall(
            mode="native",
            executable="steam",
            running=True,
            root=Path("/steam"),
            steamapps=Path("/steam/steamapps"),
            dayz_dir=Path("/steam/steamapps/common/DayZ"),
            workshop_dir=Path("/steam/steamapps/workshop/content/221100"),
            compatdata_dir=Path("/steam/steamapps/compatdata/221100"),
        )
        report = launch_troubleshooting_report(
            "native", [install], ProcessCheck(True, "Detected DayZ process")
        )
        self.assertEqual("OK", report.status)
        self.assertIn("Selected Steam mode: Native Steam", report.details)


if __name__ == "__main__":
    unittest.main()
