from __future__ import annotations

import socket
from dataclasses import dataclass
from datetime import datetime, timezone

from .models import DiscoveredServer


DAYZ_APP_ID = 221100
MASTER_SERVER_HOST = "hl2master.steampowered.com"
MASTER_SERVER_PORT = 27011
MASTER_RESPONSE_HEADER = b"\xff\xff\xff\xfff\n"
REGION_ALL = 0xFF


@dataclass(frozen=True)
class MasterServerEndpoint:
    host: str
    port: int

    @property
    def address(self) -> str:
        return f"{self.host}:{self.port}"


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
