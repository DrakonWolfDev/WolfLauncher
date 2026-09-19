"""Background availability scanning with generation-based result ownership."""

from PySide6.QtCore import QThread, Signal

from .product_availability import scan_availability


class AvailabilityWorker(QThread):
    ready = Signal(int, object)

    def __init__(self, generation: int, mode: str):
        super().__init__()
        self.generation = generation
        self.mode = mode

    def run(self):
        snapshot = scan_availability(self.mode)
        if not self.isInterruptionRequested():
            self.ready.emit(self.generation, snapshot)
