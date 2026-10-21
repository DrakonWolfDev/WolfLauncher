"""Verified HTTPS contexts without modifying the user's certificate stores."""

from __future__ import annotations

import os
import ssl
import sys
from functools import lru_cache
from pathlib import Path

LINUX_CA_BUNDLES = (
    "/etc/pki/tls/certs/ca-bundle.crt",
    "/etc/pki/ca-trust/extracted/pem/tls-ca-bundle.pem",
    "/etc/ssl/certs/ca-certificates.crt",
    "/etc/ssl/ca-bundle.pem",
)


def _load_linux_system_cas(context: ssl.SSLContext) -> None:
    # Packaged OpenSSL builds may have defaults for a different distribution.
    # Respect deliberate trust overrides rather than broadening their CA set.
    defaults = ssl.get_default_verify_paths()
    if any(key in os.environ for key in (defaults.openssl_cafile_env, defaults.openssl_capath_env)):
        return
    for filename in LINUX_CA_BUNDLES:
        if not Path(filename).is_file():
            continue
        try:
            context.load_verify_locations(cafile=filename)
        except (OSError, ssl.SSLError):
            continue
        return


def verification_backend() -> str:
    return "Windows CryptoAPI (truststore)" if sys.platform == "win32" else "OpenSSL system trust"


@lru_cache(maxsize=1)
def https_context() -> ssl.SSLContext:
    """Use Windows chain building instead of trusting stale cached intermediates.

    Python's default Windows context imports the CA store into OpenSSL, which
    can prefer an expired cross-sign over the valid chain sent by the server.
    Native verification builds a valid system-trusted chain when one exists.
    There is no unverified fallback and no global SSL monkey-patching.
    """
    if sys.platform == "win32":
        import truststore

        context = truststore.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    else:
        context = ssl.create_default_context()
        if sys.platform.startswith("linux"):
            _load_linux_system_cas(context)
    context.verify_mode = ssl.CERT_REQUIRED
    context.check_hostname = True
    context.minimum_version = ssl.TLSVersion.TLSv1_2
    context.set_alpn_protocols(["http/1.1"])
    return context
