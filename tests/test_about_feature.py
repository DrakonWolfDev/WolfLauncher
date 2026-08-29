import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication, QLabel

from wolflauncher import __version__
from wolflauncher.about_feature import AboutFeatureMixin


class AboutFeatureTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_about_tab_identifies_the_product_and_live_version(self):
        tab = AboutFeatureMixin()._build_about_tab()
        labels = [label.text() for label in tab.findChildren(QLabel)]

        self.assertIn("WOLF LAUNCHER", labels)
        self.assertIn("Free and open-source DayZ launcher", labels)
        self.assertIn("Licensed under GNU AGPLv3", labels)
        self.assertIn(f"Version {__version__}", labels)
        self.assertIn("© 2026 Andrew Hodgson t/a Wolf Forge", labels)


if __name__ == "__main__":
    unittest.main()
