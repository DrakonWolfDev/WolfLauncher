import json
from pathlib import Path
from typing import Any

from .paths import user_config_dir
from .persistence import atomic_write_text, ensure_private_directory, ensure_private_file

APP_DIR = user_config_dir()
SETTINGS_PATH = APP_DIR / "settings.json"
FAVOURITES_PATH = APP_DIR / "favourites.json"
CURATED_SERVERS_PATH = APP_DIR / "servers.yaml"
DEFAULT_DISCOVERY_PROVIDER = "wolfapi_v1"
SETTINGS_SCHEMA_VERSION = 8


def ensure_app_dir() -> None:
    ensure_private_directory(APP_DIR)


def load_json(path: Path, default: Any) -> Any:
    try:
        if path.exists():
            ensure_private_file(path)
            with path.open("r", encoding="utf-8") as handle:
                return json.load(handle)
    except (OSError, json.JSONDecodeError):
        pass
    return default


def save_json(path: Path, data: Any) -> None:
    serialized = json.dumps(data, indent=2) + "\n"
    # Validate the complete representation before replacing the live file.
    json.loads(serialized)
    atomic_write_text(path, serialized)


def load_settings() -> dict[str, Any]:
    data = load_json(SETTINGS_PATH, {})
    return normalize_settings(data)


def save_settings(data: dict[str, Any]) -> None:
    save_json(SETTINGS_PATH, normalize_settings(data))


def normalize_settings(data: Any) -> dict[str, Any]:
    """Apply additive settings migrations without discarding unknown keys."""
    if not isinstance(data, dict):
        return {"schema_version": SETTINGS_SCHEMA_VERSION}
    migrated = dict(data)
    version = migrated.get("schema_version", 0)
    try:
        version = int(version)
    except (TypeError, ValueError):
        version = 0
    if version < 0:
        version = 0
    # Version 4 removes legacy Flatpak/Snap Steam selections so an old setting
    # cannot reactivate a retired installation path.
    if version <= SETTINGS_SCHEMA_VERSION:
        if migrated.get("native_steam_mode") in {"flatpak", "snap"}:
            migrated["native_steam_mode"] = "auto"
        if version < 3:
            migrated.setdefault("hide_quality_flagged", True)
        if version < 5:
            migrated.setdefault("local_tool_profiles", [])
        if version < 6:
            migrated.setdefault("editor_extra_mod_ids", [])
        if version < 7:
            migrated.setdefault("local_host_settings", {})
        if version < 8:
            migrated.setdefault("dayz_product", "stable")
        migrated["schema_version"] = SETTINGS_SCHEMA_VERSION
    return migrated


def server_key(server) -> str:
    return f"{server.host}:{server.game_port}:{server.query_port}:{server.name}"


def favourites_path(product_key: str = "stable") -> Path:
    return FAVOURITES_PATH if product_key == "stable" else APP_DIR / f"favourites-{product_key}.json"


def curated_servers_path(product_key: str = "stable") -> Path:
    return CURATED_SERVERS_PATH if product_key == "stable" else APP_DIR / f"servers-{product_key}.yaml"


def load_favourites(product_key: str = "stable") -> set[str]:
    data = load_json(favourites_path(product_key), [])
    if isinstance(data, list):
        return {str(item) for item in data}
    return set()


def save_favourites(keys: set[str], product_key: str = "stable") -> None:
    save_json(favourites_path(product_key), sorted(keys))
