import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication, QLabel, QPushButton

from wolflauncher import __version__
from wolflauncher.about_feature import AboutFeatureMixin


class AboutFeatureTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_about_tab_identifies_the_product_and_live_version(self):
        tab = AboutFeatureMixin()._build_about_tab()
        labels = [label.text() for label in tab.findChildren(QLabel)]

        title = next(
            label for label in tab.findChildren(QLabel) if label.accessibleName() == "Wolf Launcher"
        )
        self.assertIn("WOLF", title.text())
        self.assertIn("LAUNCHER", title.text())
        self.assertIn("Free and open-source DayZ launcher for Windows & Linux", labels)
        licence = next(
            label
            for label in tab.findChildren(QLabel)
            if label.accessibleName() == "Licensed under GNU AGPLv3"
        )
        self.assertTrue(licence.openExternalLinks())
        self.assertIn("https://choosealicense.com/licenses/agpl-3.0/", licence.text())
        self.assertIn(f"Version {__version__}", labels)
        self.assertIn("© 2026 Wolf Forge", labels)
        self.assertIn("A WOLF FORGE PROJECT 🐾", labels)
        check_updates = next(
            button
            for button in tab.findChildren(QPushButton)
            if button.accessibleName() == "Check for WolfLauncher updates"
        )
        self.assertFalse(check_updates.isEnabled())


if __name__ == "__main__":
    unittest.main()
