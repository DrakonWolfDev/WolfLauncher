import tempfile
import unittest
from dataclasses import replace
from pathlib import Path
from unittest.mock import Mock, patch

from wolflauncher.dayz_product import EXPERIMENTAL, STABLE
from wolflauncher.platform_detection import SteamInstall
from wolflauncher.product_availability import EXPERIMENTAL_SETUP, inspect_install, scan_availability


def make_install(root, product=STABLE):
    steamapps = (
        root / ("Experimental library" if product.experimental else "Stable library") / "steamapps"
    )
    folder = steamapps / "common" / "Custom DayZ Ω"
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "DayZ_x64.exe").touch()
    (folder / "DayZ_BE.exe").touch()
    (steamapps / f"appmanifest_{product.client_app_id}.acf").write_text(
        '"AppState" { "installdir" "Custom DayZ Ω" }', encoding="utf-8"
    )
    workshop = root / "shared Workshop" / "221100"
    workshop.mkdir(parents=True, exist_ok=True)
    return SteamInstall("native", "steam", True, root, steamapps, folder, workshop, product=product)


class ProductAvailabilityTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)

    def test_separate_libraries_and_custom_manifest_names(self):
        installs = {p.key: make_install(self.root, p) for p in (STABLE, EXPERIMENTAL)}
        snapshot = scan_availability("native", lambda product: [installs[product.key]])
        self.assertTrue(all(s.detected for s in snapshot.values()))
        self.assertNotEqual(
            snapshot["stable"].install.dayz_dir, snapshot["experimental"].install.dayz_dir
        )
        self.assertIn("not verified", snapshot["experimental"].detail)

    def test_missing_game_steam_executable_manifest_and_selected_mode(self):
        install = make_install(self.root)
        self.assertEqual(inspect_install(None, STABLE).state, "steam_missing")
        self.assertEqual(inspect_install(replace(install, dayz_dir=None), STABLE).state, "missing")
        (install.dayz_dir / "DayZ_BE.exe").unlink()
        self.assertEqual(inspect_install(install, STABLE).state, "incomplete")
        (install.dayz_dir / "DayZ_BE.exe").touch()
        (install.steamapps / "appmanifest_221100.acf").unlink()
        self.assertEqual(inspect_install(install, STABLE).state, "incomplete")
        self.assertFalse(
            scan_availability("STEAM_ROOT env", lambda product: [install])["stable"].detected
        )

    def test_rescan_install_uninstall_and_inspection_failure_are_distinct(self):
        install = make_install(self.root, EXPERIMENTAL)
        self.assertTrue(inspect_install(install, EXPERIMENTAL).detected)
        with patch.object(Path, "read_text", side_effect=PermissionError("denied")):
            self.assertEqual(inspect_install(install, EXPERIMENTAL).state, "error")
        (install.dayz_dir / "DayZ_x64.exe").unlink()
        self.assertEqual(inspect_install(install, EXPERIMENTAL).state, "incomplete")
        (install.dayz_dir / "DayZ_x64.exe").touch()
        self.assertTrue(inspect_install(install, EXPERIMENTAL).detected)

    def test_background_result_generation_rejects_stale_scan(self):
        from wolflauncher.settings_health_controller import SettingsHealthCoordinator

        window = Mock()
        window._shutting_down = False
        coordinator = SettingsHealthCoordinator(window)
        coordinator.generation = 2
        coordinator.apply_availability(1, {})
        window.installation_status.setText.assert_not_called()
        self.assertEqual(coordinator.snapshot, {})

    def test_instructions_require_first_steam_launch_close_and_rescan(self):
        for phrase in (
            "Steam Library",
            "Launch it through Steam once",
            "BattlEye",
            "close",
            "Rescan",
        ):
            self.assertIn(phrase, EXPERIMENTAL_SETUP)
