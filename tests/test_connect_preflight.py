import unittest
from types import SimpleNamespace
from unittest.mock import Mock

from wolflauncher.connect_preflight import ConnectPreflightCoordinator
from wolflauncher.models import Server
from wolflauncher.mods import ModCheckResult


class ConnectPreflightCoordinatorTests(unittest.TestCase):
    def test_successful_mod_check_completes_when_every_item_is_ready(self):
        server = Server("Example", "Tests", "dayz.test", 2302, 27016)
        dialog = Mock()
        dialog.isVisible.return_value = True
        window = SimpleNamespace(
            preflight_mod_worker=object(),
            preflight_dialog=dialog,
            preflight_server=server,
            last_mod_result=None,
            display_mods_result=Mock(),
        )
        coordinator = ConnectPreflightCoordinator(window)
        coordinator.finish = Mock()

        coordinator.finish_mod_check(ModCheckResult(True, server, []))

        self.assertIsNone(window.preflight_mod_worker)
        self.assertIsNotNone(window.last_mod_result)
        window.display_mods_result.assert_called_once_with(window.last_mod_result)
        dialog.set_complete.assert_called_once_with("mods", "All 0 required mod(s) are ready.")
        coordinator.finish.assert_called_once_with()

    def test_failed_mod_check_marks_the_dialog_failed(self):
        server = Server("Example", "Tests", "dayz.test", 2302, 27016)
        dialog = Mock()
        dialog.isVisible.return_value = True
        window = SimpleNamespace(
            preflight_mod_worker=object(),
            preflight_dialog=dialog,
            preflight_server=server,
            launch_button=Mock(),
        )

        ConnectPreflightCoordinator(window).finish_mod_check(
            ModCheckResult(False, server, [], error="Manifest unavailable")
        )

        dialog.set_failed.assert_called_once_with("mods", "Manifest unavailable")
        window.launch_button.setEnabled.assert_called_once_with(True)


if __name__ == "__main__":
    unittest.main()
