import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import wolflauncher.config as config
from wolflauncher.models import Server


class LauncherPathDiscoveryTests(unittest.TestCase):
    def test_find_default_launcher_path_returns_first_existing_candidate(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            missing = Path(tmpdir) / "missing.sh"
            existing = Path(tmpdir) / "dayz-launcher.sh"
            existing.write_text("#!/usr/bin/env bash\n", encoding="utf-8")

            with patch.object(config, "DEFAULT_LAUNCHER_PATHS", [missing, existing]):
                self.assertEqual(config.find_default_launcher_path(), str(existing))

    def test_find_default_launcher_path_falls_back_to_first_candidate(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            first = Path(tmpdir) / "first.sh"
            second = Path(tmpdir) / "second.sh"

            with patch.object(config, "DEFAULT_LAUNCHER_PATHS", [first, second]):
                self.assertEqual(config.find_default_launcher_path(), str(first))

    def test_vendored_launcher_is_default_candidate(self):
        self.assertIn(config.VENDORED_LAUNCHER_PATH, config.DEFAULT_LAUNCHER_PATHS)
        self.assertTrue(config.VENDORED_LAUNCHER_PATH.exists())
        self.assertTrue(config.VENDORED_LAUNCHER_PATH.is_file())


class LoadServersTests(unittest.TestCase):
    def test_load_servers_reads_yaml_server_entries(self):
        yaml_text = """
servers:
  - name: Drakon Expansion
    group: Drakon
    host: drakonwolf.ddns.net
    game_port: 3302
    query_port: 3303
    favourite: true
  - name: Namalsk
    host: 203.0.113.10
    game_port: "2302"
    query_port: "27016"
"""
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "servers.yaml"
            path.write_text(yaml_text, encoding="utf-8")

            servers = config.load_servers(path)

        self.assertEqual(
            servers,
            [
                Server(
                    name="Drakon Expansion",
                    group="Drakon",
                    host="drakonwolf.ddns.net",
                    game_port=3302,
                    query_port=3303,
                    favourite=True,
                ),
                Server(
                    name="Namalsk",
                    group="Community",
                    host="203.0.113.10",
                    game_port=2302,
                    query_port=27016,
                    favourite=False,
                ),
            ],
        )

    def test_load_servers_handles_empty_yaml(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "servers.yaml"
            path.write_text("", encoding="utf-8")

            self.assertEqual(config.load_servers(path), [])


if __name__ == "__main__":
    unittest.main()
