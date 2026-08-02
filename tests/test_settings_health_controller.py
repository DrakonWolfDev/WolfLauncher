import unittest
from types import SimpleNamespace
from unittest.mock import Mock

from wolflauncher.settings_health_controller import SettingsHealthCoordinator


class SettingsHealthCoordinatorTests(unittest.TestCase):
    def test_disabled_provider_is_an_actionable_warning(self):
        window = SimpleNamespace(
            discovery_provider_key=Mock(return_value="disabled"),
            discovery_provider=Mock(),
        )
        window.discovery_provider.currentText.return_value = "Disabled"

        status, detail = SettingsHealthCoordinator(window)._provider_health()

        self.assertEqual(status, "WARN")
        self.assertEqual(detail, "Database refresh is disabled")

    def test_steam_master_configuration_failure_is_reported_as_warning(self):
        window = SimpleNamespace(
            discovery_provider_key=Mock(return_value="steam_master"),
            discovery_provider=Mock(),
            steam_master_addresses=Mock(side_effect=ValueError("Invalid endpoint")),
        )
        window.discovery_provider.currentText.return_value = "Steam master"

        status, detail = SettingsHealthCoordinator(window)._provider_health()

        self.assertEqual(status, "WARN")
        self.assertEqual(detail, "Invalid endpoint")

    def test_steam_master_default_endpoints_are_healthy(self):
        window = SimpleNamespace(
            discovery_provider_key=Mock(return_value="steam_master"),
            discovery_provider=Mock(),
            steam_master_addresses=Mock(return_value=None),
        )
        window.discovery_provider.currentText.return_value = "Steam master"

        status, detail = SettingsHealthCoordinator(window)._provider_health()

        self.assertEqual(status, "OK")
        self.assertEqual(detail, "Default Steam masters")

    def test_malformed_steam_master_endpoints_are_a_warning(self):
        class MalformedAddresses:
            def __iter__(self):
                return None

        window = SimpleNamespace(
            discovery_provider_key=Mock(return_value="steam_master"),
            discovery_provider=Mock(),
            steam_master_addresses=Mock(return_value=MalformedAddresses()),
        )
        window.discovery_provider.currentText.return_value = "Steam master"

        status, detail = SettingsHealthCoordinator(window)._provider_health()

        self.assertEqual(status, "WARN")
        self.assertEqual(detail, "Steam master endpoints could not be read")


if __name__ == "__main__":
    unittest.main()
