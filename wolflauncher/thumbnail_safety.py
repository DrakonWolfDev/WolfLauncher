"""Validation policy for remotely hosted Workshop preview images."""

from __future__ import annotations

from urllib.parse import urlparse, urlunparse

MAX_THUMBNAIL_BYTES = 2 * 1024 * 1024
MAX_THUMBNAIL_DIMENSION = 2048
THUMBNAIL_REQUEST_TIMEOUT_MS = 10_000
STEAM_ASSET_HOST_SUFFIXES = ("steamusercontent.com", "steamstatic.com")
STEAM_ASSET_HOSTS = {
    "steamcommunity-a.akamaihd.net",
    "steamuserimages-a.akamaihd.net",
}
RASTER_THUMBNAIL_CONTENT_TYPES = {"image/jpeg", "image/png", "image/webp"}


def is_safe_thumbnail_url(value: str) -> bool:
    parsed = urlparse(normalize_thumbnail_url(value))
    return parsed.scheme == "https" and bool(parsed.netloc)


def normalize_thumbnail_url(value: str) -> str:
    """Upgrade public Steam CDN previews without allowing arbitrary HTTP URLs."""
    parsed = urlparse(str(value).strip())
    host = (parsed.hostname or "").lower()
    is_steam_asset = host in STEAM_ASSET_HOSTS or any(
        host == suffix or host.endswith(f".{suffix}") for suffix in STEAM_ASSET_HOST_SUFFIXES
    )
    if parsed.scheme == "http" and is_steam_asset:
        return urlunparse(parsed._replace(scheme="https"))
    return parsed.geturl()


def is_safe_thumbnail_content_type(value: str) -> bool:
    return str(value).split(";", 1)[0].strip().lower() in RASTER_THUMBNAIL_CONTENT_TYPES


def is_safe_thumbnail_dimensions(width: int, height: int) -> bool:
    return 0 < width <= MAX_THUMBNAIL_DIMENSION and 0 < height <= MAX_THUMBNAIL_DIMENSION
