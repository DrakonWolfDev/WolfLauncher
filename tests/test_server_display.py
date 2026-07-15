import unittest

from wolflauncher.server_display import (
    display_map_name,
    display_required_mod_count,
    display_server_flags,
    ping_severity,
)


class ServerDisplayTests(unittest.TestCase):
    def test_map_names_are_capitalized_and_enoch_is_livonia(self):
        self.assertEqual(display_map_name("chernarusplus"), "Chernarusplus")
        self.assertEqual(display_map_name("namalsk"), "Namalsk")
        self.assertEqual(display_map_name("enoch"), "Livonia")
        self.assertEqual(display_map_name("ENOCH"), "Livonia")

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
