from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone

from PySide6.QtCore import QThread, Signal

from .models import Server
from .mods import check_server_mods
from .server_discovery import (
    discover_dayz_servers,
    discover_dayz_servers_battlemetrics,
    discover_dayz_servers_web_api,
    discover_dayz_servers_wolfapi,
)
from .server_enrichment import enrich_discovered_server, enrichment_probe_servers
from .status import ServerStatus, check_server


MAX_STATUS_WORKERS = 8


def _checked_server_status(server: Server) -> ServerStatus:
    try:
        return check_server(server)
    except Exception as exc:
        return ServerStatus(False, error=f"status check failed: {exc}")


class StatusWorker(QThread):
    status_ready = Signal(int, object)
    finished_all = Signal()

    def __init__(self, servers: list[Server], rows: list[int] | None = None):
        super().__init__()
        if rows is None:
            self.servers = list(enumerate(servers))
        else:
            self.servers = [(row, servers[row]) for row in rows if 0 <= row < len(servers)]

    def run(self):
        if not self.servers:
            self.finished_all.emit()
            return

        max_workers = min(MAX_STATUS_WORKERS, len(self.servers))
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {
                executor.submit(_checked_server_status, server): index
                for index, server in self.servers
            }
            for future in as_completed(futures):
                self.status_ready.emit(futures[future], future.result())
        self.finished_all.emit()


class ModWorker(QThread):
    mods_ready = Signal(object)

    def __init__(self, server: Server, workshop_dir, steam_context: str = ""):
        super().__init__()
        self.server = server
        self.workshop_dir = workshop_dir
        self.steam_context = steam_context

    def run(self):
        self.mods_ready.emit(check_server_mods(self.server, self.workshop_dir, self.steam_context))


class SteamDiscoveryWorker(QThread):
    discovery_ready = Signal(object, str)

    def __init__(self, max_batches: int = 1, master_addresses=None):
        super().__init__()
        self.max_batches = max_batches
        self.master_addresses = master_addresses

    def run(self):
        try:
            servers = discover_dayz_servers(
                max_batches=self.max_batches,
                master_addresses=self.master_addresses,
            )
        except (OSError, ValueError) as exc:
            self.discovery_ready.emit([], str(exc))
        else:
            self.discovery_ready.emit(servers, "")


class SteamWebApiDiscoveryWorker(QThread):
    discovery_ready = Signal(object, str)

    def __init__(self, api_key: str, limit: int = 5000):
        super().__init__()
        self.api_key = api_key
        self.limit = limit

    def run(self):
        try:
            servers = discover_dayz_servers_web_api(api_key=self.api_key, limit=self.limit)
        except Exception as exc:
            self.discovery_ready.emit([], str(exc))
        else:
            self.discovery_ready.emit(servers, "")


class BattleMetricsDiscoveryWorker(QThread):
    discovery_ready = Signal(object, str)

    def __init__(self, limit: int = 500, page_delay: float = 0.0, automatic: bool = False):
        super().__init__()
        self.limit = limit
        self.page_delay = page_delay
        self.automatic = automatic

    def run(self):
        try:
            servers = discover_dayz_servers_battlemetrics(limit=self.limit, page_delay=self.page_delay)
        except Exception as exc:
            self.discovery_ready.emit([], str(exc))
        else:
            self.discovery_ready.emit(servers, "")


class WolfApiDiscoveryWorker(QThread):
    discovery_ready = Signal(object, str)

    def __init__(self, limit: int = 10000, automatic: bool = False):
        super().__init__()
        self.limit = limit
        self.automatic = automatic

    def run(self):
        try:
            servers = discover_dayz_servers_wolfapi(limit=self.limit)
        except Exception as exc:
            self.discovery_ready.emit([], str(exc))
        else:
            self.discovery_ready.emit(servers, "")


class ServerEnrichmentWorker(QThread):
    enrichment_ready = Signal(object, str)

    def __init__(self, servers):
        super().__init__()
        self.servers = servers

    def run(self):
        checked_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
        enriched = []
        try:
            for server in self.servers:
                status = ServerStatus(False, error="No valid query ports to probe.")
                for probe in enrichment_probe_servers(server):
                    status = check_server(probe)
                    if status.online:
                        break
                enriched.append(enrich_discovered_server(server, status, checked_at))
        except Exception as exc:
            self.enrichment_ready.emit(enriched, str(exc))
        else:
            self.enrichment_ready.emit(enriched, "")
