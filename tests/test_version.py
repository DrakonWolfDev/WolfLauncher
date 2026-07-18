import unittest

from wolflauncher import __version__


class VersionTests(unittest.TestCase):
    def test_active_hardening_version_is_pep440(self):
        self.assertEqual(__version__, "0.9.0.dev0")


if __name__ == "__main__":
    unittest.main()
