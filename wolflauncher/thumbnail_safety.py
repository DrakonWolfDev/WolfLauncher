"""Validation policy for remotely hosted Workshop preview images."""

from __future__ import annotations

from urllib.parse import urlparse

MAX_THUMBNAIL_BYTES = 2 * 1024 * 1024
MAX_THUMBNAIL_DIMENSION = 2048


def is_safe_thumbnail_url(value: str) -> bool:
    parsed = urlparse(str(value).strip())
    return parsed.scheme == "https" and bool(parsed.netloc)


def is_safe_thumbnail_content_type(value: str) -> bool:
    return str(value).split(";", 1)[0].strip().lower().startswith("image/")


def is_safe_thumbnail_dimensions(width: int, height: int) -> bool:
    return 0 < width <= MAX_THUMBNAIL_DIMENSION and 0 < height <= MAX_THUMBNAIL_DIMENSION
