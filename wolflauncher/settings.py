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
SETTINGS_SCHEMA_VERSION = 10


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
    atomic_write_text(path, serialized, backup=True)


def load_settings() -> dict[str, Any]:
    data = load_json(SETTINGS_PATH, {})
    return normalize_settings(data)


def save_settings(data: dict[str, Any]) -> None:
    if SETTINGS_PATH.exists():
        try:
            existing = json.loads(SETTINGS_PATH.read_text(encoding="utf-8"))
            if not isinstance(existing, dict):
                raise ValueError("settings must contain an object")
        except (ValueError, UnicodeError) as exc:
            raise OSError(
                f"Settings contain damaged data. Repair or restore {SETTINGS_PATH} before saving."
            ) from exc
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
    if version <= SETTINGS_SCHEMA_VERSION:
        # Retire packaged Steam selections, including settings from this version.
        if migrated.get("native_steam_mode") in {"flatpak", "snap"}:
            migrated["native_steam_mode"] = "auto"
        if version < 3:
            migrated.setdefault("hide_quality_flagged", True)
        if version < 5:
            migrated.setdefault("local_tool_profiles", [])
        if version < 6:
            migrated.setdefault("editor_extra_mod_ids", [])
        # Editor selections are a temporary workspace, never a saved profile.
        migrated["editor_extra_mod_ids"] = []
        if version < 7:
            migrated.setdefault("local_host_settings", {})
        if version < 8:
            migrated.setdefault("dayz_product", "stable")
        if version < 9 and migrated.get("discovery_provider") == "wolfapi":
            migrated["discovery_provider"] = DEFAULT_DISCOVERY_PROVIDER
        if version < 10:
            migrated.setdefault("hide_experimental", False)
            migrated.setdefault("local_tool_product", migrated.get("dayz_product", "stable"))
        migrated["schema_version"] = SETTINGS_SCHEMA_VERSION
    return migrated


def server_key(server) -> str:
    from .server_identity import identity_key

    return identity_key(server)


def favourites_path(product_key: str = "stable") -> Path:
    return (
        FAVOURITES_PATH if product_key == "stable" else APP_DIR / f"favourites-{product_key}.json"
    )


def curated_servers_path(product_key: str = "stable") -> Path:
    return (
        CURATED_SERVERS_PATH if product_key == "stable" else APP_DIR / f"servers-{product_key}.yaml"
    )


def load_favourites(product_key: str = "stable") -> set[str]:
    data = load_json(favourites_path(product_key), [])
    if isinstance(data, list):
        return {normalize_favourite_key(str(item)) for item in data}
    return set()


def save_favourites(keys: set[str], product_key: str = "stable") -> None:
    save_json(favourites_path(product_key), sorted(keys))


def normalize_favourite_key(key: str) -> str:
    """Legacy keys append a display name; names never identify a server."""
    scope, separator, endpoint = key.partition("|")
    if not separator:
        endpoint, scope = scope, ""
    parts = endpoint.split(":", 3)
    if len(parts) >= 3 and parts[1].isdigit() and parts[2].isdigit():
        endpoint = ":".join((parts[0].strip().lower(), parts[1], parts[2]))
    return f"{scope}|{endpoint}" if separator else endpoint
