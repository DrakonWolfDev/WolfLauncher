import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from wolflauncher.models import Server
from wolflauncher.mods import RequiredMod
from wolflauncher.native_launcher import prepare_native_launch_preview
from wolflauncher.platform_detection import SteamInstall
from wolflauncher.platforms.windows import WindowsPlatformBackend
from wolflauncher.workshop_subscription import find_steam_api_library


@unittest.skipUnless(os.name == "nt", "Windows backend tests require Windows")
class WindowsPlatformTests(unittest.TestCase):
    def test_capabilities_use_native_paths_without_linux_fallbacks(self):
        capabilities = WindowsPlatformBackend.capabilities

        self.assertFalse(capabilities.uses_proton)
        self.assertFalse(capabilities.supports_external_launcher)
        self.assertEqual(capabilities.mod_link_strategy, "absolute_path")

    def test_user_paths_follow_windows_environment(self):
        backend = WindowsPlatformBackend()
        with patch.dict(
            os.environ,
            {
                "APPDATA": r"C:\Users\Test\AppData\Roaming",
                "LOCALAPPDATA": r"C:\Users\Test\AppData\Local",
            },
        ):
            self.assertEqual(
                backend.user_config_dir(), Path(r"C:\Users\Test\AppData\Roaming\wolflauncher")
            )
            self.assertEqual(
                backend.user_data_dir(), Path(r"C:\Users\Test\AppData\Local\wolflauncher")
            )

    def test_tasklist_process_matching_is_case_insensitive(self):
        output = '"Steam.exe","123","Console","1","10,000 K"\n"DAYZ_X64.EXE","456","Console","1","20,000 K"\n'
        completed = subprocess.CompletedProcess([], 0, stdout=output, stderr="")
        backend = WindowsPlatformBackend()
        with patch("wolflauncher.platforms.windows.subprocess.run", return_value=completed):
            self.assertTrue(backend.process_running("steam"))
            self.assertEqual(backend.matching_process_lines(("DayZ_x64.exe",)), ["DAYZ_X64.EXE"])

    def test_native_preview_uses_absolute_workshop_paths_without_creating_links(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            dayz_dir = root / "steamapps" / "common" / "DayZ"
            workshop_dir = root / "steamapps" / "workshop" / "content" / "221100"
            mod_dir = workshop_dir / "256"
            dayz_dir.mkdir(parents=True)
            mod_dir.mkdir(parents=True)
            (mod_dir / "meta.cpp").write_text('name = "Example Mod";', encoding="utf-8")
            install = SteamInstall(
                mode="native",
                executable=r"C:\Steam\steam.exe",
                running=True,
                root=root,
                steamapps=root / "steamapps",
                dayz_dir=dayz_dir,
                workshop_dir=workshop_dir,
            )
            server = Server("Example", "Tests", "203.0.113.10", 2302, 27016)

            preview = prepare_native_launch_preview(
                install, server, "Player", [RequiredMod("256", "Example Mod")]
            )

            self.assertEqual(preview.mod_setup.mod_links, [str(mod_dir)])
            self.assertIn(f"-mod={mod_dir}", preview.command)
            self.assertFalse((dayz_dir / "@AAE").exists())

    def test_selected_dayz_dll_is_used_for_workshop_api(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            dayz_dir = Path(temp_dir) / "DayZ"
            dayz_dir.mkdir()
            library = dayz_dir / "steam_api64.dll"
            library.touch()
            install = SteamInstall("native", "steam.exe", True, None, None, dayz_dir, None)

            self.assertEqual(find_steam_api_library(install), library)


if __name__ == "__main__":
    unittest.main()
