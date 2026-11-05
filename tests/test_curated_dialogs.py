import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtGui import QFontDatabase
from PySide6.QtWidgets import QApplication, QDialogButtonBox

from wolflauncher.curated_dialogs import EditCuratedServerDialog, PromoteServerDialog
from wolflauncher.models import Server


class CuratedDialogTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_promote_dialog_trims_name_and_defaults_empty_group(self):
        dialog = PromoteServerDialog(None, " Original ", "Initial")
        dialog.name.setText(" Curated name ")
        dialog.group.clear()

        self.assertEqual(dialog.curated_name(), "Curated name")
        self.assertEqual(dialog.curated_group(), "Discovered")
        buttons = dialog.findChild(QDialogButtonBox)
        self.assertEqual(buttons.button(QDialogButtonBox.Ok).property("uiRole"), "primary")

    def test_edit_dialog_preserves_server_fields(self):
        original = Server("Name", "Group", "example.test", 2302, 2303, True)

        result = EditCuratedServerDialog(None, original).curated_server()

        self.assertEqual(result, original)
        dialog = EditCuratedServerDialog(None, original)
        self.assertEqual(
            dialog.host.font().family(),
            QFontDatabase.systemFont(QFontDatabase.FixedFont).family(),
        )
        self.assertTrue(dialog.query_port_panel.isHidden())
        dialog.query_port_disclosure.click()
        self.assertFalse(dialog.query_port_panel.isHidden())

    def test_edit_dialog_normalizes_host_port_and_default_group(self):
        original = Server("Name", "Group", "example.test", 2302, 2303)
        dialog = EditCuratedServerDialog(None, original)
        dialog.name.setText(" Updated ")
        dialog.group.clear()
        dialog.host.setText("dayz.example.test:2402")

        result = dialog.curated_server()

        self.assertEqual(result.name, "Updated")
        self.assertEqual(result.group, "Community")
        self.assertEqual(result.host, "dayz.example.test")
        self.assertEqual(result.game_port, 2402)
        self.assertEqual(result.query_port, 2403)

    def test_custom_query_port_is_visible_explained_and_preserved(self):
        original = Server("DrakonCherno", "Community", "95.145.110.178", 3302, 2303)
        dialog = EditCuratedServerDialog(None, original)
        self.addCleanup(dialog.close)
        self.assertFalse(dialog.query_port_panel.isHidden())
        self.assertEqual(dialog.game_port.value(), 3302)
        self.assertEqual(dialog.query_port.value(), 2303)
        self.assertIn("2303", dialog.query_port_disclosure.text())
        self.assertIn("differ from the game port", dialog.query_port_help.text())
        self.assertEqual(dialog.curated_server(), original)
        dialog.query_port_disclosure.click()
        self.assertTrue(dialog.query_port_panel.isHidden())
        dialog.query_port.setValue(3303)
        self.assertIn("3303", dialog.query_port_disclosure.text())
        self.assertEqual(dialog.curated_server().game_port, 3302)
        self.assertEqual(dialog.curated_server().query_port, 3303)


if __name__ == "__main__":
    unittest.main()
