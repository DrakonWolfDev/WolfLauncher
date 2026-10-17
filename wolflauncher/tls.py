"""Verified HTTPS contexts without modifying the user's certificate stores."""

from __future__ import annotations

import ssl
import sys
from functools import lru_cache


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
    context.verify_mode = ssl.CERT_REQUIRED
    context.check_hostname = True
    context.minimum_version = ssl.TLSVersion.TLSv1_2
    context.set_alpn_protocols(["http/1.1"])
    return context
