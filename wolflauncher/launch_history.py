from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from .curated_status_cache import DATA_DIR, ensure_data_dir
from .persistence import atomic_write_text

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
    rows = load_recent_launches(path, limit=20)
    key = f"{server.host}:{server.game_port}:{server.query_port}"
    rows = [row for row in rows if row.get("key") != key]
    rows.insert(
        0,
        {
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
    atomic_write_text(path, json.dumps(rows[:20], indent=2) + "\n")


def load_recent_launches(path: Path = RECENT_LAUNCHES_PATH, *, limit: int = 3) -> list[dict]:
    try:
        rows = json.loads(path.read_text(encoding="utf-8")) if path.is_file() else []
    except (OSError, ValueError):
        return []
    return [row for row in rows if isinstance(row, dict)][:limit]
