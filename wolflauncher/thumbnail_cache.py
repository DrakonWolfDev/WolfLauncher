"""GUI-thread-only bounded storage for validated Workshop previews."""

import time
from collections import OrderedDict


class ThumbnailCache:
    def __init__(self, *, max_bytes=16 * 1024 * 1024, max_entries=32, ttl=300):
        self.max_bytes, self.max_entries, self.ttl = max_bytes, max_entries, ttl
        self.entries = OrderedDict()
        self.bytes = 0

    def get(self, key):
        self._expire()
        entry = self.entries.get(key)
        if entry is None:
            return None
        self.entries.move_to_end(key)
        return entry[1]

    def put(self, key, pixmap):
        self._expire()
        size = pixmap.width() * pixmap.height() * max(1, (pixmap.depth() + 7) // 8)
        if pixmap.isNull() or size > self.max_bytes:
            return
        old = self.entries.pop(key, None)
        if old:
            self.bytes -= old[2]
        self.entries[key] = (time.monotonic() + self.ttl, pixmap.copy(), size)
        self.bytes += size
        while len(self.entries) > self.max_entries or self.bytes > self.max_bytes:
            _, (_, _, size) = self.entries.popitem(last=False)
            self.bytes -= size

    def _expire(self):
        now = time.monotonic()
        for key, (expires, _, size) in list(self.entries.items()):
            if now >= expires:
                del self.entries[key]
                self.bytes -= size
