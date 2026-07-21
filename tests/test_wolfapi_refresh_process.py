import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from wolflauncher import server_cache
from wolflauncher.models import DiscoveredServer
from wolflauncher.server_discovery import WolfApiServerList
from wolflauncher.wolfapi_refresh_process import refresh_cache


class WolfApiRefreshProcessTests(unittest.TestCase):
    @patch("wolflauncher.wolfapi_refresh_process.discover_wolfapi_v1_pages")
    def test_process_refresh_fetches_and_commits_v1_page(self, discover):
        server = DiscoveredServer(
            "Example",
            "203.0.113.10",
            2302,
            27016,
            stable_server_id="stable-1",
        )
        discover.return_value = WolfApiServerList([server], directory_total=57411)
        with TemporaryDirectory() as directory:
            path = Path(directory) / "servers.sqlite3"

            result = refresh_cache(path, 100, True, False)

            connection = server_cache.connect(path)
            try:
                stored = server_cache.get_server(connection, server.cache_key)
            finally:
                connection.close()
        self.assertEqual(
            result,
            {"inserted": 1, "removed": 0, "directory_total": 57411, "error": ""},
        )
        self.assertIsNotNone(stored)
        discover.assert_called_once_with(100, unflagged_only=False)


if __name__ == "__main__":
    unittest.main()
