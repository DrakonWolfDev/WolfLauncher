import unittest

from wolflauncher.platforms import current_platform


class PlatformBackendTests(unittest.TestCase):
    def test_current_backend_describes_validated_linux_capabilities(self):
        capabilities = current_platform().capabilities

        self.assertEqual(capabilities.platform_id, "linux")
        self.assertEqual(capabilities.display_name, "Linux")
        self.assertTrue(capabilities.supports_flatpak)
        self.assertTrue(capabilities.uses_proton)
        self.assertTrue(capabilities.supports_external_launcher)
        self.assertEqual(capabilities.mod_link_strategy, "relative_symlink")


if __name__ == "__main__":
    unittest.main()
