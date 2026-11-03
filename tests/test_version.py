import unittest

from wolflauncher import __version__
from wolflauncher.versioning import windows_version_tuple


class VersionTests(unittest.TestCase):
    def test_first_beta_version_is_pep440(self):
        self.assertEqual(__version__, "0.9.3.5b")

    def test_windows_version_preserves_four_release_components(self):
        self.assertEqual(windows_version_tuple("0.9.3.5b"), (0, 9, 3, 5))

    def test_beta_number_is_not_a_release_component(self):
        self.assertEqual(windows_version_tuple("0.9.3b2"), (0, 9, 3, 0))

    def test_invalid_native_release_components_are_rejected(self):
        for value in ("1.2.3.4.5", "1.2.65536"):
            with self.assertRaises(ValueError):
                windows_version_tuple(value)


if __name__ == "__main__":
    unittest.main()
