"""Optional non-blocking PySide6 adapter."""

from __future__ import annotations

from threading import Event, Thread

from PySide6.QtCore import QObject, QRunnable, Qt, QThreadPool, Signal, Slot

from .core import UpdateService


class _CheckSignals(QObject):
    finished = Signal(int, object, bool)


class _CheckRunnable(QRunnable):
    def __init__(
        self,
        service: UpdateService,
        manual: bool,
        signals: _CheckSignals,
        generation: int,
        cancelled: Event,
    ) -> None:
        super().__init__()
        self.service = service
        self.manual = manual
        self.signals = signals
        self.generation = generation
        self._cancelled = cancelled

    def run(self) -> None:
        completed = Event()
        result = []

        def check() -> None:
            try:
                result.append(
                    self.service.check(
                        manual=self.manual,
                        cancelled=self._cancelled.is_set,
                    )
                )
            finally:
                completed.set()

        # urllib cannot reliably abort a DNS lookup or connect from another
        # thread. Keep that bounded operation in a daemon thread so the Qt
        # runnable can cooperate with shutdown without terminating a thread.
        Thread(target=check, name="WolfUpdateTransport", daemon=True).start()
        while not completed.wait(0.05):
            if self._cancelled.is_set():
                return
        if not self._cancelled.is_set() and result:
            self.signals.finished.emit(self.generation, result[0], self.manual)


class QtUpdateChecker(QObject):
    """Run one update check at a time without blocking the Qt event loop."""

    result_ready = Signal(object, bool)

    def __init__(self, service: UpdateService, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self.service = service
        self._pool = QThreadPool(self)
        self._pool.setMaxThreadCount(1)
        # The checker owns the signal source. No callback captures a QRunnable
        # that QThreadPool may already have auto-deleted when delivery occurs.
        self._signals = _CheckSignals(self)
        self._signals.finished.connect(self._finish, Qt.ConnectionType.QueuedConnection)
        self._running = False
        self._generation = 0
        self._cancelled: Event | None = None

    def is_running(self) -> bool:
        return self._running

    def isRunning(self) -> bool:
        """Match WolfLauncher's existing background-worker lifecycle protocol."""
        return self.is_running()

    def check(self, *, manual: bool = False) -> bool:
        if self.is_running():
            return False
        self._generation += 1
        self._cancelled = Event()
        runnable = _CheckRunnable(
            self.service, manual, self._signals, self._generation, self._cancelled
        )
        self._running = True
        self._pool.start(runnable)
        return True

    @Slot(int, object, bool)
    def _finish(self, generation: int, result: object, manual: bool) -> None:
        if generation != self._generation or not self._running:
            return
        self._running = False
        self._cancelled = None
        self.result_ready.emit(result, manual)

    def wait(self, timeout_ms: int) -> bool:
        return self._pool.waitForDone(timeout_ms)

    def requestInterruption(self) -> None:
        """Cancel result delivery and release the Qt worker promptly."""
        if self._cancelled is not None:
            self._cancelled.set()
        self._cancelled = None
        self._generation += 1
        self._running = False
