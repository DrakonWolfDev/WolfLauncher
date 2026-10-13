import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from PySide6.QtWidgets import QMessageBox

from wolflauncher.mods import RequiredMod
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

    @patch(
        "wolflauncher.workshop_resolution_controller.QMessageBox.question",
        return_value=QMessageBox.Yes,
    )
    def test_library_force_update_uses_selected_installed_mod_without_server_check(
        self, _question
    ):
        mod = RequiredMod("111", name="Library Mod", installed=True)
        install = SimpleNamespace(workshop_dir=object(), running=True)
        window = SimpleNamespace(
            viewing_installed_workshop_library=Mock(return_value=True),
            selected_required_mod=Mock(return_value=mod),
            workshop_subscription_worker=None,
            launch_engine_key=Mock(return_value="native"),
            selected_steam_install=Mock(return_value=install),
            start_installed_mod_updates=Mock(),
            _selected_mod_result=Mock(),
        )

        WorkshopResolutionCoordinator(window).force_update_mod(0)

        window.start_installed_mod_updates.assert_called_once_with([mod], install)
        window._selected_mod_result.assert_not_called()


if __name__ == "__main__":
    unittest.main()
