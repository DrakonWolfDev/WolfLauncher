"""Application-neutral update policy and orchestration."""

from __future__ import annotations

import re
import webbrowser
from dataclasses import dataclass, replace
from datetime import datetime, timedelta, timezone
from enum import Enum
from html.parser import HTMLParser
from typing import Callable
from urllib.parse import urlsplit, urlunsplit

from packaging.version import Version

from .github import GitHubReleaseSource, Release, ReleaseSourceError, select_release
from .state import StateStore, UpdateState

CHECK_INTERVAL = timedelta(hours=24)


class CheckStatus(str, Enum):
    AVAILABLE = "available"
    UP_TO_DATE = "up_to_date"
    DISMISSED = "dismissed"
    THROTTLED = "throttled"
    FAILED = "failed"


@dataclass(frozen=True)
class UpdateApplication:
    current_version: str
    repository: str
    update_url: str
    channel: str = "stable"

    def __post_init__(self) -> None:
        Version(self.current_version)
        if self.channel not in {"stable", "experimental"}:
            raise ValueError("channel must be 'stable' or 'experimental'")
        object.__setattr__(self, "update_url", validate_destination(self.update_url))


@dataclass(frozen=True)
class CheckResult:
    status: CheckStatus
    release: Release | None = None
    message: str = ""


def validate_destination(value: str) -> str:
    if not isinstance(value, str) or not value or any(ord(char) < 32 for char in value):
        raise ValueError("update destination must be a valid HTTPS URL")
    parsed = urlsplit(value)
    if parsed.scheme.lower() != "https" or not parsed.netloc or parsed.hostname is None:
        raise ValueError("update destination must be an absolute HTTPS URL")
    if parsed.username is not None or parsed.password is not None:
        raise ValueError("update destination must not contain credentials")
    if parsed.fragment:
        raise ValueError("update destination must not contain a fragment")
    try:
        hostname = parsed.hostname.encode("idna").decode("ascii")
        port = parsed.port
    except (UnicodeError, ValueError) as exc:
        raise ValueError("update destination has an invalid host or port") from exc
    if not hostname or "." not in hostname or hostname.startswith(".") or hostname.endswith("."):
        raise ValueError("update destination must use a fully qualified host")
    if not re.fullmatch(r"[a-zA-Z0-9.-]+", hostname):
        raise ValueError("update destination has an invalid host")
    netloc = hostname if port is None else f"{hostname}:{port}"
    return urlunsplit(("https", netloc, parsed.path or "/", parsed.query, ""))


class _TextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []

    def handle_data(self, data: str) -> None:
        self.parts.append(data)


def safe_release_notes(value: str, *, max_chars: int = 12_000) -> str:
    """Turn untrusted GitHub Markdown/HTML into inert readable plain text."""
    text = re.sub(r"!\[([^]]*)\]\([^)]*\)", r"\1", value)
    text = re.sub(r"\[([^]]+)\]\([^)]*\)", r"\1", text)
    text = re.sub(r"(?m)^\s{0,3}#{1,6}\s*", "", text)
    text = re.sub(r"[*_`~]", "", text)
    parser = _TextExtractor()
    parser.feed(text)
    plain = "".join(parser.parts)
    plain = re.sub(r"[ \t]+", " ", plain)
    plain = re.sub(r"\n{3,}", "\n\n", plain).strip()
    if len(plain) > max_chars:
        return plain[: max_chars - 1].rstrip() + "…"
    return plain


class UpdateService:
    def __init__(
        self,
        application: UpdateApplication,
        store: StateStore,
        *,
        source: GitHubReleaseSource | None = None,
        clock: Callable[[], datetime] | None = None,
        browser_open: Callable[[str], bool] = webbrowser.open,
    ) -> None:
        self.application = application
        self.store = store
        self.source = source or GitHubReleaseSource(application.repository)
        self.clock = clock or (lambda: datetime.now(timezone.utc))
        self.browser_open = browser_open

    def check(self, *, manual: bool = False) -> CheckResult:
        now = self.clock()
        state = self.store.load()
        if not manual and _is_throttled(state, now):
            return CheckResult(CheckStatus.THROTTLED)
        try:
            release = select_release(
                self.source.releases(),
                current_version=self.application.current_version,
                channel=self.application.channel,
            )
        except (ReleaseSourceError, OSError, ValueError) as exc:
            return CheckResult(CheckStatus.FAILED, message=str(exc))
        state = replace(state, last_successful_check=now.astimezone(timezone.utc).isoformat())
        self.store.save(state)
        if release is None:
            return CheckResult(CheckStatus.UP_TO_DATE)
        release = replace(release, notes=safe_release_notes(release.notes))
        if not manual and state.dismissed_version == str(release.version):
            return CheckResult(CheckStatus.DISMISSED, release=release)
        return CheckResult(CheckStatus.AVAILABLE, release=release)

    def dismiss(self, release: Release) -> None:
        self.store.save(replace(self.store.load(), dismissed_version=str(release.version)))

    def view_update(self) -> bool:
        return bool(self.browser_open(self.application.update_url))


def _is_throttled(state: UpdateState, now: datetime) -> bool:
    if not state.last_successful_check:
        return False
    try:
        checked = datetime.fromisoformat(state.last_successful_check)
        if checked.tzinfo is None:
            checked = checked.replace(tzinfo=timezone.utc)
    except ValueError:
        return False
    elapsed = now.astimezone(timezone.utc) - checked.astimezone(timezone.utc)
    return timedelta(0) <= elapsed < CHECK_INTERVAL
