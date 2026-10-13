"""Bounded GitHub Releases discovery and release selection."""

from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Any, Callable, Iterable

from packaging.version import InvalidVersion, Version

MAX_RESPONSE_BYTES = 2 * 1024 * 1024


@dataclass(frozen=True)
class Release:
    version: Version
    tag: str
    notes: str
    prerelease: bool


@dataclass(frozen=True)
class ReleaseSourceError(RuntimeError):
    category: str
    message: str
    status: int | None = None

    def __str__(self) -> str:
        return self.message


def _repository_path(repository: str) -> str:
    value = repository.strip()
    parts = value.split("/")
    if len(parts) != 2 or any(not part or part in {".", ".."} for part in parts):
        raise ValueError("repository must use the owner/name form")
    safe = "/".join(urllib.parse.quote(part, safe="-._") for part in parts)
    if safe != value:
        raise ValueError("repository contains unsupported characters")
    return safe


def parse_release(payload: Any) -> Release | None:
    if not isinstance(payload, dict) or payload.get("draft") is True:
        return None
    tag = payload.get("tag_name")
    if not isinstance(tag, str) or not tag.strip():
        return None
    normalized = tag.strip()
    if normalized[:1].lower() == "v":
        normalized = normalized[1:]
    try:
        version = Version(normalized)
    except InvalidVersion:
        return None
    notes = payload.get("body")
    return Release(
        version=version,
        tag=tag.strip(),
        notes=notes if isinstance(notes, str) else "",
        prerelease=bool(payload.get("prerelease")) or version.is_prerelease,
    )


def select_release(
    payloads: Iterable[Any], *, current_version: str, channel: str
) -> Release | None:
    try:
        installed = Version(current_version)
    except InvalidVersion as exc:
        raise ValueError("current_version is not a valid version") from exc
    if channel not in {"stable", "experimental"}:
        raise ValueError("channel must be 'stable' or 'experimental'")
    candidates = []
    for payload in payloads:
        release = parse_release(payload)
        if release is None or release.version <= installed:
            continue
        if channel == "stable" and release.prerelease:
            continue
        candidates.append(release)
    return max(candidates, key=lambda item: item.version, default=None)


class GitHubReleaseSource:
    """Read releases from one configured GitHub repository."""

    def __init__(
        self,
        repository: str,
        *,
        timeout: float = 10.0,
        max_bytes: int = MAX_RESPONSE_BYTES,
        opener: Callable[..., Any] = urllib.request.urlopen,
        user_agent: str = "wolf-update/0.1",
    ) -> None:
        self.repository = _repository_path(repository)
        self.timeout = timeout
        self.max_bytes = max_bytes
        self._opener = opener
        self.user_agent = user_agent

    @property
    def api_url(self) -> str:
        return f"https://api.github.com/repos/{self.repository}/releases?per_page=100"

    def releases(self) -> list[Any]:
        request = urllib.request.Request(
            self.api_url,
            headers={
                "Accept": "application/vnd.github+json",
                "User-Agent": self.user_agent,
                "X-GitHub-Api-Version": "2022-11-28",
            },
        )
        try:
            with self._opener(request, timeout=self.timeout) as response:
                content_length = (
                    response.headers.get("Content-Length") if response.headers else None
                )
                if content_length and int(content_length) > self.max_bytes:
                    raise ReleaseSourceError("too_large", "GitHub response exceeded the size limit")
                raw = response.read(self.max_bytes + 1)
        except ReleaseSourceError:
            raise
        except urllib.error.HTTPError as exc:
            category = "rate_limit" if exc.code in {403, 429} else "http"
            raise ReleaseSourceError(
                category, f"GitHub returned HTTP {exc.code}", exc.code
            ) from exc
        except (urllib.error.URLError, TimeoutError) as exc:
            raise ReleaseSourceError("network", "The update check could not reach GitHub") from exc
        except (OSError, ValueError) as exc:
            raise ReleaseSourceError("network", "The update check failed") from exc
        if len(raw) > self.max_bytes:
            raise ReleaseSourceError("too_large", "GitHub response exceeded the size limit")
        try:
            payload = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ReleaseSourceError(
                "invalid_response", "GitHub returned invalid release data"
            ) from exc
        if not isinstance(payload, list):
            raise ReleaseSourceError("invalid_response", "GitHub returned invalid release data")
        return payload
