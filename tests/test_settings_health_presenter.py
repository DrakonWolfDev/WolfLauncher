import unittest

from wolflauncher.settings_health_presenter import (
    aggregate_health_status,
    settings_health_groups,
)


class SettingsHealthPresenterTests(unittest.TestCase):
    def test_groups_prioritise_steam_launcher_and_graphics_checks(self):
        rows = (
            ("Launch engine", "OK", "Native"),
            ("Server API", "WARN", "Disabled"),
            ("Required tools", "OK", "All found"),
            ("Launcher script", "OK", "Not required"),
            ("Selected Steam", "OK", "Running"),
            ("DayZ Stable", "OK", "/dayz"),
            ("Workshop", "MISSING", "Not detected"),
            ("Proton compatdata", "OK", "/compatdata"),
            ("Steam candidates", "OK", "Support detail"),
        )

        groups = settings_health_groups(rows)

        self.assertEqual(
            [group.key for group in groups], ["steam", "experimental", "launcher", "graphics"]
        )
        self.assertEqual(groups[0].status, "MISSING")
        self.assertEqual(groups[2].status, "WARN")
        self.assertEqual(groups[3].status, "OK")
        self.assertEqual([row[0] for row in groups[2].rows], ["Server API"])
        self.assertIn("DayZ Stable", [row[0] for row in groups[0].rows])
        self.assertNotIn("Proton compatdata", [row[0] for row in groups[0].rows])
        self.assertNotIn("Steam candidates", [row[0] for group in groups for row in group.rows])

    def test_aggregate_status_uses_missing_then_warning_then_ok(self):
        self.assertEqual(aggregate_health_status((("A", "OK", ""),)), "OK")
        self.assertEqual(
            aggregate_health_status((("A", "OK", ""), ("B", "WARN", ""))),
            "WARN",
        )
        self.assertEqual(
            aggregate_health_status((("A", "WARN", ""), ("B", "MISSING", ""))),
            "MISSING",
        )

    def test_windows_rows_leave_linux_graphics_group_empty(self):
        groups = settings_health_groups(
            (
                ("Server API", "OK", "WolfAPI"),
                ("Selected Steam", "OK", "Native Steam"),
                ("DayZ Experimental", "OK", "C:/DayZ Exp"),
                ("Workshop", "OK", "C:/Workshop"),
            )
        )

        self.assertEqual(groups[3].key, "graphics")
        self.assertEqual(groups[3].rows, ())


if __name__ == "__main__":
    unittest.main()
