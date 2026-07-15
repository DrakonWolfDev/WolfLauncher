import unittest

from wolflauncher.curated_server_presenter import curated_server_row
from wolflauncher.models import Server
from wolflauncher.status import ServerStatus


class CuratedServerPresenterTests(unittest.TestCase):
    def setUp(self):
        self.server = Server(
            name="Configured Name",
            group="Community",
            host="dayz.example.test",
            game_port=2302,
            query_port=27016,
            favourite=True,
        )

    def test_unchecked_row_uses_config_and_checking_placeholders(self):
        row = curated_server_row(self.server)

        self.assertEqual(len(row), 16)
        self.assertEqual(row[:3], ["★", "Community", "Configured Name"])
        self.assertEqual(row[3], "Configured Name")
        self.assertEqual(row[4:9], ["dayz.example.test", "Checking...", "2302", "27016", "Checking..."])

    def test_online_row_includes_live_values_and_flags(self):
        status = ServerStatus(
            online=True,
            resolved_ip="203.0.113.10",
            server_name="Live Name",
            map_name="chernarusplus",
            players="12/60",
            time="14:30",
            ping="42",
            version="1.28",
            password=True,
            modded=True,
            connect="203.0.113.10:2402",
        )

        row = curated_server_row(self.server, status)

        self.assertEqual(row[3], "Live Name")
        self.assertEqual(row[5], "203.0.113.10")
        self.assertEqual(row[8:13], ["ONLINE", "chernarusplus", "12/60", "14:30", "42ms"])
        self.assertEqual(row[14:], ["Password, Mods", "203.0.113.10:2402"])

    def test_online_row_handles_missing_name_ping_and_flags(self):
        row = curated_server_row(self.server, ServerStatus(online=True))

        self.assertEqual(row[3], "Configured Name")
        self.assertEqual(row[12], "")
        self.assertEqual(row[14], "Vanilla/unknown")

    def test_offline_row_shows_resolution_and_error(self):
        status = ServerStatus(
            online=False,
            resolved_ip="203.0.113.10",
            error="offline or no response",
        )

        row = curated_server_row(self.server, status)

        self.assertEqual(row[5], "203.0.113.10")
        self.assertEqual(row[3], "Configured Name")
        self.assertEqual(row[8], "OFFLINE")
        self.assertEqual(row[9], "offline or no response")
        self.assertEqual(row[10:], ["", "", "", "", "", ""])


if __name__ == "__main__":
    unittest.main()
