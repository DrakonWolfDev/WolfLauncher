import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from wolflauncher.platform_detection import (
    SteamInstall,
    best_install,
    dayz_process_check,
    detect_steam,
    install_label,
    install_readiness,
    parse_libraryfolders_paths,
    select_steam_install,
    steam_selection_candidates_detail,
    steam_selection_report,
    steam_mode_label,
    steam_selection_readiness,
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
        self.assertEqual(install_label(make_install("flatpak")), "Flatpak Steam")
        self.assertEqual(install_label(make_install("STEAM_ROOT env")), "STEAM_ROOT Steam library")

    def test_steam_mode_label_names_selection_modes(self):
        self.assertEqual(steam_mode_label("auto"), "Auto")
        self.assertEqual(steam_mode_label("native"), "Native Steam")
        self.assertEqual(steam_mode_label("flatpak"), "Flatpak Steam")
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

    def test_install_readiness_reports_flatpak_library_without_dayz(self):
        install = make_install(
            mode="flatpak",
            executable="com.valvesoftware.Steam",
            root=Path("/flatpak/Steam"),
            steamapps=Path("/flatpak/Steam/steamapps"),
            running=False,
        )

        self.assertEqual(
            install_readiness(install),
            ("WARN", "Flatpak Steam library found, but DayZ install is not visible (not running)"),
        )

    def test_install_readiness_reports_executable_without_data_root(self):
        install = make_install(mode="flatpak", executable="com.valvesoftware.Steam")

        self.assertEqual(
            install_readiness(install),
            ("WARN", "Flatpak Steam executable found, but Steam data root was not detected (not running)"),
        )

    def test_parse_libraryfolders_paths_reads_steam_vdf_paths(self):
        text = r'''
        "libraryfolders"
        {
            "0"
            {
                "path" "/home/andi/.local/share/Steam"
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
        '''

        self.assertEqual(
            parse_libraryfolders_paths(text),
            [
                Path("/home/andi/.local/share/Steam"),
                Path("/mnt/Games/SteamLibrary"),
                Path("D:\\SteamLibrary"),
            ],
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
                with patch("wolflauncher.platform_detection.FLATPAK_STEAM_ROOT", home / "missing-flatpak"):
                    with patch("wolflauncher.platform_detection.shutil.which") as which:
                        which.side_effect = lambda command: "/usr/bin/steam" if command == "steam" else None
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
            ("OK", "Auto selected Native Steam ready (running)"),
        )
        self.assertEqual(
            steam_selection_readiness("flatpak", [ready_native]),
            ("MISSING", "Flatpak Steam not detected"),
        )

    def test_steam_selection_report_lists_auto_selection_candidates(self):
        native = make_install(
            mode="native",
            executable="/usr/bin/steam",
            root=Path("/steam"),
            steamapps=Path("/steam/steamapps"),
        )
        flatpak = make_install(
            mode="flatpak",
            executable="com.valvesoftware.Steam",
            root=Path("/flatpak/Steam"),
            steamapps=Path("/flatpak/Steam/steamapps"),
            dayz_dir=Path("/flatpak/Steam/steamapps/common/DayZ"),
            workshop_dir=Path("/flatpak/Steam/steamapps/workshop/content/221100"),
        )

        report = steam_selection_report("auto", [native, flatpak])

        self.assertEqual(report.status, "OK")
        self.assertEqual(report.selected_label, "Flatpak Steam")
        self.assertEqual(report.detail, "Auto selected Flatpak Steam ready (not running)")
        self.assertEqual(
            report.candidates,
            [
                "Native Steam library found, but DayZ install is not visible (not running)",
                "Flatpak Steam ready (not running)",
            ],
        )
        self.assertIn("Native Steam library found", steam_selection_candidates_detail(report))
        self.assertIn("Flatpak Steam ready", steam_selection_candidates_detail(report))

    @patch("wolflauncher.platform_detection.subprocess.run")
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

    @patch("wolflauncher.platform_detection.subprocess.run")
    def test_dayz_process_check_reports_no_known_processes(self, run):
        run.return_value = subprocess.CompletedProcess(["pgrep"], 1, stdout="", stderr="")

        check = dayz_process_check()

        self.assertFalse(check.running)
        self.assertEqual(check.detail, "No known DayZ process detected")


if __name__ == "__main__":
    unittest.main()
