"""Cache display names against current file identity, never installed readiness."""

import threading
from collections import OrderedDict


class ModNameCache:
    def __init__(self, max_entries=1024):
        self.max_entries = max_entries
        self._lock = threading.Lock()
        self._entries = OrderedDict()

    @staticmethod
    def _identity(path):
        info = path.stat()
        return info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns, info.st_ctime_ns

    def read(self, path, reader):
        try:
            key, before = str(path.absolute()), self._identity(path)
            with self._lock:
                cached = self._entries.get(key)
                if cached and cached[0] == before:
                    self._entries.move_to_end(key)
                    return cached[1]
            value = reader(path)
            if self._identity(path) != before:
                return ""
            # Limit retained name payload to 8 KiB per entry. Larger names may
            # still be displayed, but are not retained in the bounded cache.
            if len(value.encode("utf-8")) <= 8192:
                with self._lock:
                    self._entries[key] = before, value
                    self._entries.move_to_end(key)
                    while len(self._entries) > self.max_entries:
                        self._entries.popitem(last=False)
            return value
        except OSError:
            return ""


mod_name_cache = ModNameCache()
