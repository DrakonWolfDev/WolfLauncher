import tempfile
import unittest
from pathlib import Path

from wolflauncher import launch_history


class LaunchHistoryTests(unittest.TestCase):
    def test_save_and_load_last_launch_report(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "last_launch_report.txt"

            launch_history.save_last_launch_report("WolfLauncher launch output\nCommand: steam", path)

            self.assertEqual(
                launch_history.load_last_launch_report(path),
                "WolfLauncher launch output\nCommand: steam",
            )

    def test_save_last_launch_report_ignores_blank_report(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "last_launch_report.txt"

            launch_history.save_last_launch_report("  \n", path)

            self.assertFalse(path.exists())
            self.assertEqual(launch_history.load_last_launch_report(path), "")

    def test_load_last_launch_report_returns_empty_when_missing(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "missing.txt"

            self.assertEqual(launch_history.load_last_launch_report(path), "")

    def test_save_last_launch_report_reports_write_failures(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            parent_file = Path(tmpdir) / "not-a-directory"
            parent_file.write_text("", encoding="utf-8")
            path = parent_file / "last_launch_report.txt"

            with self.assertRaises(OSError):
                launch_history.save_last_launch_report("WolfLauncher launch output", path)

            self.assertEqual(launch_history.load_last_launch_report(path), "")


if __name__ == "__main__":
    unittest.main()
