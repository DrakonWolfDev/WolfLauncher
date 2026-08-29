"""About-page presentation for WolfLauncher."""

from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QVBoxLayout, QWidget

from . import __version__
from .theme import WOLF_MARK_PATH, brand_wordmark, set_ui_role


class AboutFeatureMixin:
    def _build_about_tab(self) -> QWidget:
        """Build a compact product card without advertising unpublished links."""
        widget = QWidget()
        set_ui_role(widget, "workspace")
        layout = QVBoxLayout(widget)
        layout.setAlignment(Qt.AlignCenter)

        card = QFrame()
        set_ui_role(card, "aboutCard")
        card.setMaximumWidth(560)
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(42, 38, 42, 34)
        card_layout.setSpacing(10)
        card_layout.setAlignment(Qt.AlignHCenter)

        mark = QLabel()
        mark.setPixmap(QIcon(str(WOLF_MARK_PATH)).pixmap(QSize(92, 92)))
        mark.setAlignment(Qt.AlignCenter)
        mark.setAccessibleName("Wolf Launcher logo")
        card_layout.addWidget(mark)

        title = QLabel(brand_wordmark())
        title.setAlignment(Qt.AlignCenter)
        title.setAccessibleName("Wolf Launcher")
        set_ui_role(title, "aboutTitle")
        card_layout.addWidget(title)

        tagline = QLabel("Free and open-source DayZ launcher for Windows & Linux")
        tagline.setAlignment(Qt.AlignCenter)
        set_ui_role(tagline, "aboutTagline")
        card_layout.addWidget(tagline)

        licence = QLabel(
            'Licensed under <a href="https://choosealicense.com/licenses/agpl-3.0/">'
            "GNU AGPLv3</a>"
        )
        licence.setAlignment(Qt.AlignCenter)
        licence.setOpenExternalLinks(True)
        licence.setToolTip("Open the full GNU AGPLv3 licence details")
        licence.setAccessibleName("Licensed under GNU AGPLv3")
        set_ui_role(licence, "aboutLicence")
        card_layout.addWidget(licence)

        links = QHBoxLayout()
        links.setContentsMargins(0, 12, 0, 8)
        links.setSpacing(8)
        links.setAlignment(Qt.AlignCenter)
        for label in ("◌  Website", "<>  GitHub", "#  Discord"):
            link = QLabel(label)
            link.setAlignment(Qt.AlignCenter)
            link.setToolTip("Coming soon")
            set_ui_role(link, "aboutLink")
            links.addWidget(link)
        card_layout.addLayout(links)

        version = QLabel(f"Version {__version__}")
        version.setAlignment(Qt.AlignCenter)
        set_ui_role(version, "aboutMetadata")
        card_layout.addWidget(version)

        copyright_notice = QLabel("© 2026 Andrew Hodgson t/a Wolf Forge")
        copyright_notice.setAlignment(Qt.AlignCenter)
        set_ui_role(copyright_notice, "aboutCopyright")
        card_layout.addWidget(copyright_notice)

        layout.addWidget(card)
        return widget
