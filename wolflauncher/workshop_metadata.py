"""Bounded shared HTTP work and display-only Workshop metadata snapshots.

Completed revision/state evidence is never served from the display cache. A
forced recheck also bypasses requests already in flight (including pre-download
requests). The caller still owns all library-specific readiness decisions.
"""

import threading
import time
from collections import OrderedDict
from copy import deepcopy
from dataclasses import dataclass, field

from .http_client import HttpClientError

DISPLAY_FIELDS = ("title", "description", "preview_url", "file_size")


@dataclass
class _Flight:
    done: threading.Event = field(default_factory=threading.Event)
    result: dict = field(default_factory=dict)
    error: Exception | None = None


class WorkshopMetadataBroker:
    def __init__(self, *, max_entries=512, max_bytes=8 * 1024 * 1024, ttl=300):
        self.max_entries, self.max_bytes, self.ttl = max_entries, max_bytes, ttl
        self._condition = threading.Condition()
        self._slots = threading.BoundedSemaphore(4)
        self._flights = {}
        self._display = OrderedDict()
        self._display_bytes = 0
        self._active_items = 0

    @staticmethod
    def _guard(cancelled):
        if cancelled and cancelled():
            raise HttpClientError("cancelled", "Workshop metadata request cancelled")

    def display(self, ids):
        """Return copied presentation fields only; never timestamps or state."""
        now = time.monotonic()
        with self._condition:
            self._expire(now)
            result = {}
            for item in ids:
                if item in self._display:
                    self._display.move_to_end(item)
                    result[item] = deepcopy(self._display[item][1])
            return result

    def _expire(self, now):
        for item, (expires, _, size) in list(self._display.items()):
            if now >= expires:
                self._display_bytes -= size
                del self._display[item]

    def _remember(self, item, detail):
        if detail.get("result") != 1:
            return
        display = {key: detail[key] for key in DISPLAY_FIELDS if key in detail}
        size = len(item.encode("utf-8")) + sum(
            len(str(value).encode("utf-8")) for value in display.values()
        )
        if size > self.max_bytes:
            return
        old = self._display.pop(item, None)
        if old:
            self._display_bytes -= old[2]
        self._display[item] = (time.monotonic() + self.ttl, deepcopy(display), size)
        self._display_bytes += size
        while len(self._display) > self.max_entries or self._display_bytes > self.max_bytes:
            _, (_, _, removed_size) = self._display.popitem(last=False)
            self._display_bytes -= removed_size

    def fetch(self, ids, *, include_children, load, cancelled=None, force_refresh=False):
        """Coalesce overlapping item requests; each fresh call obtains live HTTP evidence.

        No threads are created here. Owners load synchronously in their existing
        worker; followers can cancel independently. A cancelled owner releases its
        followers to retry rather than poisoning their request or the cache.
        """
        pending = list(ids)
        result = {}
        while pending:
            self._guard(cancelled)
            owned, waiting = {}, {}
            with self._condition:
                self._expire(time.monotonic())
                for item in pending:
                    key = (item, include_children)
                    flight = self._flights.get(key)
                    if flight is not None and not force_refresh:
                        waiting[item] = flight
                    elif len(owned) < 100 and self._active_items < 400:
                        flight = _Flight()
                        self._flights[key] = owned[item] = flight
                        self._active_items += 1
                if not owned and not waiting:
                    self._condition.wait(0.05)
                    continue
            if owned:
                acquired = False
                try:
                    while not acquired:
                        self._guard(cancelled)
                        acquired = self._slots.acquire(timeout=0.05)
                    self._guard(cancelled)
                    details = load(tuple(owned))
                    self._guard(cancelled)
                    with self._condition:
                        for item, flight in owned.items():
                            flight.result = deepcopy(details.get(item, {}))
                            # Older forced-away owners cannot refresh cached data.
                            if self._flights.get((item, include_children)) is flight:
                                self._remember(item, flight.result)
                except Exception as exc:
                    for flight in owned.values():
                        flight.error = exc
                    raise
                finally:
                    if acquired:
                        self._slots.release()
                    with self._condition:
                        for item, flight in owned.items():
                            if self._flights.get((item, include_children)) is flight:
                                del self._flights[(item, include_children)]
                            self._active_items -= 1
                            flight.done.set()
                        self._condition.notify_all()
            retry = set()
            for item, flight in {**owned, **waiting}.items():
                while not flight.done.wait(0.05):
                    self._guard(cancelled)
                self._guard(cancelled)
                if flight.error:
                    if (
                        isinstance(flight.error, HttpClientError)
                        and flight.error.category == "cancelled"
                    ):
                        retry.add(item)
                        continue
                    raise flight.error
                if flight.result:
                    result[item] = deepcopy(flight.result)
            finished = (owned.keys() | waiting.keys()) - retry
            pending = [item for item in pending if item not in finished]
        return result


metadata_broker = WorkshopMetadataBroker()
