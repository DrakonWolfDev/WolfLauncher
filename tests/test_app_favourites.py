import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from PySide6.QtWidgets import QMessageBox

from wolflauncher.app import MainWindow
from wolflauncher.models import Server
from wolflauncher.platform_detection import SteamInstall, build_steam_start_command


def stopped_install() -> SteamInstall:
    return SteamInstall(
        mode="native",
        executable="steam",
        running=False,
        root=Path("/steam"),
        steamapps=Path("/steam/steamapps"),
        dayz_dir=Path("/steam/steamapps/common/DayZ"),
        workshop_dir=Path("/steam/steamapps/workshop/content/221100"),
    )


class StartupSteamCheckTests(unittest.TestCase):
    def test_native_steam_start_command_uses_detected_executable(self):
        self.assertEqual(build_steam_start_command(stopped_install()), ["steam"])

    def test_native_steam_start_command_uses_selected_executable(self):
        install = stopped_install()
        install.executable = "com.valvesoftware.Steam"
        self.assertEqual(
            build_steam_start_command(install),
            ["com.valvesoftware.Steam"],
        )

    @patch("wolflauncher.launch_feature.QMessageBox.warning")
    def test_stopped_steam_is_explained_at_startup(self, warning):
        window = SimpleNamespace(selected_steam_install=Mock(return_value=stopped_install()))

        MainWindow.check_startup_steam_state(window)

        self.assertIn("not currently running", warning.call_args.args[2])
        self.assertIn("Workshop mod information", warning.call_args.args[2])

    @patch("wolflauncher.launch_feature.QMessageBox.warning")
    def test_running_steam_does_not_warn(self, warning):
        install = stopped_install()
        install.running = True
        window = SimpleNamespace(selected_steam_install=Mock(return_value=install))

        MainWindow.check_startup_steam_state(window)

        warning.assert_not_called()


class FavouriteRemovalChoiceTests(unittest.TestCase):
    def window(self):
        server = Server("Example", "Community", "dayz.test", 2302, 27016, True)
        return SimpleNamespace(
            servers=[server],
            favourites={"dayz.test:2302:27016"},
            config_path=Path("servers.yaml"),
            table=Mock(),
            refresh_curated_server_cards=Mock(),
            remove_curated_server_row=Mock(),
        )

    @patch("wolflauncher.settings_feature.save_favourites")
    @patch("wolflauncher.curated_servers_controller.update_curated_server", return_value=True)
    @patch(
        "wolflauncher.curated_servers_controller.QMessageBox.question",
        return_value=QMessageBox.No,
    )
    def test_unfavourite_can_keep_server_in_list(self, _question, update, save):
        window = self.window()

        MainWindow.toggle_favourite(window, 0)

        self.assertFalse(window.servers[0].favourite)
        update.assert_called_once()
        window.remove_curated_server_row.assert_not_called()
        save.assert_called_once()

    @patch(
        "wolflauncher.curated_servers_controller.QMessageBox.question",
        return_value=QMessageBox.Yes,
    )
    def test_unfavourite_can_remove_server_from_list(self, _question):
        window = self.window()

        MainWindow.toggle_favourite(window, 0)

        window.remove_curated_server_row.assert_called_once_with(0, confirm=False)

    @patch(
        "wolflauncher.curated_servers_controller.QMessageBox.question",
        return_value=QMessageBox.Cancel,
    )
    def test_unfavourite_can_be_cancelled(self, _question):
        window = self.window()

        MainWindow.toggle_favourite(window, 0)

        self.assertTrue(window.servers[0].favourite)
        window.remove_curated_server_row.assert_not_called()


class FavouriteEmptyStateTests(unittest.TestCase):
    def window(self, favourite: bool):
        return SimpleNamespace(
            servers=[Server("Example", "Community", "dayz.test", 2302, 27016, favourite)],
            empty_favourites_card=Mock(),
            server_cards=Mock(),
            table=Mock(),
            move_server_up_button=Mock(),
            move_server_down_button=Mock(),
            refresh_status_button=Mock(),
            launch_button=Mock(),
        )

    def test_empty_state_is_shown_when_no_servers_are_favourited(self):
        window = self.window(favourite=False)

        MainWindow._update_empty_favourites_state(window)

        window.empty_favourites_card.setVisible.assert_called_once_with(True)
        window.server_cards.setVisible.assert_called_once_with(False)
        window.launch_button.setEnabled.assert_called_once_with(False)

    def test_empty_state_is_hidden_when_a_server_is_favourited(self):
        window = self.window(favourite=True)

        MainWindow._update_empty_favourites_state(window)

        window.empty_favourites_card.setVisible.assert_called_once_with(False)
        window.server_cards.setVisible.assert_called_once_with(True)
        window.launch_button.setEnabled.assert_called_once_with(True)


if __name__ == "__main__":
    unittest.main()
