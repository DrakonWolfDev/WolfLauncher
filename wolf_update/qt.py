"""Optional non-blocking PySide6 adapter."""

from __future__ import annotations

from threading import Event, Thread

from PySide6.QtCore import QObject, QRunnable, QThreadPool, Signal

from .core import UpdateService


class _CheckSignals(QObject):
    finished = Signal(object)


class _CheckRunnable(QRunnable):
    def __init__(self, service: UpdateService, manual: bool) -> None:
        super().__init__()
        self.service = service
        self.manual = manual
        self.signals = _CheckSignals()
        self._cancelled = Event()

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
            self.signals.finished.emit(result[0])

    def cancel(self) -> None:
        self._cancelled.set()


class QtUpdateChecker(QObject):
    """Run one update check at a time without blocking the Qt event loop."""

    result_ready = Signal(object, bool)

    def __init__(self, service: UpdateService, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self.service = service
        self._pool = QThreadPool(self)
        self._pool.setMaxThreadCount(1)
        self._running = False
        self._runnable: _CheckRunnable | None = None

    def is_running(self) -> bool:
        return self._running

    def isRunning(self) -> bool:
        """Match WolfLauncher's existing background-worker lifecycle protocol."""
        return self.is_running()

    def check(self, *, manual: bool = False) -> bool:
        if self.is_running():
            return False
        runnable = _CheckRunnable(self.service, manual)
        runnable.signals.finished.connect(lambda result: self._finish(runnable, result, manual))
        self._running = True
        self._runnable = runnable
        self._pool.start(runnable)
        return True

    def _finish(self, runnable: _CheckRunnable, result: object, manual: bool) -> None:
        if self._runnable is not runnable:
            return
        self._running = False
        self._runnable = None
        self.result_ready.emit(result, manual)

    def wait(self, timeout_ms: int) -> bool:
        return self._pool.waitForDone(timeout_ms)

    def requestInterruption(self) -> None:
        """Cancel result delivery and release the Qt worker promptly."""
        runnable = self._runnable
        if runnable is None:
            return
        runnable.cancel()
        self._runnable = None
        self._running = False
