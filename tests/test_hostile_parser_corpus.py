"""Deterministic, synthetic hostile inputs for persistence and provider parsers."""

import io
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from wolflauncher import config
from wolflauncher import server_cache
from wolflauncher.http_client import HttpClientError, fetch_json
from wolflauncher.server_discovery import (
    parse_battlemetrics_servers,
    parse_steam_web_api_servers,
    parse_wolfapi_servers,
)


class _Response:
    def __init__(self, payload: bytes):
        self._stream = io.BytesIO(payload)
        self.headers = {}

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def read(self, size=-1):
        return self._stream.read(size)


class HostileParserCorpusTests(unittest.TestCase):
    def test_synthetic_yaml_corpus_fails_with_controlled_errors(self):
        corpus = (
            "servers: [\n  - name: truncated",
            "- not-a-mapping",
            "servers: not-a-list",
            "servers:\n  - name: Missing endpoint fields",
        )
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "servers.yaml"
            for text in corpus:
                path.write_text(text, encoding="utf-8")
                with self.assertRaises(ValueError):
                    config.load_servers(path)

    def test_synthetic_import_corpus_fails_with_controlled_errors(self):
        corpus = {
            "truncated.json": '[{"host": "203.0.113.1"',
            "not-a-list.json": '{"host": "203.0.113.1"}',
            "truncated.yaml": "servers:\n  - host: 203.0.113.1\n    game_port: [",
            "bad-row.yaml": "servers:\n  - host: 203.0.113.1\n    game_port: no",
        }
        with tempfile.TemporaryDirectory() as directory:
            for filename, text in corpus.items():
                path = Path(directory) / filename
                path.write_text(text, encoding="utf-8")
                with self.assertRaises(ValueError):
                    server_cache.load_discovered_servers(path)

    @patch("wolflauncher.http_client.urllib.request.urlopen")
    def test_synthetic_raw_json_corpus_raises_controlled_errors(self, urlopen):
        for payload in (b'{"servers":', b'\xff\xfe', b'not-json'):
            urlopen.return_value = _Response(payload)
            with self.assertRaisesRegex(HttpClientError, "invalid JSON"):
                fetch_json("https://example.test/servers", retries=0)

    def test_synthetic_provider_corpus_retains_only_valid_rows(self):
        steam_rows = [
            None,
            [],
            {},
            {"addr": "203.0.113.1:27016", "gameport": 2302, "name": "Valid"},
        ]
        wolfapi_rows = [
            None,
            [],
            {"ip": "x", "port": 0},
            {"ip": "203.0.113.2", "port": 2302, "query_port": 27016, "name": "Valid"},
        ]
        battlemetrics_rows = [
            None,
            {},
            {"attributes": []},
            {
                "attributes": {
                    "ip": "203.0.113.3",
                    "port": 2302,
                    "portQuery": 27016,
                    "name": "Valid",
                }
            },
        ]

        self.assertEqual(len(parse_steam_web_api_servers({"response": {"servers": steam_rows}})), 1)
        self.assertEqual(len(parse_wolfapi_servers({"servers": wolfapi_rows})), 1)
        self.assertEqual(len(parse_battlemetrics_servers({"data": battlemetrics_rows})), 1)
