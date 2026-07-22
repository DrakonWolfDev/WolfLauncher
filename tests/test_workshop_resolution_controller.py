import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from wolflauncher.workshop_resolution_controller import WorkshopResolutionCoordinator


class WorkshopResolutionCoordinatorTests(unittest.TestCase):
    def test_native_resolution_uses_the_selected_steam_install(self):
        install = object()
        window = SimpleNamespace(
            launch_engine_key=Mock(return_value="native"),
            selected_steam_install=Mock(return_value=install),
        )

        self.assertIs(WorkshopResolutionCoordinator(window)._install(), install)
        window.selected_steam_install.assert_called_once_with()

    @patch("wolflauncher.workshop_resolution_controller.QMessageBox.warning")
    def test_missing_mod_check_does_not_start_a_worker(self, warning):
        window = SimpleNamespace(
            _selected_mod_result=Mock(return_value=None),
        )

        WorkshopResolutionCoordinator(window).subscribe_missing_mods()

        warning.assert_called_once()


if __name__ == "__main__":
    unittest.main()
