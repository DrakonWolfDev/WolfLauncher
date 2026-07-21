from __future__ import annotations

import json
import os
import socket
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timezone

from .models import DiscoveredServer

DAYZ_APP_ID = 221100
STEAM_WEB_API_SERVER_LIST_URL = "https://api.steampowered.com/IGameServersService/GetServerList/v1/"
BATTLEMETRICS_SERVER_LIST_URL = "https://api.battlemetrics.com/servers"
WOLFAPI_SERVER_LIST_URL = "https://api.drakonwolf.ddns.net/api/servers"
WOLFAPI_V1_SERVER_LIST_URL = "https://api.drakonwolf.ddns.net/api/v1/servers"
WOLFAPI_V1_SEARCH_URL = f"{WOLFAPI_V1_SERVER_LIST_URL}/search"
WOLFAPI_V1_RESOLVE_URL = f"{WOLFAPI_V1_SERVER_LIST_URL}/resolve"
MASTER_SERVER_HOST = "hl2master.steampowered.com"
MASTER_SERVER_HOSTS = [
    MASTER_SERVER_HOST,
    "hl2master.steamcontent.com",
]
MASTER_SERVER_PORT = 27011
MASTER_RESPONSE_HEADER = b"\xff\xff\xff\xfff\n"
REGION_ALL = 0xFF


@dataclass(frozen=True)
class MasterServerAddress:
    host: str
    port: int = MASTER_SERVER_PORT

    @property
    def address(self) -> str:
        return f"{self.host}:{self.port}"


@dataclass(frozen=True)
class MasterServerEndpoint:
    host: str
    port: int

    @property
    def address(self) -> str:
        return f"{self.host}:{self.port}"


class SteamMasterServerError(OSError):
    pass


class SteamWebApiError(RuntimeError):
    pass


class BattleMetricsError(RuntimeError):
    pass


class WolfApiError(RuntimeError):
    pass


class WolfApiServerList(list):
    """Server rows plus the whole-directory size reported by WolfAPI v1."""

    def __init__(self, servers=(), *, directory_total: int | None = None):
        super().__init__(servers)
        self.directory_total = directory_total


def build_master_server_request(
    start_address: str = "0.0.0.0:0",
    app_id: int = DAYZ_APP_ID,
    region: int = REGION_ALL,
    extra_filter: str = "",
) -> bytes:
    filters = f"\\appid\\{app_id}{extra_filter}"
    return (
        b"1"
        + bytes([region])
        + start_address.encode("ascii")
        + b"\0"
        + filters.encode("ascii")
        + b"\0"
    )


def parse_master_server_response(packet: bytes) -> tuple[list[MasterServerEndpoint], bool]:
    if not packet.startswith(MASTER_RESPONSE_HEADER):
        raise ValueError("Invalid Steam master server response header.")

    endpoints = []
    complete = False
    offset = len(MASTER_RESPONSE_HEADER)
    while offset + 6 <= len(packet):
        host_bytes = packet[offset : offset + 4]
        port_bytes = packet[offset + 4 : offset + 6]
        offset += 6
        host = ".".join(str(part) for part in host_bytes)
        port = int.from_bytes(port_bytes, "big")
        if host == "0.0.0.0" and port == 0:
            complete = True
            break
        endpoints.append(MasterServerEndpoint(host, port))
    return endpoints, complete


def query_master_server_batch(
    start_address: str = "0.0.0.0:0",
    app_id: int = DAYZ_APP_ID,
    timeout: float = 5.0,
    master_host: str = MASTER_SERVER_HOST,
    master_port: int = MASTER_SERVER_PORT,
    extra_filter: str = "",
) -> tuple[list[MasterServerEndpoint], bool]:
    request = build_master_server_request(
        start_address=start_address,
        app_id=app_id,
        extra_filter=extra_filter,
    )
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
        sock.settimeout(timeout)
        sock.sendto(request, (master_host, master_port))
        packet, _address = sock.recvfrom(65535)
    return parse_master_server_response(packet)


def discover_dayz_servers(
    max_batches: int = 10,
    timeout: float = 5.0,
    master_host: str = "",
    master_port: int = MASTER_SERVER_PORT,
    master_addresses: list[MasterServerAddress] | None = None,
    extra_filter: str = "",
) -> list[DiscoveredServer]:
    addresses = _configured_master_addresses(master_host, master_port, master_addresses)
    errors = []
    for address in addresses:
        try:
            return _discover_dayz_servers_from_master(
                max_batches=max_batches,
                timeout=timeout,
                master_host=address.host,
                master_port=address.port,
                extra_filter=extra_filter,
            )
        except OSError as exc:
            errors.append(f"{address.address} -> {exc}")

    raise SteamMasterServerError(
        "Steam master discovery failed for all configured hosts: " + "; ".join(errors)
    )


def parse_master_address(value: str, default_port: int = MASTER_SERVER_PORT) -> MasterServerAddress:
    value = value.strip()
    if not value:
        raise ValueError("Steam master address cannot be empty.")
    if ":" not in value:
        return MasterServerAddress(value, default_port)
    host, port_text = value.rsplit(":", 1)
    host = host.strip()
    if not host:
        raise ValueError("Steam master address host cannot be empty.")
    try:
        port = int(port_text)
    except ValueError as exc:
        raise ValueError(f"Invalid Steam master port: {port_text!r}.") from exc
    if port <= 0 or port > 65535:
        raise ValueError(f"Invalid Steam master port: {port}.")
    return MasterServerAddress(host, port)


def _configured_master_addresses(
    master_host: str = "",
    master_port: int = MASTER_SERVER_PORT,
    master_addresses: list[MasterServerAddress] | None = None,
) -> list[MasterServerAddress]:
    if master_addresses:
        return master_addresses

    endpoints = os.environ.get("WOLFLAUNCHER_STEAM_MASTER_ENDPOINTS", "")
    if endpoints:
        return [
            parse_master_address(item, master_port) for item in endpoints.split(",") if item.strip()
        ]

    configured_host = master_host or os.environ.get("WOLFLAUNCHER_STEAM_MASTER_HOST", "")
    configured_port = int(os.environ.get("WOLFLAUNCHER_STEAM_MASTER_PORT", master_port))
    if configured_host:
        return [MasterServerAddress(configured_host, configured_port)]

    return [MasterServerAddress(host, master_port) for host in MASTER_SERVER_HOSTS]


def _discover_dayz_servers_from_master(
    max_batches: int = 10,
    timeout: float = 5.0,
    master_host: str = MASTER_SERVER_HOST,
    master_port: int = MASTER_SERVER_PORT,
    extra_filter: str = "",
) -> list[DiscoveredServer]:
    endpoints: list[MasterServerEndpoint] = []
    start_address = "0.0.0.0:0"

    for _index in range(max_batches):
        batch, complete = query_master_server_batch(
            start_address=start_address,
            timeout=timeout,
            master_host=master_host,
            master_port=master_port,
            extra_filter=extra_filter,
        )
        if not batch:
            break
        endpoints.extend(batch)
        start_address = batch[-1].address
        if complete:
            break

    seen = set()
    servers = []
    now = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    for endpoint in endpoints:
        if endpoint.address in seen:
            continue
        seen.add(endpoint.address)
        servers.append(discovered_server_from_endpoint(endpoint, now))
    return servers


def discovered_server_from_endpoint(
    endpoint: MasterServerEndpoint, timestamp: str = ""
) -> DiscoveredServer:
    return DiscoveredServer(
        name=endpoint.address,
        source="steam_master",
        host=endpoint.host,
        game_port=endpoint.port,
        query_port=endpoint.port,
        last_seen=timestamp,
    )


def _required_mod_count(row: dict) -> int | None:
    for key in ("required_mod_count", "requiredModCount", "mod_count", "mods_count"):
        value = _optional_int(row.get(key))
        if value is not None and value >= 0:
            return value
    mods = row.get("required_mods") or row.get("requiredMods") or row.get("mods")
    return len(mods) if isinstance(mods, list) else None


def discover_dayz_servers_web_api(
    api_key: str = "",
    limit: int = 5000,
    timeout: float = 15.0,
    filter_text: str = "",
) -> list[DiscoveredServer]:
    api_key = (
        api_key
        or os.environ.get("WOLFLAUNCHER_STEAM_WEB_API_KEY", "")
        or os.environ.get("STEAM_WEB_API_KEY", "")
    )
    if not api_key:
        raise SteamWebApiError("Steam Web API key is required.")

    params = {
        "key": api_key,
        "limit": str(limit),
        "filter": filter_text or f"\\appid\\{DAYZ_APP_ID}",
    }
    url = f"{STEAM_WEB_API_SERVER_LIST_URL}?{urllib.parse.urlencode(params)}"
    request = urllib.request.Request(url, headers={"User-Agent": "WolfLauncher/0.6"})

    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            payload = response.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as exc:
        raise SteamWebApiError(f"Steam Web API HTTP error: {exc.code}") from exc
    except urllib.error.URLError as exc:
        raise SteamWebApiError(f"Steam Web API connection failed: {exc.reason}") from exc
    except TimeoutError as exc:
        raise SteamWebApiError("Steam Web API timed out") from exc

    try:
        data = json.loads(payload)
    except json.JSONDecodeError as exc:
        raise SteamWebApiError("Steam Web API returned invalid JSON") from exc

    return parse_steam_web_api_servers(data)


def parse_steam_web_api_servers(data: dict) -> list[DiscoveredServer]:
    response = data.get("response", {}) if isinstance(data, dict) else {}
    rows = response.get("servers", []) if isinstance(response, dict) else []
    if not isinstance(rows, list):
        raise SteamWebApiError("Steam Web API response did not contain a server list.")

    now = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    servers = []
    seen = set()
    for row in rows:
        if not isinstance(row, dict):
            continue
        server = discovered_server_from_web_api_row(row, now)
        if not server or server.cache_key in seen:
            continue
        seen.add(server.cache_key)
        servers.append(server)
    return servers


def discovered_server_from_web_api_row(row: dict, timestamp: str = "") -> DiscoveredServer | None:
    host, query_port = _host_port_from_addr(str(row.get("addr") or ""))
    if not host:
        host = str(row.get("ip") or row.get("host") or "").strip()
    if not host:
        return None

    game_port = _optional_int(row.get("gameport")) or query_port
    if game_port is None:
        return None
    if query_port is None:
        query_port = game_port

    name = str(row.get("name") or f"{host}:{game_port}")
    players_current = _optional_int(row.get("players"))
    players_max = _optional_int(row.get("max_players") or row.get("maxplayers"))
    gametype = str(row.get("gametype") or "")

    return DiscoveredServer(
        name=name,
        source="steam_web_api",
        server_name=name,
        host=host,
        game_port=game_port,
        query_port=query_port,
        map_name=str(row.get("map") or ""),
        players_current=players_current,
        players_max=players_max,
        version=str(row.get("version") or ""),
        password=bool(row.get("password", False)),
        modded="mod" in gametype.lower(),
        online=True,
        last_checked=timestamp,
        last_seen=timestamp,
        required_mod_count=_required_mod_count(row),
    )


def discover_dayz_servers_battlemetrics(
    limit: int = 500,
    timeout: float = 15.0,
    search: str = "",
    page_delay: float = 0.0,
) -> list[DiscoveredServer]:
    limit = max(1, int(limit))
    page_size = min(limit, 100)
    params = {
        "filter[game]": "dayz",
        "page[size]": str(page_size),
    }
    if search:
        params["filter[search]"] = search
    url = f"{BATTLEMETRICS_SERVER_LIST_URL}?{urllib.parse.urlencode(params)}"

    servers = []
    seen = set()
    while url and len(servers) < limit:
        data = fetch_battlemetrics_page(url, timeout)
        for server in parse_battlemetrics_servers(data):
            if server.cache_key in seen:
                continue
            seen.add(server.cache_key)
            servers.append(server)
            if len(servers) >= limit:
                break
        next_url = _battlemetrics_next_url(data)
        if next_url and len(servers) < limit and page_delay > 0:
            time.sleep(page_delay)
        url = next_url
    return servers


def discover_dayz_servers_wolfapi(
    limit: int = 10000,
    timeout: float = 15.0,
    url: str = "",
) -> list[DiscoveredServer]:
    endpoint = (
        url or os.environ.get("WOLFLAUNCHER_WOLFAPI_SERVER_LIST_URL", "") or WOLFAPI_SERVER_LIST_URL
    )
    return _fetch_wolfapi_servers(endpoint, limit=limit, timeout=timeout)


def discover_dayz_servers_wolfapi_v1(
    limit: int = 100,
    offset: int = 0,
    timeout: float = 15.0,
    url: str = "",
    unflagged_only: bool = False,
) -> list[DiscoveredServer]:
    endpoint = (
        url
        or os.environ.get("WOLFLAUNCHER_WOLFAPI_V1_SERVER_LIST_URL", "")
        or WOLFAPI_V1_SERVER_LIST_URL
    )
    endpoint = _url_with_query(
        endpoint,
        {
            "limit": max(1, min(int(limit), 500)),
            "offset": max(0, int(offset)),
            **({"quality": "unflagged"} if unflagged_only else {}),
        },
    )
    return _fetch_wolfapi_servers(endpoint, limit=limit, timeout=timeout, require_v1=True)


def search_dayz_servers_wolfapi_v1(
    query: str,
    limit: int = 100,
    offset: int = 0,
    map_name: str = "",
    version: str = "",
    timeout: float = 15.0,
    url: str = "",
    unflagged_only: bool = False,
) -> list[DiscoveredServer]:
    query = " ".join(query.split())
    if not query:
        raise ValueError("WolfAPI search query is required.")
    params = {
        "q": query,
        "limit": max(1, min(int(limit), 500)),
        "offset": max(0, int(offset)),
    }
    if map_name.strip():
        params["map"] = map_name.strip()
    if version.strip():
        params["version"] = version.strip()
    if unflagged_only:
        params["quality"] = "unflagged"
    endpoint = (
        url or os.environ.get("WOLFLAUNCHER_WOLFAPI_V1_SEARCH_URL", "") or WOLFAPI_V1_SEARCH_URL
    )
    return _fetch_wolfapi_servers(
        _url_with_query(endpoint, params),
        limit=limit,
        timeout=timeout,
        require_v1=True,
    )


def resolve_dayz_server_wolfapi_v1(
    host: str,
    game_port: int | None = None,
    query_port: int | None = None,
    timeout: float = 15.0,
    url: str = "",
) -> list[DiscoveredServer]:
    host = host.strip()
    if not host:
        raise ValueError("WolfAPI resolution host is required.")
    if game_port is None and query_port is None:
        raise ValueError("WolfAPI resolution requires a game or query port.")
    params: dict[str, str | int] = {"host": host}
    if game_port is not None:
        params["game_port"] = int(game_port)
    if query_port is not None:
        params["query_port"] = int(query_port)
    endpoint = (
        url or os.environ.get("WOLFLAUNCHER_WOLFAPI_V1_RESOLVE_URL", "") or WOLFAPI_V1_RESOLVE_URL
    )
    return _fetch_wolfapi_servers(
        _url_with_query(endpoint, params),
        limit=500,
        timeout=timeout,
        require_v1=True,
    )


def parse_exact_server_endpoint(value: str) -> tuple[str, int] | None:
    """Recognize a complete host:port search without treating names as endpoints."""
    value = value.strip()
    if not value or any(character.isspace() for character in value) or value.count(":") != 1:
        return None
    host, port_text = value.rsplit(":", 1)
    host = host.strip()
    try:
        port = int(port_text)
    except ValueError:
        return None
    if not host or not 1 <= port <= 65535:
        return None
    return host, port


def _url_with_query(url: str, params: dict[str, str | int]) -> str:
    separator = "&" if "?" in url else "?"
    return f"{url}{separator}{urllib.parse.urlencode(params)}"


def _fetch_wolfapi_servers(
    endpoint: str,
    limit: int,
    timeout: float,
    require_v1: bool = False,
) -> list[DiscoveredServer]:
    request = urllib.request.Request(endpoint, headers={"User-Agent": "WolfLauncher/0.7"})

    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            payload = response.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as exc:
        raise WolfApiError(f"WolfAPI HTTP error: {exc.code}") from exc
    except urllib.error.URLError as exc:
        raise WolfApiError(f"WolfAPI connection failed: {exc.reason}") from exc
    except TimeoutError as exc:
        raise WolfApiError("WolfAPI timed out") from exc

    try:
        data = json.loads(payload)
    except json.JSONDecodeError as exc:
        raise WolfApiError("WolfAPI returned invalid JSON") from exc

    if require_v1:
        return parse_wolfapi_v1_servers(data, limit=limit)
    return parse_wolfapi_servers(data, limit=limit)


def parse_wolfapi_v1_servers(data, limit: int = 500) -> list[DiscoveredServer]:
    if not isinstance(data, dict):
        raise WolfApiError("WolfAPI v1 response must be an object.")
    try:
        contract_version = int(data.get("contract_version", 0))
    except (TypeError, ValueError) as exc:
        raise WolfApiError("WolfAPI returned an invalid v1 contract version.") from exc
    if contract_version < 1:
        raise WolfApiError("WolfAPI v1 contract is not available.")
    required = ("generated_at", "validation_policy", "coverage", "validation_queue")
    missing = [field for field in required if not data.get(field)]
    if missing:
        raise WolfApiError("WolfAPI v1 response is missing rollout metadata: " + ", ".join(missing))
    coverage = data["coverage"]
    try:
        directory_total = int(coverage.get("eligible"))
    except (AttributeError, TypeError, ValueError) as exc:
        raise WolfApiError("WolfAPI returned an invalid eligible directory count.") from exc
    if directory_total < 0:
        raise WolfApiError("WolfAPI returned an invalid eligible directory count.")
    return WolfApiServerList(
        parse_wolfapi_servers(data, limit=limit),
        directory_total=directory_total,
    )


def parse_wolfapi_servers(data, limit: int = 10000) -> list[DiscoveredServer]:
    if isinstance(data, list):
        rows = data
        updated_at = ""
    elif isinstance(data, dict):
        rows = data.get("servers", data.get("data", []))
        updated_at = str(data.get("generated_at") or data.get("updated_at") or "")
    else:
        rows = []
        updated_at = ""

    if not isinstance(rows, list):
        raise WolfApiError("WolfAPI response did not contain a server list.")

    now = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    timestamp = updated_at or now
    servers = []
    seen = set()
    limit = max(1, int(limit))
    for row in rows:
        server = discovered_server_from_wolfapi_row(row, timestamp)
        identity = server.stable_server_id if server else ""
        identity = identity or (server.cache_key if server else "")
        if not server or identity in seen:
            continue
        seen.add(identity)
        servers.append(server)
        if len(servers) >= limit:
            break
    return servers


def discovered_server_from_wolfapi_row(row: dict, timestamp: str = "") -> DiscoveredServer | None:
    if not isinstance(row, dict):
        return None

    host, addr_query_port = _host_port_from_addr(str(row.get("addr") or row.get("address") or ""))
    host = host or str(row.get("ip") or row.get("host") or "").strip()
    game_port = (
        _optional_int(row.get("game_port"))
        or _optional_int(row.get("gameport"))
        or _optional_int(row.get("port"))
    )
    query_port = (
        _optional_int(row.get("query_port"))
        or _optional_int(row.get("queryPort"))
        or _optional_int(row.get("portQuery"))
        or addr_query_port
    )
    if game_port is None:
        game_port = query_port
    if query_port is None:
        query_port = game_port
    if not host or game_port is None or query_port is None:
        return None

    name = str(row.get("name") or row.get("server_name") or f"{host}:{game_port}")
    gametype = str(row.get("gametype") or "")
    online = row.get("online")
    if online is None:
        status = str(row.get("status") or "").lower()
        online = status != "offline" if status else True
    country_code = _country_code(row.get("country_code"))
    country_source = str(row.get("country_source") or "").strip().lower()
    if country_source != "battlemetrics":
        country_code = ""
        country_source = ""

    return DiscoveredServer(
        name=name,
        source="wolfapi",
        server_name=name,
        host=host,
        game_port=game_port,
        query_port=query_port,
        map_name=str(row.get("map") or row.get("map_name") or ""),
        players_current=_optional_int(_first_present(row, "players", "players_current")),
        players_max=_optional_int(_first_present(row, "max_players", "maxplayers", "players_max")),
        ping_ms=_optional_int(_first_present(row, "ping_ms", "ping", "latency")),
        version=str(row.get("version") or ""),
        password=bool(row.get("password", False)),
        modded="mod" in gametype.lower() or bool(row.get("modded", False)),
        online=bool(online),
        last_checked=str(
            row.get("validation_checked_at")
            or row.get("provider_last_checked")
            or row.get("last_checked")
            or timestamp
        ),
        last_seen=str(
            row.get("validation_seen_at")
            or row.get("provider_last_seen")
            or row.get("last_seen")
            or timestamp
        ),
        stable_server_id=str(row.get("server_id") or ""),
        endpoint_aliases=tuple(
            str(alias) for alias in row.get("endpoint_aliases", []) if str(alias).strip()
        )
        if isinstance(row.get("endpoint_aliases", []), list)
        else (),
        freshness=str(row.get("freshness") or ""),
        freshness_expires_at=str(row.get("freshness_expires_at") or ""),
        validation_status=str(row.get("validation_status") or ""),
        validation_checked_at=str(row.get("validation_checked_at") or ""),
        validation_seen_at=str(row.get("validation_seen_at") or ""),
        validation_error_code=str(row.get("validation_error_code") or ""),
        provider_last_checked=str(row.get("provider_last_checked") or ""),
        provider_last_seen=str(row.get("provider_last_seen") or ""),
        required_mod_count=_required_mod_count(row),
        mod_metadata_status=str(row.get("mod_metadata_status") or ""),
        mod_metadata_checked_at=str(row.get("mod_metadata_checked_at") or ""),
        mod_metadata_expires_at=str(row.get("mod_metadata_expires_at") or ""),
        mod_metadata_error_code=str(row.get("mod_metadata_error_code") or ""),
        mod_manifest_hash=str(row.get("mod_manifest_hash") or ""),
        quality_flags=_quality_flags(row.get("quality_flags")),
        country_code=country_code,
        country_source=country_source,
    )


def _quality_flags(value) -> tuple[str, ...]:
    if isinstance(value, str):
        value = value.split(",")
    if not isinstance(value, (list, tuple)):
        return ()
    return tuple(dict.fromkeys(str(item).strip() for item in value if str(item).strip()))


def fetch_battlemetrics_page(url: str, timeout: float = 15.0) -> dict:
    request = urllib.request.Request(url, headers={"User-Agent": "WolfLauncher/0.6"})

    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            payload = response.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as exc:
        raise BattleMetricsError(f"BattleMetrics API HTTP error: {exc.code}") from exc
    except urllib.error.URLError as exc:
        raise BattleMetricsError(f"BattleMetrics API connection failed: {exc.reason}") from exc
    except TimeoutError as exc:
        raise BattleMetricsError("BattleMetrics API timed out") from exc

    try:
        data = json.loads(payload)
    except json.JSONDecodeError as exc:
        raise BattleMetricsError("BattleMetrics API returned invalid JSON") from exc

    if not isinstance(data, dict):
        raise BattleMetricsError("BattleMetrics API returned invalid JSON object.")
    return data


def _battlemetrics_next_url(data: dict) -> str:
    links = data.get("links", {}) if isinstance(data, dict) else {}
    next_url = links.get("next") if isinstance(links, dict) else ""
    return str(next_url or "")


def parse_battlemetrics_servers(data: dict) -> list[DiscoveredServer]:
    rows = data.get("data", []) if isinstance(data, dict) else []
    if not isinstance(rows, list):
        raise BattleMetricsError("BattleMetrics API response did not contain a server list.")

    now = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    servers = []
    seen = set()
    for row in rows:
        server = discovered_server_from_battlemetrics_row(row, now)
        if not server or server.cache_key in seen:
            continue
        seen.add(server.cache_key)
        servers.append(server)
    return servers


def discovered_server_from_battlemetrics_row(
    row: dict, timestamp: str = ""
) -> DiscoveredServer | None:
    if not isinstance(row, dict):
        return None
    attributes = row.get("attributes", {})
    if not isinstance(attributes, dict):
        return None

    host = str(attributes.get("ip") or attributes.get("address") or "").strip()
    port = _optional_int(attributes.get("port"))
    query_port = (
        _optional_int(attributes.get("portQuery"))
        or _optional_int(attributes.get("queryPort"))
        or _optional_int(attributes.get("query_port"))
        or port
    )
    if not host or port is None:
        return None

    details = attributes.get("details", {})
    if not isinstance(details, dict):
        details = {}

    name = str(attributes.get("name") or f"{host}:{port}")
    status = str(attributes.get("status") or "").lower()
    players_current = _optional_int(attributes.get("players"))
    players_max = _optional_int(attributes.get("maxPlayers") or attributes.get("maxplayers"))
    country_code = _country_code(attributes.get("country"))

    return DiscoveredServer(
        name=name,
        source="battlemetrics",
        server_name=name,
        host=host,
        game_port=port,
        query_port=query_port,
        map_name=str(details.get("map") or attributes.get("map") or ""),
        players_current=players_current,
        players_max=players_max,
        version=str(details.get("version") or attributes.get("version") or ""),
        password=bool(details.get("password", False)),
        modded=bool(details.get("modded", False)),
        online=status == "online",
        last_checked=timestamp,
        last_seen=timestamp if status == "online" else "",
        required_mod_count=(
            _required_mod_count(details)
            if _required_mod_count(details) is not None
            else _required_mod_count(attributes)
        ),
        country_code=country_code,
        country_source="battlemetrics" if country_code else "",
    )


def _country_code(value) -> str:
    code = str(value or "").strip().upper()
    return code if len(code) == 2 and code.isalpha() else ""


def _host_port_from_addr(value: str) -> tuple[str, int | None]:
    value = value.strip()
    if not value:
        return "", None
    if ":" not in value:
        return value, None
    host, port_text = value.rsplit(":", 1)
    return host.strip(), _optional_int(port_text)


def _optional_int(value) -> int | None:
    if value is None or value == "":
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _first_present(row: dict, *keys: str):
    for key in keys:
        value = row.get(key)
        if value is not None and value != "":
            return value
    return None
