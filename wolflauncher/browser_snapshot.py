"""One cancellable, read-only browser snapshot worker and a latest-query queue."""

import sqlite3
import threading
from collections import OrderedDict
from pathlib import Path

from PySide6.QtCore import QThread, Signal

from .server_browser_controller import browser_filter_options, load_browser_snapshot


class BrowserSnapshotWorker(QThread):
    ready = Signal(object, object, str)

    def __init__(self, path, query, namespace, auxiliary=None):
        super().__init__()
        self.path, self.query, self.namespace = path, query, namespace
        self.auxiliary = auxiliary
        self.cancelled = threading.Event()

    def cancel(self):
        self.cancelled.set()

    def run(self):
        connection = None
        try:
            if self.cancelled.is_set():
                return
            uri = Path(self.path).resolve().as_uri() + "?mode=ro"
            connection = sqlite3.connect(uri, uri=True, timeout=0.1)
            connection.row_factory = sqlite3.Row
            connection.set_progress_handler(lambda: int(self.cancelled.is_set()), 1000)
            # Counts and rows must describe the same database snapshot.
            connection.execute("BEGIN")
            options, summary = self.auxiliary or (None, None)
            if options is None:
                options = browser_filter_options(connection, self.namespace, self.query.products)
            snapshot = load_browser_snapshot(connection, self.query, cache_summary=summary)
            if not self.cancelled.is_set():
                self.ready.emit(snapshot, options, "")
        except (sqlite3.Error, OSError, ValueError) as exc:
            if not self.cancelled.is_set():
                self.ready.emit(None, None, str(exc))
        finally:
            if connection is not None:
                connection.close()


class BrowserSnapshotLoader:
    def __init__(self, window, path):
        self.window, self.path = window, path
        self.generation = 0
        self.pending = None
        self.pending_freshness = False
        self.applied_generation = 0
        self.applied_query = None
        self.auxiliary = OrderedDict()
        window.browser_snapshot_worker = None

    def _database_token(self):
        connection = self.window.server_cache
        return (
            connection.total_changes,
            connection.execute("PRAGMA data_version").fetchone()[0],
            connection.in_transaction,
        )

    def request(self, query):
        if getattr(self.window, "_shutting_down", False):
            return
        self.generation += 1
        self.pending = (self.generation, query)
        worker = self.window.browser_snapshot_worker
        if worker is not None:
            worker.cancel()
        else:
            self._start_pending()

    def _start_pending(self):
        if getattr(self.window, "_shutting_down", False):
            self.pending = None
            return
        if self.pending is None:
            return
        generation, query = self.pending
        self.pending = None
        token = self._database_token()
        namespace = "_experimental" if query.products == ("experimental",) else ""
        key = query.products, namespace
        cached = self.auxiliary.get(key)
        auxiliary = cached[1] if cached and cached[0] == token else None
        worker = BrowserSnapshotWorker(self.path, query, namespace, auxiliary)
        self.window.browser_snapshot_worker = worker
        worker.ready.connect(
            lambda snapshot, options, error: self._ready(
                generation, query, token, key, snapshot, options, error
            )
        )
        worker.finished.connect(lambda: self._finished(worker))
        worker.start()

    def _ready(self, generation, query, token, key, snapshot, options, error):
        window = self.window
        if (
            generation != self.generation
            or getattr(window, "_shutting_down", False)
            or window.current_browser_query() != query
        ):
            return
        if token != self._database_token():
            self.request(query)
            return
        if error:
            window.statusBar().showMessage(f"Could not refresh cached servers: {error}", 7000)
            return
        self.auxiliary[key] = token, (options, snapshot.cache_summary)
        self.auxiliary.move_to_end(key)
        while len(self.auxiliary) > 4:
            self.auxiliary.popitem(last=False)
        window.apply_browser_filter_options(options)
        # Removing a disappeared option can change the active filter. Query the
        # resulting controls rather than applying rows for the previous filter.
        if window.current_browser_query() != query:
            self.request(window.current_browser_query())
            return
        window.apply_browser_snapshot(snapshot)
        self.applied_generation = generation
        self.applied_query = query

    def _finished(self, worker):
        if self.window.browser_snapshot_worker is worker:
            self.window.browser_snapshot_worker = None
        worker.deleteLater()
        self._start_pending()
        if (
            not getattr(self.window, "_shutting_down", False)
            and self.window.browser_snapshot_worker is None
            and self.pending_freshness
            and self.applied_generation == self.generation
            and self.window.current_browser_query() == self.applied_query
        ):
            self.pending_freshness = False
            self.window.continue_initial_results_freshness_check()
