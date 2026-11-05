import unittest

from wolflauncher.server_display import (
    display_map_name,
    display_required_mod_count,
    display_server_flags,
    is_displayable_server_name,
    map_filter_key,
    ping_severity,
)


class ServerDisplayTests(unittest.TestCase):
    def test_address_and_punctuation_placeholders_are_not_server_names(self):
        for name in (
            "",
            "  ",
            "!",
            "!!!",
            "---",
            "\ufffd",
            "Broken\x00name",
            "115.191.45.245:27101",
            " 101.126.11.42:27129 ",
            "203.0.113.10",
            "::1",
            "2001:db8::1",
            "[2001:db8::1]:2302",
            "[2001:db8::1]",
        ):
            with self.subTest(name=name):
                self.assertFalse(is_displayable_server_name(name))
        for name in (
            "![GER] DayZ - Community PVE",
            "! [GER] DayZ - Community PVE Badlands",
            "123",
            "生存服务器",
            "Сервер",
            "203.0.113.10 Community",
            "DayZ : 2302",
        ):
            with self.subTest(name=name):
                self.assertTrue(is_displayable_server_name(name))

    def test_known_map_names_are_canonical_and_enoch_is_livonia(self):
        self.assertEqual(display_map_name("chernarusplus"), "ChernarusPlus")
        self.assertEqual(display_map_name("namalsk"), "Namalsk")
        self.assertEqual(display_map_name("enoch"), "Livonia")
        self.assertEqual(display_map_name("ENOCH"), "Livonia")

    def test_case_variants_share_a_display_name_and_technical_key(self):
        self.assertEqual(display_map_name("Takistanplus"), "TakistanPlus")
        self.assertEqual(display_map_name("TAKISTANPLUS"), "TakistanPlus")
        self.assertEqual(map_filter_key("TakistanPlus"), "takistanplus")
        self.assertEqual(map_filter_key("Livonia"), "enoch")

    def test_flags_always_state_modded_or_vanilla(self):
        self.assertEqual(display_server_flags(False, True), "Modded")
        self.assertEqual(display_server_flags(False, False), "Vanilla")
        self.assertEqual(display_server_flags(True, True), "Password, Modded")

    def test_zero_and_unknown_mod_counts_use_a_dash(self):
        self.assertEqual(display_required_mod_count(None), "–")
        self.assertEqual(display_required_mod_count(0), "–")
        self.assertEqual(display_required_mod_count(17), "17")

    def test_ping_severity_matches_dayz_warning_thresholds(self):
        self.assertEqual(ping_severity(None), "unknown")
        self.assertEqual(ping_severity(199), "normal")
        self.assertEqual(ping_severity(200), "warning")
        self.assertEqual(ping_severity(249), "warning")
        self.assertEqual(ping_severity(250), "critical")


if __name__ == "__main__":
    unittest.main()
