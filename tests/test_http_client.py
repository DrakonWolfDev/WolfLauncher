from __future__ import annotations

import io
import ssl
import unittest
import urllib.error
from unittest.mock import patch

from wolflauncher.http_client import (
    HttpClientError,
    fetch_html,
    fetch_json,
    post_form_json,
    post_json,
    user_agent,
)
from wolflauncher.tls import https_context


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

    @patch("wolflauncher.http_client.urllib.request.urlopen")
    def test_all_provider_request_types_use_verified_context(self, urlopen):
        for call in (
            lambda: fetch_json("https://example.test/status"),
            lambda: fetch_html("https://example.test/page"),
            lambda: post_json("https://example.test/json", {}),
            lambda: post_form_json("https://example.test/form", [("key", "value")]),
        ):
            with self.subTest(call=call):
                urlopen.return_value = _Response(b"{}")
                call()
                self.assertIs(urlopen.call_args.kwargs["context"], https_context())

    @patch("wolflauncher.http_client.urllib.request.urlopen")
    def test_certificate_failure_never_retries_without_verification(self, urlopen):
        urlopen.side_effect = urllib.error.URLError(
            ssl.SSLCertVerificationError("certificate has expired")
        )
        with patch("wolflauncher.http_client.time.sleep"):
            with self.assertRaisesRegex(HttpClientError, "certificate has expired"):
                fetch_json("https://example.test/status")
        for call in urlopen.call_args_list:
            context = call.kwargs["context"]
            self.assertEqual(context.verify_mode, ssl.CERT_REQUIRED)
            self.assertTrue(context.check_hostname)


class CompressedJsonTests(unittest.TestCase):
    def response(self, body, encoding="gzip"):
        response = _Response(body)
        response.headers["Content-Encoding"] = encoding
        return response

    @patch("wolflauncher.http_client.urllib.request.urlopen")
    def test_gzip_json_is_negotiated_and_decoded_with_existing_size_limits(self, urlopen):
        import gzip

        urlopen.return_value = self.response(gzip.compress(b'{"ready":true}'))
        self.assertEqual(fetch_json("https://example.test", retries=0), {"ready": True})
        self.assertEqual(urlopen.call_args.args[0].headers["Accept-encoding"], "gzip")

    @patch("wolflauncher.http_client.urllib.request.urlopen")
    def test_compressed_bomb_is_rejected_before_unbounded_allocation(self, urlopen):
        import gzip

        urlopen.return_value = self.response(gzip.compress(b" " * 1_000_000))
        with self.assertRaises(HttpClientError) as caught:
            fetch_json("https://example.test", max_bytes=4096, retries=0)
        self.assertEqual(caught.exception.category, "too_large")

    @patch("wolflauncher.http_client.urllib.request.urlopen")
    def test_invalid_truncated_trailing_and_unsupported_encoding_are_rejected(self, urlopen):
        import gzip

        body = gzip.compress(b"[]")
        for payload, encoding in (
            (b"bad", "gzip"),
            (body[:-1], "gzip"),
            (body + b"extra", "gzip"),
            (body + body, "gzip"),
            (b"[]", "br"),
        ):
            with self.subTest(payload=payload, encoding=encoding):
                urlopen.return_value = self.response(payload, encoding)
                with self.assertRaises(HttpClientError) as caught:
                    fetch_json("https://example.test", retries=0)
                self.assertEqual(caught.exception.category, "content_encoding")

    @patch("wolflauncher.http_client.urllib.request.urlopen")
    def test_exact_decoded_limit_and_cancellation_after_read(self, urlopen):
        import gzip
        from unittest.mock import Mock

        payload = b'"' + b"a" * 1022 + b'"'
        urlopen.return_value = self.response(gzip.compress(payload))
        self.assertEqual(len(fetch_json("https://example.test", max_bytes=1024, retries=0)), 1022)
        urlopen.return_value = self.response(gzip.compress(payload))
        with self.assertRaises(HttpClientError) as caught:
            fetch_json(
                "https://example.test",
                max_bytes=1024,
                retries=0,
                cancel=Mock(side_effect=[False, False, True]),
            )
        self.assertEqual(caught.exception.category, "cancelled")
