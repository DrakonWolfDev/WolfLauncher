import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path

from PySide6.QtCore import QThread, Signal

from . import server_cache
from .models import Server
from .mods import (
    WORKSHOP_URL,
    RequiredMod,
    apply_workshop_install_timestamps,
    apply_workshop_item_states,
    apply_workshop_metadata,
    cached_workshop_dependency_graphs,
    contribute_workshop_dependency_graph,
    check_server_mods,
    fetch_workshop_metadata,
    resolve_workshop_dependencies,
    scan_experimental_local_mods,
    scan_installed_mods,
    workshop_install_timestamps,
)
from .server_discovery import (
    WolfApiServerList,
    discover_wolfapi_v1_maps,
    discover_dayz_servers,
    discover_dayz_servers_battlemetrics,
    discover_dayz_servers_web_api,
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
        install = self.workshop_install
        installed_mods = (
            scan_experimental_local_mods(install.dayz_dir, self.workshop_dir)
            if install and install.product.experimental
            else None
        )
        result = check_server_mods(
            self.server, self.workshop_dir, self.steam_context, installed_mods
        )
        if self.include_metadata and result.ok and result.required_mods:
            apply_workshop_metadata(
                result,
                fetch_workshop_metadata(mod.workshop_id for mod in result.required_mods),
            )
            if install:
                apply_workshop_install_timestamps(result, workshop_install_timestamps(install))
        if result.ok and result.required_mods and install and install.running:
            states = query_workshop_item_states_isolated(
                (mod.workshop_id for mod in result.required_mods), install
            )
            if states.error:
                result.workshop_state_error = states.error
            else:
                apply_workshop_item_states(result, states.items)
        self.mods_ready.emit(result)


def load_installed_workshop_library(install) -> tuple[list[RequiredMod], str]:
    """Read local DayZ Workshop items and compare them with Steam's current state."""
    workshop_dir = getattr(install, "workshop_dir", None)
    installed = (
        scan_experimental_local_mods(getattr(install, "dayz_dir", None), workshop_dir)
        if getattr(getattr(install, "product", None), "experimental", False)
        else scan_installed_mods(workshop_dir)
    )
    mods = [
        RequiredMod(
            workshop_id=workshop_id,
            name=name,
            installed=True,
            installed_name=name,
            workshop_url=WORKSHOP_URL.format(mod_id=workshop_id),
        )
        for workshop_id, name in installed.items()
    ]
    if not mods:
        return [], ""
    metadata = fetch_workshop_metadata(mod.workshop_id for mod in mods)
    timestamps = workshop_install_timestamps(install)
    for mod in mods:
        detail = metadata.get(mod.workshop_id, {})
        mod.workshop_file_size = max(0, int(detail.get("file_size") or 0))
        mod.workshop_description = str(detail.get("description") or "").strip()
        mod.workshop_preview_url = str(detail.get("preview_url") or "").strip()
        mod.workshop_updated_at = max(0, int(detail.get("time_updated") or 0))
        mod.installed_updated_at = max(0, int(timestamps.get(mod.workshop_id, 0)))
    if not getattr(install, "running", False):
        return mods, "Start Steam to check live Workshop update/download state."
    states = query_workshop_item_states_isolated((mod.workshop_id for mod in mods), install)
    if states.error:
        return mods, states.error
    by_id = {item.workshop_id: item for item in states.items}
    for mod in mods:
        item = by_id.get(mod.workshop_id)
        if item:
            mod.workshop_state = item.state
            mod.workshop_downloaded = item.downloaded
            mod.workshop_total = item.total
    return mods, ""


class WorkshopLibraryWorker(QThread):
    library_ready = Signal(object, str)

    def __init__(self, install):
        super().__init__()
        self.install = install

    def run(self):
        try:
            mods, error = load_installed_workshop_library(self.install)
        except Exception as exc:
            mods, error = [], str(exc)
        self.library_ready.emit(mods, error)


class WorkshopDependencyWorker(QThread):
    """Resolve author-declared Workshop requirements away from the Qt thread."""

    dependencies_ready = Signal(object, object)

    def __init__(self, workshop_ids):
        super().__init__()
        self.workshop_ids = tuple(workshop_ids)

    def run(self):
        try:
            cached = cached_workshop_dependency_graphs(self.workshop_ids)
            graphs = cached[0] if cached is not None else {}
            resolved, metadata = [], {}
            for root in self.workshop_ids:
                if root in graphs:
                    graph_resolved, graph_metadata = graphs[root]
                else:
                    # Query only the cache miss. A new selection must not
                    # make a ready graph for an earlier selection vanish.
                    graph_resolved, graph_metadata = resolve_workshop_dependencies([root])
                    contribute_workshop_dependency_graph(root, graph_resolved, graph_metadata)
                for workshop_id in graph_resolved:
                    if workshop_id not in resolved:
                        resolved.append(workshop_id)
                metadata.update(graph_metadata)
        except Exception:
            # Dependency metadata is advisory. Keep the explicit selection
            # launchable if Steam's public endpoint is temporarily unavailable.
            resolved, metadata = self.workshop_ids, {}
        self.dependencies_ready.emit(resolved, metadata)


class WorkshopSubscriptionWorker(QThread):
    progress_ready = Signal(object)
    subscription_ready = Signal(object)

    def __init__(
        self,
        workshop_ids: list[str],
        install,
        *,
        force_update: bool = False,
        subscribe_missing: bool = True,
    ):
        super().__init__()
        self.workshop_ids = list(workshop_ids)
        self.install = install
        self.force_update = force_update
        self.subscribe_missing = subscribe_missing
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
                force_update=self.force_update,
                subscribe_missing=self.subscribe_missing,
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

    def __init__(self, max_batches: int = 1, master_addresses=None, app_id: int = 221100):
        super().__init__()
        self.max_batches = max_batches
        self.master_addresses = master_addresses
        self.app_id = app_id

    def run(self):
        try:
            servers = discover_dayz_servers(
                max_batches=self.max_batches,
                master_addresses=self.master_addresses,
                app_id=self.app_id,
            )
        except (OSError, ValueError) as exc:
            self.discovery_ready.emit([], str(exc))
        else:
            self.discovery_ready.emit(servers, "")


class SteamWebApiDiscoveryWorker(QThread):
    discovery_ready = Signal(object, str)

    def __init__(self, api_key: str, limit: int = 5000, app_id: int = 221100):
        super().__init__()
        self.api_key = api_key
        self.limit = limit
        self.app_id = app_id

    def run(self):
        try:
            servers = discover_dayz_servers_web_api(
                api_key=self.api_key, limit=self.limit, app_id=self.app_id
            )
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
        unflagged_only: bool = False,
        product: str = "stable",
    ):
        super().__init__()
        self.limit = limit
        self.automatic = automatic
        self.unflagged_only = unflagged_only
        self.product = product

    @property
    def provider_label(self) -> str:
        return "WolfAPI"

    def run(self):
        try:
            if self.unflagged_only:
                servers = discover_wolfapi_v1_pages(
                    self.limit, unflagged_only=True, product=self.product
                )
            else:
                servers = discover_wolfapi_v1_pages(self.limit, product=self.product)
        except Exception as exc:
            self.discovery_ready.emit([], str(exc))
        else:
            self.discovery_ready.emit(servers, "")


class WolfApiCacheMergeWorker(QThread):
    merge_ready = Signal(int, int, str)

    def __init__(self, cache_path: Path, servers, bounded_v1: bool, source: str = "wolfapi"):
        super().__init__()
        self.cache_path = Path(cache_path)
        self.servers = list(servers)
        self.bounded_v1 = bounded_v1
        self.source = source

    def run(self):
        connection = None
        try:
            connection = server_cache.connect(self.cache_path)
            if self.bounded_v1:
                inserted = server_cache.merge_source_servers(connection, self.source, self.servers)
                removed = 0
            else:
                inserted, removed = server_cache.sync_source_servers(
                    connection, self.source, self.servers
                )
        except Exception as exc:
            self.merge_ready.emit(0, 0, str(exc))
        else:
            self.merge_ready.emit(inserted, removed, "")
        finally:
            if connection is not None:
                connection.close()


def discover_wolfapi_v1_pages(
    limit: int, unflagged_only: bool = False, product: str = "stable"
) -> list:
    """Fetch bounded v1 pages in a background worker up to the user limit."""
    target = max(1, int(limit))
    servers = []
    directory_total = None
    offset = 0
    while len(servers) < target:
        page_limit = min(WOLFAPI_V1_PAGE_SIZE, target - len(servers))
        kwargs = {"limit": page_limit, "offset": offset, "product": product}
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
        product: str = "stable",
    ):
        super().__init__()
        self.query = " ".join(query.split())
        self.limit = limit
        self.map_name = map_name
        self.version = version
        self.unflagged_only = unflagged_only
        self.product = product

    def run(self):
        try:
            endpoint = parse_exact_server_endpoint(self.query)
            if endpoint is None:
                kwargs = {
                    "limit": self.limit,
                    "map_name": self.map_name,
                    "version": self.version,
                    "product": self.product,
                }
                if self.unflagged_only:
                    kwargs["unflagged_only"] = True
                servers = search_dayz_servers_wolfapi_v1(self.query, **kwargs)
            else:
                host, port = endpoint
                game_matches = resolve_dayz_server_wolfapi_v1(
                    host, game_port=port, product=self.product
                )
                query_matches = resolve_dayz_server_wolfapi_v1(
                    host, query_port=port, product=self.product
                )
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


class WolfApiMapWorker(QThread):
    """Fetch a bounded remote map slice even when the local cache has none."""

    map_ready = Signal(str, object, str)

    def __init__(
        self, map_name: str, limit: int = 500,
        unflagged_only: bool = False, product: str = "stable",
    ):
        super().__init__()
        self.map_name = " ".join(map_name.split())
        self.limit = max(1, min(int(limit), 500))
        self.unflagged_only = unflagged_only
        self.product = product

    def run(self):
        try:
            servers = discover_dayz_servers_wolfapi_v1(
                limit=self.limit,
                map_name=self.map_name,
                unflagged_only=self.unflagged_only,
                product=self.product,
            )
        except Exception as exc:
            self.map_ready.emit(self.map_name, [], str(exc))
        else:
            self.map_ready.emit(self.map_name, servers, "")


class WolfApiMapCatalogWorker(QThread):
    catalog_ready = Signal(object, str)

    def run(self):
        try:
            maps = discover_wolfapi_v1_maps()
        except Exception as exc:
            self.catalog_ready.emit([], str(exc))
        else:
            self.catalog_ready.emit(maps, "")


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
