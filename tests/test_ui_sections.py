import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication, QPushButton, QWidget

from wolflauncher.ui_sections import set_disclosure_state


class DisclosureSectionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_collapsed_state_hides_panel_and_offers_show_action(self):
        button = QPushButton()
        button.setCheckable(True)
        panel = QWidget()

        set_disclosure_state(button, panel, "advanced tools", False)

        self.assertTrue(panel.isHidden())
        self.assertFalse(button.isChecked())
        self.assertEqual(button.text(), "Show advanced tools")

    def test_expanded_state_shows_panel_and_offers_hide_action(self):
        button = QPushButton()
        button.setCheckable(True)
        panel = QWidget()

        set_disclosure_state(button, panel, "advanced tools", True)

        self.assertFalse(panel.isHidden())
        self.assertTrue(button.isChecked())
        self.assertEqual(button.text(), "Hide advanced tools")


if __name__ == "__main__":
    unittest.main()
