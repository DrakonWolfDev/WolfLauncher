from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from wolflauncher.diagnostics import launch_troubleshooting_report, prime_environment_report, run_diagnostics
from wolflauncher.models import Server
from wolflauncher.platform_detection import ProcessCheck, SteamInstall


class DiagnosticsTests(unittest.TestCase):
    def test_reports_prime_environment_without_reading_steam_launch_options(self):
        with tempfile.NamedTemporaryFile() as launcher:
            with patch("wolflauncher.diagnostics.detect_steam", return_value=[]):
                with patch("wolflauncher.diagnostics.resolve_host", return_value="203.0.113.10"):
                    with patch(
                        "wolflauncher.diagnostics.dayz_process_check",
                        return_value=ProcessCheck(False, "No known DayZ process detected"),
                    ):
                        with patch.dict(
                            "wolflauncher.diagnostics.os.environ",
                            {
                                "__NV_PRIME_RENDER_OFFLOAD": "1",
                                "__GLX_VENDOR_LIBRARY_NAME": "nvidia",
                            },
                            clear=True,
                        ):
                            report = run_diagnostics(
                                launcher.name,
                                [
                                    Server(
                                        name="Example",
                                        group="Tests",
                                        host="example.test",
                                        game_port=2302,
                                        query_port=27016,
                                    )
                                ],
                            )

        self.assertIn("Launch option environment:", report)
        self.assertIn("__NV_PRIME_RENDER_OFFLOAD: 1", report)
        self.assertIn("__GLX_VENDOR_LIBRARY_NAME: nvidia", report)
        self.assertIn("DRI_PRIME: not set", report)
        self.assertIn("PRIME status: WARN", report)
        self.assertIn("known bad Steam launch-option pattern", report)
        self.assertIn("Test DayZ directly from Steam with no per-game launch options", report)
        self.assertIn("prime-run glxinfo -B", report)
        self.assertIn("Steam launch options: not readable by WolfLauncher", report)
        self.assertIn("DayZ process check:", report)
        self.assertIn("No known DayZ process detected", report)
        self.assertIn("Auto selection: MISSING - Auto selection found no Steam install", report)
        self.assertIn("Auto candidates: No native, Flatpak or STEAM_ROOT Steam installs detected", report)
        self.assertIn("Launch troubleshooting:", report)
        self.assertIn("Detail: Selected mode: Auto", report)
        self.assertIn("Detail: Steam command: not detected", report)
        self.assertIn("Detail: Post-handoff process visibility: No known DayZ process detected", report)
        self.assertIn("Next step: Open Settings health", report)

    def test_launch_troubleshooting_report_summarizes_selected_flatpak_install(self):
        install = SteamInstall(
            mode="flatpak",
            executable="com.valvesoftware.Steam",
            running=True,
            root=Path("/home/user/.var/app/com.valvesoftware.Steam/data/Steam"),
            steamapps=Path("/home/user/.var/app/com.valvesoftware.Steam/data/Steam/steamapps"),
            dayz_dir=Path("/home/user/.var/app/com.valvesoftware.Steam/data/Steam/steamapps/common/DayZ"),
            workshop_dir=Path(
                "/home/user/.var/app/com.valvesoftware.Steam/data/Steam/steamapps/workshop/content/221100"
            ),
        )

        report = launch_troubleshooting_report(
            "flatpak",
            [install],
            ProcessCheck(True, "Detected known DayZ process: DayZ_x64.exe"),
            {},
        )

        self.assertEqual("OK", report.status)
        self.assertIn("Flatpak Steam ready", report.summary)
        self.assertIn("Selected mode: Flatpak Steam", report.details)
        self.assertIn("Selected install: Flatpak Steam", report.details)
        self.assertIn("Steam command: com.valvesoftware.Steam", report.details)
        self.assertIn("Post-handoff process visibility: Detected known DayZ process: DayZ_x64.exe", report.details)
        self.assertTrue(any("compare native versus Flatpak Steam" in step for step in report.next_steps))

    def test_launch_troubleshooting_report_warns_for_known_bad_prime_pair(self):
        report = launch_troubleshooting_report(
            "auto",
            [],
            ProcessCheck(False, "No known DayZ process detected"),
            {
                "__NV_PRIME_RENDER_OFFLOAD": "1",
                "__GLX_VENDOR_LIBRARY_NAME": "nvidia",
            },
        )

        self.assertEqual("MISSING", report.status)
        self.assertTrue(any("known bad NVIDIA PRIME" in step for step in report.next_steps))

    def test_prime_report_warns_only_for_known_bad_nvidia_pair(self):
        report = prime_environment_report(
            {
                "__NV_PRIME_RENDER_OFFLOAD": "1",
                "__GLX_VENDOR_LIBRARY_NAME": "nvidia",
            }
        )

        self.assertEqual("WARN", report.status)
        self.assertIn("Known problematic NVIDIA PRIME", report.summary)

    def test_prime_report_allows_other_prime_environment_values(self):
        report = prime_environment_report({"DRI_PRIME": "1"})

        self.assertEqual("OK", report.status)
        self.assertIn("not the known bad NVIDIA launch-option pair", report.summary)
        self.assertTrue(any("Per-game Steam launch options" in detail for detail in report.details))

    def test_prime_report_explains_absent_visible_prime_environment(self):
        report = prime_environment_report({})

        self.assertEqual("OK", report.status)
        self.assertIn("No PRIME-related variables are visible to WolfLauncher", report.summary)
        self.assertIn("Steam launch options may still set them", report.summary)
        self.assertTrue(any("does not prove Steam has no per-game launch options" in detail for detail in report.details))


if __name__ == "__main__":
    unittest.main()
