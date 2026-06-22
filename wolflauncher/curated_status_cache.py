from __future__ import annotations

from pathlib import Path

from .models import Server
from .settings import load_json, save_json, server_key
from .status import ServerStatus


DATA_DIR = Path.home() / ".local" / "share" / "wolflauncher"
CURATED_STATUS_CACHE_PATH = DATA_DIR / "curated_status.json"


def ensure_data_dir(path: Path = DATA_DIR) -> None:
    path.mkdir(parents=True, exist_ok=True)


def load_status_cache(path: Path = CURATED_STATUS_CACHE_PATH) -> dict[str, ServerStatus]:
    data = load_json(path, {})
    if not isinstance(data, dict):
        return {}
    cache: dict[str, ServerStatus] = {}
    for key, value in data.items():
        if not isinstance(value, dict):
            continue
        cache[str(key)] = _status_from_dict(value)
    return cache


def save_status_cache(cache: dict[str, ServerStatus], path: Path = CURATED_STATUS_CACHE_PATH) -> None:
    ensure_data_dir(path.parent)
    save_json(path, {key: _status_to_dict(status) for key, status in cache.items()})


def cached_status_for_server(
    cache: dict[str, ServerStatus],
    server: Server,
) -> ServerStatus | None:
    return cache.get(server_key(server))


def update_status_cache(
    cache: dict[str, ServerStatus],
    server: Server,
    status: ServerStatus,
    path: Path = CURATED_STATUS_CACHE_PATH,
) -> None:
    cache[server_key(server)] = status
    save_status_cache(cache, path)


def _status_to_dict(status: ServerStatus) -> dict[str, object]:
    return {
        "online": status.online,
        "resolved_ip": status.resolved_ip,
        "server_name": status.server_name,
        "map_name": status.map_name,
        "players": status.players,
        "time": status.time,
        "version": status.version,
        "ping": status.ping,
        "password": status.password,
        "modded": status.modded,
        "connect": status.connect,
        "error": status.error,
    }


def _status_from_dict(data: dict) -> ServerStatus:
    return ServerStatus(
        online=bool(data.get("online", False)),
        resolved_ip=str(data.get("resolved_ip") or ""),
        server_name=str(data.get("server_name") or ""),
        map_name=str(data.get("map_name") or ""),
        players=str(data.get("players") or ""),
        time=str(data.get("time") or ""),
        version=str(data.get("version") or ""),
        ping=str(data.get("ping") or ""),
        password=bool(data.get("password", False)),
        modded=bool(data.get("modded", False)),
        connect=str(data.get("connect") or ""),
        error=str(data.get("error") or ""),
    )
