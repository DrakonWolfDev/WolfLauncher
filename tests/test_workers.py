import unittest
from unittest.mock import patch

from wolflauncher.models import DiscoveredServer, Server
from wolflauncher.status import ServerStatus
from wolflauncher.workers import (
    ServerEnrichmentWorker,
    StatusWorker,
    SteamDiscoveryWorker,
    _checked_server_status,
)


def sample_server(name: str = "Test") -> Server:
    return Server(name, "Group", "127.0.0.1", 2302, 2303)


class WorkerTests(unittest.TestCase):
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
            lambda server, count, total: progress.append((server.name, count, total))
        )
        worker.enrichment_ready.connect(
            lambda enriched, error: completed.append((enriched, error))
        )

        worker.run()

        self.assertEqual(sorted(item[0] for item in progress), ["One", "Two"])
        self.assertEqual(sorted(item[1] for item in progress), [1, 2])
        self.assertTrue(all(item[2] == 2 for item in progress))
        self.assertEqual(len(completed[0][0]), 2)
        self.assertEqual(completed[0][1], "")


if __name__ == "__main__":
    unittest.main()
