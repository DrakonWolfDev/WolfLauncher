"""Minimal persistent state for update checks."""

from __future__ import annotations

import json
import os
import tempfile
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Protocol


@dataclass(frozen=True)
class UpdateState:
    last_successful_check: str | None = None
    dismissed_version: str | None = None


class StateStore(Protocol):
    def load(self) -> UpdateState: ...

    def save(self, state: UpdateState) -> None: ...


class MemoryStateStore:
    def __init__(self, state: UpdateState | None = None) -> None:
        self.state = state or UpdateState()

    def load(self) -> UpdateState:
        return self.state

    def save(self, state: UpdateState) -> None:
        self.state = state


class JsonFileStateStore:
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)

    def load(self) -> UpdateState:
        try:
            payload = json.loads(self.path.read_text(encoding="utf-8"))
            if not isinstance(payload, dict):
                return UpdateState()
            return UpdateState(
                last_successful_check=_optional_string(payload.get("last_successful_check")),
                dismissed_version=_optional_string(payload.get("dismissed_version")),
            )
        except (OSError, UnicodeDecodeError, json.JSONDecodeError, TypeError):
            return UpdateState()

    def save(self, state: UpdateState) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        descriptor, temporary = tempfile.mkstemp(prefix=self.path.name, dir=self.path.parent)
        try:
            with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
                json.dump(asdict(state), handle, indent=2, sort_keys=True)
                handle.write("\n")
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, self.path)
        except BaseException:
            try:
                os.unlink(temporary)
            except OSError:
                pass
            raise


def _optional_string(value: object) -> str | None:
    return value if isinstance(value, str) and value else None
