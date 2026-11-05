import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from wolflauncher.curated_server_cards import CuratedServerCard
from wolflauncher.curated_server_presenter import curated_server_row, curated_status_tooltip
from wolflauncher.models import Server
from wolflauncher.status import ServerStatus, ServerStatusOutcome


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
    def test_timeout_card_keeps_ports_and_raw_errors_in_the_tooltip(self):
        server = Server("Example", "Community", "203.0.113.10", 3302, 2303)
        status = ServerStatus(
            False,
            outcome=ServerStatusOutcome.TIMEOUT,
            error="Query port 2303 did not answer: Failed all 2 attempts",
        )
        card = CuratedServerCard(
            0,
            curated_server_row(server, status),
            status_tooltip=curated_status_tooltip(server, status),
        )
        self.addCleanup(card.close)
        self.assertIn("Server offline", card.metadata_label.text())
        self.assertEqual(card.property("onlineState"), "offline")
        self.assertNotIn("2303", card.metadata_label.text())
        self.assertNotIn("Failed all", card.metadata_label.text())
        self.assertIn("Join in DayZ: 203.0.113.10:3302", card.metadata_label.toolTip())
        self.assertIn("Check server status: 203.0.113.10:2303", card.metadata_label.toolTip())
        self.assertIn("Failed all 2 attempts", card.metadata_label.toolTip())
        self.assertFalse(card.connect_button.isEnabled())

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

    def test_unknown_card_explains_failure_without_claiming_offline(self):
        values = card_values("UNKNOWN")
        values[9] = "Unable to check server: DNS failed"

        card = CuratedServerCard(0, values)

        self.assertEqual(card.property("onlineState"), "unknown")
        self.assertIn("Unable to check server", card.metadata_label.text())
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

    def test_time_and_stats_columns_keep_fixed_widths(self):
        single_digit = card_values()
        single_digit[10] = "3/20"
        double_digit = card_values()
        double_digit[10] = "10/20"

        first_card = CuratedServerCard(0, single_digit)
        second_card = CuratedServerCard(1, double_digit)

        self.assertEqual(first_card.time_label.width(), CuratedServerCard.TIME_COLUMN_WIDTH)
        self.assertEqual(second_card.time_label.width(), CuratedServerCard.TIME_COLUMN_WIDTH)
        self.assertEqual(first_card.stats_label.width(), CuratedServerCard.STATS_COLUMN_WIDTH)
        self.assertEqual(second_card.stats_label.width(), CuratedServerCard.STATS_COLUMN_WIDTH)


if __name__ == "__main__":
    unittest.main()
