"""Deterministic, synthetic hostile inputs for persistence and provider parsers."""

import tempfile
import unittest
from pathlib import Path

from wolflauncher import config
from wolflauncher.server_discovery import (
    parse_battlemetrics_servers,
    parse_steam_web_api_servers,
    parse_wolfapi_servers,
)


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

    def test_synthetic_provider_json_corpus_never_creates_invalid_servers(self):
        self.assertEqual(parse_steam_web_api_servers({"response": {"servers": [None, [], {}]}}), [])
        self.assertEqual(parse_wolfapi_servers({"servers": [None, [], {"ip": "x", "port": 0}]}), [])
        self.assertEqual(parse_battlemetrics_servers({"data": [None, {}, {"attributes": []}]}), [])
