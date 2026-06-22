from __future__ import annotations

from pathlib import Path

from .curated_status_cache import DATA_DIR, ensure_data_dir


LAST_LAUNCH_REPORT_PATH = DATA_DIR / "last_launch_report.txt"


def save_last_launch_report(report: str, path: Path = LAST_LAUNCH_REPORT_PATH) -> None:
    text = report.strip()
    if not text:
        return
    try:
        ensure_data_dir(path.parent)
        tmp = path.with_suffix(path.suffix + ".tmp")
        tmp.write_text(text + "\n", encoding="utf-8")
        tmp.replace(path)
    except OSError:
        pass


def load_last_launch_report(path: Path = LAST_LAUNCH_REPORT_PATH) -> str:
    try:
        if path.is_file():
            return path.read_text(encoding="utf-8").strip()
    except OSError:
        pass
    return ""
