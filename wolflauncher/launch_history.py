from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from .curated_status_cache import DATA_DIR, ensure_data_dir
from .persistence import atomic_write_text
from .server_identity import identity_key, saved_server_fields

LAST_LAUNCH_REPORT_PATH = DATA_DIR / "last_launch_report.txt"
RECENT_LAUNCHES_PATH = DATA_DIR / "recent_launches.json"


def save_last_launch_report(report: str, path: Path = LAST_LAUNCH_REPORT_PATH) -> bool:
    text = report.strip()
    if not text:
        return False
    ensure_data_dir(path.parent)
    atomic_write_text(path, text + "\n")
    return True


def load_last_launch_report(path: Path = LAST_LAUNCH_REPORT_PATH) -> str:
    try:
        if path.is_file():
            return path.read_text(encoding="utf-8").strip()
    except OSError:
        pass
    return ""


def record_launch(server, path: Path = RECENT_LAUNCHES_PATH) -> None:
    """Keep a bounded local launch history for recent-server shortcuts."""
    rows = load_recent_launches(path, limit=20, strict=True)
    key = identity_key(server)
    previous = next((row for row in rows if row.get("key") == key), {})
    rows = [row for row in rows if row.get("key") != key]
    rows.insert(
        0,
        {
            **previous,
            **saved_server_fields(server),
            "key": key,
            "name": server.name,
            "group": server.group,
            "host": server.host,
            "game_port": server.game_port,
            "query_port": server.query_port,
            "launched_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        },
    )
    ensure_data_dir(path.parent)
    atomic_write_text(path, json.dumps(rows[:20], indent=2) + "\n", backup=True)


def load_recent_launches(
    path: Path = RECENT_LAUNCHES_PATH, *, limit: int = 3, strict: bool = False
) -> list[dict]:
    import logging
    from types import SimpleNamespace

    try:
        rows = json.loads(path.read_text(encoding="utf-8")) if path.is_file() else []
        if not isinstance(rows, list):
            raise ValueError("Recent history must contain a list.")
    except (OSError, ValueError) as exc:
        if strict:
            raise ValueError(f"Could not read recent history {path}: {exc}") from exc
        logging.getLogger(__name__).warning("Could not read recent history %s: %s", path, exc)
        return []
    result, seen = [], set()
    for row in rows:
        try:
            if not isinstance(row, dict):
                raise ValueError("entry is not a mapping")
            normalized = {**row, **saved_server_fields(row)}
            for port in ("game_port", "query_port"):
                normalized[port] = int(row[port])
                if not 0 < normalized[port] <= 65535:
                    raise ValueError("invalid port")
            if not isinstance(row.get("host"), str) or not row["host"].strip():
                raise ValueError("missing host")
            normalized["key"] = identity_key(SimpleNamespace(**normalized))
        except (KeyError, TypeError, ValueError) as exc:
            logging.getLogger(__name__).warning("Invalid recent history entry in %s: %s", path, exc)
            if strict:
                # Do not rewrite partially corrupt authoritative data.
                raise ValueError(f"Invalid recent history entry in {path}") from exc
            continue
        if normalized["key"] not in seen:
            seen.add(normalized["key"])
            result.append(normalized)
    return result[:limit]
