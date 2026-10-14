"""Native card-style presentation for the small curated server list."""

from PySide6.QtCore import QPoint, QSize, Qt, Signal
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

from .server_display import ping_severity
from .theme import set_monospace, set_ui_role, theme_icon, time_icon


class CuratedServerCard(QFrame):
    TIME_COLUMN_WIDTH = 42
    STATS_COLUMN_WIDTH = 44

    selected = Signal(int)
    activated = Signal(int)
    favourite_requested = Signal(int)
    context_requested = Signal(int, QPoint)

    def __init__(
        self,
        row: int,
        values: list[str],
        parent: QWidget | None = None,
        *,
        experimental: bool = False,
        stable: bool = False,
    ):
        super().__init__(parent)
        self.row = row
        self.setProperty("uiRole", "serverCard")
        self.setProperty("experimental", experimental)
        self.setProperty("stable", stable)
        self.setProperty("onlineState", self._online_state(values[8]))
        self.setCursor(Qt.PointingHandCursor)
        name = values[3] or values[2] or "Unnamed server"
        status = values[8].lower() or "unknown"
        self.setAccessibleName(f"{name}, {status}")
        self.setAccessibleDescription(
            "Favourite DayZ server card. Select it to inspect; use the Connect button to launch."
        )

        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(10)

        self.favourite_button = QPushButton(values[0] or "☆")
        set_ui_role(self.favourite_button, "star")
        self.favourite_button.setProperty("favourite", values[0] == "★")
        self.favourite_button.setFixedWidth(28)
        self.favourite_button.setToolTip("Toggle favourite")
        self.favourite_button.setAccessibleName(f"Toggle favourite for {name}")
        self.favourite_button.clicked.connect(lambda: self.favourite_requested.emit(self.row))

        self.password_lock = QLabel()
        set_ui_role(self.password_lock, "passwordLock")
        self.password_lock.setFixedWidth(15)
        if "Password" in values[14]:
            self.password_lock.setPixmap(theme_icon("lock").pixmap(QSize(15, 15)))
            self.password_lock.setToolTip("This server requires a password to join.")
            self.password_lock.setAccessibleName("Password required")
        markers = QHBoxLayout()
        markers.setContentsMargins(0, 0, 0, 0)
        markers.setSpacing(4)
        markers.addWidget(self.favourite_button)
        markers.addWidget(self.password_lock)
        layout.addLayout(markers)
        layout.addSpacing(6)

        text = QVBoxLayout()
        text.setSpacing(2)
        self.name_label = QLabel(name)
        set_ui_role(self.name_label, "cardTitle")
        self.metadata_label = QLabel(self._metadata(values))
        set_ui_role(self.metadata_label, "cardMetadata")
        if values[8] in {"OFFLINE", "UNKNOWN"} and values[9]:
            self.metadata_label.setToolTip(values[9])
        text.addWidget(self.name_label)
        text.addWidget(self.metadata_label)
        layout.addLayout(text, 1)

        self.time_icon_label = QLabel()
        self.time_icon_label.setAlignment(Qt.AlignHCenter | Qt.AlignBottom)
        self.time_icon_label.setFixedHeight(20)
        self.time_icon_label.setFixedWidth(self.TIME_COLUMN_WIDTH)
        self.time_label = QLabel(values[11])
        self.time_label.setAlignment(Qt.AlignHCenter | Qt.AlignTop)
        self.time_label.setFixedWidth(self.TIME_COLUMN_WIDTH)
        set_ui_role(self.time_label, "cardStats")
        set_monospace(self.time_label)
        is_day = self._game_time_is_day(values[11])
        if is_day is not None:
            self.time_icon_label.setPixmap(time_icon(is_day).pixmap(QSize(18, 18)))
            phase = "Daytime" if is_day else "Night-time"
            self.time_icon_label.setToolTip(f"{phase}: {values[11]}")
            self.time_icon_label.setAccessibleName(f"{phase}, server time {values[11]}")
        time_block = QVBoxLayout()
        time_block.setContentsMargins(0, 0, 0, 0)
        time_block.setSpacing(2)
        time_block.addWidget(self.time_icon_label)
        time_block.addWidget(self.time_label)
        layout.addLayout(time_block)

        self.stats_label = QLabel(self._stats(values))
        set_ui_role(self.stats_label, self._ping_role(values[12]))
        self.stats_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.stats_label.setFixedWidth(self.STATS_COLUMN_WIDTH)
        set_monospace(self.stats_label)
        layout.addWidget(self.stats_label)

        self.connect_button = QPushButton("Connect")
        self.connect_button.setAccessibleName(f"Connect to {name}")
        set_ui_role(self.connect_button, "accent")
        self.connect_button.setMinimumWidth(82)
        self.connect_button.setEnabled(values[8] == "ONLINE")
        self.connect_button.clicked.connect(lambda: self.activated.emit(self.row))
        layout.addWidget(self.connect_button)

    @staticmethod
    def _online_state(status: str) -> str:
        if status == "ONLINE":
            return "online"
        if status == "OFFLINE":
            return "offline"
        if status == "UNKNOWN":
            return "unknown"
        return "pending"

    @staticmethod
    def _metadata(values: list[str]) -> str:
        host = values[15] or f"{values[4]}:{values[6]}"
        if values[8] in {"OFFLINE", "UNKNOWN"}:
            reason = values[9] or (
                "Server offline" if values[8] == "OFFLINE" else "Unable to check server"
            )
            return f"{reason} · {host}"
        details = " · ".join(part for part in (values[9], host, values[13]) if part)
        if values[8] == "Rechecking…":
            return f"Rechecking… · Last known details · {details}"
        if values[8] == "Checking…":
            return f"Checking… · {details}"
        return details

    @staticmethod
    def _stats(values: list[str]) -> str:
        return "\n".join(part for part in (values[10], values[12]) if part)

    @staticmethod
    def _game_time_is_day(value: str) -> bool | None:
        try:
            hour, minute = (int(part) for part in value.split(":", 1))
        except (TypeError, ValueError):
            return None
        if not 0 <= hour <= 23 or not 0 <= minute <= 59:
            return None
        return 6 <= hour < 18

    @staticmethod
    def _ping_role(ping_text: str) -> str:
        try:
            ping_ms = int(ping_text.removesuffix("ms")) if ping_text else None
        except ValueError:
            ping_ms = None
        severity = ping_severity(ping_ms)
        if severity == "warning":
            return "pingWarning"
        if severity == "critical":
            return "pingCritical"
        return "cardStats"

    def set_selected(self, selected: bool) -> None:
        self.setProperty("selected", selected)
        set_ui_role(
            self.connect_button,
            "primary" if selected and self.connect_button.isEnabled() else "accent",
        )
        self.style().unpolish(self)
        self.style().polish(self)
        self.connect_button.style().unpolish(self.connect_button)
        self.connect_button.style().polish(self.connect_button)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.selected.emit(self.row)
        super().mousePressEvent(event)

    def mouseDoubleClickEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.activated.emit(self.row)
        super().mouseDoubleClickEvent(event)

    def contextMenuEvent(self, event):
        self.context_requested.emit(self.row, event.globalPos())
        event.accept()
