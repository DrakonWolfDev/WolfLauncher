import os
import unittest
from unittest.mock import Mock, patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from packaging.version import Version
from PySide6.QtWidgets import QApplication, QMainWindow

from wolf_update import CheckResult, CheckStatus, Release
from wolflauncher.update_feature import UPDATE_DESTINATION, UpdateFeatureMixin


class Window(UpdateFeatureMixin, QMainWindow):
    def __init__(self):
        super().__init__()
        self.settings = {}
        self.saved = 0
        self.update_banner = self._build_update_banner()

    def save_user_settings(self, silent=False):
        self.saved += 1
        return True


class UpdateFeatureTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.window = Window()
        self.window.setup_update_feature()

    def tearDown(self):
        self.window.close()

    @staticmethod
    def release(version="0.9.0b3", notes="Fixed one thing"):
        return Release(Version(version), f"v{version}", notes, True)

    def test_confirmed_destination_is_application_configuration(self):
        self.assertEqual(self.window.update_service.application.update_url, UPDATE_DESTINATION)
        self.assertNotIn("wolf-forge", self.window.update_service.source.api_url)

    def test_available_result_shows_non_modal_plain_text_banner(self):
        result = CheckResult(CheckStatus.AVAILABLE, self.release(notes="[Fix](https://bad.test)"))

        self.window.handle_update_result(result, False)

        self.assertTrue(self.window.update_banner.isVisible())
        self.assertEqual(self.window.update_version_label.text(), "Version 0.9.0b3 is available.")
        self.assertEqual(self.window.update_notes.toPlainText(), "[Fix](https://bad.test)")
        self.assertFalse(self.window.update_notes.acceptRichText())

    def test_dismiss_persists_version_and_hides_banner(self):
        self.window.show_update_banner(self.release())

        self.window.dismiss_available_update()

        self.assertFalse(self.window.update_banner.isVisible())
        self.assertEqual(self.window.settings["update_dismissed_version"], "0.9.0b3")
        self.assertGreater(self.window.saved, 0)

    @patch("wolflauncher.update_feature.QMessageBox.information")
    def test_manual_up_to_date_check_gives_feedback(self, information):
        self.window.handle_update_result(CheckResult(CheckStatus.UP_TO_DATE), True)
        information.assert_called_once()

    @patch("wolflauncher.update_feature.QMessageBox.warning")
    def test_failed_automatic_check_is_silent_but_manual_failure_is_visible(self, warning):
        result = CheckResult(CheckStatus.FAILED, message="offline")
        self.window.handle_update_result(result, False)
        warning.assert_not_called()
        self.window.handle_update_result(result, True)
        warning.assert_called_once()

    @patch("wolflauncher.update_feature.QMessageBox.warning")
    def test_browser_failure_does_not_fall_back_to_github(self, warning):
        self.window.update_service.browser_open = Mock(return_value=False)
        self.window.view_available_update()
        self.window.update_service.browser_open.assert_called_once_with(UPDATE_DESTINATION)
        warning.assert_called_once()


if __name__ == "__main__":
    unittest.main()
