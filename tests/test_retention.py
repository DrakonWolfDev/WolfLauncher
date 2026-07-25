import os
import tempfile
import unittest
from pathlib import Path

from wolflauncher.retention import (
    CACHE_RETENTION_DAYS,
    SUPPORT_RETENTION_DAYS,
    run_local_retention,
)


class LocalRetentionTests(unittest.TestCase):
    def test_removes_only_stale_disposable_files(self):
        now = 2_000_000_000
        with tempfile.TemporaryDirectory() as temporary_directory:
            data_dir = Path(temporary_directory)
            old_cache = data_dir / "server_cache.sqlite3"
            old_log = data_dir / "wolflauncher.log.2"
            old_report = data_dir / "last_launch_report.txt"
            fresh_cache = data_dir / "curated_status.json"
            settings = data_dir / "settings.json"
            curated = data_dir / "servers.yaml"
            for path in (old_cache, old_log, old_report, fresh_cache, settings, curated):
                path.write_text("data", encoding="utf-8")
            thumbnail_directory = data_dir / "thumbnails"
            thumbnail_directory.mkdir()
            old_thumbnail = thumbnail_directory / "old.png"
            fresh_thumbnail = thumbnail_directory / "fresh.png"
            old_thumbnail.write_bytes(b"old")
            fresh_thumbnail.write_bytes(b"fresh")

            stale_cache_time = now - (CACHE_RETENTION_DAYS + 1) * 24 * 60 * 60
            stale_support_time = now - (SUPPORT_RETENTION_DAYS + 1) * 24 * 60 * 60
            for path in (old_cache, old_thumbnail):
                os.utime(path, (stale_cache_time, stale_cache_time))
            for path in (old_log, old_report):
                os.utime(path, (stale_support_time, stale_support_time))
            for path in (fresh_cache, fresh_thumbnail, settings, curated):
                os.utime(path, (now, now))

            result = run_local_retention(data_dir, now=now)

            self.assertEqual(result.removed_cache_files, 1)
            self.assertEqual(result.removed_support_files, 2)
            self.assertEqual(result.removed_thumbnail_files, 1)
            self.assertFalse(old_cache.exists())
            self.assertFalse(old_log.exists())
            self.assertFalse(old_report.exists())
            self.assertFalse(old_thumbnail.exists())
            self.assertTrue(fresh_cache.exists())
            self.assertTrue(fresh_thumbnail.exists())
            self.assertTrue(settings.exists())
            self.assertTrue(curated.exists())

    def test_recent_files_are_retained(self):
        now = 2_000_000_000
        with tempfile.TemporaryDirectory() as temporary_directory:
            data_dir = Path(temporary_directory)
            cache = data_dir / "server_cache.sqlite3"
            log = data_dir / "wolflauncher.log"
            report = data_dir / "last_launch_report.txt"
            for path in (cache, log, report):
                path.write_text("data", encoding="utf-8")
                os.utime(path, (now, now))

            result = run_local_retention(data_dir, now=now)

            self.assertEqual(result.removed_cache_files, 0)
            self.assertEqual(result.removed_support_files, 0)
            self.assertTrue(cache.exists())
            self.assertTrue(log.exists())
            self.assertTrue(report.exists())
