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


if __name__ == "__main__":
    unittest.main()
