from pathlib import Path
from datetime import datetime, timezone
import tempfile
import unittest
from unittest.mock import patch

from wolflauncher.diagnostics import (
    format_launch_output_report,
    format_settings_health_report,
    launch_troubleshooting_report,
    post_handoff_launch_option_guidance,
    prime_environment_report,
    prime_helper_report,
    run_diagnostics,
    steam_launch_options_report,
)
from wolflauncher.models import Server
from wolflauncher.platform_detection import ProcessCheck, SteamInstall


class DiagnosticsTests(unittest.TestCase):
    def test_format_settings_health_report_is_copyable(self):
        report = format_settings_health_report(
            "Selected Flatpak Steam | DayZ OK | Workshop OK",
            [
                ["PRIME environment", "OK", "No PRIME-related variables are visible"],
                ["Selected Steam", "OK", "Flatpak Steam ready (not running)"],
            ],
            generated_at=datetime(2026, 6, 21, 15, 16, 59, tzinfo=timezone.utc),
        )

        self.assertIn("WolfLauncher Settings Health", report)
        self.assertIn("Generated at: 2026-06-21T15:16:59+00:00", report)
        self.assertIn("Summary: Selected Flatpak Steam | DayZ OK | Workshop OK", report)
        self.assertIn("PRIME environment | OK | No PRIME-related variables are visible", report)
        self.assertIn("Selected Steam | OK | Flatpak Steam ready (not running)", report)

    def test_format_launch_output_report_is_copyable(self):
        report = format_launch_output_report(
            "bash /home/andi/dayz-launcher.sh -s 81.152.152.55:3302 -p 3303 -n Andi --launch",
            "Starting launcher...\n[dayz-launcher.sh][info] Using flatpak mode",
            generated_at=datetime(2026, 6, 21, 15, 53, 45, tzinfo=timezone.utc),
        )

        self.assertIn("WolfLauncher launch output", report)
        self.assertIn("Generated at: 2026-06-21T15:53:45+00:00", report)
        self.assertIn(
            "Command: bash ~/dayz-launcher.sh -s 81.152.152.55:3302 -p 3303 -n Andi --launch",
            report,
        )
        self.assertIn("Output:\nStarting launcher...", report)
        self.assertIn("[dayz-launcher.sh][info] Using flatpak mode", report)

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
                                generated_at=datetime(2026, 6, 21, 15, 16, 59, tzinfo=timezone.utc),
                            )

        self.assertIn("Generated at: 2026-06-21T15:16:59+00:00", report)
        self.assertIn("Launch option environment:", report)
        self.assertIn("__NV_PRIME_RENDER_OFFLOAD: 1", report)
        self.assertIn("__GLX_VENDOR_LIBRARY_NAME: nvidia", report)
        self.assertIn("DRI_PRIME: not set", report)
        self.assertIn("PRIME status: WARN", report)
        self.assertIn("known bad Steam launch-option pattern", report)
        self.assertIn("Test DayZ directly from Steam with no per-game launch options", report)
        self.assertIn("prime-run glxinfo -B", report)
        self.assertIn("PRIME helpers:", report)
        self.assertIn("PRIME helper detail: prime-run:", report)
        self.assertIn("PRIME helper detail: switcherooctl:", report)
        self.assertIn(
            "Steam launch options: WARN - Check Steam's DayZ launch options for the known bad NVIDIA PRIME option.",
            report,
        )
        self.assertIn("Steam launch option guidance: Open Steam, DayZ, Properties, General, Launch Options", report)
        self.assertIn(
            "Steam launch option guidance: Remove __NV_PRIME_RENDER_OFFLOAD=1 __GLX_VENDOR_LIBRARY_NAME=nvidia %command%",
            report,
        )
        self.assertIn("DayZ process check:", report)
        self.assertIn("No known DayZ process detected", report)
        self.assertIn("Auto selection: MISSING - Auto selection found no Steam install", report)
        self.assertIn("Auto candidates: No native, Flatpak or STEAM_ROOT Steam installs detected", report)
        self.assertIn("Launch troubleshooting:", report)
        self.assertIn("Detail: Selected Steam mode: Auto", report)
        self.assertIn("Detail: Steam command: not detected", report)
        self.assertIn("Detail: Known DayZ process visibility: No known DayZ process detected", report)
        self.assertIn(
            "Detail: Steam launch options: WARN - Check Steam's DayZ launch options for the known bad NVIDIA PRIME option.",
            report,
        )
        self.assertIn("Next step: Open Settings health", report)

    def test_diagnostics_report_uses_one_environment_snapshot(self):
        def mutate_environment():
            env.clear()
            return []

        env = {
            "__NV_PRIME_RENDER_OFFLOAD": "1",
            "__GLX_VENDOR_LIBRARY_NAME": "nvidia",
        }

        with tempfile.NamedTemporaryFile() as launcher:
            with patch("wolflauncher.diagnostics.detect_steam", side_effect=mutate_environment):
                with patch("wolflauncher.diagnostics.resolve_host", return_value="203.0.113.10"):
                    with patch(
                        "wolflauncher.diagnostics.dayz_process_check",
                        return_value=ProcessCheck(False, "No known DayZ process detected"),
                    ):
                        with patch("wolflauncher.diagnostics.os.environ", env):
                            report = run_diagnostics(
                                launcher.name,
                                [],
                                generated_at=datetime(2026, 6, 21, 15, 16, 59, tzinfo=timezone.utc),
                            )

        self.assertIn("__NV_PRIME_RENDER_OFFLOAD: 1", report)
        self.assertIn("__GLX_VENDOR_LIBRARY_NAME: nvidia", report)
        self.assertIn("PRIME status: WARN", report)
        self.assertIn("Detail: PRIME status: WARN", report)
        self.assertIn(
            "Detail: Steam launch options: WARN - Check Steam's DayZ launch options for the known bad NVIDIA PRIME option.",
            report,
        )
        self.assertIn("Next step: Remove the known bad NVIDIA PRIME Steam launch option", report)

    def test_diagnostics_report_includes_selected_launch_engine_when_provided(self):
        with tempfile.NamedTemporaryFile() as launcher:
            with patch("wolflauncher.diagnostics.detect_steam", return_value=[]):
                with patch("wolflauncher.diagnostics.resolve_host", return_value="203.0.113.10"):
                    with patch(
                        "wolflauncher.diagnostics.dayz_process_check",
                        return_value=ProcessCheck(False, "No known DayZ process detected"),
                    ):
                        report = run_diagnostics(
                            launcher.name,
                            [],
                            selected_steam_mode="flatpak",
                            launch_engine="native",
                            generated_at=datetime(2026, 6, 21, 15, 16, 59, tzinfo=timezone.utc),
                        )

        self.assertIn("Generated at: 2026-06-21T15:16:59+00:00", report)
        self.assertIn("Launch engine: Native launcher", report)
        self.assertIn("Selected Steam mode: Flatpak Steam", report)
        self.assertIn("Selected Steam install: MISSING - Flatpak Steam not detected", report)

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
            compatdata_dir=Path("/home/user/.var/app/com.valvesoftware.Steam/data/Steam/steamapps/compatdata/221100"),
        )

        report = launch_troubleshooting_report(
            "flatpak",
            [install],
            ProcessCheck(True, "Detected known DayZ process: DayZ_x64.exe"),
            {},
        )

        self.assertEqual("OK", report.status)
        self.assertIn("Flatpak Steam ready", report.summary)
        self.assertIn("Selected Steam mode: Flatpak Steam", report.details)
        self.assertIn("Selected install: Flatpak Steam", report.details)
        self.assertIn(
            "Steam readiness: OK - Flatpak Steam ready (running); command: flatpak run com.valvesoftware.Steam",
            report.details,
        )
        self.assertIn("Steam command: flatpak run com.valvesoftware.Steam", report.details)
        self.assertIn(
            "Proton compatdata: /home/user/.var/app/com.valvesoftware.Steam/data/Steam/steamapps/compatdata/221100",
            report.details,
        )
        self.assertIn("Known DayZ process visibility: Detected known DayZ process: DayZ_x64.exe", report.details)
        self.assertTrue(any("compare native versus Flatpak Steam" in step for step in report.next_steps))

    def test_launch_troubleshooting_report_explains_missing_compatdata_for_ready_install(self):
        install = SteamInstall(
            mode="native",
            executable="steam",
            running=False,
            root=Path("/steam"),
            steamapps=Path("/steam/steamapps"),
            dayz_dir=Path("/steam/steamapps/common/DayZ"),
            workshop_dir=Path("/steam/steamapps/workshop/content/221100"),
        )

        report = launch_troubleshooting_report(
            "native",
            [install],
            ProcessCheck(False, "No known DayZ process detected"),
            {},
        )

        self.assertIn(
            "Proton compatdata: not detected yet; Steam may create it on first Proton launch",
            report.details,
        )
        self.assertTrue(any("If this was captured after a successful handoff" in step for step in report.next_steps))
        self.assertTrue(any("start it once directly from Steam" in step for step in report.next_steps))
        self.assertTrue(any("Check Steam's DayZ launch options in Steam" in step for step in report.next_steps))

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

    def test_prime_helper_report_lists_visible_helpers(self):
        report = prime_helper_report(
            {
                "prime-run": "/usr/bin/prime-run",
                "switcherooctl": None,
            }.get
        )

        self.assertEqual("OK", report.status)
        self.assertIn("prime-run", report.summary)
        self.assertIn("prime-run: /usr/bin/prime-run", report.details)
        self.assertIn("switcherooctl: not found", report.details)

    def test_prime_helper_report_is_informational_when_helpers_are_absent(self):
        report = prime_helper_report({}.get)

        self.assertEqual("OK", report.status)
        self.assertIn("may be normal on non-hybrid systems", report.summary)
        self.assertIn("prime-run: not found", report.details)
        self.assertIn("switcherooctl: not found", report.details)

    def test_steam_launch_options_report_warns_for_known_bad_prime_pair(self):
        report = steam_launch_options_report(
            {
                "__NV_PRIME_RENDER_OFFLOAD": "1",
                "__GLX_VENDOR_LIBRARY_NAME": "nvidia",
            }
        )

        self.assertEqual("WARN", report.status)
        self.assertIn("known bad NVIDIA PRIME option", report.summary)
        self.assertTrue(any("Open Steam, DayZ, Properties" in detail for detail in report.details))
        self.assertTrue(any("__NV_PRIME_RENDER_OFFLOAD=1" in detail for detail in report.details))
        self.assertTrue(any("Do not add that option as a WolfLauncher default" in detail for detail in report.details))

    def test_steam_launch_options_report_is_advisory_without_known_bad_pair(self):
        report = steam_launch_options_report({})

        self.assertEqual("OK", report.status)
        self.assertIn("external to WolfLauncher", report.summary)
        self.assertTrue(any("baseline testing" in detail for detail in report.details))
        self.assertTrue(any("does not prove which variables Steam will apply" in detail for detail in report.details))

    def test_post_handoff_launch_option_guidance_warns_for_known_bad_prime_pair(self):
        guidance = post_handoff_launch_option_guidance(
            {
                "__NV_PRIME_RENDER_OFFLOAD": "1",
                "__GLX_VENDOR_LIBRARY_NAME": "nvidia",
            }
        )

        self.assertIn("remove the known bad", guidance)
        self.assertIn("__NV_PRIME_RENDER_OFFLOAD=1", guidance)

    def test_post_handoff_launch_option_guidance_is_advisory_without_known_bad_pair(self):
        guidance = post_handoff_launch_option_guidance({})

        self.assertIn("Check Steam's DayZ launch options in Steam", guidance)
        self.assertIn("after handoff", guidance)


if __name__ == "__main__":
    unittest.main()
