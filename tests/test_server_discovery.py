import unittest
from unittest.mock import patch

from wolflauncher.models import DiscoveredServer
from wolflauncher.server_discovery import (
    DAYZ_APP_ID,
    MasterServerEndpoint,
    build_master_server_request,
    discover_dayz_servers,
    discovered_server_from_endpoint,
    parse_master_server_response,
)


class SteamMasterServerProtocolTests(unittest.TestCase):
    def test_build_master_server_request_uses_dayz_app_filter(self):
        request = build_master_server_request()

        self.assertEqual(request[0:1], b"1")
        self.assertEqual(request[1], 0xFF)
        self.assertIn(b"0.0.0.0:0\0", request)
        self.assertIn(f"\\appid\\{DAYZ_APP_ID}".encode("ascii"), request)
        self.assertTrue(request.endswith(b"\0"))

    def test_parse_master_server_response_reads_endpoints_until_terminator(self):
        packet = (
            b"\xff\xff\xff\xfff\n"
            + bytes([203, 0, 113, 10])
            + (27016).to_bytes(2, "big")
            + bytes([198, 51, 100, 20])
            + (2303).to_bytes(2, "big")
            + bytes([0, 0, 0, 0])
            + (0).to_bytes(2, "big")
        )

        endpoints, complete = parse_master_server_response(packet)

        self.assertTrue(complete)
        self.assertEqual(
            endpoints,
            [
                MasterServerEndpoint("203.0.113.10", 27016),
                MasterServerEndpoint("198.51.100.20", 2303),
            ],
        )

    def test_parse_master_server_response_rejects_bad_header(self):
        with self.assertRaisesRegex(ValueError, "header"):
            parse_master_server_response(b"not a master response")

    def test_endpoint_maps_to_discovered_server_candidate(self):
        server = discovered_server_from_endpoint(
            MasterServerEndpoint("203.0.113.10", 27016),
            "2026-06-20T14:00:00+00:00",
        )

        self.assertEqual(
            server,
            DiscoveredServer(
                name="203.0.113.10:27016",
                source="steam_master",
                host="203.0.113.10",
                game_port=27016,
                query_port=27016,
                last_seen="2026-06-20T14:00:00+00:00",
            ),
        )

    @patch("wolflauncher.server_discovery.query_master_server_batch")
    def test_discover_dayz_servers_pages_until_complete_and_deduplicates(self, query_batch):
        query_batch.side_effect = [
            (
                [
                    MasterServerEndpoint("203.0.113.10", 27016),
                    MasterServerEndpoint("203.0.113.20", 27016),
                ],
                False,
            ),
            (
                [
                    MasterServerEndpoint("203.0.113.20", 27016),
                    MasterServerEndpoint("203.0.113.30", 27016),
                ],
                True,
            ),
        ]

        servers = discover_dayz_servers(max_batches=5)

        self.assertEqual([server.host for server in servers], [
            "203.0.113.10",
            "203.0.113.20",
            "203.0.113.30",
        ])
        self.assertEqual(query_batch.call_count, 2)


if __name__ == "__main__":
    unittest.main()
