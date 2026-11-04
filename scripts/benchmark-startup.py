"""Measure fresh-process source startup with a seeded cache, isolated from user data."""

import argparse
import json
import os
import shutil
import statistics
import subprocess
import sys
import tempfile
import time
from pathlib import Path

SCRIPT_STARTED = time.perf_counter()
ROOT = Path(__file__).resolve().parents[1]


def isolated_paths():
    root = Path(os.environ.get("WOLFLAUNCHER_SMOKE_ROOT", "/")).resolve()
    temporary = Path(tempfile.gettempdir()).resolve()
    if root == temporary or not root.is_relative_to(temporary):
        raise ValueError("Use the isolated parent runner")
    for key, suffix in (("XDG_CONFIG_HOME", "config"), ("XDG_DATA_HOME", "data")):
        if Path(os.environ.get(key, "/")).resolve() != root / suffix:
            raise ValueError("Use the isolated parent runner")
    sys.path.insert(0, str(ROOT))
    return root


def prepare():
    root = isolated_paths()
    from wolflauncher import server_cache
    from wolflauncher.models import DiscoveredServer

    (root / "config/wolflauncher").mkdir(parents=True, exist_ok=True)
    (root / "config/wolflauncher/servers.yaml").write_text("servers: []\n")
    (root / "config/wolflauncher/settings.json").write_text(
        json.dumps({"schema_version": 10, "discovery_auto_refresh": False, "refresh_seconds": 0})
    )
    connection, recovered = server_cache.connect_recovering()
    try:
        if recovered is not None:
            raise AssertionError("Unexpected cache recovery")
        server_cache.upsert_servers(
            connection,
            [
                DiscoveredServer(
                    f"Startup Stable {i:04}",
                    f"127.1.{i // 250}.{i % 250 + 1}",
                    2302,
                    2303,
                    product="stable",
                    source="wolfapi",
                )
                for i in range(1000)
            ],
        )
    finally:
        connection.close()


def measured_child():
    isolated_paths()
    from PySide6.QtCore import QEvent, QObject, QTimer

    from wolflauncher import app as application
    from wolflauncher.browser_snapshot import BrowserSnapshotWorker

    metrics = {"imports_ms": (time.perf_counter() - SCRIPT_STARTED) * 1000}
    worker_times = []
    original_run = BrowserSnapshotWorker.run

    def timed_run(worker):
        started = time.perf_counter()
        original_run(worker)
        worker_times.append((time.perf_counter() - started) * 1000)

    BrowserSnapshotWorker.run = timed_run
    original_window = application.MainWindow

    class PaintObserver(QObject):
        def eventFilter(self, obj, event):
            if event.type() == QEvent.Paint and metrics.get("rows_applied") == 200:
                QTimer.singleShot(0, self.parent().finish_measurement)
            return False

    class MeasuredWindow(original_window):
        def __init__(self):
            started = time.perf_counter()
            super().__init__()
            metrics["construction_ms"] = (time.perf_counter() - started) * 1000
            # Controlled cached-browser scenario: suppress optional public work,
            # exactly as in the isolated resource soak; never launches a game.
            self._game_session_active = True
            self.timer.stop()
            self.observer = PaintObserver(self)
            self.browser_table.viewport().installEventFilter(self.observer)
            self.tabs.setCurrentIndex(self.server_browser_tab_index)
            self.finished_measurement = False
            QTimer.singleShot(15000, lambda: application.QApplication.instance().exit(124))

        def paintEvent(self, event):
            super().paintEvent(event)
            metrics.setdefault(
                "first_window_paint_ms", (time.perf_counter() - SCRIPT_STARTED) * 1000
            )

        def apply_browser_snapshot(self, snapshot):
            super().apply_browser_snapshot(snapshot)
            metrics["rows_applied"] = self.browser_table.rowCount()
            metrics["snapshot_applied_ms"] = (time.perf_counter() - SCRIPT_STARTED) * 1000

        def finish_measurement(self):
            if self.finished_measurement:
                return
            self.finished_measurement = True
            if metrics.get("rows_applied") != 200:
                raise AssertionError("Cached browser rows were not applied")
            metrics["browser_painted_ms"] = (time.perf_counter() - SCRIPT_STARTED) * 1000
            metrics["snapshot_worker_ms"] = worker_times
            print(json.dumps({"startup": "passed", **metrics}), flush=True)
            self.close()

    application.MainWindow = MeasuredWindow
    # Exercise the real entry point, including single-instance setup, retention,
    # logging, QApplication/theme creation and coordinated shutdown.
    sys.argv = [sys.argv[0]]
    application.main()


def suite(repeats):
    root = isolated_paths()
    subprocess.run([sys.executable, __file__, "--prepare"], check=True, timeout=15)
    records = []
    for index in range(repeats):
        started = time.perf_counter()
        result = subprocess.run(
            [sys.executable, __file__, "--child"], capture_output=True, text=True, timeout=25
        )
        (root / f"startup-{index}.stdout.txt").write_text(result.stdout)
        (root / f"startup-{index}.stderr.txt").write_text(result.stderr)
        parsed = []
        for line in result.stdout.splitlines():
            try:
                item = json.loads(line)
            except ValueError:
                continue
            if isinstance(item, dict) and "startup" in item:
                parsed.append(item)
        if result.returncode != 0 or len(parsed) != 1 or parsed[0]["startup"] != "passed":
            raise RuntimeError(f"Startup sample {index} failed; see retained logs")
        records.append(
            {
                "sample": index + 1,
                "process_wall_ms": (time.perf_counter() - started) * 1000,
                **parsed[0],
            }
        )
    summary = {
        "passed": True,
        "cache_rows": 1000,
        "displayed_rows": 200,
        "samples": records,
        "median_ms": {
            key: round(statistics.median(r[key] for r in records), 2)
            for key in (
                "imports_ms",
                "construction_ms",
                "first_window_paint_ms",
                "snapshot_applied_ms",
                "browser_painted_ms",
                "process_wall_ms",
            )
        },
        "limits": "Fresh source processes, seeded/reused temporary profile, offscreen Qt, optional polling paused and network isolated. OS caches are not flushed; these are not disk-cold, packaged or real server/mod-readiness timings.",
    }
    (root / "result.json").write_text(json.dumps(summary, indent=2) + "\n")
    print(json.dumps({"output_root": str(root), **summary}, indent=2))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repeats", type=int, default=5)
    for mode in ("suite", "prepare", "child"):
        parser.add_argument("--" + mode, action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args()
    if not 3 <= args.repeats <= 10:
        parser.error("repeats must be 3–10")
    if args.prepare:
        return prepare()
    if args.child:
        return measured_child()
    if args.suite:
        return suite(args.repeats)
    if not shutil.which("bwrap"):
        parser.error("bubblewrap is required")
    root = Path(tempfile.mkdtemp(prefix="wolflauncher-startup-"))
    (root / "runtime").mkdir(mode=0o700)
    command = [
        "bwrap",
        "--die-with-parent",
        "--unshare-pid",
        "--unshare-net",
        "--ro-bind",
        "/",
        "/",
        "--tmpfs",
        "/tmp",
        "--bind",
        str(root),
        str(root),
        "--proc",
        "/proc",
        "--dev",
        "/dev",
    ]
    for name, value in {
        "XDG_CONFIG_HOME": str(root / "config"),
        "XDG_DATA_HOME": str(root / "data"),
        "XDG_CACHE_HOME": str(root / "cache"),
        "XDG_RUNTIME_DIR": str(root / "runtime"),
        "QT_QPA_PLATFORM": "offscreen",
        "PYTHONDONTWRITEBYTECODE": "1",
        "DBUS_SESSION_BUS_ADDRESS": "unix:path=/nonexistent-wolf-startup",
        "WOLFLAUNCHER_SMOKE_ROOT": str(root),
    }.items():
        command.extend(("--setenv", name, value))
    command.extend(
        (
            "--",
            sys.executable,
            str(Path(__file__).resolve()),
            "--suite",
            "--repeats",
            str(args.repeats),
        )
    )
    return subprocess.run(command, timeout=300).returncode


if __name__ == "__main__":
    raise SystemExit(main())
