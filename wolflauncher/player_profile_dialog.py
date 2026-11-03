"""Explicit selection of an existing player name, without profile-file writes."""

from copy import copy

from PySide6.QtCore import QDateTime, Qt, QThread, Signal
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QHeaderView,
    QLabel,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)

from .player_profiles import ProfileDiscoveryResult, discover_player_profiles, profile_still_exists
from .theme import configure_data_table


class PlayerProfileWorker(QThread):
    profiles_ready = Signal(object)

    def __init__(self, install, platform_id, parent=None):
        super().__init__(parent)
        self.install = copy(install)
        self.platform_id = platform_id

    def cancel(self):
        self.requestInterruption()

    def run(self):
        try:
            result = discover_player_profiles(
                self.install,
                platform_id=self.platform_id,
                cancelled=self.isInterruptionRequested,
            )
        except Exception:
            result = ProfileDiscoveryResult(note="The profile folders could not be checked.")
        if not self.isInterruptionRequested():
            self.profiles_ready.emit(result)


class PlayerProfileDialog(QDialog):
    def __init__(self, parent, product_label, current_name):
        super().__init__(parent)
        self.setWindowTitle(f"Existing profiles — {product_label}")
        self.resize(780, 380)
        self.current_name = current_name
        self.profiles = ()
        self.selected_profile = None
        self.scan_worker = None
        layout = QVBoxLayout(self)
        explanation = QLabel(
            "DayZ saves settings under each profile name. Choose an existing name to use in "
            "WolfLauncher. Profile files stay unchanged."
        )
        explanation.setWordWrap(True)
        layout.addWidget(explanation)
        self.status = QLabel("Looking for existing profiles…")
        self.status.setTextFormat(Qt.PlainText)
        self.status.setWordWrap(True)
        layout.addWidget(self.status)
        self.table = QTableWidget(0, 3)
        self.table.setHorizontalHeaderLabels(["Profile name", "Last modified", "Location"])
        self.table.setAccessibleName("Existing DayZ player profiles")
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setSelectionMode(QTableWidget.SingleSelection)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        configure_data_table(self.table)
        self.table.setSortingEnabled(False)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
        self.table.itemSelectionChanged.connect(self.update_selection)
        layout.addWidget(self.table)
        buttons = QDialogButtonBox(QDialogButtonBox.Cancel)
        self.use_button = buttons.addButton("Use profile name", QDialogButtonBox.AcceptRole)
        self.use_button.setEnabled(False)
        buttons.accepted.connect(self.accept_selection)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def show_profiles(self, result):
        self.profiles = result.profiles
        self.table.setRowCount(len(self.profiles))
        for row, profile in enumerate(self.profiles):
            modified = QDateTime.fromMSecsSinceEpoch(profile.modified_ns // 1_000_000).toString(
                "yyyy-MM-dd HH:mm"
            )
            locations = "\n".join(str(path.parent) for path in profile.files)
            for column, value in enumerate((profile.name, modified, locations)):
                item = QTableWidgetItem(value)
                item.setToolTip(value)
                self.table.setItem(row, column, item)
        self.table.resizeColumnsToContents()
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
        self.table.resizeRowsToContents()
        if self.profiles:
            self.status.setText(
                "Choose a profile name. Names found in multiple locations are grouped. "
                "DayZ uses its normal profile lookup. " + result.note
            )
            current = next(
                (i for i, profile in enumerate(self.profiles) if profile.name == self.current_name),
                0,
            )
            self.table.selectRow(current)
        else:
            self.status.setText(
                "No profiles were found in the folders checked. You can keep your current name "
                "or launch this edition through Steam once and try again. "
                "Custom profile folders are not searched. " + result.note
            )
        self.status.setToolTip("\n".join(str(path) for path in result.checked_folders))

    def update_selection(self):
        self.use_button.setEnabled(0 <= self.table.currentRow() < len(self.profiles))

    def accept_selection(self):
        row = self.table.currentRow()
        if not 0 <= row < len(self.profiles):
            return
        profile = self.profiles[row]
        if not profile_still_exists(profile):
            self.status.setText("This profile is no longer available. Close and search again.")
            self.use_button.setEnabled(False)
            return
        self.selected_profile = profile
        self.accept()

    def scan_finished(self):
        self.scan_worker = None

    def reject(self):
        if self.scan_worker is not None:
            self.scan_worker.cancel()
        super().reject()
