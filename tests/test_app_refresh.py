import unittest
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

from wolflauncher.app import MainWindow


class AutoRefreshThrottleTests(unittest.TestCase):
    def test_recent_provider_refresh_is_throttled(self):
        recent = datetime.now(timezone.utc) - timedelta(hours=1)
        window = SimpleNamespace(
            settings={"last_wolfapi_auto_refresh_at": recent.isoformat()}
        )

        self.assertFalse(MainWindow.should_auto_refresh_provider(window, "wolfapi"))

    def test_naive_old_provider_refresh_is_treated_as_utc(self):
        old = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(hours=25)
        window = SimpleNamespace(
            settings={"last_wolfapi_auto_refresh_at": old.isoformat()}
        )

        self.assertTrue(MainWindow.should_auto_refresh_provider(window, "wolfapi"))


if __name__ == "__main__":
    unittest.main()
