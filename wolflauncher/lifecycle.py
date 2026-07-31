from __future__ import annotations

import time

from PySide6.QtCore import QProcess

WORKER_ATTRIBUTES = (
    "worker",
    "mod_worker",
    "workshop_subscription_worker",
    "workshop_state_worker",
    "preflight_mod_worker",
    "preflight_workshop_worker",
    "discovery_worker",
    "web_api_worker",
    "battlemetrics_worker",
    "wolfapi_worker",
    "wolfapi_cache_worker",
    "wolfapi_search_worker",
    "results_freshness_worker",
)

WORKER_COLLECTION_ATTRIBUTES = (
    "selection_enrichment_workers",
    "browser_mod_workers",
)

TIMER_ATTRIBUTES = (
    "timer",
    "remote_search_timer",
    "browser_filter_timer",
    "browser_selection_timer",
    "steam_server_install_timer",
)


class RuntimeShutdownCoordinator:
    """Own the bounded, non-blocking shutdown protocol for one Qt window."""

    def __init__(self, owner, *, timeout_seconds: float = 15, monotonic=None):
        self.owner = owner
        self.timeout_seconds = timeout_seconds
        self._monotonic = monotonic or time.monotonic
        self.started = False
        self.deadline: float | None = None

    def begin(self) -> bool:
        """Start shutdown once and report whether all runtime work has stopped."""
        if not self.started:
            self.started = True
            self.deadline = self._monotonic() + self.timeout_seconds
            begin_runtime_shutdown(self.owner)
        return runtime_shutdown_complete(self.owner)

    def poll(self) -> bool:
        """Advance shutdown without blocking, killing only an overdue child process."""
        if runtime_shutdown_complete(self.owner):
            return True
        if self.deadline is not None and self._monotonic() >= self.deadline:
            kill_runtime_process(self.owner)
        return False

    def overdue(self) -> bool:
        return self.deadline is not None and self._monotonic() >= self.deadline


def stop_runtime_scheduling(owner) -> None:
    owner._shutting_down = True
    for name in TIMER_ATTRIBUTES:
        timer = getattr(owner, name, None)
        if timer is not None:
            timer.stop()
    for name in (
        "pending_selection_checks",
        "pending_browser_mod_previews",
        "results_freshness_attempted_keys",
    ):
        pending = getattr(owner, name, None)
        if pending is not None:
            pending.clear()
    if hasattr(owner, "pending_wolfapi_search"):
        owner.pending_wolfapi_search = ""
    if hasattr(owner, "pending_results_freshness"):
        owner.pending_results_freshness = False


def active_workers(owner) -> list:
    candidates = [getattr(owner, name, None) for name in WORKER_ATTRIBUTES]
    for name in WORKER_COLLECTION_ATTRIBUTES:
        collection = getattr(owner, name, None) or {}
        candidates.extend(collection.values())
    unique = []
    seen = set()
    for worker in candidates:
        if worker is None or id(worker) in seen:
            continue
        seen.add(id(worker))
        if worker.isRunning():
            unique.append(worker)
    return unique


def begin_runtime_shutdown(owner) -> None:
    """Request shutdown without blocking Qt's GUI thread."""
    stop_runtime_scheduling(owner)
    for worker in active_workers(owner):
        cancel = getattr(worker, "cancel", None)
        if callable(cancel):
            cancel()
        request_interruption = getattr(worker, "requestInterruption", None)
        if callable(request_interruption):
            request_interruption()

    process = getattr(owner, "wolfapi_refresh_process", None)
    if process is not None and process.state() != QProcess.NotRunning:
        process.terminate()


def runtime_shutdown_complete(owner) -> bool:
    process = getattr(owner, "wolfapi_refresh_process", None)
    process_running = process is not None and process.state() != QProcess.NotRunning
    return not process_running and not active_workers(owner)


def kill_runtime_process(owner) -> None:
    process = getattr(owner, "wolfapi_refresh_process", None)
    if process is not None and process.state() != QProcess.NotRunning:
        process.kill()


def stop_runtime(owner, timeout_ms: int = 15_000) -> bool:
    """Stop timers, workers and the refresh helper within one total deadline."""
    begin_runtime_shutdown(owner)
    workers = active_workers(owner)

    deadline = time.monotonic() + max(0, timeout_ms) / 1000
    process = getattr(owner, "wolfapi_refresh_process", None)
    if process is not None and process.state() != QProcess.NotRunning:
        if not process.waitForFinished(_remaining_ms(deadline)):
            process.kill()
            process.waitForFinished(_remaining_ms(deadline))

    for worker in workers:
        if worker.isRunning() and not worker.wait(_remaining_ms(deadline)):
            return False
    return not any(worker.isRunning() for worker in workers)


def _remaining_ms(deadline: float) -> int:
    return max(0, int((deadline - time.monotonic()) * 1000))
