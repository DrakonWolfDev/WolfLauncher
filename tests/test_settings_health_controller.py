import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from wolflauncher.settings_health_controller import SettingsHealthCoordinator


class SettingsHealthCoordinatorTests(unittest.TestCase):
    def test_experimental_detection_is_green_or_neutral_independent_of_stable(self):
        from pathlib import Path

        from wolflauncher.dayz_product import STABLE
        from wolflauncher.settings_health import SettingsHealthSnapshot
        from wolflauncher.settings_health_presenter import settings_health_groups
        from wolflauncher.theme import COLOURS, STATUS_COLOURS

        for detected in (True, False):
            with self.subTest(detected=detected):
                window = Mock()
                window._shutting_down = False
                coordinator = SettingsHealthCoordinator(window)
                availability = {
                    "stable": SimpleNamespace(candidates=()),
                    "experimental": SimpleNamespace(
                        detected=detected,
                        state="detected" if detected else "missing",
                        install=SimpleNamespace(dayz_dir=Path("/games/DayZ Exp")),
                    ),
                }
                with patch(
                    "wolflauncher.settings_health_controller.build_settings_health_snapshot",
                    return_value=SettingsHealthSnapshot("Stable summary", ()),
                ) as build:
                    coordinator.apply_availability(0, availability)
                self.assertEqual(build.call_args.kwargs["product"], STABLE)
                rows = window.update_settings_health_groups.call_args.args[0]
                expected = "OK" if detected else "OPTIONAL"
                self.assertEqual(rows[0][1], expected)
                group = settings_health_groups(rows)[1]
                self.assertEqual(group.key, "experimental")
                self.assertEqual(group.status, expected)
                self.assertEqual(
                    coordinator.colour(expected),
                    STATUS_COLOURS["positive"] if detected else COLOURS["text_muted"],
                )

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
