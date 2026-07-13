import unittest
from datetime import datetime, timedelta, timezone

from wolflauncher.discovery_refresh import auto_refresh_due, auto_refresh_timestamp
from wolflauncher.settings import DEFAULT_DISCOVERY_PROVIDER


class AutoRefreshThrottleTests(unittest.TestCase):
    def test_fresh_install_discovery_provider_is_wolfapi_v1(self):
        self.assertEqual(DEFAULT_DISCOVERY_PROVIDER, "wolfapi_v1")

    def test_recent_provider_refresh_is_throttled(self):
        now = datetime(2026, 7, 11, 20, 0, tzinfo=timezone.utc)
        recent = now - timedelta(hours=1)

        self.assertFalse(auto_refresh_due(recent.isoformat(), now=now))

    def test_naive_old_provider_refresh_is_treated_as_utc(self):
        now = datetime(2026, 7, 11, 20, 0, tzinfo=timezone.utc)
        old = now.replace(tzinfo=None) - timedelta(hours=25)

        self.assertTrue(auto_refresh_due(old.isoformat(), now=now))

    def test_missing_or_invalid_timestamp_is_due(self):
        self.assertTrue(auto_refresh_due(""))
        self.assertTrue(auto_refresh_due("not-a-timestamp"))

    def test_timestamp_is_normalized_to_utc_without_microseconds(self):
        now = datetime(2026, 7, 11, 21, 15, 30, 123456, tzinfo=timezone(timedelta(hours=1)))

        self.assertEqual(auto_refresh_timestamp(now), "2026-07-11T20:15:30+00:00")


if __name__ == "__main__":
    unittest.main()
