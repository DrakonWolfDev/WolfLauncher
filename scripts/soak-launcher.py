"""Bounded source UI resource soak in private Linux data/network namespaces."""

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def child(cycles):
    # Reject direct child invocation before constructing the application or
    # importing code that could initialize ordinary user configuration.
    root = Path(os.environ.get("WOLFLAUNCHER_SMOKE_ROOT", "/")).resolve()
    temporary = Path(tempfile.gettempdir()).resolve()
    if root == temporary or not root.is_relative_to(temporary):
        raise ValueError("Use the isolated parent runner")
    for name, suffix in (
        ("XDG_CONFIG_HOME", "config"),
        ("XDG_DATA_HOME", "data"),
        ("XDG_CACHE_HOME", "cache"),
        ("XDG_RUNTIME_DIR", "runtime"),
    ):
        if Path(os.environ.get(name, "/")).resolve() != root / suffix:
            raise ValueError("Use the isolated parent runner")
    # Imports stay inside the isolated child; the parent never opens application data.
    sys.path.insert(0, str(ROOT))
    from PySide6.QtCore import QObject, QSignalBlocker, Qt, QTimer
    from PySide6.QtGui import QPixmap
    from PySide6.QtWidgets import QApplication

    from wolflauncher.app import MainWindow
    from wolflauncher.packaged_validation import PackagedValidation
    from wolflauncher.theme import apply_application_theme

    class Soak(PackagedValidation):
        def __init__(self, app, window, environment):
            super().__init__(app, window, environment)
            self.completed = 0
            self.waiting = False
            self.samples = []
            self.browser_requests = 0

        def tick(self):
            # Parent watchdog also bounds shutdown if an exception stalls Qt.
            try:
                now = time.monotonic()
                self.max_tick_gap_ms = max(self.max_tick_gap_ms, (now - self.last_tick) * 1000)
                self.last_tick = now
                if now - self.started > 150:
                    raise RuntimeError("Resource soak timed out")
                self.step()
            except Exception as exc:
                self.timer.stop()
                self.app.setProperty("packagedValidationFailed", True)
                print(
                    json.dumps({"soak": "failed", "cycle": self.completed, "error": str(exc)}),
                    flush=True,
                )
                self.window.close()

        def sample(self):
            status = dict(
                line.split(":", 1)
                for line in Path("/proc/self/status").read_text().splitlines()
                if ":" in line
            )
            window = self.window
            return {
                "cycle": self.completed,
                "rss_kib": int(status["VmRSS"].split()[0]),
                "threads": int(status["Threads"]),
                "file_descriptors": len(list(Path("/proc/self/fd").iterdir())),
                "qt_objects": len(window.findChildren(QObject)),
                "thumbnail_entries": len(window.mod_thumbnail_cache.entries),
                "thumbnail_bytes": window.mod_thumbnail_cache.bytes,
                "auxiliary_entries": len(window.browser_snapshot_loader.auxiliary),
            }

        def step(self):
            if self.phase < 4:
                super().step()
                return
            window = self.window
            if window.browser_snapshot_worker is not None:
                return
            if self.waiting:
                product = "stable" if self.completed % 2 == 0 else "experimental"
                expected = 1000 if product == "stable" else 10
                if len(window.browser_servers) != expected or any(
                    s.product != product for s in window.browser_servers
                ):
                    raise AssertionError("Latest edition/filter snapshot did not win")
                if window.browser_snapshot_loader.pending is not None:
                    raise AssertionError("Pending browser request survived idle")
                self.completed += 1
                self.waiting = False
                if self.completed % 10 == 0:
                    self.samples.append(self.sample())
                if self.completed == cycles:
                    self.finish()
                return
            product = "stable" if self.completed % 2 == 0 else "experimental"
            window.browser_edition.setCurrentIndex(window.browser_edition.findData(product))
            for query in ("Validation", "no matching row", ""):
                window.browser_search.setText(query)
                window.browser_filter_timer.stop()
                window.remote_search_timer.stop()
                window.refresh_server_browser()
                self.browser_requests += 1
            result = window.last_mod_result
            item = window.mods_table.item(150, 1)
            selected = window.mods_table.item(window.mods_table.currentRow(), 2).text()
            result.required_mods[0].workshop_file_size = 1024 * (self.completed + 1)
            window.display_mods_result(result)
            if (
                window.mods_table.item(150, 1) is not item
                or window.mods_table.item(window.mods_table.currentRow(), 2).text() != selected
            ):
                raise AssertionError("Mod item reuse or selection regressed")
            for index in range(2):
                preview = QPixmap(512, 512)
                preview.fill(Qt.red if index else Qt.blue)
                key = (f"https://validation.invalid/{self.completed}-{index}.png", 1)
                window.mod_thumbnail_cache.put(key, preview)
            with QSignalBlocker(window.mods_table):
                window.load_mod_thumbnail(key[0], revision=1)
            cache = window.mod_thumbnail_cache
            if len(cache.entries) > cache.max_entries or cache.bytes > cache.max_bytes:
                raise AssertionError("Thumbnail cache exceeded its bound")
            if window.mod_thumbnail_reply is not None:
                raise AssertionError("Synthetic cached preview created a network reply")
            window.browser_table.verticalScrollBar().setValue(self.completed % 500)
            window.tabs.setCurrentIndex(
                window.mods_tab_index if self.completed % 2 else window.server_browser_tab_index
            )
            self.waiting = True

        def finish(self):
            # Compare equally warmed checkpoints; RSS is resident memory, not a
            # Python-only allocation count. Allow bounded allocator/cache slack.
            steady = self.samples[4:]
            baseline, final = steady[0], steady[-1]
            growth = final["rss_kib"] - baseline["rss_kib"]
            if growth > 32 * 1024:
                raise AssertionError(f"Post-warmup RSS grew {growth} KiB")
            for field, allowance in (("threads", 2), ("file_descriptors", 2), ("qt_objects", 10)):
                if max(s[field] for s in steady) > baseline[field] + allowance:
                    raise AssertionError(f"Post-warmup {field} accumulated")
            self.timer.stop()
            print(
                json.dumps(
                    {
                        "soak": "passed",
                        "cycles": cycles,
                        "explicit_browser_requests": self.browser_requests,
                        "samples": self.samples,
                        "warmup_cycles": 50,
                        "rss_growth_kib": growth,
                        "elapsed_ms": round((time.monotonic() - self.started) * 1000),
                        "max_tick_gap_ms": round(self.max_tick_gap_ms, 1),
                        "limits": "Synthetic source/offscreen test; no public network, Steam, real downloads or packaged/live compatibility evidence.",
                    }
                ),
                flush=True,
            )
            self.window.close()

    app = QApplication([])
    app.setApplicationName("WolfLauncher")
    app.setOrganizationName("WolfLauncher")
    apply_application_theme(app)
    window = MainWindow()
    window.show()
    validation = Soak(app, window, os.environ)
    window.packaged_validation = validation
    validation.start()
    QTimer.singleShot(165000, lambda: app.exit(124))
    code = app.exec()
    return 126 if app.property("packagedValidationFailed") else code


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cycles", type=int, default=300)
    parser.add_argument("--child", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args()
    if not 100 <= args.cycles <= 1000:
        parser.error("cycles must be between 100 and 1000")
    if args.child:
        return child(args.cycles)
    if not shutil.which("bwrap"):
        parser.error("bubblewrap is required")
    root = Path(tempfile.mkdtemp(prefix="wolflauncher-source-soak-"))
    (root / "config/wolflauncher").mkdir(parents=True)
    (root / "data").mkdir()
    (root / "runtime").mkdir(mode=0o700)
    (root / "config/wolflauncher/servers.yaml").write_text("servers: []\n")
    (root / "config/wolflauncher/settings.json").write_text(
        json.dumps({"schema_version": 10, "discovery_auto_refresh": False, "refresh_seconds": 0})
    )
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
        "DBUS_SESSION_BUS_ADDRESS": "unix:path=/nonexistent-wolf-soak",
        "QT_QPA_PLATFORM": "offscreen",
        "PYTHONDONTWRITEBYTECODE": "1",
        "WOLFLAUNCHER_SMOKE_ROOT": str(root),
    }.items():
        command.extend(("--setenv", name, value))
    command.extend(
        (
            "--",
            sys.executable,
            str(Path(__file__).resolve()),
            "--child",
            "--cycles",
            str(args.cycles),
        )
    )
    try:
        result = subprocess.run(command, capture_output=True, text=True, timeout=180)
    except subprocess.TimeoutExpired as exc:
        (root / "stdout.txt").write_bytes(exc.stdout or b"")
        (root / "stderr.txt").write_bytes(exc.stderr or b"")
        print(json.dumps({"output_root": str(root), "passed": False, "error": "watchdog timeout"}))
        return 1
    (root / "stdout.txt").write_text(result.stdout)
    (root / "stderr.txt").write_text(result.stderr)
    records = []
    for line in result.stdout.splitlines():
        try:
            record = json.loads(line)
        except ValueError:
            continue
        if isinstance(record, dict) and "soak" in record:
            records.append(record)
    passed = result.returncode == 0 and len(records) == 1 and records[0]["soak"] == "passed"
    summary = {"passed": passed, "exit_code": result.returncode, "records": records}
    (root / "result.json").write_text(json.dumps(summary, indent=2) + "\n")
    print(json.dumps({"output_root": str(root), **summary}, indent=2))
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
