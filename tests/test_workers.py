import unittest
from unittest.mock import patch

from wolflauncher.models import Server
from wolflauncher.status import ServerStatus
from wolflauncher.workers import StatusWorker, SteamDiscoveryWorker, _checked_server_status


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


if __name__ == "__main__":
    unittest.main()
