import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from wolflauncher.platform_detection import (
    SteamInstall,
    best_install,
    best_install_from,
    dayz_battleye_process_check,
    dayz_game_process_check,
    dayz_process_check,
    detect_steam,
    install_label,
    install_readiness,
    parse_appmanifest_installdir,
    parse_libraryfolders_paths,
    proton_compatdata_detail,
    select_steam_install,
    selected_install_summary,
    steam_command_detail,
    steam_install_summary,
    steam_mode_label,
    steam_selection_candidates_detail,
    steam_selection_readiness,
    steam_selection_report,
)


def make_install(
    mode: str = "native",
    *,
    executable: str = "steam",
    running: bool = False,
    root: Path | None = None,
    steamapps: Path | None = None,
    dayz_dir: Path | None = None,
    workshop_dir: Path | None = None,
    compatdata_dir: Path | None = None,
) -> SteamInstall:
    return SteamInstall(
        mode=mode,
        executable=executable,
        running=running,
        root=root,
        steamapps=steamapps,
        dayz_dir=dayz_dir,
        workshop_dir=workshop_dir,
        compatdata_dir=compatdata_dir,
    )


class PlatformDetectionTests(unittest.TestCase):
    def test_install_label_names_supported_steam_modes(self):
        self.assertEqual(install_label(make_install("native")), "Native Steam")
        self.assertEqual(install_label(make_install("STEAM_ROOT env")), "STEAM_ROOT Steam library")

    def test_steam_command_detail_reports_native_command(self):
        self.assertEqual(
            steam_command_detail(make_install("native", executable="/usr/bin/steam")),
            "/usr/bin/steam",
        )
        self.assertEqual(
            steam_command_detail(make_install("native", executable="")), "not detected"
        )

    def test_steam_install_summary_includes_readiness_and_command_detail(self):
        install = make_install(
            "native",
            executable="/usr/bin/steam",
            root=Path("/steam"),
            steamapps=Path("/steam/steamapps"),
            dayz_dir=Path("/steam/steamapps/common/DayZ"),
            workshop_dir=Path("/steam/steamapps/workshop/content/221100"),
        )

        self.assertEqual(
            steam_install_summary(install),
            "Native Steam ready (not running); command: /usr/bin/steam",
        )
        self.assertEqual(steam_install_summary(None), "Not detected")

    def test_selected_install_summary_includes_state_and_command_detail(self):
        ready = make_install(
            "native",
            executable="/usr/bin/steam",
            root=Path("/steam"),
            steamapps=Path("/steam/steamapps"),
            dayz_dir=Path("/steam/steamapps/common/DayZ"),
            workshop_dir=Path("/steam/steamapps/workshop/content/221100"),
        )
        partial = make_install(
            "native",
            executable="/usr/bin/steam",
            root=Path("/steam"),
            steamapps=Path("/steam/steamapps"),
        )

        self.assertEqual(
            selected_install_summary(ready),
            "Selected Native Steam | DayZ OK | Workshop OK | command: /usr/bin/steam",
        )
        self.assertEqual(
            selected_install_summary(partial),
            "Selected Native Steam | DayZ not found yet | command: /usr/bin/steam",
        )
        self.assertEqual(selected_install_summary(None), "Selected Steam/DayZ not detected")

    def test_steam_mode_label_names_selection_modes(self):
        self.assertEqual(steam_mode_label("auto"), "Auto")
        self.assertEqual(steam_mode_label("native"), "Native Steam")
        self.assertEqual(steam_mode_label("STEAM_ROOT env"), "STEAM_ROOT Steam library")

    def test_install_readiness_reports_ready_native_steam(self):
        install = make_install(
            root=Path("/steam"),
            steamapps=Path("/steam/steamapps"),
            dayz_dir=Path("/steam/steamapps/common/DayZ"),
            workshop_dir=Path("/steam/steamapps/workshop/content/221100"),
            running=True,
        )

        self.assertEqual(install_readiness(install), ("OK", "Native Steam ready (running)"))

    def test_install_readiness_warns_when_ready_library_lacks_steam_command(self):
        install = make_install(
            mode="STEAM_ROOT env",
            executable="",
            root=Path("/steam-library"),
            steamapps=Path("/steam-library/steamapps"),
            dayz_dir=Path("/steam-library/steamapps/common/DayZ"),
            workshop_dir=Path("/steam-library/steamapps/workshop/content/221100"),
        )

        self.assertEqual(
            install_readiness(install),
            (
                "WARN",
                "STEAM_ROOT Steam library ready, but Steam command is not detected (not running)",
            ),
        )

    def test_proton_compatdata_detail_reports_visible_prefix(self):
        install = make_install(
            root=Path("/steam"),
            steamapps=Path("/steam/steamapps"),
            compatdata_dir=Path("/steam/steamapps/compatdata/221100"),
        )

        expected = (
            "not applicable on Windows" if os.name == "nt" else "/steam/steamapps/compatdata/221100"
        )
        self.assertEqual(proton_compatdata_detail(install), expected)

    def test_proton_compatdata_detail_explains_missing_prefix_for_detected_install(self):
        install = make_install(
            root=Path("/steam"),
            steamapps=Path("/steam/steamapps"),
            dayz_dir=Path("/steam/steamapps/common/DayZ"),
            workshop_dir=Path("/steam/steamapps/workshop/content/221100"),
        )

        expected = (
            "not applicable on Windows"
            if os.name == "nt"
            else "not detected yet; Steam may create it on first Proton launch"
        )
        self.assertEqual(proton_compatdata_detail(install), expected)

    def test_proton_compatdata_detail_reports_missing_without_install(self):
        expected = "not applicable on Windows" if os.name == "nt" else "not detected"
        self.assertEqual(proton_compatdata_detail(None), expected)

    def test_parse_libraryfolders_paths_reads_steam_vdf_paths(self):
        text = r"""
        "libraryfolders"
        {
            "0"
            {
                "path" "/home/user/.local/share/Steam"
            }
            "1"
            {
                "path" "/mnt/Games/SteamLibrary"
            }
            "2"
            {
                "path" "D:\\SteamLibrary"
            }
        }
        """

        self.assertEqual(
            parse_libraryfolders_paths(text),
            [
                Path("/home/user/.local/share/Steam"),
                Path("/mnt/Games/SteamLibrary"),
                Path("D:\\SteamLibrary"),
            ],
        )

    def test_parse_appmanifest_installdir_reads_dayz_install_folder(self):
        text = r"""
        "AppState"
        {
            "appid"     "221100"
            "installdir"        "DayZ Experimental \"Test\""
        }
        """

        self.assertEqual(parse_appmanifest_installdir(text), 'DayZ Experimental "Test"')

    def test_detect_steam_uses_dayz_appmanifest_installdir(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            home = Path(tmpdir)
            native_root = home / ".local/share/Steam"
            steamapps = native_root / "steamapps"
            dayz_dir = steamapps / "common" / "DayZ Custom"
            workshop_dir = steamapps / "workshop" / "content" / "221100"
            steamapps.mkdir(parents=True)
            dayz_dir.mkdir(parents=True)
            workshop_dir.mkdir(parents=True)
            (steamapps / "appmanifest_221100.acf").write_text(
                '"AppState" { "appid" "221100" "installdir" "DayZ Custom" }',
                encoding="utf-8",
            )

            with patch("wolflauncher.platform_detection.NATIVE_STEAM_ROOTS", [native_root]):
                with patch("wolflauncher.platforms.linux.shutil.which") as which:
                    which.side_effect = lambda command: (
                        "/usr/bin/steam" if command == "steam" else None
                    )
                    with patch("wolflauncher.platform_detection._is_running", return_value=False):
                        installs = detect_steam()

        self.assertEqual(installs[0].dayz_dir, dayz_dir)
        self.assertEqual(installs[0].workshop_dir, workshop_dir)

    def test_detect_steam_root_env_uses_native_steam_command_when_available(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            steamapps = root / "steamapps"
            dayz_dir = steamapps / "common" / "DayZ"
            workshop_dir = steamapps / "workshop" / "content" / "221100"
            dayz_dir.mkdir(parents=True)
            workshop_dir.mkdir(parents=True)

            with patch.dict(
                "wolflauncher.platform_detection.os.environ", {"STEAM_ROOT": str(root)}, clear=True
            ):
                with patch(
                    "wolflauncher.platform_detection.NATIVE_STEAM_ROOTS", [root / "missing-native"]
                ):
                    with patch("wolflauncher.platforms.linux.shutil.which") as which:
                        which.side_effect = lambda command: (
                            "/usr/bin/steam" if command == "steam" else None
                        )
                        with patch(
                            "wolflauncher.platform_detection._is_running", return_value=True
                        ):
                            installs = detect_steam()

        steam_root = installs[-1]
        self.assertEqual(steam_root.mode, "STEAM_ROOT env")
        self.assertTrue(steam_root.executable)
        self.assertEqual(steam_root.executable, installs[0].executable)
        self.assertTrue(steam_root.running)
        self.assertEqual(steam_root.dayz_dir, dayz_dir)
        self.assertEqual(
            install_readiness(steam_root), ("OK", "STEAM_ROOT Steam library ready (running)")
        )

    def test_detect_steam_finds_dayz_in_secondary_native_library(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            home = Path(tmpdir)
            native_root = home / ".local/share/Steam"
            primary_steamapps = native_root / "steamapps"
            secondary_root = home / "Games/SteamLibrary"
            secondary_steamapps = secondary_root / "steamapps"
            dayz_dir = secondary_steamapps / "common" / "DayZ"
            workshop_dir = secondary_steamapps / "workshop" / "content" / "221100"
            compatdata_dir = secondary_steamapps / "compatdata" / "221100"
            primary_steamapps.mkdir(parents=True)
            dayz_dir.mkdir(parents=True)
            workshop_dir.mkdir(parents=True)
            compatdata_dir.mkdir(parents=True)
            (primary_steamapps / "libraryfolders.vdf").write_text(
                f'"libraryfolders" {{ "1" {{ "path" "{secondary_root}" }} }}',
                encoding="utf-8",
            )

            with patch("wolflauncher.platform_detection.NATIVE_STEAM_ROOTS", [native_root]):
                with patch("wolflauncher.platforms.linux.shutil.which") as which:
                    which.side_effect = lambda command: (
                        "/usr/bin/steam" if command == "steam" else None
                    )
                    with patch("wolflauncher.platform_detection._is_running", return_value=True):
                        installs = detect_steam()

        native = installs[0]
        self.assertEqual(native.steamapps, secondary_steamapps)
        self.assertEqual(native.library_steamapps, [primary_steamapps, secondary_steamapps])
        self.assertEqual(native.dayz_dir, dayz_dir)
        self.assertEqual(native.workshop_dir, workshop_dir)
        self.assertEqual(native.compatdata_dir, compatdata_dir)

    def test_best_install_prefers_complete_flatpak_over_partial_native(self):
        native = make_install(root=Path("/steam"), steamapps=Path("/steam/steamapps"))
        flatpak = make_install(
            mode="flatpak",
            executable="com.valvesoftware.Steam",
            root=Path("/flatpak/Steam"),
            steamapps=Path("/flatpak/Steam/steamapps"),
            dayz_dir=Path("/flatpak/Steam/steamapps/common/DayZ"),
            workshop_dir=Path("/flatpak/Steam/steamapps/workshop/content/221100"),
        )

        with patch("wolflauncher.platform_detection.detect_steam", return_value=[native, flatpak]):
            self.assertIs(best_install(), flatpak)

    def test_best_install_keeps_detection_priority_when_multiple_installs_are_complete(self):
        native = make_install(
            mode="native",
            dayz_dir=Path("/native/DayZ"),
            workshop_dir=Path("/native/workshop/content/221100"),
        )
        flatpak = make_install(
            mode="flatpak",
            executable="com.valvesoftware.Steam",
            dayz_dir=Path("/flatpak/DayZ"),
            workshop_dir=Path("/flatpak/workshop/content/221100"),
        )

        self.assertIs(best_install_from([native, flatpak]), native)
        self.assertIs(best_install_from([flatpak, native]), flatpak)

    def test_best_install_returns_none_without_detected_candidates(self):
        self.assertIsNone(best_install_from([]))

    def test_select_steam_install_auto_uses_best_detected_install(self):
        native = make_install(mode="native", executable="/usr/bin/steam")
        flatpak = make_install(
            mode="flatpak",
            executable="com.valvesoftware.Steam",
            root=Path("/flatpak/Steam"),
            steamapps=Path("/flatpak/Steam/steamapps"),
            dayz_dir=Path("/flatpak/Steam/steamapps/common/DayZ"),
            workshop_dir=Path("/flatpak/Steam/steamapps/workshop/content/221100"),
        )

        self.assertIs(select_steam_install("auto", [native, flatpak]), flatpak)

    def test_select_steam_install_uses_explicit_mode(self):
        native = make_install(mode="native", executable="/usr/bin/steam")
        flatpak = make_install(mode="flatpak", executable="com.valvesoftware.Steam")

        self.assertIs(select_steam_install("native", [native, flatpak]), native)
        self.assertIs(select_steam_install("flatpak", [native, flatpak]), flatpak)
        self.assertIsNone(select_steam_install("STEAM_ROOT env", [native, flatpak]))

    def test_select_steam_install_uses_explicit_steam_root_mode(self):
        native = make_install(mode="native", executable="/usr/bin/steam")
        steam_root = make_install(
            mode="STEAM_ROOT env",
            executable="/usr/bin/steam",
            root=Path("/custom/Steam"),
        )

        self.assertIs(
            select_steam_install("STEAM_ROOT env", [native, steam_root]),
            steam_root,
        )

    def test_steam_selection_readiness_describes_auto_and_missing_modes(self):
        ready_native = make_install(
            mode="native",
            executable="/usr/bin/steam",
            root=Path("/steam"),
            steamapps=Path("/steam/steamapps"),
            dayz_dir=Path("/steam/steamapps/common/DayZ"),
            workshop_dir=Path("/steam/steamapps/workshop/content/221100"),
            running=True,
        )

        self.assertEqual(
            steam_selection_readiness("auto", [ready_native]),
            ("OK", "Auto selected Native Steam ready (running); command: /usr/bin/steam"),
        )
        self.assertEqual(
            steam_selection_readiness("STEAM_ROOT env", [ready_native]),
            ("MISSING", "STEAM_ROOT Steam library not detected"),
        )

    def test_steam_selection_report_lists_auto_selection_candidates(self):
        native = make_install(
            mode="native",
            executable="/usr/bin/steam",
            root=Path("/steam"),
            steamapps=Path("/steam/steamapps"),
        )
        steam_root = make_install(
            mode="STEAM_ROOT env",
            executable="/usr/bin/steam",
            root=Path("/custom/Steam"),
            steamapps=Path("/custom/Steam/steamapps"),
            dayz_dir=Path("/custom/Steam/steamapps/common/DayZ"),
            workshop_dir=Path("/custom/Steam/steamapps/workshop/content/221100"),
        )

        report = steam_selection_report("auto", [native, steam_root])

        self.assertEqual(report.status, "OK")
        self.assertEqual(report.selected_label, "STEAM_ROOT Steam library")
        self.assertEqual(
            report.detail,
            "Auto selected STEAM_ROOT Steam library ready (not running); command: /usr/bin/steam",
        )
        self.assertEqual(
            report.candidates,
            [
                "Native Steam library found, but DayZ install is not visible (not running); command: /usr/bin/steam",
                "STEAM_ROOT Steam library ready (not running); command: /usr/bin/steam",
            ],
        )
        self.assertIn("Native Steam library found", steam_selection_candidates_detail(report))
        self.assertIn("STEAM_ROOT Steam library ready", steam_selection_candidates_detail(report))

    @unittest.skipIf(os.name == "nt", "Linux pgrep behavior is validated on Linux")
    @patch("wolflauncher.platforms.linux.subprocess.run")
    def test_dayz_process_check_reports_known_dayz_processes(self, run):
        run.return_value = subprocess.CompletedProcess(
            ["pgrep"],
            0,
            stdout=(
                "1234 C:\\Program Files\\DayZ\\DayZ_x64.exe\n"
                "1235 C:\\Program Files\\DayZ\\DayZ_BE.exe\n"
            ),
            stderr="",
        )

        check = dayz_process_check()

        self.assertTrue(check.running)
        self.assertIn("DayZ_x64.exe", check.detail)
        self.assertIn("DayZ_BE.exe", check.detail)
        run.assert_called_once()
        self.assertEqual(run.call_args.args[0][:2], ["pgrep", "-afi"])

    @unittest.skipIf(os.name == "nt", "Linux pgrep behavior is validated on Linux")
    @patch("wolflauncher.platforms.linux.subprocess.run")
    def test_dayz_process_check_matches_process_names_case_insensitively(self, run):
        run.return_value = subprocess.CompletedProcess(
            ["pgrep"],
            0,
            stdout="1234 z:\\home\\steam\\dayz_x64.exe\n",
            stderr="",
        )

        check = dayz_process_check()

        self.assertTrue(check.running)
        self.assertIn("DayZ_x64.exe", check.detail)

    @unittest.skipIf(os.name == "nt", "Linux pgrep behavior is validated on Linux")
    @patch("wolflauncher.platforms.linux.subprocess.run")
    def test_dayz_process_check_ignores_the_dayz_tools_diagnostic_client(self, run):
        run.return_value = subprocess.CompletedProcess(
            ["pgrep"], 0, stdout="1234 DayZDiag_x64.exe\n", stderr=""
        )

        check = dayz_process_check()

        self.assertFalse(check.running)
        self.assertEqual(check.detail, "No known DayZ process detected")

    @patch("wolflauncher.platform_detection._matching_process_lines")
    def test_dayz_process_check_does_not_block_for_the_diagnostic_client(self, matching):
        matching.return_value = ["1234 DayZDiag_x64.exe"]

        check = dayz_process_check()

        self.assertFalse(check.running)
        self.assertEqual(check.detail, "No known DayZ process detected")

    @patch("wolflauncher.platform_detection._matching_process_lines")
    def test_game_and_battleye_process_checks_are_independent(self, matching):
        matching.side_effect = [["DayZ_BE.exe"], ["DayZ_BE.exe"]]

        game = dayz_game_process_check()
        battleye = dayz_battleye_process_check()

        self.assertFalse(game.running)
        self.assertTrue(battleye.running)
        self.assertIn("DayZ_BE.exe", battleye.detail)

    @unittest.skipIf(os.name == "nt", "Linux pgrep behavior is validated on Linux")
    @patch("wolflauncher.platforms.linux.subprocess.run")
    def test_dayz_process_check_reports_no_known_processes(self, run):
        run.return_value = subprocess.CompletedProcess(["pgrep"], 1, stdout="", stderr="")

        check = dayz_process_check()

        self.assertFalse(check.running)
        self.assertEqual(check.detail, "No known DayZ process detected")


class LinuxNativeSteamTests(unittest.TestCase):
    def test_detection_only_looks_up_native_steam(self):
        from wolflauncher.platforms.linux import LinuxPlatformBackend

        with patch(
            "wolflauncher.platforms.linux.shutil.which", return_value="/usr/bin/steam"
        ) as which:
            self.assertEqual(LinuxPlatformBackend().native_steam_executable(), "/usr/bin/steam")
        which.assert_called_once_with("steam")

    def test_snap_shim_is_not_native_steam(self):
        from wolflauncher.platforms.linux import LinuxPlatformBackend

        with patch("wolflauncher.platforms.linux.shutil.which", return_value="/snap/bin/steam"):
            self.assertEqual(LinuxPlatformBackend().native_steam_executable(), "")

    def test_native_roots_exclude_installed_packaged_clients(self):
        from wolflauncher.platforms.linux import LinuxPlatformBackend

        with (
            patch("pathlib.Path.home", return_value=Path("/home/test")),
            patch("pathlib.Path.exists", return_value=True),
        ):
            self.assertEqual(
                LinuxPlatformBackend().native_steam_roots(),
                (
                    Path("/home/test/.local/share/Steam"),
                    Path("/home/test/.steam/steam"),
                ),
            )


if __name__ == "__main__":
    unittest.main()
