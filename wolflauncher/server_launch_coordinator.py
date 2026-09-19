"""Resolve server launch requests off the GUI thread and reject stale callbacks."""

import threading
import uuid
from dataclasses import replace

from PySide6.QtCore import QThread, Signal
from PySide6.QtWidgets import QMessageBox

from .server_identity import endpoint_key, saved_server_fields
from .server_launch_context import IdentityResolutionError, resolve_context
from .settings import server_key


class IdentityWorker(QThread):
    ready = Signal(str, object, str)

    def __init__(self, server, request_id, steam_mode, engine):
        super().__init__()
        self.server, self.request_id = server, request_id
        self.steam_mode, self.engine = steam_mode, engine
        self.cancel_event = threading.Event()

    def cancel(self):
        self.cancel_event.set()
        self.requestInterruption()

    def run(self):
        try:
            context = resolve_context(
                self.server, self.request_id, self.steam_mode, self.engine, self.cancel_event
            )
            error = ""
        except IdentityResolutionError as exc:
            context, error = exc.resolved_server, str(exc)
        except Exception as exc:
            context, error = None, str(exc)
        if not self.cancel_event.is_set():
            self.ready.emit(self.request_id, context, error)


class ServerLaunchCoordinator:
    def __init__(self, window):
        self.window = window
        self.request_id = ""
        self.context = None
        window.identity_workers = {}
        window.context_mod_workers = {}
        self.mod_callbacks = {}
        self.pending_identity = None
        self.pending_mods = None

    def invalidate(self):
        self.request_id = ""
        self.context = None
        self.pending_identity = None
        self.mod_callbacks.clear()
        self.pending_mods = None
        for worker in self.window.context_mod_workers.values():
            worker.cancel()
        for worker in self.window.identity_workers.values():
            worker.cancel()
        preflight = getattr(self.window, "connect_preflight", None)
        if preflight is not None:
            preflight.invalidate()

    def current(self, context, *, require_fresh=True):
        return (
            context is not None
            and context.request_id == self.request_id
            and not getattr(self.window, "_shutting_down", False)
            and context.matches(self.window.active_server_context())
            and (not require_fresh or context.fresh())
        )

    def prepare(self, server, continuation, *, silent=False, force=False, engine_override=None):
        mode = self.window.native_steam_mode_key()
        engine = engine_override or self.window.launch_engine_key()
        context = self.context
        if (
            not force
            and self.current(context)
            and context.matches(server)
            and context.steam_mode == mode
            and context.engine == ("native" if context.product.experimental else engine)
        ):
            continuation(context)
            return
        self.invalidate()
        request_id = self.request_id = uuid.uuid4().hex
        worker = IdentityWorker(server, request_id, mode, engine)
        self.window.identity_workers[request_id] = worker
        self.window.statusBar().showMessage(f"Verifying the DayZ edition for {server.name}…")
        worker.ready.connect(
            lambda request, result, error: self._ready(
                request, server, result, error, continuation, silent
            )
        )
        worker.finished.connect(lambda: self.window.identity_workers.pop(request_id, None))
        self._start_identity(worker, request_id)

    def _start_identity(self, worker, worker_key):
        if len(self.window.identity_workers) > 2:
            self.window.identity_workers.pop(worker_key, None)
            self.pending_identity = (worker, worker_key)
            return
        worker.finished.connect(self._run_pending_identity)
        worker.start()

    def _run_pending_identity(self):
        if getattr(self.window, "_shutting_down", False):
            self.pending_identity = None
            return
        pending = self.pending_identity
        if pending and len(self.window.identity_workers) < 2:
            worker, key = pending
            self.pending_identity = None
            if worker.request_id == self.request_id:
                self.window.identity_workers[key] = worker
                self._start_identity(worker, key)

    def check_mods(self, context, continuation, *, force=False):
        from .workers import ModWorker

        if not self.current(context, require_fresh=False):
            return
        cached = getattr(self.window, "last_mod_result", None)
        if (
            not force
            and cached is not None
            and cached.ok
            and cached.request_id == context.request_id
            and cached.launch_context_key == context.mod_context_key
        ):
            continuation(cached)
            return
        request = context.request_id
        if request in self.window.context_mod_workers:
            self.mod_callbacks.setdefault(request, []).append(continuation)
            return
        if len(self.window.context_mod_workers) >= 2:
            self.pending_mods = (context, continuation, force)
            return
        self.mod_callbacks[request] = [continuation]
        worker = ModWorker(
            context.server,
            context.install.workshop_dir,
            f"{context.product.label}: {context.install.dayz_dir}",
            workshop_install=context.install,
            launch_context=context,
        )
        self.window.context_mod_workers[request] = worker

        def ready(result):
            callbacks = self.mod_callbacks.pop(request, [])
            if not self.current(context, require_fresh=False):
                return
            if result.request_id != request or result.launch_context_key != context.mod_context_key:
                return
            self.window.last_mod_result = result
            self.window.display_mods_result(result)
            for callback in callbacks:
                callback(result)

        worker.mods_ready.connect(ready)
        worker.finished.connect(lambda: self._mod_finished(request))
        worker.start()

    def _mod_finished(self, request):
        self.window.context_mod_workers.pop(request, None)
        if self.pending_mods is not None:
            context, continuation, force = self.pending_mods
            self.pending_mods = None
            self.check_mods(context, continuation, force=force)

    def revalidate(self, context, continuation):
        if not self.current(context, require_fresh=False):
            return
        if context.fresh():
            continuation(context)
            return
        worker_key = uuid.uuid4().hex
        worker = IdentityWorker(
            context.server, context.request_id, context.steam_mode, context.engine
        )
        self.window.identity_workers[worker_key] = worker

        def ready(request, refreshed, error):
            if request != self.request_id or not self.current(context, require_fresh=False):
                return
            if error or refreshed.mod_context_key != context.mod_context_key:
                self.invalidate()
                QMessageBox.warning(
                    self.window,
                    "Server needs a new check",
                    error
                    or "The server edition or installation changed. Retry Join to check its mods again.",
                )
                return
            refreshed = replace(refreshed, original_endpoint=context.original_endpoint)
            self.context = refreshed
            continuation(refreshed)

        worker.ready.connect(ready)
        worker.finished.connect(lambda: self.window.identity_workers.pop(worker_key, None))
        self._start_identity(worker, worker_key)

    def _ready(self, request_id, original, context, error, continuation, silent):
        window = self.window
        current = window.active_server_context()
        if (
            request_id != self.request_id
            or getattr(window, "_shutting_down", False)
            or current is None
            or endpoint_key(current) != endpoint_key(original)
        ):
            return
        if error:
            self.context = None
            if context is not None:
                self._save_identity(original, context)
            window.statusBar().showMessage(error, 15000)
            if hasattr(window, "mod_readiness"):
                window.mod_readiness.setText(error)
            if not silent:
                QMessageBox.warning(window, "Could not prepare server", error)
            return
        self.context = context
        self._save_identity(original, context.server)
        continuation(context)

    def _save_identity(self, original, resolved):
        window = self.window
        # Persist historical identity without rewriting a hostname to a transient IP.
        updated = replace(original, **saved_server_fields(resolved))
        repository = getattr(window, "saved_server_repository", None)
        if repository is not None:
            try:
                if repository.update(original, updated):
                    for index, saved in enumerate(window.servers):
                        if endpoint_key(saved) == endpoint_key(original):
                            window.servers[index] = replace(saved, **saved_server_fields(updated))
                    window.favourites = {server_key(s) for s in window.servers if s.favourite}
                    window.refresh_curated_server_cards()
            except (OSError, ValueError) as exc:
                window.statusBar().showMessage(
                    f"Identity verified; could not save it: {exc}", 10000
                )
        if getattr(window, "active_discovered_server", None) is not None:
            window.active_discovered_server = updated
