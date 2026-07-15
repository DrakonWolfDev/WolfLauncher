import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from PySide6.QtWidgets import QMessageBox

from wolflauncher.app import MainWindow
from wolflauncher.models import Server
from wolflauncher.platform_detection import SteamInstall


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
    @patch("wolflauncher.app.QMessageBox.warning")
    def test_stopped_steam_is_explained_at_startup(self, warning):
        window = SimpleNamespace(selected_steam_install=Mock(return_value=stopped_install()))

        MainWindow.check_startup_steam_state(window)

        self.assertIn("not currently running", warning.call_args.args[2])
        self.assertIn("Workshop mod information", warning.call_args.args[2])

    @patch("wolflauncher.app.QMessageBox.warning")
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

    @patch("wolflauncher.app.save_favourites")
    @patch("wolflauncher.app.update_curated_server", return_value=True)
    @patch("wolflauncher.app.QMessageBox.question", return_value=QMessageBox.No)
    def test_unfavourite_can_keep_server_in_list(self, _question, update, save):
        window = self.window()

        MainWindow.toggle_favourite(window, 0)

        self.assertFalse(window.servers[0].favourite)
        update.assert_called_once()
        window.remove_curated_server_row.assert_not_called()
        save.assert_called_once()

    @patch("wolflauncher.app.QMessageBox.question", return_value=QMessageBox.Yes)
    def test_unfavourite_can_remove_server_from_list(self, _question):
        window = self.window()

        MainWindow.toggle_favourite(window, 0)

        window.remove_curated_server_row.assert_called_once_with(0, confirm=False)

    @patch("wolflauncher.app.QMessageBox.question", return_value=QMessageBox.Cancel)
    def test_unfavourite_can_be_cancelled(self, _question):
        window = self.window()

        MainWindow.toggle_favourite(window, 0)

        self.assertTrue(window.servers[0].favourite)
        window.remove_curated_server_row.assert_not_called()


if __name__ == "__main__":
    unittest.main()
