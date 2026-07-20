import unittest
from pathlib import Path

INSTALLER_SCRIPT = (
    Path(__file__).resolve().parents[1] / "packaging" / "windows" / "WolfLauncher.iss"
)


class WindowsInstallerContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.script = INSTALLER_SCRIPT.read_text(encoding="utf-8")

    def test_installer_is_per_user_and_does_not_require_elevation(self):
        self.assertIn(r"DefaultDirName={localappdata}\Programs\WolfLauncher", self.script)
        self.assertIn("PrivilegesRequired=lowest", self.script)

    def test_uninstaller_owns_only_the_application_bundle(self):
        self.assertIn(
            'Source: "{#BundleRoot}\\*"; DestDir: "{app}";',
            self.script,
        )
        self.assertNotIn("[UninstallDelete]", self.script)
        self.assertNotIn(r"{userappdata}\wolflauncher", self.script.lower())
        self.assertNotIn(r"{localappdata}\wolflauncher", self.script.lower())

    def test_installer_has_stable_upgrade_identity_and_shortcuts(self):
        self.assertIn("AppId={{E4A3A1B2-39D8-4B94-9617-7E2361DE281A}", self.script)
        self.assertIn('Name: "{group}\\WolfLauncher";', self.script)
        self.assertIn('Name: "{autodesktop}\\WolfLauncher";', self.script)


if __name__ == "__main__":
    unittest.main()
