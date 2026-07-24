from __future__ import annotations

import io
import unittest
import urllib.error
from unittest.mock import patch

from wolflauncher.http_client import HttpClientError, fetch_json, post_form_json, user_agent


class _Response:
    def __init__(self, payload: bytes, content_type: str = ""):
        self._stream = io.BytesIO(payload)
        self.headers = {"Content-Type": content_type} if content_type else {}

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def read(self, size=-1):
        return self._stream.read(size)


class HttpClientTests(unittest.TestCase):
    @patch("wolflauncher.http_client.urllib.request.urlopen")
    def test_fetch_json_uses_versioned_agent_and_bounded_read(self, urlopen):
        urlopen.return_value = _Response(b'{"ready": true}')

        self.assertEqual(fetch_json("https://example.test/status", retries=0), {"ready": True})
        request = urlopen.call_args.args[0]
        self.assertEqual(request.headers["User-agent"], user_agent())
        self.assertEqual(request.headers["Accept"], "application/json")

    @patch("wolflauncher.http_client.urllib.request.urlopen")
    def test_rejects_oversize_response(self, urlopen):
        urlopen.return_value = _Response(b"x" * 11)

        with self.assertRaisesRegex(HttpClientError, "size limit"):
            fetch_json("https://example.test/status", max_bytes=10, retries=0)

    @patch("wolflauncher.http_client.urllib.request.urlopen")
    def test_retries_transient_get_failure_once(self, urlopen):
        urlopen.side_effect = [urllib.error.URLError("offline"), _Response(b"[]")]

        with patch("wolflauncher.http_client.time.sleep"):
            self.assertEqual(fetch_json("https://example.test/status"), [])
        self.assertEqual(urlopen.call_count, 2)

    def test_honours_cancellation_before_request(self):
        with self.assertRaisesRegex(HttpClientError, "cancelled"):
            fetch_json("https://example.test/status", cancel=lambda: True)

    @patch("wolflauncher.http_client.urllib.request.urlopen")
    def test_post_form_is_not_retried(self, urlopen):
        urlopen.side_effect = urllib.error.URLError("offline")

        with self.assertRaises(HttpClientError):
            post_form_json("https://example.test/form", [("key", "value")])
        self.assertEqual(urlopen.call_count, 1)
