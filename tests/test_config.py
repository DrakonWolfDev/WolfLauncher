import os
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

    @unittest.skipIf(os.name == "nt", "External shell launcher is Linux-only")
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


class NormalizeServerEndpointTests(unittest.TestCase):
    def test_normalize_server_endpoint_splits_host_and_port(self):
        self.assertEqual(
            config.normalize_server_endpoint(" dayz.example.test:2402 ", 2302, 2303),
            ("dayz.example.test", 2402, 2403),
        )

    def test_normalize_server_endpoint_keeps_custom_query_port(self):
        self.assertEqual(
            config.normalize_server_endpoint("dayz.example.test:2402", 2302, 27016),
            ("dayz.example.test", 2402, 27016),
        )

    def test_normalize_server_endpoint_leaves_plain_host_unchanged(self):
        self.assertEqual(
            config.normalize_server_endpoint(" dayz.example.test ", 2302, 2303),
            ("dayz.example.test", 2302, 2303),
        )

    def test_normalize_server_endpoint_ignores_invalid_port_suffix(self):
        self.assertEqual(
            config.normalize_server_endpoint("dayz.example.test:not-a-port", 2302, 2303),
            ("dayz.example.test:not-a-port", 2302, 2303),
        )

    def test_normalize_server_endpoint_ignores_multi_colon_hosts(self):
        self.assertEqual(
            config.normalize_server_endpoint("2001:db8::1", 2302, 2303),
            ("2001:db8::1", 2302, 2303),
        )


class EnsureServersFileTests(unittest.TestCase):
    def test_ensure_servers_file_copies_example_when_missing(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "servers.yaml"
            example = Path(tmpdir) / "example.servers.yaml"
            example.write_text(
                """
servers:
  - name: Example
    host: 203.0.113.10
    game_port: 2302
    query_port: 2303
""",
                encoding="utf-8",
            )

            config.ensure_servers_file(path, example)

            self.assertEqual(path.read_text(encoding="utf-8"), example.read_text(encoding="utf-8"))

    def test_ensure_servers_file_migrates_legacy_without_changing_source(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            path = root / "config" / "servers.yaml"
            legacy = root / "checkout" / "servers.yaml"
            example = root / "example.servers.yaml"
            legacy.parent.mkdir()
            legacy.write_text("servers: []\n# personal\n", encoding="utf-8")
            example.write_text("servers: []\n# example\n", encoding="utf-8")

            result = config.ensure_servers_file(path, example, legacy)

            self.assertEqual(result, "migrated")
            self.assertEqual(path.read_text(encoding="utf-8"), "servers: []\n# personal\n")
            self.assertEqual(legacy.read_text(encoding="utf-8"), "servers: []\n# personal\n")

    def test_ensure_servers_file_does_not_overwrite_existing_target_with_legacy(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            path = root / "config" / "servers.yaml"
            legacy = root / "checkout" / "servers.yaml"
            path.parent.mkdir()
            legacy.parent.mkdir()
            path.write_text("servers: []\n# target\n", encoding="utf-8")
            legacy.write_text("servers: []\n# legacy\n", encoding="utf-8")

            result = config.ensure_servers_file(path, legacy_path=legacy)

            self.assertEqual(result, "existing")
            self.assertEqual(path.read_text(encoding="utf-8"), "servers: []\n# target\n")
            self.assertEqual(legacy.read_text(encoding="utf-8"), "servers: []\n# legacy\n")

    def test_ensure_servers_file_rejects_invalid_legacy_without_creating_target(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            path = root / "config" / "servers.yaml"
            legacy = root / "servers.yaml"
            legacy.write_text("servers: not-a-list\n", encoding="utf-8")

            with self.assertRaisesRegex(ValueError, "servers.*list"):
                config.ensure_servers_file(path, legacy_path=legacy)

            self.assertFalse(path.exists())

    def test_ensure_servers_file_preserves_existing_file(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "servers.yaml"
            example = Path(tmpdir) / "example.servers.yaml"
            path.write_text("servers: []\n", encoding="utf-8")
            example.write_text("servers:\n- name: Example\n", encoding="utf-8")

            config.ensure_servers_file(path, example)

            self.assertEqual(path.read_text(encoding="utf-8"), "servers: []\n")

    def test_ensure_servers_file_writes_empty_list_when_example_missing(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "servers.yaml"

            config.ensure_servers_file(path, Path(tmpdir) / "missing.yaml")

            self.assertEqual(path.read_text(encoding="utf-8"), "servers: []\n")


class AddCuratedServerTests(unittest.TestCase):
    def test_add_curated_server_appends_yaml_entry(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "servers.yaml"
            path.write_text(
                """
servers:
  - name: Existing
    group: Existing Group
    host: 203.0.113.10
    game_port: 2302
    query_port: 27016
""",
                encoding="utf-8",
            )

            config.add_curated_server(
                path,
                Server(
                    name="Promoted",
                    group="Discovered",
                    host="203.0.113.20",
                    game_port=2402,
                    query_port=27017,
                    favourite=False,
                ),
            )

            self.assertEqual(
                config.load_servers(path),
                [
                    Server(
                        name="Existing",
                        group="Existing Group",
                        host="203.0.113.10",
                        game_port=2302,
                        query_port=27016,
                    ),
                    Server(
                        name="Promoted",
                        group="Discovered",
                        host="203.0.113.20",
                        game_port=2402,
                        query_port=27017,
                    ),
                ],
            )
            self.assertTrue(path.with_suffix(".yaml.bak").is_file())

    def test_add_curated_server_rejects_duplicate_host_and_ports(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "servers.yaml"
            path.write_text(
                """
servers:
  - name: Existing
    host: 203.0.113.10
    game_port: 2302
    query_port: 27016
""",
                encoding="utf-8",
            )

            with self.assertRaisesRegex(ValueError, "already"):
                config.add_curated_server(
                    path,
                    Server(
                        name="Duplicate Name",
                        group="Discovered",
                        host="203.0.113.10",
                        game_port=2302,
                        query_port=27016,
                    ),
                )

    def test_add_curated_server_keeps_original_when_atomic_replace_fails(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "servers.yaml"
            original = "servers: []\n"
            path.write_text(original, encoding="utf-8")

            with patch("wolflauncher.config.atomic_write_text", side_effect=OSError("disk full")):
                with self.assertRaisesRegex(OSError, "disk full"):
                    config.add_curated_server(
                        path,
                        Server("Example", "Community", "dayz.test", 2302, 27016),
                    )

            self.assertEqual(path.read_text(encoding="utf-8"), original)


class RemoveCuratedServerTests(unittest.TestCase):
    def test_remove_curated_server_deletes_matching_yaml_entry(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "servers.yaml"
            path.write_text(
                """
servers:
  - name: Keep
    group: Existing Group
    host: 203.0.113.10
    game_port: 2302
    query_port: 27016
  - name: Remove
    group: Mistake
    host: 203.0.113.20
    game_port: 2402
    query_port: 27017
""",
                encoding="utf-8",
            )

            removed = config.remove_curated_server(
                path,
                Server(
                    name="Remove",
                    group="Mistake",
                    host="203.0.113.20",
                    game_port=2402,
                    query_port=27017,
                ),
            )

            self.assertTrue(removed)
            self.assertEqual(
                config.load_servers(path),
                [
                    Server(
                        name="Keep",
                        group="Existing Group",
                        host="203.0.113.10",
                        game_port=2302,
                        query_port=27016,
                    ),
                ],
            )

    def test_remove_curated_server_reports_missing_entry(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "servers.yaml"
            path.write_text(
                """
servers:
  - name: Keep
    host: 203.0.113.10
    game_port: 2302
    query_port: 27016
""",
                encoding="utf-8",
            )

            removed = config.remove_curated_server(
                path,
                Server(
                    name="Missing",
                    group="Community",
                    host="203.0.113.99",
                    game_port=2302,
                    query_port=27016,
                ),
            )

            self.assertFalse(removed)
            self.assertEqual(len(config.load_servers(path)), 1)


class UpdateCuratedServerTests(unittest.TestCase):
    def test_update_curated_server_rewrites_matching_yaml_entry(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "servers.yaml"
            path.write_text(
                """
servers:
  - name: Keep
    group: Existing Group
    host: 203.0.113.10
    game_port: 2302
    query_port: 27016
  - name: Edit Me
    group: Old Group
    host: 203.0.113.20
    game_port: 2402
    query_port: 27017
""",
                encoding="utf-8",
            )

            updated = config.update_curated_server(
                path,
                Server(
                    name="Edit Me",
                    group="Old Group",
                    host="203.0.113.20",
                    game_port=2402,
                    query_port=27017,
                ),
                Server(
                    name="Edited",
                    group="New Group",
                    host="203.0.113.30",
                    game_port=2502,
                    query_port=27018,
                    favourite=True,
                ),
            )

            self.assertTrue(updated)
            self.assertEqual(
                config.load_servers(path),
                [
                    Server(
                        name="Keep",
                        group="Existing Group",
                        host="203.0.113.10",
                        game_port=2302,
                        query_port=27016,
                    ),
                    Server(
                        name="Edited",
                        group="New Group",
                        host="203.0.113.30",
                        game_port=2502,
                        query_port=27018,
                        favourite=True,
                    ),
                ],
            )

    def test_update_curated_server_rejects_duplicate_updated_endpoint(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "servers.yaml"
            path.write_text(
                """
servers:
  - name: Existing
    host: 203.0.113.10
    game_port: 2302
    query_port: 27016
  - name: Edit Me
    host: 203.0.113.20
    game_port: 2402
    query_port: 27017
""",
                encoding="utf-8",
            )

            with self.assertRaisesRegex(ValueError, "Another favourite server"):
                config.update_curated_server(
                    path,
                    Server(
                        name="Edit Me",
                        group="Community",
                        host="203.0.113.20",
                        game_port=2402,
                        query_port=27017,
                    ),
                    Server(
                        name="Duplicate",
                        group="Community",
                        host="203.0.113.10",
                        game_port=2302,
                        query_port=27016,
                    ),
                )

    def test_update_curated_server_reports_missing_entry(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "servers.yaml"
            path.write_text(
                """
servers:
  - name: Existing
    host: 203.0.113.10
    game_port: 2302
    query_port: 27016
""",
                encoding="utf-8",
            )

            updated = config.update_curated_server(
                path,
                Server(
                    name="Missing",
                    group="Community",
                    host="203.0.113.99",
                    game_port=2302,
                    query_port=27016,
                ),
                Server(
                    name="Still Missing",
                    group="Community",
                    host="203.0.113.99",
                    game_port=2303,
                    query_port=27017,
                ),
            )

            self.assertFalse(updated)


if __name__ == "__main__":
    unittest.main()
