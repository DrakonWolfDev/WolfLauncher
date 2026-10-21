from __future__ import annotations

import socket
import ssl
import sys
import threading
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from wolflauncher.tls import _load_linux_system_cas, https_context

FIXTURES = Path(__file__).parent / "fixtures" / "tls"


class TLSVerificationTests(unittest.TestCase):
    def test_discovered_system_bundle_validates_real_chain(self):
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        with patch.dict("os.environ", {}, clear=True), patch(
            "wolflauncher.tls.LINUX_CA_BUNDLES", (str(FIXTURES / "root.pem"),)
        ):
            _load_linux_system_cas(context)
        self.handshake(context)
        with self.assertRaises(ssl.SSLCertVerificationError):
            self.handshake(context, hostname="wrong.invalid")
        with self.assertRaises(ssl.SSLCertVerificationError):
            self.handshake(context, expired=True)

    def test_fedora_and_mint_bundle_discovery_skips_unusable_files(self):
        for bundle in (
            "/etc/pki/tls/certs/ca-bundle.crt",
            "/etc/ssl/certs/ca-certificates.crt",
        ):
            context = Mock()
            context.load_verify_locations.side_effect = [ssl.SSLError("invalid"), None]
            with patch.dict("os.environ", {}, clear=True), patch(
                "wolflauncher.tls.LINUX_CA_BUNDLES", ("/missing", "/invalid", bundle)
            ), patch.object(Path, "is_file", side_effect=[False, True, True]):
                _load_linux_system_cas(context)
            self.assertEqual(context.load_verify_locations.call_count, 2)
            context.load_verify_locations.assert_called_with(cafile=bundle)

    def test_explicit_trust_overrides_are_preserved(self):
        for key in ("SSL_CERT_FILE", "SSL_CERT_DIR"):
            context = Mock()
            with patch.dict("os.environ", {key: "/custom"}, clear=True):
                _load_linux_system_cas(context)
            context.load_verify_locations.assert_not_called()

    def handshake(self, context, *, hostname="localhost", expired=False):
        server_context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        server_context.load_cert_chain(
            FIXTURES / ("expired-server.pem" if expired else "server.pem"),
            FIXTURES / "server-key.pem",
        )
        client, server = socket.socketpair()
        client.settimeout(5)
        server.settimeout(5)
        errors = []

        def serve():
            try:
                with server, server_context.wrap_socket(server, server_side=True):
                    pass
            except (ssl.SSLError, ConnectionResetError, ConnectionAbortedError):
                pass  # Expected when the client rejects this certificate.
            except Exception as error:
                errors.append(error)

        worker = threading.Thread(target=serve, daemon=True)
        worker.start()
        try:
            with client, context.wrap_socket(client, server_hostname=hostname):
                pass
        finally:
            client.close()
            worker.join(timeout=6)
            self.assertFalse(worker.is_alive(), "TLS server did not terminate")
            self.assertEqual(errors, [])

    def context(self, *, trusted=True, stale=False):
        # Never mutate the shared application context or the system stores.
        context = https_context.__wrapped__()
        if trusted:
            context.load_verify_locations(cafile=str(FIXTURES / "root.pem"))
        if stale:
            context.load_verify_locations(cafile=str(FIXTURES / "expired-intermediate.pem"))
        return context

    def test_valid_chain_succeeds(self):
        self.handshake(self.context())

    def test_expired_server_is_rejected(self):
        with self.assertRaises(ssl.SSLCertVerificationError):
            self.handshake(self.context(), expired=True)

    def test_wrong_hostname_is_rejected(self):
        with self.assertRaises(ssl.SSLCertVerificationError):
            self.handshake(self.context(), hostname="wrong.invalid")

    def test_untrusted_server_is_rejected(self):
        with self.assertRaises(ssl.SSLCertVerificationError):
            self.handshake(self.context(trusted=False))

    def test_context_requires_certificate_hostname_and_tls12(self):
        context = self.context()
        self.assertEqual(context.verify_mode, ssl.CERT_REQUIRED)
        self.assertTrue(context.check_hostname)
        self.assertGreaterEqual(context.minimum_version, ssl.TLSVersion.TLSv1_2)

    @unittest.skipUnless(sys.platform == "win32", "Windows native chain builder regression")
    def test_expired_cached_intermediate_does_not_shadow_valid_chain(self):
        legacy = ssl.create_default_context()
        legacy.load_verify_locations(cafile=str(FIXTURES / "root.pem"))
        self.handshake(legacy)
        legacy.load_verify_locations(cafile=str(FIXTURES / "expired-intermediate.pem"))
        with self.assertRaisesRegex(ssl.SSLCertVerificationError, "certificate has expired"):
            self.handshake(legacy)
        self.handshake(self.context(stale=True))
