import os
import sys
from ipaddress import IPv6Address, ip_address
from pathlib import Path

import yaml

from .models import Server
from .persistence import atomic_write_text, ensure_private_file
from .platforms import current_platform
from .settings import CURATED_SERVERS_PATH

PROJECT_ROOT = Path(__file__).resolve().parent.parent
INSTALL_SHARE_ROOT = Path(
    os.environ.get("WOLFLAUNCHER_SHARE_ROOT", Path(sys.prefix) / "share" / "wolflauncher")
)


def _source_or_installed(source_path: Path, installed_path: Path) -> Path:
    return source_path if source_path.is_file() else installed_path


VENDORED_LAUNCHER_PATH = _source_or_installed(
    PROJECT_ROOT / "external/dayz-linux-cli-launcher/dayz-launcher.sh",
    INSTALL_SHARE_ROOT / "external/dayz-launcher.sh",
)
EXAMPLE_SERVERS_PATH = _source_or_installed(
    PROJECT_ROOT / "example.servers.yaml",
    INSTALL_SHARE_ROOT / "example.servers.yaml",
)
LEGACY_SERVERS_PATH = PROJECT_ROOT / "servers.yaml"

DEFAULT_LAUNCHER_PATHS = (
    [
        Path.home() / ".local/bin/dayz-launcher.sh",
        Path("/opt/wolflauncher/dayz-launcher.sh"),
        Path.home() / "dayz-launcher.sh",
        VENDORED_LAUNCHER_PATH,
    ]
    if current_platform().capabilities.supports_external_launcher
    else []
)


def normalize_server_endpoint(host: str, game_port: int, query_port: int) -> tuple[str, int, int]:
    host = host.strip()
    if host.count(":") != 1:
        return host, game_port, query_port

    split_host, port_text = (part.strip() for part in host.rsplit(":", 1))
    if not split_host:
        return host, game_port, query_port
    try:
        parsed_port = int(port_text)
    except ValueError:
        return host, game_port, query_port
    if parsed_port <= 0 or parsed_port > 65535:
        return host, game_port, query_port

    adjusted_query_port = parsed_port + 1 if query_port == game_port + 1 else query_port
    return split_host, parsed_port, adjusted_query_port


def validate_dayz_host(host: str) -> str:
    """Reject IPv6 endpoints until DayZ support is deliberately validated."""
    normalized = host.strip()
    candidate = normalized.removeprefix("[").removesuffix("]")
    try:
        address = ip_address(candidate)
    except ValueError:
        return normalized
    if isinstance(address, IPv6Address):
        raise ValueError("IPv6 DayZ server endpoints are not supported.")
    return normalized


def ensure_servers_file(
    path: Path = CURATED_SERVERS_PATH,
    example_path: Path = EXAMPLE_SERVERS_PATH,
    legacy_path: Path | None = None,
) -> str:
    if path.exists():
        ensure_private_file(path)
        return "existing"

    migration_source = LEGACY_SERVERS_PATH if path == CURATED_SERVERS_PATH else None
    if legacy_path is not None:
        migration_source = legacy_path
    source = (
        migration_source
        if migration_source is not None and migration_source.is_file()
        else example_path
    )
    if source.is_file():
        text = source.read_text(encoding="utf-8")
        _validate_server_yaml_text(text)
        atomic_write_text(path, text)
        return "migrated" if source == migration_source else "seeded"

    atomic_write_text(path, "servers: []\n")
    return "created"


def ensure_empty_servers_file(path: Path) -> str:
    """Create an empty profile-scoped curated list without inheriting examples."""
    if path.exists():
        ensure_private_file(path)
        return "existing"
    atomic_write_text(path, "servers: []\n")
    return "created"


def find_default_launcher_path() -> str:
    for path in DEFAULT_LAUNCHER_PATHS:
        if path.exists():
            return str(path)
    return str(DEFAULT_LAUNCHER_PATHS[0]) if DEFAULT_LAUNCHER_PATHS else ""


def load_servers(path: Path) -> list[Server]:
    data = _load_server_yaml(path)
    rows = data.get("servers", [])
    if not isinstance(rows, list):
        raise ValueError("servers.yaml must contain a 'servers' list.")

    servers = []
    for item in rows:
        if not isinstance(item, dict):
            raise ValueError("Each servers.yaml entry must be a mapping.")
        try:
            servers.append(
                Server(
                    name=str(item["name"]),
                    group=str(item.get("group", "Community")),
                    host=validate_dayz_host(str(item["host"])),
                    game_port=int(item["game_port"]),
                    query_port=int(item["query_port"]),
                    favourite=bool(item.get("favourite", False)),
                )
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError("Invalid servers.yaml server entry.") from exc
    return servers


def add_curated_server(path: Path, server: Server) -> None:
    validate_dayz_host(server.host)
    data = _load_server_yaml(path)
    servers = data.setdefault("servers", [])
    if not isinstance(servers, list):
        raise ValueError("servers.yaml must contain a 'servers' list.")

    for item in servers:
        if not isinstance(item, dict):
            continue
        if (
            str(item.get("host")) == server.host
            and int(item.get("game_port", 0)) == server.game_port
            and int(item.get("query_port", 0)) == server.query_port
        ):
            raise ValueError("This server is already in the Favourite Servers list.")

    servers.append(
        {
            "name": server.name,
            "group": server.group,
            "host": server.host,
            "game_port": server.game_port,
            "query_port": server.query_port,
            "favourite": server.favourite,
        }
    )
    _write_server_yaml(path, data)


def remove_curated_server(path: Path, server: Server) -> bool:
    data = _load_server_yaml(path)
    servers = data.setdefault("servers", [])
    if not isinstance(servers, list):
        raise ValueError("servers.yaml must contain a 'servers' list.")

    for index, item in enumerate(servers):
        if not isinstance(item, dict):
            continue
        if (
            str(item.get("host")) == server.host
            and int(item.get("game_port", 0)) == server.game_port
            and int(item.get("query_port", 0)) == server.query_port
        ):
            del servers[index]
            _write_server_yaml(path, data)
            return True

    return False


def update_curated_server(path: Path, original: Server, updated: Server) -> bool:
    validate_dayz_host(updated.host)
    data = _load_server_yaml(path)
    servers = data.setdefault("servers", [])
    if not isinstance(servers, list):
        raise ValueError("servers.yaml must contain a 'servers' list.")

    match_index = None
    for index, item in enumerate(servers):
        if not isinstance(item, dict):
            continue
        if _same_server_entry(item, original):
            match_index = index
            break

    if match_index is None:
        return False

    for index, item in enumerate(servers):
        if index == match_index or not isinstance(item, dict):
            continue
        if _same_server_entry(item, updated):
            raise ValueError(
                "Another favourite server already uses that host and port combination."
            )

    servers[match_index] = {
        "name": updated.name,
        "group": updated.group,
        "host": updated.host,
        "game_port": updated.game_port,
        "query_port": updated.query_port,
        "favourite": updated.favourite,
    }
    _write_server_yaml(path, data)
    return True


def reorder_curated_servers(path: Path, ordered_servers: list[Server]) -> None:
    """Persist an explicit curated-server order without dropping extra YAML fields."""
    data = _load_server_yaml(path)
    entries = data.setdefault("servers", [])
    if not isinstance(entries, list):
        raise ValueError("servers.yaml must contain a 'servers' list.")

    by_endpoint = {}
    for entry in entries:
        if not isinstance(entry, dict):
            raise ValueError("Each servers.yaml entry must be a mapping.")
        key = (
            str(entry.get("host", "")),
            int(entry.get("game_port", 0)),
            int(entry.get("query_port", 0)),
        )
        if key in by_endpoint:
            raise ValueError("servers.yaml contains duplicate server endpoints.")
        by_endpoint[key] = entry

    reordered = []
    for server in ordered_servers:
        key = (server.host, server.game_port, server.query_port)
        entry = by_endpoint.pop(key, None)
        if entry is None:
            raise ValueError("A favourite server was changed before its order could be saved.")
        reordered.append(entry)
    if by_endpoint:
        raise ValueError("The saved favourite-server list changed before its order could be saved.")

    data["servers"] = reordered
    _write_server_yaml(path, data)


def _same_server_entry(item: dict, server: Server) -> bool:
    return (
        str(item.get("host")) == server.host
        and int(item.get("game_port", 0)) == server.game_port
        and int(item.get("query_port", 0)) == server.query_port
    )


def _load_server_yaml(path: Path) -> dict:
    if not path.exists():
        return {"servers": []}
    try:
        with path.open("r", encoding="utf-8") as handle:
            data = yaml.safe_load(handle) or {}
    except yaml.YAMLError as exc:
        raise ValueError("servers.yaml contains invalid YAML.") from exc
    if not isinstance(data, dict):
        raise ValueError("servers.yaml must contain a mapping.")
    return data


def _validate_server_yaml_text(text: str) -> dict:
    data = yaml.safe_load(text) or {}
    if not isinstance(data, dict):
        raise ValueError("servers.yaml must contain a mapping.")
    servers = data.get("servers", [])
    if not isinstance(servers, list):
        raise ValueError("servers.yaml must contain a 'servers' list.")
    return data


def _write_server_yaml(path: Path, data: dict) -> None:
    serialized = yaml.safe_dump(data, sort_keys=False)
    _validate_server_yaml_text(serialized)
    atomic_write_text(path, serialized, backup=True)
