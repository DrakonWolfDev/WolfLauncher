import unittest
from unittest.mock import patch

from wolflauncher.models import DiscoveredServer
from wolflauncher.server_discovery import (
    BattleMetricsError,
    DAYZ_APP_ID,
    MasterServerAddress,
    MasterServerEndpoint,
    SteamMasterServerError,
    SteamWebApiError,
    _discover_dayz_servers_from_master,
    build_master_server_request,
    discover_dayz_servers,
    discovered_server_from_endpoint,
    discovered_server_from_battlemetrics_row,
    discovered_server_from_web_api_row,
    parse_battlemetrics_servers,
    parse_master_address,
    parse_master_server_response,
    parse_steam_web_api_servers,
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

    def test_parse_master_address_uses_default_port(self):
        self.assertEqual(
            parse_master_address("203.0.113.10"),
            MasterServerAddress("203.0.113.10", 27011),
        )

    def test_parse_master_address_accepts_explicit_port(self):
        self.assertEqual(
            parse_master_address("203.0.113.10:27015"),
            MasterServerAddress("203.0.113.10", 27015),
        )

    def test_parse_master_address_rejects_bad_port(self):
        with self.assertRaisesRegex(ValueError, "port"):
            parse_master_address("203.0.113.10:not-a-port")

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
    def test_discover_dayz_servers_from_master_pages_until_complete_and_deduplicates(self, query_batch):
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

        servers = _discover_dayz_servers_from_master(max_batches=5)

        self.assertEqual([server.host for server in servers], [
            "203.0.113.10",
            "203.0.113.20",
            "203.0.113.30",
        ])
        self.assertEqual(query_batch.call_count, 2)

    @patch("wolflauncher.server_discovery._discover_dayz_servers_from_master")
    def test_discover_dayz_servers_tries_fallback_hosts(self, discover_from_master):
        discover_from_master.side_effect = [
            OSError("dns failed"),
            [
                DiscoveredServer(
                    name="Candidate",
                    host="203.0.113.10",
                    game_port=27016,
                    query_port=27016,
                )
            ],
        ]

        servers = discover_dayz_servers()

        self.assertEqual(len(servers), 1)
        self.assertEqual(discover_from_master.call_count, 2)

    @patch("wolflauncher.server_discovery._discover_dayz_servers_from_master")
    def test_discover_dayz_servers_reports_all_failed_hosts(self, discover_from_master):
        discover_from_master.side_effect = OSError("dns failed")

        with self.assertRaisesRegex(SteamMasterServerError, "all configured hosts"):
            discover_dayz_servers()

    @patch.dict("wolflauncher.server_discovery.os.environ", {"WOLFLAUNCHER_STEAM_MASTER_HOST": "203.0.113.10"})
    @patch("wolflauncher.server_discovery._discover_dayz_servers_from_master")
    def test_discover_dayz_servers_uses_environment_host_override(self, discover_from_master):
        discover_from_master.return_value = []

        discover_dayz_servers()

        discover_from_master.assert_called_once()
        self.assertEqual(discover_from_master.call_args.kwargs["master_host"], "203.0.113.10")

    @patch.dict(
        "wolflauncher.server_discovery.os.environ",
        {"WOLFLAUNCHER_STEAM_MASTER_ENDPOINTS": "203.0.113.10:27011,203.0.113.20:27015"},
    )
    @patch("wolflauncher.server_discovery._discover_dayz_servers_from_master")
    def test_discover_dayz_servers_uses_environment_endpoint_list(self, discover_from_master):
        discover_from_master.side_effect = [
            OSError("timed out"),
            [],
        ]

        discover_dayz_servers()

        self.assertEqual(discover_from_master.call_count, 2)
        self.assertEqual(discover_from_master.call_args_list[0].kwargs["master_host"], "203.0.113.10")
        self.assertEqual(discover_from_master.call_args_list[0].kwargs["master_port"], 27011)
        self.assertEqual(discover_from_master.call_args_list[1].kwargs["master_host"], "203.0.113.20")
        self.assertEqual(discover_from_master.call_args_list[1].kwargs["master_port"], 27015)

    @patch("wolflauncher.server_discovery._discover_dayz_servers_from_master")
    def test_discover_dayz_servers_accepts_explicit_master_addresses(self, discover_from_master):
        discover_from_master.return_value = []

        discover_dayz_servers(
            master_addresses=[
                MasterServerAddress("203.0.113.10", 27015),
            ]
        )

        discover_from_master.assert_called_once()
        self.assertEqual(discover_from_master.call_args.kwargs["master_host"], "203.0.113.10")
        self.assertEqual(discover_from_master.call_args.kwargs["master_port"], 27015)


class SteamWebApiDiscoveryTests(unittest.TestCase):
    def test_web_api_row_maps_to_discovered_server(self):
        server = discovered_server_from_web_api_row(
            {
                "addr": "203.0.113.10:27016",
                "gameport": 2302,
                "name": "Web API DayZ",
                "map": "chernarusplus",
                "players": 12,
                "max_players": 60,
                "version": "1.26",
                "gametype": "battleye,mod",
            },
            "2026-06-20T15:00:00+00:00",
        )

        self.assertEqual(
            server,
            DiscoveredServer(
                name="Web API DayZ",
                source="steam_web_api",
                server_name="Web API DayZ",
                host="203.0.113.10",
                game_port=2302,
                query_port=27016,
                map_name="chernarusplus",
                players_current=12,
                players_max=60,
                version="1.26",
                modded=True,
                online=True,
                last_checked="2026-06-20T15:00:00+00:00",
                last_seen="2026-06-20T15:00:00+00:00",
            ),
        )

    def test_web_api_row_uses_gameport_when_addr_has_no_port(self):
        server = discovered_server_from_web_api_row(
            {
                "addr": "203.0.113.20",
                "gameport": "2302",
                "name": "No Query Port",
            }
        )

        self.assertEqual(server.host, "203.0.113.20")
        self.assertEqual(server.game_port, 2302)
        self.assertEqual(server.query_port, 2302)

    def test_parse_web_api_response_deduplicates_cache_keys(self):
        servers = parse_steam_web_api_servers(
            {
                "response": {
                    "servers": [
                        {
                            "addr": "203.0.113.10:27016",
                            "gameport": 2302,
                            "name": "First",
                        },
                        {
                            "addr": "203.0.113.10:27016",
                            "gameport": 2302,
                            "name": "Duplicate",
                        },
                    ]
                }
            }
        )

        self.assertEqual(len(servers), 1)
        self.assertEqual(servers[0].name, "First")

    def test_parse_web_api_response_rejects_missing_server_list(self):
        with self.assertRaisesRegex(SteamWebApiError, "server list"):
            parse_steam_web_api_servers({"response": {"servers": {}}})


class BattleMetricsDiscoveryTests(unittest.TestCase):
    def test_battlemetrics_row_maps_to_discovered_server(self):
        server = discovered_server_from_battlemetrics_row(
            {
                "type": "server",
                "id": "123",
                "attributes": {
                    "name": "BattleMetrics DayZ",
                    "ip": "203.0.113.10",
                    "port": 2302,
                    "queryPort": 27016,
                    "players": 12,
                    "maxPlayers": 60,
                    "status": "online",
                    "details": {
                        "map": "chernarusplus",
                        "version": "1.26",
                        "modded": True,
                    },
                },
            },
            "2026-06-20T16:00:00+00:00",
        )

        self.assertEqual(
            server,
            DiscoveredServer(
                name="BattleMetrics DayZ",
                source="battlemetrics",
                server_name="BattleMetrics DayZ",
                host="203.0.113.10",
                game_port=2302,
                query_port=27016,
                map_name="chernarusplus",
                players_current=12,
                players_max=60,
                version="1.26",
                modded=True,
                online=True,
                last_checked="2026-06-20T16:00:00+00:00",
                last_seen="2026-06-20T16:00:00+00:00",
            ),
        )

    def test_battlemetrics_row_uses_port_when_query_port_missing(self):
        server = discovered_server_from_battlemetrics_row(
            {
                "attributes": {
                    "name": "No Query Port",
                    "address": "203.0.113.20",
                    "port": "2302",
                    "status": "offline",
                }
            }
        )

        self.assertEqual(server.host, "203.0.113.20")
        self.assertEqual(server.game_port, 2302)
        self.assertEqual(server.query_port, 2302)
        self.assertFalse(server.online)

    def test_parse_battlemetrics_response_deduplicates_cache_keys(self):
        servers = parse_battlemetrics_servers(
            {
                "data": [
                    {
                        "attributes": {
                            "name": "First",
                            "ip": "203.0.113.10",
                            "port": 2302,
                            "queryPort": 27016,
                        }
                    },
                    {
                        "attributes": {
                            "name": "Duplicate",
                            "ip": "203.0.113.10",
                            "port": 2302,
                            "queryPort": 27016,
                        }
                    },
                ]
            }
        )

        self.assertEqual(len(servers), 1)
        self.assertEqual(servers[0].name, "First")

    def test_parse_battlemetrics_response_rejects_missing_server_list(self):
        with self.assertRaisesRegex(BattleMetricsError, "server list"):
            parse_battlemetrics_servers({"data": {}})


if __name__ == "__main__":
    unittest.main()
