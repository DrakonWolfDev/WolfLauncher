from __future__ import annotations

import os
import json
import socket
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timezone

from .models import DiscoveredServer


DAYZ_APP_ID = 221100
STEAM_WEB_API_SERVER_LIST_URL = "https://api.steampowered.com/IGameServersService/GetServerList/v1/"
BATTLEMETRICS_SERVER_LIST_URL = "https://api.battlemetrics.com/servers"
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


def build_master_server_request(
    start_address: str = "0.0.0.0:0",
    app_id: int = DAYZ_APP_ID,
    region: int = REGION_ALL,
    extra_filter: str = "",
) -> bytes:
    filters = f"\\appid\\{app_id}{extra_filter}"
    return b"1" + bytes([region]) + start_address.encode("ascii") + b"\0" + filters.encode("ascii") + b"\0"


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

    raise SteamMasterServerError("Steam master discovery failed for all configured hosts: " + "; ".join(errors))


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
        return [parse_master_address(item, master_port) for item in endpoints.split(",") if item.strip()]

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


def discovered_server_from_endpoint(endpoint: MasterServerEndpoint, timestamp: str = "") -> DiscoveredServer:
    return DiscoveredServer(
        name=endpoint.address,
        source="steam_master",
        host=endpoint.host,
        game_port=endpoint.port,
        query_port=endpoint.port,
        last_seen=timestamp,
    )


def discover_dayz_servers_web_api(
    api_key: str = "",
    limit: int = 5000,
    timeout: float = 15.0,
    filter_text: str = "",
) -> list[DiscoveredServer]:
    api_key = api_key or os.environ.get("WOLFLAUNCHER_STEAM_WEB_API_KEY", "") or os.environ.get("STEAM_WEB_API_KEY", "")
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
    )


def discover_dayz_servers_battlemetrics(
    limit: int = 100,
    timeout: float = 15.0,
    search: str = "",
) -> list[DiscoveredServer]:
    params = {
        "filter[game]": "dayz",
        "page[size]": str(max(1, min(int(limit), 100))),
    }
    if search:
        params["filter[search]"] = search
    url = f"{BATTLEMETRICS_SERVER_LIST_URL}?{urllib.parse.urlencode(params)}"
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

    return parse_battlemetrics_servers(data)


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


def discovered_server_from_battlemetrics_row(row: dict, timestamp: str = "") -> DiscoveredServer | None:
    if not isinstance(row, dict):
        return None
    attributes = row.get("attributes", {})
    if not isinstance(attributes, dict):
        return None

    host = str(attributes.get("ip") or attributes.get("address") or "").strip()
    port = _optional_int(attributes.get("port"))
    query_port = _optional_int(attributes.get("queryPort") or attributes.get("query_port")) or port
    if not host or port is None:
        return None

    details = attributes.get("details", {})
    if not isinstance(details, dict):
        details = {}

    name = str(attributes.get("name") or f"{host}:{port}")
    status = str(attributes.get("status") or "").lower()
    players_current = _optional_int(attributes.get("players"))
    players_max = _optional_int(attributes.get("maxPlayers") or attributes.get("maxplayers"))

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
    )


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
