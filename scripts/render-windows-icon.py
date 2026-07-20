"""Render the tracked SVG wolf mark into a Windows executable icon."""

from __future__ import annotations

import argparse
import os
from pathlib import Path

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QGuiApplication, QImage, QPainter
from PySide6.QtSvg import QSvgRenderer


def render_icon(source: Path, destination: Path, size: int = 256) -> None:
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    app = QGuiApplication.instance() or QGuiApplication([])
    renderer = QSvgRenderer(str(source))
    if not renderer.isValid():
        raise ValueError(f"Could not load SVG icon source: {source}")

    image = QImage(size, size, QImage.Format.Format_ARGB32)
    image.fill(Qt.GlobalColor.transparent)
    painter = QPainter(image)
    renderer.render(painter, QRectF(0, 0, size, size))
    painter.end()

    destination.parent.mkdir(parents=True, exist_ok=True)
    if not image.save(str(destination), "ICO"):
        raise ValueError(f"Could not write Windows icon: {destination}")
    app.processEvents()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("source", type=Path)
    parser.add_argument("destination", type=Path)
    parser.add_argument("--size", type=int, default=256)
    args = parser.parse_args()
    render_icon(args.source, args.destination, args.size)


if __name__ == "__main__":
    main()
