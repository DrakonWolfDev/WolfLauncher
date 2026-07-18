from __future__ import annotations

from dataclasses import dataclass
from typing import Any

SERVICE_NAME = "WolfLauncher"
STEAM_API_KEY_ACCOUNT = "steam-web-api-key"
SETTINGS_KEY = "steam_web_api_key"


@dataclass
class SecretStore:
    keyring_module: Any = None

    def __post_init__(self) -> None:
        if self.keyring_module is not None:
            return
        module: Any
        try:
            import keyring as module
        except ImportError:
            module = None
        self.keyring_module = module

    def available(self) -> bool:
        if self.keyring_module is None:
            return False
        try:
            return float(self.keyring_module.get_keyring().priority) > 0
        except Exception:
            return False

    def get(self) -> str:
        if not self.available():
            return ""
        try:
            return str(self.keyring_module.get_password(SERVICE_NAME, STEAM_API_KEY_ACCOUNT) or "")
        except Exception:
            return ""

    def save(self, value: str) -> bool:
        if not self.available():
            return False
        try:
            if value:
                self.keyring_module.set_password(SERVICE_NAME, STEAM_API_KEY_ACCOUNT, value)
            else:
                try:
                    self.keyring_module.delete_password(SERVICE_NAME, STEAM_API_KEY_ACCOUNT)
                except Exception:
                    pass
            return True
        except Exception:
            return False


def load_steam_api_key(settings: dict[str, Any], store: SecretStore) -> str:
    return store.get() or str(settings.get(SETTINGS_KEY) or "")


def settings_with_stored_steam_api_key(
    settings: dict[str, Any], value: str, store: SecretStore
) -> dict[str, Any]:
    updated = dict(settings)
    if store.save(value):
        updated.pop(SETTINGS_KEY, None)
    else:
        updated[SETTINGS_KEY] = value
    return updated
