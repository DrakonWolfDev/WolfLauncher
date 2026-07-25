"""Small, local-only retention policy for disposable support data."""

from __future__ import annotations

import time
from dataclasses import dataclass
from pathlib import Path

from .paths import user_data_dir

CACHE_RETENTION_DAYS = 30
SUPPORT_RETENTION_DAYS = 90
THUMBNAIL_CACHE_DIRECTORY = "thumbnails"


@dataclass(frozen=True)
class RetentionResult:
    removed_cache_files: int = 0
    removed_support_files: int = 0
    removed_thumbnail_files: int = 0


def run_local_retention(data_dir: Path | None = None, *, now: float | None = None) -> RetentionResult:
    """Remove only stale disposable data; settings and curated YAML are never touched."""
    directory = data_dir or user_data_dir()
    current_time = time.time() if now is None else now
    cache_cutoff = current_time - CACHE_RETENTION_DAYS * 24 * 60 * 60
    support_cutoff = current_time - SUPPORT_RETENTION_DAYS * 24 * 60 * 60

    cache_paths = (
        directory / "server_cache.sqlite3",
        directory / "server_cache.sqlite3-wal",
        directory / "server_cache.sqlite3-shm",
        directory / "curated_status.json",
    )
    support_paths = (
        directory / "wolflauncher.log",
        directory / "wolflauncher.log.1",
        directory / "wolflauncher.log.2",
        directory / "wolflauncher.log.3",
        directory / "last_launch_report.txt",
    )

    removed_cache = sum(_remove_if_stale(path, cache_cutoff) for path in cache_paths)
    removed_support = sum(_remove_if_stale(path, support_cutoff) for path in support_paths)
    thumbnail_directory = directory / THUMBNAIL_CACHE_DIRECTORY
    removed_thumbnails = 0
    if thumbnail_directory.is_dir():
        for path in thumbnail_directory.rglob("*"):
            if path.is_file():
                removed_thumbnails += _remove_if_stale(path, cache_cutoff)
    return RetentionResult(removed_cache, removed_support, removed_thumbnails)


def _remove_if_stale(path: Path, cutoff: float) -> int:
    try:
        if path.is_file() and path.stat().st_mtime < cutoff:
            path.unlink()
            return 1
    except OSError:
        pass
    return 0
