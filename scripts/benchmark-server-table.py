"""Local synthetic Qt table benchmark; no server queries or Steam operations.

Run with --revision HEAD to compare the committed table implementation with the
working tree. Timings include event processing and use a visible offscreen table.
"""

# ruff: noqa: E402 - project-path bootstrap must precede application imports

import argparse
import importlib.util
import json
import os
import statistics
import subprocess
import sys
import time
from dataclasses import replace
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from PySide6 import QtSvg  # noqa: F401 - preload the SVG dependency for icon plugins
from PySide6.QtCore import QCoreApplication, QEvent, Qt
from PySide6.QtGui import QFontDatabase
from PySide6.QtWidgets import QApplication, QTableWidget, QWidget

from wolflauncher import server_browser_table
from wolflauncher.models import DiscoveredServer
from wolflauncher.theme import apply_application_theme, configure_data_table


def flush_events(app):
    app.processEvents()
    QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete)


def measure(app, implementation, count, repeats):
    servers = [
        DiscoveredServer(
            f"Server {index:04}", f"host{index}", 2302, 27016,
            online=True, players_current=index % 60, players_max=60,
            ping_ms=index % 300, modded=True,
        )
        for index in range(count)
    ]
    table = QTableWidget(0, implementation.BROWSER_COLUMN_COUNT)
    configure_data_table(table)
    table.resize(1200, 600)
    table.sortItems(1, Qt.AscendingOrder)
    table.show()
    flush_events(app)
    population, enrichment, previews = [], [], []
    for _ in range(repeats):
        start = time.perf_counter()
        implementation.populate_browser_table(table, servers)
        flush_events(app)
        population.append((time.perf_counter() - start) * 1000)
        start = time.perf_counter()
        for server in servers[:50]:
            updated = replace(server, ping_ms=server.ping_ms + 1, players_current=61)
            implementation.update_browser_table_row(table, server.cache_key, updated)
        flush_events(app)
        enrichment.append((time.perf_counter() - start) * 1000)
        start = time.perf_counter()
        for server in servers[:50]:
            implementation.update_browser_mod_cell(table, server.cache_key, "3 MISSING", "Preview")
        flush_events(app)
        previews.append((time.perf_counter() - start) * 1000)
    result = {
        "rows": count,
        "populate_ms": round(statistics.median(population), 2),
        "50_enrichments_ms": round(statistics.median(enrichment), 2),
        "50_mod_previews_ms": round(statistics.median(previews), 2),
        "descendant_widgets": len(table.findChildren(QWidget)),
    }
    table.close()
    table.deleteLater()
    flush_events(app)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--revision", help="Read the table module from this local Git revision")
    parser.add_argument("--repeats", type=int, default=5)
    args = parser.parse_args()
    if args.repeats < 1:
        parser.error("--repeats must be at least 1")
    implementation = server_browser_table
    if args.revision:
        source = subprocess.run(
            ["git", "show", f"{args.revision}:wolflauncher/server_browser_table.py"],
            cwd=ROOT, check=True, capture_output=True, encoding="utf-8",
        ).stdout
        spec = importlib.util.spec_from_loader("wolflauncher._benchmark_table", loader=None)
        implementation = importlib.util.module_from_spec(spec)
        exec(compile(source, "<git table implementation>", "exec"), implementation.__dict__)
    app = QApplication.instance() or QApplication([])
    # Qt's Windows offscreen plugin may start without a system font database.
    # Load the same fonts for both implementations so text is measured faithfully.
    if sys.platform == "win32":
        fonts = Path(os.environ.get("WINDIR", "C:/Windows")) / "Fonts"
        for name in ("segoeui.ttf", "seguisym.ttf"):
            QFontDatabase.addApplicationFont(str(fonts / name))
    apply_application_theme(app)
    print(json.dumps({
        "implementation": args.revision or "working tree",
        "python": sys.version.split()[0],
        "measurements": [measure(app, implementation, count, args.repeats)
                         for count in (200, 500, 1000)],
    }, indent=2))


if __name__ == "__main__":
    main()
