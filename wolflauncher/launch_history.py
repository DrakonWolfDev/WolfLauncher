from __future__ import annotations

from pathlib import Path

from .curated_status_cache import DATA_DIR, ensure_data_dir
from .persistence import atomic_write_text

LAST_LAUNCH_REPORT_PATH = DATA_DIR / "last_launch_report.txt"


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
