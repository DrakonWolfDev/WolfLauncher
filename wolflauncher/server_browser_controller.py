from dataclasses import dataclass
from typing import Any

from . import server_cache
from .models import DiscoveredServer
from .server_display import display_map_name


@dataclass(frozen=True)
class BrowserQuery:
    text: str = ""
    online_only: bool = False
    map_name: str = ""
    version: str = ""
    source: str = ""
    style_terms: tuple[str, ...] = ()
    modded: bool | None = None
    hide_quality_flagged: bool = False
    sort_by: str = "name"
    descending: bool = False
    limit: int = 200


@dataclass(frozen=True)
class BrowserSnapshot:
    servers: list[DiscoveredServer]
    match_count: int
    cache_summary: dict[str, int]


def load_browser_snapshot(connection: Any, query: BrowserQuery) -> BrowserSnapshot:
    filters = {
        "text": query.text,
        "online_only": query.online_only,
        "map_name": query.map_name,
        "version": query.version,
        "source": query.source,
        "style_terms": list(query.style_terms),
        "modded": query.modded,
        "hide_quality_flagged": query.hide_quality_flagged,
    }
    servers = server_cache.search_servers(
        connection,
        **filters,
        sort_by=query.sort_by,
        descending=query.descending,
        limit=query.limit,
    )
    return BrowserSnapshot(
        servers=servers,
        match_count=server_cache.count_search_servers(connection, **filters),
        cache_summary=server_cache.cache_summary(connection),
    )


def browser_filter_options(connection: Any) -> dict[str, list[str]]:
    map_labels = {}
    for value in server_cache.distinct_values(connection, "map"):
        label = display_map_name(value)
        if label:
            map_labels.setdefault(label.casefold(), label)
    return {
        "map": sorted(map_labels.values(), key=str.casefold),
        "version": server_cache.distinct_values(connection, "version"),
        "source": server_cache.distinct_values(connection, "source"),
    }
