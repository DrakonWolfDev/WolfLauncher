import unittest
import urllib.parse
from unittest.mock import patch

from wolflauncher.models import DiscoveredServer
from wolflauncher.server_discovery import (
    DAYZ_APP_ID,
    BattleMetricsError,
    MasterServerAddress,
    MasterServerEndpoint,
    SteamMasterServerError,
    SteamWebApiError,
    WolfApiError,
    _discover_dayz_servers_from_master,
    build_master_server_request,
    discover_dayz_servers,
    discover_dayz_servers_battlemetrics,
    discover_dayz_servers_wolfapi,
    discover_dayz_servers_wolfapi_v1,
    discovered_server_from_battlemetrics_row,
    discovered_server_from_endpoint,
    discovered_server_from_web_api_row,
    discovered_server_from_wolfapi_row,
    parse_battlemetrics_servers,
    parse_exact_server_endpoint,
    parse_master_address,
    parse_master_server_response,
    parse_steam_web_api_servers,
    parse_wolfapi_servers,
    parse_wolfapi_v1_servers,
    resolve_dayz_server_wolfapi_v1,
    search_dayz_servers_wolfapi_v1,
)


class SteamMasterServerProtocolTests(unittest.TestCase):
    def test_provider_rows_drop_invalid_ports_and_oversized_names(self):
        self.assertIsNone(
            discovered_server_from_web_api_row(
                {"addr": "203.0.113.10:70000", "gameport": 2302, "name": "Invalid"}
            )
        )
        self.assertIsNone(
            discovered_server_from_wolfapi_row(
                {"ip": "203.0.113.10", "game_port": 2302, "query_port": 27016, "name": "x" * 257}
            )
        )
        self.assertIsNone(
            discovered_server_from_battlemetrics_row(
                {"attributes": {"ip": "2001:db8::1", "port": 2302, "name": "IPv6"}}
            )
        )

    def test_build_master_server_request_uses_dayz_app_filter(self):
        request = build_master_server_request()

        self.assertEqual(request[0:1], b"1")
        self.assertEqual(request[1], 0xFF)
        self.assertIn(b"0.0.0.0:0\0", request)
        self.assertIn(f"\\appid\\{DAYZ_APP_ID}".encode("ascii"), request)
        self.assertTrue(request.endswith(b"\0"))

    def test_build_master_server_request_accepts_experimental_app_id(self):
        request = build_master_server_request(app_id=1024020)

        self.assertIn(b"\\appid\\1024020", request)

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
    def test_discover_dayz_servers_from_master_pages_until_complete_and_deduplicates(
        self, query_batch
    ):
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

        self.assertEqual(
            [server.host for server in servers],
            [
                "203.0.113.10",
                "203.0.113.20",
                "203.0.113.30",
            ],
        )
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

    @patch.dict(
        "wolflauncher.server_discovery.os.environ",
        {"WOLFLAUNCHER_STEAM_MASTER_HOST": "203.0.113.10"},
    )
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
        self.assertEqual(
            discover_from_master.call_args_list[0].kwargs["master_host"], "203.0.113.10"
        )
        self.assertEqual(discover_from_master.call_args_list[0].kwargs["master_port"], 27011)
        self.assertEqual(
            discover_from_master.call_args_list[1].kwargs["master_host"], "203.0.113.20"
        )
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
                    "portQuery": 27016,
                    "players": 12,
                    "maxPlayers": 60,
                    "country": "us",
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
                country_code="US",
                country_source="battlemetrics",
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

    @patch("wolflauncher.server_discovery.fetch_battlemetrics_page")
    def test_battlemetrics_discovery_follows_next_links_until_limit(self, fetch_page):
        fetch_page.side_effect = [
            {
                "data": [
                    {
                        "attributes": {
                            "name": "One",
                            "ip": "203.0.113.10",
                            "port": 2302,
                        }
                    },
                    {
                        "attributes": {
                            "name": "Two",
                            "ip": "203.0.113.20",
                            "port": 2302,
                        }
                    },
                ],
                "links": {"next": "https://api.battlemetrics.com/servers?page[key]=next"},
            },
            {
                "data": [
                    {
                        "attributes": {
                            "name": "Three",
                            "ip": "203.0.113.30",
                            "port": 2302,
                        }
                    }
                ]
            },
        ]

        servers = discover_dayz_servers_battlemetrics(limit=3)

        self.assertEqual([server.name for server in servers], ["One", "Two", "Three"])
        self.assertEqual(fetch_page.call_count, 2)

    @patch("wolflauncher.server_discovery.time.sleep")
    @patch("wolflauncher.server_discovery.fetch_battlemetrics_page")
    def test_battlemetrics_discovery_sleeps_between_pages_when_configured(self, fetch_page, sleep):
        fetch_page.side_effect = [
            {
                "data": [
                    {
                        "attributes": {
                            "name": "One",
                            "ip": "203.0.113.10",
                            "port": 2302,
                        }
                    }
                ],
                "links": {"next": "https://api.battlemetrics.com/servers?page[key]=next"},
            },
            {
                "data": [
                    {
                        "attributes": {
                            "name": "Two",
                            "ip": "203.0.113.20",
                            "port": 2302,
                        }
                    }
                ]
            },
        ]

        discover_dayz_servers_battlemetrics(limit=2, page_delay=2.0)

        sleep.assert_called_once_with(2.0)

    @patch("wolflauncher.server_discovery.fetch_battlemetrics_page")
    def test_battlemetrics_discovery_stops_at_limit_mid_page(self, fetch_page):
        fetch_page.return_value = {
            "data": [
                {
                    "attributes": {
                        "name": "One",
                        "ip": "203.0.113.10",
                        "port": 2302,
                    }
                },
                {
                    "attributes": {
                        "name": "Two",
                        "ip": "203.0.113.20",
                        "port": 2302,
                    }
                },
            ],
            "links": {"next": "https://api.battlemetrics.com/servers?page[key]=next"},
        }

        servers = discover_dayz_servers_battlemetrics(limit=1)

        self.assertEqual([server.name for server in servers], ["One"])
        fetch_page.assert_called_once()


class WolfApiDiscoveryTests(unittest.TestCase):
    def test_wolfapi_row_maps_to_discovered_server(self):
        server = discovered_server_from_wolfapi_row(
            {
                "id": "81.152.152.55:3303",
                "addr": "81.152.152.55:3303",
                "ip": "81.152.152.55",
                "game_port": 3302,
                "query_port": 3303,
                "name": "DrakonCherno",
                "map": "chernarusplus",
                "players": 0,
                "max_players": 6,
                "version": "1.29.163047",
                "gametype": "battleye,external,mod",
                "last_seen": "2026-06-21T19:27:29+00:00",
                "required_mod_count": 17,
            },
            "2026-06-21T19:30:00+00:00",
        )

        self.assertEqual(
            server,
            DiscoveredServer(
                name="DrakonCherno",
                source="wolfapi",
                server_name="DrakonCherno",
                host="81.152.152.55",
                game_port=3302,
                query_port=3303,
                map_name="chernarusplus",
                players_current=0,
                players_max=6,
                version="1.29.163047",
                modded=True,
                online=True,
                last_checked="2026-06-21T19:30:00+00:00",
                last_seen="2026-06-21T19:27:29+00:00",
                required_mod_count=17,
            ),
        )

    def test_wolfapi_row_uses_addr_port_when_query_port_missing(self):
        server = discovered_server_from_wolfapi_row(
            {
                "addr": "203.0.113.10:27016",
                "game_port": "2302",
                "name": "WolfAPI DayZ",
            }
        )

        self.assertEqual(server.host, "203.0.113.10")
        self.assertEqual(server.game_port, 2302)
        self.assertEqual(server.query_port, 27016)

    def test_wolfapi_row_accepts_future_ping_field(self):
        server = discovered_server_from_wolfapi_row(
            {
                "addr": "203.0.113.10:27016",
                "game_port": 2302,
                "name": "WolfAPI DayZ",
                "ping_ms": "47",
            }
        )

        self.assertEqual(server.ping_ms, 47)

    def test_wolfapi_v1_row_preserves_stable_identity_and_freshness_contract(self):
        server = discovered_server_from_wolfapi_row(
            {
                "server_id": "11111111-1111-1111-1111-111111111111",
                "legacy_endpoint_id": "203.0.113.10:2402:28016",
                "endpoint_aliases": [
                    "203.0.113.10:2402:28016",
                    "203.0.113.10:2302:27016",
                ],
                "ip": "203.0.113.10",
                "game_port": 2402,
                "query_port": 28016,
                "name": "WolfAPI V1",
                "freshness": "live",
                "freshness_expires_at": "2026-07-13T12:30:00+00:00",
                "validation_status": "online",
                "validation_checked_at": "2026-07-13T12:00:00+00:00",
                "validation_seen_at": "2026-07-13T12:00:00+00:00",
                "provider_last_checked": "2026-07-13T11:55:00+00:00",
                "provider_last_seen": "2026-07-13T11:55:00+00:00",
                "required_mod_count": 17,
                "mod_metadata_status": "ready",
                "mod_metadata_checked_at": "2026-07-13T12:01:00+00:00",
                "mod_metadata_expires_at": "2026-07-13T18:01:00+00:00",
                "mod_metadata_error_code": "",
                "mod_manifest_hash": "sha256:example",
                "quality_flags": "suspicious_bots,high_population_cluster",
                "country_code": "de",
                "country_source": "battlemetrics",
            },
            "2026-07-13T12:05:00+00:00",
        )

        self.assertEqual(server.stable_server_id, "11111111-1111-1111-1111-111111111111")
        self.assertEqual(server.cache_key, "203.0.113.10:2402:28016")
        self.assertEqual(len(server.endpoint_aliases), 2)
        self.assertEqual(server.freshness, "live")
        self.assertEqual(server.validation_status, "online")
        self.assertEqual(server.last_checked, "2026-07-13T12:00:00+00:00")
        self.assertEqual(server.last_seen, "2026-07-13T12:00:00+00:00")
        self.assertEqual(server.required_mod_count, 17)
        self.assertEqual(server.mod_metadata_status, "ready")
        self.assertEqual(server.mod_manifest_hash, "sha256:example")
        self.assertEqual(
            server.quality_flags,
            ("suspicious_bots", "high_population_cluster"),
        )
        self.assertEqual(server.country_code, "DE")
        self.assertEqual(server.country_source, "battlemetrics")

    def test_parse_wolfapi_response_deduplicates_and_limits_rows(self):
        servers = parse_wolfapi_servers(
            {
                "updated_at": "2026-06-21T19:30:00+00:00",
                "servers": [
                    {
                        "addr": "203.0.113.10:27016",
                        "game_port": 2302,
                        "name": "First",
                    },
                    {
                        "addr": "203.0.113.10:27016",
                        "game_port": 2302,
                        "name": "Duplicate",
                    },
                    {
                        "addr": "203.0.113.20:27016",
                        "game_port": 2302,
                        "name": "Second",
                    },
                ],
            },
            limit=1,
        )

        self.assertEqual(len(servers), 1)
        self.assertEqual(servers[0].name, "First")
        self.assertEqual(servers[0].last_checked, "2026-06-21T19:30:00+00:00")

    def test_parse_wolfapi_response_flags_three_matching_names(self):
        servers = parse_wolfapi_servers(
            {
                "servers": [
                    {"addr": "203.0.113.10:27016", "game_port": 2302, "name": "Copied server"},
                    {"addr": "203.0.113.20:27016", "game_port": 2302, "name": " copied   server "},
                    {"addr": "203.0.113.30:27016", "game_port": 2302, "name": "COPIED SERVER"},
                    {"addr": "203.0.113.40:27016", "game_port": 2302, "name": "Legitimate server"},
                ]
            }
        )

        self.assertEqual(
            [server.quality_flags for server in servers],
            [
                ("duplicate_name_cluster",),
                ("duplicate_name_cluster",),
                ("duplicate_name_cluster",),
                (),
            ],
        )

    def test_parse_wolfapi_response_accepts_raw_list(self):
        servers = parse_wolfapi_servers(
            [
                {
                    "addr": "203.0.113.10:27016",
                    "game_port": 2302,
                    "name": "Raw List",
                }
            ]
        )

        self.assertEqual(len(servers), 1)
        self.assertEqual(servers[0].source, "wolfapi")

    def test_parse_wolfapi_response_rejects_missing_server_list(self):
        with self.assertRaisesRegex(WolfApiError, "server list"):
            parse_wolfapi_servers({"servers": {}})

    def test_parse_wolfapi_v1_rejects_incomplete_rollout_metadata(self):
        with self.assertRaisesRegex(WolfApiError, "rollout metadata"):
            parse_wolfapi_v1_servers({"contract_version": "1", "servers": []})

    def test_parse_wolfapi_v1_preserves_whole_directory_total(self):
        servers = parse_wolfapi_v1_servers(
            {
                "contract_version": "1",
                "generated_at": "2026-07-21T12:00:00Z",
                "validation_policy": {"live_for_seconds": 1800},
                "coverage": {"eligible": 57411},
                "validation_queue": {"ready": 1},
                "servers": [],
            }
        )

        self.assertEqual(servers.directory_total, 57411)

    def test_parse_wolfapi_v1_rejects_invalid_whole_directory_total(self):
        with self.assertRaisesRegex(WolfApiError, "eligible directory count"):
            parse_wolfapi_v1_servers(
                {
                    "contract_version": "1",
                    "generated_at": "2026-07-21T12:00:00Z",
                    "validation_policy": {"live_for_seconds": 1800},
                    "coverage": {"eligible": "unknown"},
                    "validation_queue": {"ready": 1},
                    "servers": [],
                }
            )

    @patch("wolflauncher.http_client.urllib.request.urlopen")
    def test_wolfapi_discovery_fetches_default_endpoint(self, urlopen):
        class FakeResponse:
            def __enter__(self):
                return self

            def __exit__(self, *_args):
                return False

            def read(self, _size=-1):
                return b'{"servers": [{"addr": "203.0.113.10:27016", "game_port": 2302}]}'

        urlopen.return_value = FakeResponse()

        servers = discover_dayz_servers_wolfapi(limit=5, timeout=7)

        self.assertEqual(len(servers), 1)
        request = urlopen.call_args.args[0]
        self.assertEqual(request.full_url, "https://api.wolfcontrol.co.uk/api/servers")
        self.assertEqual(urlopen.call_args.kwargs["timeout"], 7)

    @patch("wolflauncher.http_client.urllib.request.urlopen")
    def test_wolfapi_v1_initial_page_is_bounded(self, urlopen):
        urlopen.return_value = self.fake_wolfapi_response()

        servers = discover_dayz_servers_wolfapi_v1(limit=750, offset=25, timeout=4)

        self.assertEqual(len(servers), 1)
        request = urlopen.call_args.args[0]
        parsed = urllib.parse.urlparse(request.full_url)
        self.assertEqual(parsed.path, "/api/v1/servers")
        self.assertEqual(urllib.parse.parse_qs(parsed.query), {"limit": ["500"], "offset": ["25"]})
        self.assertEqual(urlopen.call_args.kwargs["timeout"], 4)

    @patch("wolflauncher.http_client.urllib.request.urlopen")
    def test_wolfapi_v1_list_requests_unflagged_quality_when_selected(self, urlopen):
        urlopen.return_value = self.fake_wolfapi_response()

        discover_dayz_servers_wolfapi_v1(limit=100, unflagged_only=True)

        request = urlopen.call_args.args[0]
        query = urllib.parse.parse_qs(urllib.parse.urlparse(request.full_url).query)
        self.assertEqual(query["quality"], ["unflagged"])

    @patch("wolflauncher.http_client.urllib.request.urlopen")
    def test_wolfapi_v1_search_normalizes_and_encodes_filters(self, urlopen):
        urlopen.return_value = self.fake_wolfapi_response()

        search_dayz_servers_wolfapi_v1(
            "  Alpha   Server ",
            limit=25,
            offset=50,
            map_name="chernarusplus",
            version="1.29",
        )

        request = urlopen.call_args.args[0]
        parsed = urllib.parse.urlparse(request.full_url)
        self.assertEqual(parsed.path, "/api/v1/servers/search")
        self.assertEqual(
            urllib.parse.parse_qs(parsed.query),
            {
                "q": ["Alpha Server"],
                "limit": ["25"],
                "offset": ["50"],
                "map": ["chernarusplus"],
                "version": ["1.29"],
            },
        )

    @patch("wolflauncher.http_client.urllib.request.urlopen")
    def test_wolfapi_v1_search_requests_unflagged_quality_when_selected(self, urlopen):
        urlopen.return_value = self.fake_wolfapi_response()

        search_dayz_servers_wolfapi_v1("Alpha", unflagged_only=True)

        request = urlopen.call_args.args[0]
        query = urllib.parse.parse_qs(urllib.parse.urlparse(request.full_url).query)
        self.assertEqual(query["quality"], ["unflagged"])

    def test_wolfapi_v1_search_requires_text(self):
        with self.assertRaisesRegex(ValueError, "query"):
            search_dayz_servers_wolfapi_v1("   ")

    @patch("wolflauncher.http_client.urllib.request.urlopen")
    def test_wolfapi_v1_resolution_encodes_exact_endpoint(self, urlopen):
        urlopen.return_value = self.fake_wolfapi_response()

        resolve_dayz_server_wolfapi_v1(
            "203.0.113.10",
            game_port=2302,
            query_port=27016,
        )

        request = urlopen.call_args.args[0]
        parsed = urllib.parse.urlparse(request.full_url)
        self.assertEqual(parsed.path, "/api/v1/servers/resolve")
        self.assertEqual(
            urllib.parse.parse_qs(parsed.query),
            {"host": ["203.0.113.10"], "game_port": ["2302"], "query_port": ["27016"]},
        )

    def test_wolfapi_v1_resolution_requires_a_port(self):
        with self.assertRaisesRegex(ValueError, "port"):
            resolve_dayz_server_wolfapi_v1("203.0.113.10")

    def test_exact_endpoint_parser_rejects_names_and_invalid_ports(self):
        self.assertEqual(
            parse_exact_server_endpoint(" 203.0.113.10:2302 "),
            ("203.0.113.10", 2302),
        )
        self.assertEqual(
            parse_exact_server_endpoint("dayz.example.test:27016"),
            ("dayz.example.test", 27016),
        )
        self.assertIsNone(parse_exact_server_endpoint("Alpha Server"))
        self.assertIsNone(parse_exact_server_endpoint("203.0.113.10:70000"))
        self.assertIsNone(parse_exact_server_endpoint("203.0.113.10:not-a-port"))

    @staticmethod
    def fake_wolfapi_response():
        class FakeResponse:
            def __enter__(self):
                return self

            def __exit__(self, *_args):
                return False

            def read(self, _size=-1):
                return (
                    b'{"contract_version":"1","generated_at":"2026-07-13T12:00:00Z",'
                    b'"validation_policy":{"live_for_seconds":1800},'
                    b'"coverage":{"eligible":1},'
                    b'"validation_queue":{"ready":1},'
                    b'"servers":[{"ip":"203.0.113.10","game_port":2302,"query_port":27016}]}'
                )

        return FakeResponse()


if __name__ == "__main__":
    unittest.main()

