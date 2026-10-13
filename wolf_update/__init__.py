"""Notification-only application update discovery."""

from .core import (
    CheckResult,
    CheckStatus,
    UpdateApplication,
    UpdateService,
    validate_destination,
)
from .github import GitHubReleaseSource, Release, ReleaseSourceError, select_release
from .state import JsonFileStateStore, MemoryStateStore, UpdateState

__all__ = [
    "CheckResult",
    "CheckStatus",
    "GitHubReleaseSource",
    "JsonFileStateStore",
    "MemoryStateStore",
    "Release",
    "ReleaseSourceError",
    "UpdateApplication",
    "UpdateService",
    "UpdateState",
    "select_release",
    "validate_destination",
]

__version__ = "0.1.0"
