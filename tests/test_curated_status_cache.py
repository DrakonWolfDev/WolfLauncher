import tempfile
import unittest
from pathlib import Path

from wolflauncher import curated_status_cache
from wolflauncher.models import Server
from wolflauncher.status import ServerStatus, ServerStatusOutcome


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
                day_acceleration=6,
                night_acceleration=4,
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

    def test_legacy_failed_status_is_loaded_as_unknown(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "curated_status.json"
            path.write_text(
                '{"server": {"online": false, "error": "status check timed out"}}',
                encoding="utf-8",
            )

            status = curated_status_cache.load_status_cache(path)["server"]

            self.assertIs(status.outcome, ServerStatusOutcome.CHECK_ERROR)
            self.assertEqual(status.display_state, "UNKNOWN")

    def test_cached_status_for_server_returns_none_when_missing(self):
        self.assertIsNone(curated_status_cache.cached_status_for_server({}, self.make_server()))

    def test_failure_history_increments_and_success_resets_it(self):
        previous = ServerStatus(
            False,
            outcome=ServerStatusOutcome.TIMEOUT,
            last_successful_query="2026-10-12T09:00:00+00:00",
            consecutive_failures=2,
        )
        failed = curated_status_cache.merge_status_history(
            ServerStatus(False, outcome=ServerStatusOutcome.NETWORK_ERROR), previous
        )
        recovered = curated_status_cache.merge_status_history(
            ServerStatus(
                True,
                query_started_at="2026-10-13T10:00:00+00:00",
                outcome=ServerStatusOutcome.ONLINE,
            ),
            failed,
        )

        self.assertEqual(failed.last_successful_query, previous.last_successful_query)
        self.assertEqual(failed.consecutive_failures, 3)
        self.assertEqual(recovered.last_successful_query, recovered.query_started_at)
        self.assertEqual(recovered.consecutive_failures, 0)


if __name__ == "__main__":
    unittest.main()
