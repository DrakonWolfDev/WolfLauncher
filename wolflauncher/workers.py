import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path

from PySide6.QtCore import QThread, Signal

from . import server_cache
from .models import Server
from .mods import (
    apply_workshop_item_states,
    apply_workshop_metadata,
    check_server_mods,
    fetch_workshop_metadata,
)
from .server_discovery import (
    WolfApiServerList,
    discover_dayz_servers,
    discover_dayz_servers_battlemetrics,
    discover_dayz_servers_web_api,
    discover_dayz_servers_wolfapi,
    discover_dayz_servers_wolfapi_v1,
    parse_exact_server_endpoint,
    resolve_dayz_server_wolfapi_v1,
    search_dayz_servers_wolfapi_v1,
)
from .server_enrichment import enrich_discovered_server, enrichment_probe_servers
from .status import ServerStatus, check_server
from .workshop_subscription import (
    WorkshopSubscriptionResult,
    query_workshop_item_states_isolated,
    subscribe_workshop_items_isolated,
)

MAX_STATUS_WORKERS = 8
MAX_ENRICHMENT_WORKERS = 8
WOLFAPI_V1_PAGE_SIZE = 100


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

    def __init__(
        self,
        server: Server,
        workshop_dir,
        steam_context: str = "",
        workshop_install=None,
        include_metadata: bool = True,
    ):
        super().__init__()
        self.server = server
        self.workshop_dir = workshop_dir
        self.steam_context = steam_context
        self.workshop_install = workshop_install
        self.include_metadata = include_metadata

    def run(self):
        result = check_server_mods(self.server, self.workshop_dir, self.steam_context)
        if self.include_metadata and result.ok and result.required_mods:
            apply_workshop_metadata(
                result,
                fetch_workshop_metadata(mod.workshop_id for mod in result.required_mods),
            )
        if result.ok and result.required_mods and self.workshop_install:
            states = query_workshop_item_states_isolated(
                (mod.workshop_id for mod in result.required_mods), self.workshop_install
            )
            if states.error:
                result.workshop_state_error = states.error
            else:
                apply_workshop_item_states(result, states.items)
        self.mods_ready.emit(result)


class WorkshopSubscriptionWorker(QThread):
    progress_ready = Signal(object)
    subscription_ready = Signal(object)

    def __init__(self, workshop_ids: list[str], install):
        super().__init__()
        self.workshop_ids = list(workshop_ids)
        self.install = install
        self._cancelled = threading.Event()

    def cancel(self):
        self._cancelled.set()

    def run(self):
        try:
            result = subscribe_workshop_items_isolated(
                self.workshop_ids,
                self.install,
                progress_callback=self.progress_ready.emit,
                cancelled=self._cancelled,
            )
        except Exception as exc:
            result = WorkshopSubscriptionResult((), tuple(self.workshop_ids), error=str(exc))
        self.subscription_ready.emit(result)


class WorkshopStateWorker(QThread):
    state_ready = Signal(object)

    def __init__(self, workshop_ids, install):
        super().__init__()
        self.workshop_ids = tuple(workshop_ids)
        self.install = install

    def run(self):
        self.state_ready.emit(query_workshop_item_states_isolated(self.workshop_ids, self.install))


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
            servers = discover_dayz_servers_battlemetrics(
                limit=self.limit, page_delay=self.page_delay
            )
        except Exception as exc:
            self.discovery_ready.emit([], str(exc))
        else:
            self.discovery_ready.emit(servers, "")


class WolfApiDiscoveryWorker(QThread):
    discovery_ready = Signal(object, str)

    def __init__(
        self,
        limit: int = 10000,
        automatic: bool = False,
        use_v1: bool = False,
        unflagged_only: bool = False,
    ):
        super().__init__()
        self.limit = limit
        self.automatic = automatic
        self.use_v1 = use_v1
        self.unflagged_only = unflagged_only

    @property
    def provider_label(self) -> str:
        return "WolfAPI v1" if self.use_v1 else "WolfAPI legacy"

    def run(self):
        try:
            if self.use_v1:
                if self.unflagged_only:
                    servers = discover_wolfapi_v1_pages(self.limit, unflagged_only=True)
                else:
                    servers = discover_wolfapi_v1_pages(self.limit)
            else:
                servers = discover_dayz_servers_wolfapi(limit=self.limit)
        except Exception as exc:
            self.discovery_ready.emit([], str(exc))
        else:
            self.discovery_ready.emit(servers, "")


class WolfApiCacheMergeWorker(QThread):
    merge_ready = Signal(int, int, str)

    def __init__(self, cache_path: Path, servers, bounded_v1: bool):
        super().__init__()
        self.cache_path = Path(cache_path)
        self.servers = list(servers)
        self.bounded_v1 = bounded_v1

    def run(self):
        connection = None
        try:
            connection = server_cache.connect(self.cache_path)
            if self.bounded_v1:
                inserted = server_cache.merge_source_servers(connection, "wolfapi", self.servers)
                removed = 0
            else:
                inserted, removed = server_cache.sync_source_servers(
                    connection, "wolfapi", self.servers
                )
        except Exception as exc:
            self.merge_ready.emit(0, 0, str(exc))
        else:
            self.merge_ready.emit(inserted, removed, "")
        finally:
            if connection is not None:
                connection.close()


def discover_wolfapi_v1_pages(limit: int, unflagged_only: bool = False) -> list:
    """Fetch bounded v1 pages in a background worker up to the user limit."""
    target = max(1, int(limit))
    servers = []
    directory_total = None
    offset = 0
    while len(servers) < target:
        page_limit = min(WOLFAPI_V1_PAGE_SIZE, target - len(servers))
        kwargs = {"limit": page_limit, "offset": offset}
        if unflagged_only:
            kwargs["unflagged_only"] = True
        page = discover_dayz_servers_wolfapi_v1(**kwargs)
        if getattr(page, "directory_total", None) is not None:
            directory_total = page.directory_total
        servers.extend(page)
        if len(page) < page_limit:
            break
        offset += len(page)
    return WolfApiServerList(servers[:target], directory_total=directory_total)


class WolfApiSearchWorker(QThread):
    search_ready = Signal(str, object, str)

    def __init__(
        self,
        query: str,
        limit: int = 100,
        map_name: str = "",
        version: str = "",
        unflagged_only: bool = False,
    ):
        super().__init__()
        self.query = " ".join(query.split())
        self.limit = limit
        self.map_name = map_name
        self.version = version
        self.unflagged_only = unflagged_only

    def run(self):
        try:
            endpoint = parse_exact_server_endpoint(self.query)
            if endpoint is None:
                kwargs = {
                    "limit": self.limit,
                    "map_name": self.map_name,
                    "version": self.version,
                }
                if self.unflagged_only:
                    kwargs["unflagged_only"] = True
                servers = search_dayz_servers_wolfapi_v1(self.query, **kwargs)
            else:
                host, port = endpoint
                game_matches = resolve_dayz_server_wolfapi_v1(host, game_port=port)
                query_matches = resolve_dayz_server_wolfapi_v1(host, query_port=port)
                directory_total = getattr(game_matches, "directory_total", None)
                if directory_total is None:
                    directory_total = getattr(query_matches, "directory_total", None)
                resolved = [*game_matches, *query_matches]
                servers = WolfApiServerList(directory_total=directory_total)
                seen = set()
                for server in resolved:
                    identity = server.stable_server_id or server.cache_key
                    if identity in seen:
                        continue
                    seen.add(identity)
                    servers.append(server)
        except Exception as exc:
            self.search_ready.emit(self.query, [], str(exc))
        else:
            self.search_ready.emit(self.query, servers, "")


class ServerEnrichmentWorker(QThread):
    enrichment_ready = Signal(object, str)
    enrichment_progress = Signal(object, int, int)

    def __init__(self, servers, probe_fallbacks: bool = True):
        super().__init__()
        self.servers = servers
        self.probe_fallbacks = probe_fallbacks
        self._cancel_event = threading.Event()

    def cancel(self):
        self._cancel_event.set()
        self.requestInterruption()

    def run(self):
        checked_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
        enriched = []
        total = len(self.servers)

        def enrich_one(server):
            if self._cancel_event.is_set():
                return None
            try:
                status = ServerStatus(False, error="No valid query ports to probe.")
                probes = enrichment_probe_servers(server)
                if not self.probe_fallbacks:
                    probes = probes[:1]
                for probe in probes:
                    status = check_server(
                        probe,
                        socket_timeout_ms=750 if not self.probe_fallbacks else 1500,
                        process_timeout=2 if not self.probe_fallbacks else 5,
                        cancel_event=self._cancel_event if not self.probe_fallbacks else None,
                    )
                    if self._cancel_event.is_set():
                        return None
                    if status.online:
                        break
            except Exception as exc:
                status = ServerStatus(False, error=f"live check failed: {exc}")
            return enrich_discovered_server(server, status, checked_at)

        max_workers = min(MAX_ENRICHMENT_WORKERS, total) if total else 1
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            for completed, (original, server) in enumerate(
                zip(self.servers, executor.map(enrich_one, self.servers)), 1
            ):
                if server is None:
                    continue
                enriched.append(server)
                self.enrichment_progress.emit((original.cache_key, server), completed, total)
        self.enrichment_ready.emit(enriched, "")
