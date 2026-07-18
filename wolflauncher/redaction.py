from __future__ import annotations

import os
import re
from collections.abc import Iterable
from pathlib import Path

_KEY_VALUE_PATTERN = re.compile(
    r"(?i)(?P<label>(?:steam[_ -]?web[_ -]?api[_ -]?key|api[_ -]?key|token|secret)\s*[:=]\s*)(?P<value>[^\s&]+)"
)
_QUERY_KEY_PATTERN = re.compile(r"(?i)(?P<label>[?&](?:key|token)=)[^&\s]+")
_STEAM_USERDATA_PATTERN = re.compile(r"(?i)(/userdata/)(\d+)")


def redact_support_text(text: str, secrets: Iterable[str] = ()) -> str:
    """Remove credentials and local identity from copyable support text."""
    redacted = str(text)
    candidates = {
        str(value).strip()
        for value in secrets
        if value is not None and len(str(value).strip()) >= 4
    }
    for name, value in os.environ.items():
        upper = name.upper()
        if ("API_KEY" in upper or "TOKEN" in upper or "SECRET" in upper) and value:
            candidates.add(value)
    for secret in sorted(candidates, key=len, reverse=True):
        redacted = redacted.replace(secret, "<redacted>")

    redacted = _KEY_VALUE_PATTERN.sub(r"\g<label><redacted>", redacted)
    redacted = _QUERY_KEY_PATTERN.sub(r"\g<label><redacted>", redacted)
    redacted = _STEAM_USERDATA_PATTERN.sub(r"\1<steam-account>", redacted)
    home = str(Path.home())
    if home and home != "/":
        redacted = redacted.replace(home, "~")
    return redacted
