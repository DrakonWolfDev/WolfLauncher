import unittest

from wolflauncher.launch_selection import server_with_resolved_ipv4
from wolflauncher.models import Server


class LaunchSelectionTests(unittest.TestCase):
    def setUp(self):
        self.server = Server(
            name="Example",
            group="Tests",
            host="dayz.example.test",
            game_port=2302,
            query_port=27016,
            favourite=True,
        )

    def test_valid_resolved_ipv4_replaces_host_only(self):
        selected = server_with_resolved_ipv4(self.server, " 203.0.113.10 ")

        self.assertEqual(selected.host, "203.0.113.10")
        self.assertEqual(selected.name, self.server.name)
        self.assertEqual(selected.game_port, self.server.game_port)
        self.assertTrue(selected.favourite)

    def test_checking_placeholder_preserves_configured_host(self):
        self.assertIs(server_with_resolved_ipv4(self.server, "Checking..."), self.server)

    def test_blank_or_malformed_value_preserves_configured_host(self):
        for candidate in ("", "not-an-ip", "203.0.113.999"):
            with self.subTest(candidate=candidate):
                self.assertIs(server_with_resolved_ipv4(self.server, candidate), self.server)

    def test_ipv6_is_not_used_for_current_ipv4_launch_contract(self):
        self.assertIs(server_with_resolved_ipv4(self.server, "2001:db8::1"), self.server)


if __name__ == "__main__":
    unittest.main()
