import json
import stat
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from wolflauncher.persistence import atomic_write_text, ensure_private_file
from wolflauncher.settings import save_json


class AtomicPersistenceTests(unittest.TestCase):
    def test_existing_private_file_permissions_are_tightened(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "settings.json"
            path.write_text("{}\n", encoding="utf-8")
            path.chmod(0o664)

            ensure_private_file(path)

            self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o600)

    def test_atomic_write_creates_private_file_and_parent(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "nested" / "value.txt"

            atomic_write_text(path, "complete\n")

            self.assertEqual(path.read_text(encoding="utf-8"), "complete\n")
            self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o600)
            self.assertEqual(stat.S_IMODE(path.parent.stat().st_mode), 0o700)

    def test_atomic_write_preserves_backup_of_previous_value(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "servers.yaml"
            atomic_write_text(path, "old\n")

            atomic_write_text(path, "new\n", backup=True)

            self.assertEqual(path.read_text(encoding="utf-8"), "new\n")
            self.assertEqual(path.with_suffix(".yaml.bak").read_text(encoding="utf-8"), "old\n")

    def test_replace_failure_preserves_destination_and_removes_temporary_file(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "settings.json"
            atomic_write_text(path, "old\n")

            with patch("wolflauncher.persistence.os.replace", side_effect=OSError("disk full")):
                with self.assertRaisesRegex(OSError, "disk full"):
                    atomic_write_text(path, "new\n")

            self.assertEqual(path.read_text(encoding="utf-8"), "old\n")
            self.assertEqual(list(path.parent.glob(".*.tmp")), [])

    def test_json_save_is_complete_and_private(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "settings.json"

            save_json(path, {"steam_web_api_key": "secret"})

            self.assertEqual(
                json.loads(path.read_text(encoding="utf-8")), {"steam_web_api_key": "secret"}
            )
            self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o600)


if __name__ == "__main__":
    unittest.main()
