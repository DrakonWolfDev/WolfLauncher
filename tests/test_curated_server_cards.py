import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from wolflauncher.curated_server_cards import CuratedServerCard


def card_values(status: str = "ONLINE") -> list[str]:
    return [
        "★",
        "Community",
        "Configured name",
        "Live server name",
        "dayz.example.test",
        "203.0.113.10",
        "2302",
        "27016",
        status,
        "chernarusplus" if status == "ONLINE" else "offline or no response",
        "12/60" if status == "ONLINE" else "",
        "14:30",
        "42ms" if status == "ONLINE" else "",
        "1.29",
        "Mods",
        "203.0.113.10:2302" if status == "ONLINE" else "",
    ]


class CuratedServerCardTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_online_card_presents_two_line_summary_and_actions(self):
        card = CuratedServerCard(2, card_values())

        self.assertEqual(card.property("onlineState"), "online")
        self.assertEqual(card.name_label.text(), "Live server name")
        self.assertIn("chernarusplus", card.metadata_label.text())
        self.assertIn("203.0.113.10:2302", card.metadata_label.text())
        self.assertEqual(card.time_label.text(), "14:30")
        self.assertFalse(card.time_icon_label.pixmap().isNull())
        self.assertEqual(card.stats_label.text(), "12/60\n42ms")
        self.assertTrue(card.connect_button.isEnabled())
        self.assertTrue(card.favourite_button.property("favourite"))

    def test_selected_online_card_promotes_its_connect_action(self):
        card = CuratedServerCard(0, card_values())

        card.set_selected(True)

        self.assertTrue(card.property("selected"))
        self.assertEqual(card.connect_button.property("uiRole"), "primary")

    def test_offline_card_keeps_identity_and_disables_connect(self):
        card = CuratedServerCard(0, card_values("OFFLINE"))

        self.assertEqual(card.property("onlineState"), "offline")
        self.assertIn("offline or no response", card.metadata_label.text())
        self.assertFalse(card.connect_button.isEnabled())

    def test_card_exposes_server_specific_accessibility_labels(self):
        card = CuratedServerCard(0, card_values())

        self.assertIn("Live server name", card.accessibleName())
        self.assertIn("Live server name", card.connect_button.accessibleName())
        self.assertIn("Live server name", card.favourite_button.accessibleName())

    def test_password_protection_is_visible_on_the_card(self):
        values = card_values()
        values[14] = "Password, Mods"

        card = CuratedServerCard(0, values)

        self.assertFalse(card.password_lock.isHidden())
        self.assertFalse(card.password_lock.pixmap().isNull())

    def test_night_time_uses_the_moon_icon(self):
        values = card_values()
        values[11] = "23:10"

        card = CuratedServerCard(0, values)

        self.assertEqual(card.time_icon_label.toolTip(), "Night-time: 23:10")
        self.assertFalse(card.time_icon_label.pixmap().isNull())


if __name__ == "__main__":
    unittest.main()
