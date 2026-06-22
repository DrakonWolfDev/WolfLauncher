import tempfile
import unittest
from pathlib import Path

from wolflauncher import curated_status_cache
from wolflauncher.models import Server
from wolflauncher.status import ServerStatus


class CuratedStatusCacheTests(unittest.TestCase):
    def make_server(self) -> Server:
        return Server(
            name="Example",
            group="Community",
            host="203.0.113.10",
            game_port=2302,
            query_port=2303,
        )

    def test_update_status_cache_persists_status_by_server_key(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "curated_status.json"
            cache = {}
            status = ServerStatus(
                online=True,
                resolved_ip="203.0.113.10",
                server_name="Live Example",
                map_name="Chernarus",
                players="4/60",
                time="12:00",
                version="1.26",
                ping="42",
                password=True,
                modded=True,
                connect="203.0.113.10:2302",
            )

            curated_status_cache.update_status_cache(cache, self.make_server(), status, path)

            loaded = curated_status_cache.load_status_cache(path)
            cached = curated_status_cache.cached_status_for_server(loaded, self.make_server())
            self.assertEqual(cached, status)

    def test_load_status_cache_skips_invalid_rows(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "curated_status.json"
            path.write_text(
                """
{
  "valid": {"online": true, "resolved_ip": "203.0.113.10"},
  "invalid": "not a status"
}
""",
                encoding="utf-8",
            )

            loaded = curated_status_cache.load_status_cache(path)

            self.assertEqual(list(loaded), ["valid"])
            self.assertEqual(loaded["valid"].resolved_ip, "203.0.113.10")

    def test_cached_status_for_server_returns_none_when_missing(self):
        self.assertIsNone(curated_status_cache.cached_status_for_server({}, self.make_server()))


if __name__ == "__main__":
    unittest.main()
