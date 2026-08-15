import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from wolflauncher.models import DiscoveredServer, Server
from wolflauncher.status import ServerStatus
from wolflauncher.workers import (
    ServerEnrichmentWorker,
    StatusWorker,
    SteamDiscoveryWorker,
    WolfApiCacheMergeWorker,
    WolfApiDiscoveryWorker,
    WolfApiSearchWorker,
    _checked_server_status,
    discover_wolfapi_v1_pages,
)


def sample_server(name: str = "Test") -> Server:
    return Server(name, "Group", "127.0.0.1", 2302, 2303)


class WorkerTests(unittest.TestCase):
    def test_wolfapi_cache_merge_worker_commits_with_its_own_connection(self):
        server = DiscoveredServer(
            "WolfAPI", "203.0.113.10", 2302, 27016, stable_server_id="stable-1"
        )
        results = []
        with TemporaryDirectory() as directory:
            path = Path(directory) / "servers.sqlite3"
            worker = WolfApiCacheMergeWorker(
                path, [server], bounded_v1=True, source="wolfapi_experimental"
            )
            worker.merge_ready.connect(
                lambda inserted, removed, error: results.append((inserted, removed, error))
            )

            worker.run()

            from wolflauncher import server_cache

            connection = server_cache.connect(path)
            try:
                stored = server_cache.get_server(connection, server.cache_key)
            finally:
                connection.close()
        self.assertEqual(results, [(1, 0, "")])
        self.assertIsNotNone(stored)
        self.assertEqual(stored.source, "wolfapi_experimental")

    def test_status_worker_filters_invalid_requested_rows(self):
        servers = [sample_server("One"), sample_server("Two")]

        worker = StatusWorker(servers, rows=[1, -1, 3])

        self.assertEqual(worker.servers, [(1, servers[1])])

    @patch("wolflauncher.workers.check_server", side_effect=RuntimeError("broken query"))
    def test_checked_server_status_converts_unexpected_error(self, _check_server):
        status = _checked_server_status(sample_server())

        self.assertFalse(status.online)
        self.assertEqual(status.error, "status check failed: broken query")

    @patch("wolflauncher.workers.discover_dayz_servers", side_effect=OSError("network down"))
    def test_steam_discovery_worker_emits_recoverable_error(self, _discover):
        results = []
        worker = SteamDiscoveryWorker()
        worker.discovery_ready.connect(lambda servers, error: results.append((servers, error)))

        worker.run()

        self.assertEqual(results, [([], "network down")])

    @patch("wolflauncher.workers.discover_dayz_servers_wolfapi_v1")
    def test_wolfapi_worker_uses_strict_bounded_v1_when_selected(self, discover):
        discover.return_value = ["v1-server"]
        results = []
        worker = WolfApiDiscoveryWorker(limit=100, use_v1=True)
        worker.discovery_ready.connect(lambda servers, error: results.append((servers, error)))

        worker.run()

        discover.assert_called_once_with(limit=100, offset=0, product="stable")
        self.assertEqual(worker.provider_label, "WolfAPI v1")
        self.assertEqual(results, [(["v1-server"], "")])

    @patch("wolflauncher.workers.discover_dayz_servers_wolfapi")
    def test_wolfapi_worker_preserves_legacy_fallback(self, discover):
        discover.return_value = ["legacy-server"]
        results = []
        worker = WolfApiDiscoveryWorker(limit=500, use_v1=False)
        worker.discovery_ready.connect(lambda servers, error: results.append((servers, error)))

        worker.run()

        discover.assert_called_once_with(limit=500)
        self.assertEqual(worker.provider_label, "WolfAPI legacy")
        self.assertEqual(results, [(["legacy-server"], "")])

    @patch("wolflauncher.workers.discover_dayz_servers_wolfapi_v1")
    def test_v1_background_discovery_fetches_bounded_pages(self, discover):
        from wolflauncher.server_discovery import WolfApiServerList

        discover.side_effect = [
            WolfApiServerList(range(100), directory_total=57411),
            WolfApiServerList(range(100, 150), directory_total=57411),
        ]

        servers = discover_wolfapi_v1_pages(150)

        self.assertEqual(len(servers), 150)
        self.assertEqual(servers.directory_total, 57411)
        self.assertEqual(
            discover.call_args_list,
            [
                unittest.mock.call(limit=100, offset=0, product="stable"),
                unittest.mock.call(limit=50, offset=100, product="stable"),
            ],
        )

    @patch("wolflauncher.workers.discover_dayz_servers_wolfapi_v1")
    def test_v1_background_discovery_forwards_quality_filter(self, discover):
        discover.return_value = []

        discover_wolfapi_v1_pages(100, unflagged_only=True)

        discover.assert_called_once_with(limit=100, offset=0, product="stable", unflagged_only=True)

    @patch("wolflauncher.workers.search_dayz_servers_wolfapi_v1")
    def test_v1_search_worker_preserves_query_and_filters(self, search):
        search.return_value = ["remote-server"]
        results = []
        worker = WolfApiSearchWorker(
            "  Alpha   Server ", limit=50, map_name="chernarusplus", version="1.29"
        )
        worker.search_ready.connect(
            lambda query, servers, error: results.append((query, servers, error))
        )

        worker.run()

        search.assert_called_once_with(
            "Alpha Server",
            limit=50,
            map_name="chernarusplus",
            version="1.29",
            product="stable",
        )
        self.assertEqual(results, [("Alpha Server", ["remote-server"], "")])

    @patch("wolflauncher.workers.search_dayz_servers_wolfapi_v1")
    def test_v1_search_worker_forwards_quality_filter(self, search):
        search.return_value = []
        worker = WolfApiSearchWorker("Alpha", unflagged_only=True)

        worker.run()

        search.assert_called_once_with(
            "Alpha",
            limit=100,
            map_name="",
            version="",
            product="stable",
            unflagged_only=True,
        )

    @patch("wolflauncher.workers.resolve_dayz_server_wolfapi_v1")
    @patch("wolflauncher.workers.search_dayz_servers_wolfapi_v1")
    def test_v1_search_worker_uses_alias_aware_resolution_for_endpoint(self, search, resolve):
        server = unittest.mock.Mock(
            stable_server_id="stable-1", cache_key="203.0.113.10:2302:27016"
        )
        resolve.side_effect = [[server], [server]]
        results = []
        worker = WolfApiSearchWorker("203.0.113.10:2302")
        worker.search_ready.connect(
            lambda query, servers, error: results.append((query, servers, error))
        )

        worker.run()

        search.assert_not_called()
        self.assertEqual(
            resolve.call_args_list,
            [
                unittest.mock.call("203.0.113.10", game_port=2302, product="stable"),
                unittest.mock.call("203.0.113.10", query_port=2302, product="stable"),
            ],
        )
        self.assertEqual(results, [("203.0.113.10:2302", [server], "")])

    @patch("wolflauncher.workers.check_server")
    def test_checked_server_status_returns_successful_result(self, check_server):
        expected = ServerStatus(True, ping="42 ms")
        check_server.return_value = expected

        self.assertIs(_checked_server_status(sample_server()), expected)

    @patch("wolflauncher.workers.check_server", return_value=ServerStatus(True))
    def test_enrichment_worker_emits_incremental_progress(self, _check_server):
        servers = [
            DiscoveredServer("One", "127.0.0.1", 2302, 2303),
            DiscoveredServer("Two", "127.0.0.2", 2302, 2303),
        ]
        progress = []
        completed = []
        worker = ServerEnrichmentWorker(servers)
        worker.enrichment_progress.connect(
            lambda payload, count, total: progress.append(
                (payload[0], payload[1].name, count, total)
            )
        )
        worker.enrichment_ready.connect(lambda enriched, error: completed.append((enriched, error)))

        worker.run()

        self.assertEqual([item[1] for item in progress], ["One", "Two"])
        self.assertEqual([item[2] for item in progress], [1, 2])
        self.assertTrue(all(item[3] == 2 for item in progress))
        self.assertEqual(progress[0][0], servers[0].cache_key)
        self.assertEqual(len(completed[0][0]), 2)
        self.assertEqual(completed[0][1], "")

    @patch("wolflauncher.workers.check_server", return_value=ServerStatus(False))
    def test_fast_enrichment_checks_only_primary_query_port(self, check_server):
        server = DiscoveredServer("Fast", "127.0.0.1", 2302, 2302)
        worker = ServerEnrichmentWorker([server], probe_fallbacks=False)

        worker.run()

        check_server.assert_called_once()
        self.assertEqual(check_server.call_args.args[0].query_port, 2302)
        self.assertEqual(check_server.call_args.kwargs["socket_timeout_ms"], 750)
        self.assertEqual(check_server.call_args.kwargs["process_timeout"], 2)

    @patch("wolflauncher.workers.check_server")
    def test_cancelled_enrichment_does_not_start_more_checks(self, check_server):
        worker = ServerEnrichmentWorker(
            [DiscoveredServer("Cancelled", "127.0.0.1", 2302, 2302)],
            probe_fallbacks=False,
        )

        worker.cancel()
        worker.run()

        check_server.assert_not_called()


if __name__ == "__main__":
    unittest.main()
