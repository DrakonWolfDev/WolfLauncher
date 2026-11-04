"""Synthetic offscreen mod-table timings; no Steam or network operations."""

# ruff: noqa: E402 - add the source root before importing the application

import argparse
import ast
import json
import os
import statistics
import subprocess
import sys
import time
from pathlib import Path
from types import MethodType

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from PySide6.QtWidgets import QApplication, QTableWidget

from wolflauncher.mods import RequiredMod
from wolflauncher.mods_feature import ModsFeatureMixin
from wolflauncher.theme import apply_application_theme, configure_data_table


class View(ModsFeatureMixin):
    def __init__(self):
        self.mods_table = QTableWidget(0, 4)
        configure_data_table(self.mods_table)
        self.mods_table.resize(1200, 600)

    def apply_mod_filter(self):
        pass

    def update_mod_detail_card(self):
        pass


def old_population(revision):
    source = subprocess.run(
        ["git", "show", f"{revision}:wolflauncher/mods_feature.py"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    cls = next(
        node
        for node in ast.parse(source).body
        if isinstance(node, ast.ClassDef) and node.name == "ModsFeatureMixin"
    )
    method = next(
        node
        for node in cls.body
        if isinstance(node, ast.FunctionDef) and node.name == "_display_mod_rows"
    )
    from PySide6.QtCore import Qt
    from PySide6.QtGui import QColor
    from PySide6.QtWidgets import QHeaderView, QTableWidgetItem

    from wolflauncher.mod_presenter import mod_row
    from wolflauncher.theme import monospace_font

    namespace = dict(
        globals(),
        Qt=Qt,
        QColor=QColor,
        QHeaderView=QHeaderView,
        QTableWidgetItem=QTableWidgetItem,
        mod_row=mod_row,
        monospace_font=monospace_font,
    )
    exec(
        compile(ast.Module(body=[method], type_ignores=[]), "<baseline method>", "exec"), namespace
    )
    return namespace["_display_mod_rows"]


def measure(app, count, repeats, baseline):
    samples = {key: [] for key in ("initial_ms", "unchanged_ms", "one_changed_ms")}
    for _ in range(repeats):
        view = View()
        if baseline:
            view._display_mod_rows = MethodType(baseline, view)
        view.mods_table.show()
        app.processEvents()
        mods = [RequiredMod(str(1000 + i), f"Mod {i:04}", installed=True) for i in range(count)]
        for mode in samples:
            if mode == "one_changed_ms":
                mods[-1].workshop_file_size = 1024 * 1024
            started = time.perf_counter()
            view._display_mod_rows(mods, preserve_position=mode != "initial_ms")
            app.processEvents()
            samples[mode].append((time.perf_counter() - started) * 1000)
        view.mods_table.close()
    return {
        "rows": count,
        **{key: round(statistics.median(value), 2) for key, value in samples.items()},
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--revision", help="Load the old population method from a local Git revision"
    )
    parser.add_argument("--rows", type=int, nargs="+", default=[200, 500, 1000])
    parser.add_argument("--repeats", type=int, default=5)
    args = parser.parse_args()
    if args.repeats < 1 or any(count < 1 or count > 10000 for count in args.rows):
        parser.error("use positive repeats and row counts between 1 and 10000")
    app = QApplication.instance() or QApplication([])
    apply_application_theme(app)
    baseline = old_population(args.revision) if args.revision else None
    print(
        json.dumps(
            {
                "implementation": args.revision or "working tree",
                "measurements": [
                    measure(app, count, args.repeats, baseline) for count in args.rows
                ],
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
