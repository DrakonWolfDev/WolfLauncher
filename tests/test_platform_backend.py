import unittest

from wolflauncher.platforms import current_platform


class PlatformBackendTests(unittest.TestCase):
    def test_current_backend_describes_supported_platform_capabilities(self):
        capabilities = current_platform().capabilities

        self.assertIn(capabilities.platform_id, {"linux", "windows"})
        if capabilities.platform_id == "linux":
            self.assertTrue(capabilities.supports_flatpak)
            self.assertTrue(capabilities.uses_proton)
            self.assertTrue(capabilities.supports_external_launcher)
            self.assertEqual(capabilities.mod_link_strategy, "relative_symlink")
        else:
            self.assertFalse(capabilities.supports_flatpak)
            self.assertFalse(capabilities.uses_proton)
            self.assertFalse(capabilities.supports_external_launcher)
            self.assertEqual(capabilities.mod_link_strategy, "absolute_path")


if __name__ == "__main__":
    unittest.main()
