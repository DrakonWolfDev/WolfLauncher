import unittest
from unittest.mock import Mock

from wolflauncher.secret_store import (
    SETTINGS_KEY,
    SecretStore,
    load_steam_api_key,
    settings_with_stored_steam_api_key,
)


def keyring(priority=1):
    module = Mock()
    module.get_keyring.return_value.priority = priority
    return module


class SecretStoreTests(unittest.TestCase):
    def test_usable_keyring_takes_precedence_over_settings_fallback(self):
        module = keyring()
        module.get_password.return_value = "keyring-value"
        store = SecretStore(module)
        self.assertEqual(
            load_steam_api_key({SETTINGS_KEY: "fallback-value"}, store), "keyring-value"
        )

    def test_save_removes_plaintext_when_keyring_succeeds(self):
        module = keyring()
        settings = settings_with_stored_steam_api_key(
            {"other": True, SETTINGS_KEY: "old"}, "new", SecretStore(module)
        )
        self.assertEqual(settings, {"other": True})
        module.set_password.assert_called_once()

    def test_unavailable_keyring_keeps_owner_only_settings_fallback(self):
        settings = settings_with_stored_steam_api_key(
            {}, "fallback", SecretStore(keyring(priority=0))
        )
        self.assertEqual(settings, {SETTINGS_KEY: "fallback"})

    def test_backend_failure_keeps_settings_fallback(self):
        module = keyring()
        module.set_password.side_effect = RuntimeError("locked")
        settings = settings_with_stored_steam_api_key({}, "fallback", SecretStore(module))
        self.assertEqual(settings, {SETTINGS_KEY: "fallback"})


if __name__ == "__main__":
    unittest.main()
