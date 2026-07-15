from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLineEdit,
    QSpinBox,
    QVBoxLayout,
)

from .config import normalize_server_endpoint
from .models import Server
from .theme import set_monospace, set_ui_role


class PromoteServerDialog(QDialog):
    def __init__(self, parent, name: str, group: str = "Discovered"):
        super().__init__(parent)
        self.setWindowTitle("Add to Favourite Servers")
        self.resize(420, 140)

        layout = QVBoxLayout(self)
        form = QFormLayout()
        self.name = QLineEdit(name)
        self.group = QLineEdit(group)
        form.addRow("Name", self.name)
        form.addRow("Group", self.group)
        layout.addLayout(form)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        set_ui_role(buttons.button(QDialogButtonBox.Ok), "primary")
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def curated_name(self) -> str:
        return self.name.text().strip()

    def curated_group(self) -> str:
        return self.group.text().strip() or "Discovered"


class EditCuratedServerDialog(QDialog):
    def __init__(self, parent, server: Server, title: str = "Edit a favourite server"):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.resize(440, 240)

        layout = QVBoxLayout(self)
        form = QFormLayout()
        self.name = QLineEdit(server.name)
        self.group = QLineEdit(server.group)
        self.host = QLineEdit(server.host)
        set_monospace(self.host)
        self.game_port = QSpinBox()
        self.game_port.setRange(1, 65535)
        self.game_port.setValue(server.game_port)
        self.query_port = QSpinBox()
        self.query_port.setRange(1, 65535)
        self.query_port.setValue(server.query_port)
        self.favourite = QCheckBox("Favourite")
        self.favourite.setChecked(server.favourite)
        form.addRow("Name", self.name)
        form.addRow("Group", self.group)
        form.addRow("Host", self.host)
        form.addRow("Game port", self.game_port)
        form.addRow("Query port", self.query_port)
        form.addRow("", self.favourite)
        layout.addLayout(form)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        set_ui_role(buttons.button(QDialogButtonBox.Ok), "primary")
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def curated_server(self) -> Server:
        host, game_port, query_port = normalize_server_endpoint(
            self.host.text(),
            self.game_port.value(),
            self.query_port.value(),
        )
        return Server(
            name=self.name.text().strip(),
            group=self.group.text().strip() or "Community",
            host=host,
            game_port=game_port,
            query_port=query_port,
            favourite=self.favourite.isChecked(),
        )
