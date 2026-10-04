import configparser
import unittest
from pathlib import Path

import wolflauncher
import wolflauncher.config as config

ROOT = Path(__file__).resolve().parent.parent


class PackagingMetadataTests(unittest.TestCase):
    def test_debian_package_declares_qt_egl_runtime(self):
        script = (ROOT / "scripts/build-deb.sh").read_text(encoding="utf-8")
        self.assertIn(", libegl1", script)

    def test_pyproject_derives_version_from_package(self):
        text = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
        self.assertIn('version = {attr = "wolflauncher.__version__"}', text)
        self.assertNotIn('version = "0.9.0b1"', text)
        self.assertEqual(wolflauncher.__version__, "0.9.0b2")

    def test_wheel_declares_server_query_dependency_and_map_metadata(self):
        text = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
        self.assertIn('"python-a2s>=1.4.2,<2"', text)
        self.assertIn('"assets/*.json"', text)

    def test_desktop_entry_names_installed_command_and_icon(self):
        parser = configparser.ConfigParser(interpolation=None)
        parser.read(ROOT / "packaging/linux/wolflauncher.desktop", encoding="utf-8")
        entry = parser["Desktop Entry"]
        self.assertEqual(entry["Exec"], "wolflauncher")
        self.assertEqual(entry["Icon"], "wolflauncher")
        self.assertEqual(entry["Terminal"], "false")
        self.assertEqual(entry["Actions"], "Uninstall;")
        self.assertEqual(parser["Desktop Action Uninstall"]["Exec"], "wolflauncher-uninstall")
        self.assertNotIn("Terminal", parser["Desktop Action Uninstall"])

    def test_source_resource_paths_remain_available(self):
        self.assertTrue(config.EXAMPLE_SERVERS_PATH.is_file())
        self.assertTrue(config.VENDORED_LAUNCHER_PATH.is_file())

    def test_release_requirements_pin_direct_runtime_dependencies(self):
        requirements = (ROOT / "requirements-release.txt").read_text(encoding="utf-8")
        self.assertIn("PySide6==", requirements)
        self.assertIn("PyYAML==", requirements)
        self.assertIn("keyring==", requirements)
        self.assertNotIn(">=", requirements)

    def test_npm_lock_owns_exact_gamedig_runtime(self):
        lock = (ROOT / "packaging/npm/package-lock.json").read_text(encoding="utf-8")
        self.assertIn('"node_modules/gamedig"', lock)
        self.assertIn('"version": "5.3.3"', lock)


if __name__ == "__main__":
    unittest.main()
