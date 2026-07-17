"""Original map-flavour atmosphere for the selected-server inspector."""

from pathlib import Path

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QLinearGradient, QPainter, QPixmap
from PySide6.QtWidgets import QFrame


ATLAS_PATH = Path(__file__).resolve().parent / "assets" / "server-map-atmosphere-v2.png"


def map_atmosphere_flavour(map_name: str) -> str:
    """Return an honest broad environment flavour, never a server screenshot."""
    value = (map_name or "").strip().casefold()
    if "namalsk" in value:
        return "snow"
    if "sakhal" in value:
        return "volcanic"
    if value in {"enoch", "livonia"} or "livonia" in value:
        return "wetland"
    if "chernarus" in value:
        return "conifer"
    return "neutral"


class ServerMapAtmosphereFrame(QFrame):
    """Paint one atlas vista in the inspector's remaining visual space."""

    _columns = {
        "snow": 0,
        "conifer": 1,
        "wetland": 2,
        "volcanic": 3,
        "neutral": 1,
    }

    def __init__(self, parent=None):
        super().__init__(parent)
        self._atlas = QPixmap(str(ATLAS_PATH))
        self._flavour = "neutral"
        self.setMinimumHeight(168)

    def set_map_name(self, map_name: str) -> None:
        flavour = map_atmosphere_flavour(map_name)
        if flavour != self._flavour:
            self._flavour = flavour
            self.update()

    def paintEvent(self, event):
        super().paintEvent(event)
        if self._atlas.isNull() or self.width() <= 0 or self.height() <= 0:
            return
        painter = QPainter(self)
        painter.setRenderHint(QPainter.SmoothPixmapTransform, True)
        source = self._source_rect()
        target = QRectF(self.rect())
        painter.drawPixmap(target, self._atlas, self._cover_crop(source, target))
        gradient = QLinearGradient(0, 0, self.width(), self.height())
        if self._flavour == "neutral":
            gradient.setColorAt(0.0, QColor(21, 19, 15, 205))
            gradient.setColorAt(1.0, QColor(21, 19, 15, 170))
        else:
            gradient = QLinearGradient(0, 0, 0, self.height())
            gradient.setColorAt(0.0, QColor(21, 19, 15, 176))
            gradient.setColorAt(0.22, QColor(21, 19, 15, 98))
            gradient.setColorAt(0.78, QColor(21, 19, 15, 78))
            gradient.setColorAt(1.0, QColor(21, 19, 15, 132))
        painter.fillRect(self.rect(), gradient)
        self._paint_vignette(painter)

    def _paint_vignette(self, painter: QPainter) -> None:
        """Dissolve the rectangular artwork edge into the inspector surface."""
        surface = (21, 19, 15)
        vertical = QLinearGradient(0, 0, 0, self.height())
        vertical.setColorAt(0.0, QColor(*surface, 238))
        vertical.setColorAt(0.12, QColor(*surface, 92))
        vertical.setColorAt(0.30, QColor(*surface, 0))
        vertical.setColorAt(0.72, QColor(*surface, 0))
        vertical.setColorAt(0.90, QColor(*surface, 78))
        vertical.setColorAt(1.0, QColor(*surface, 218))
        painter.fillRect(self.rect(), vertical)

        horizontal = QLinearGradient(0, 0, self.width(), 0)
        horizontal.setColorAt(0.0, QColor(*surface, 92))
        horizontal.setColorAt(0.08, QColor(*surface, 18))
        horizontal.setColorAt(0.92, QColor(*surface, 18))
        horizontal.setColorAt(1.0, QColor(*surface, 106))
        painter.fillRect(self.rect(), horizontal)

    def _source_rect(self) -> QRectF:
        column = self._columns[self._flavour]
        column_width = self._atlas.width() / 4
        inset = max(1, round(self._atlas.width() * 0.003))
        x = column * column_width + inset
        return QRectF(
            x,
            inset,
            column_width - (2 * inset),
            self._atlas.height() - (2 * inset),
        )

    @staticmethod
    def _cover_crop(source: QRectF, target: QRectF) -> QRectF:
        source_ratio = source.width() / source.height()
        target_ratio = target.width() / max(1.0, target.height())
        if source_ratio > target_ratio:
            width = source.height() * target_ratio
            return QRectF(
                source.x() + (source.width() - width) / 2,
                source.y(),
                width,
                source.height(),
            )
        height = source.width() / max(target_ratio, 0.01)
        return QRectF(
            source.x(),
            source.y() + (source.height() - height) / 2,
            source.width(),
            height,
        )
