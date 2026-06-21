import subprocess
import unittest
from pathlib import Path
from unittest.mock import patch

from wolflauncher.platform_detection import SteamInstall, best_install, dayz_process_check, install_label, install_readiness


def make_install(
    mode: str = "native",
    *,
    executable: str = "steam",
    running: bool = False,
    root: Path | None = None,
    steamapps: Path | None = None,
    dayz_dir: Path | None = None,
    workshop_dir: Path | None = None,
) -> SteamInstall:
    return SteamInstall(
        mode=mode,
        executable=executable,
        running=running,
        root=root,
        steamapps=steamapps,
        dayz_dir=dayz_dir,
        workshop_dir=workshop_dir,
    )


class PlatformDetectionTests(unittest.TestCase):
    def test_install_label_names_supported_steam_modes(self):
        self.assertEqual(install_label(make_install("native")), "Native Steam")
        self.assertEqual(install_label(make_install("flatpak")), "Flatpak Steam")
        self.assertEqual(install_label(make_install("STEAM_ROOT env")), "STEAM_ROOT Steam library")

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
