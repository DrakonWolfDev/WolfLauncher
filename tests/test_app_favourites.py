import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from PySide6.QtWidgets import QMessageBox

from wolflauncher.app import MainWindow
from wolflauncher.models import DiscoveredServer, Server
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
            empty_favourites_page=Mock(),
            server_cards=Mock(),
            favourites_content=Mock(),
            table=Mock(),
            move_server_up_button=Mock(),
            move_server_down_button=Mock(),
            refresh_status_button=Mock(),
            launch_button=Mock(),
        )

    def test_empty_state_is_shown_when_no_servers_are_favourited(self):
        window = self.window(favourite=False)

        MainWindow._update_empty_favourites_state(window)

        window.favourites_content.setCurrentWidget.assert_called_once_with(
            window.empty_favourites_page
        )
        window.launch_button.setEnabled.assert_called_once_with(False)

    def test_empty_state_is_hidden_when_a_server_is_favourited(self):
        window = self.window(favourite=True)

        MainWindow._update_empty_favourites_state(window)

        window.favourites_content.setCurrentWidget.assert_called_once_with(window.server_cards)
        window.launch_button.setEnabled.assert_called_once_with(True)


class BrowserFavouriteTests(unittest.TestCase):
    @patch("wolflauncher.server_browser_feature.add_curated_server")
    @patch("wolflauncher.server_browser_feature.server_cache.get_server")
    def test_browser_star_persists_a_new_favourite(self, get_server, add_curated):
        discovered = DiscoveredServer(
            "Provider Name", "203.0.113.10", 2302, 27016, server_name="Live Name"
        )
        get_server.return_value = discovered
        name_item = Mock()
        name_item.data.return_value = discovered.cache_key
        browser_table = Mock()
        browser_table.item.return_value = name_item
        window = SimpleNamespace(
            browser_table=browser_table,
            server_cache=Mock(),
            servers=[],
            favourites=set(),
            config_path=Path("servers.yaml"),
            _save_favourites_index=Mock(),
            add_curated_server_row=Mock(),
        )

        MainWindow.handle_browser_cell_clicked(window, 0, 0)

        self.assertEqual(len(window.favourites), 1)
        window._save_favourites_index.assert_called_once_with()
        curated = add_curated.call_args.args[1]
        self.assertTrue(curated.favourite)
        window.add_curated_server_row.assert_called_once_with(curated)


class FavouriteProfileReloadTests(unittest.TestCase):
    def test_profile_reload_rebuilds_the_visible_curated_rows(self):
        server = Server("Experimental", "Community", "dayz.test", 2302, 27016, True)
        window = SimpleNamespace(
            table=Mock(),
            servers=[server],
            curated_status_cache={},
            _set_curated_server_table_item=Mock(),
            saved_selected_row=Mock(return_value=-1),
            update_curated_status_summary=Mock(),
            refresh_curated_server_cards=Mock(),
            refresh_recent_servers=Mock(),
            update_launch_button_text=Mock(),
        )

        MainWindow.reload_curated_servers(window)

        window.table.clearContents.assert_called_once()
        window.table.setRowCount.assert_called_once_with(1)
        window.refresh_curated_server_cards.assert_called_once()
        window.refresh_recent_servers.assert_called_once()


class StatusRefreshNoticeTests(unittest.TestCase):
    def window(self):
        status_bar = Mock()
        return SimpleNamespace(
            table=Mock(),
            last_refresh_label=Mock(),
            _status_refresh_rows={0, 1},
            _status_refresh_outcomes={0: "UNKNOWN", 1: "UNKNOWN"},
            _status_failure_notice_shown=False,
            _set_status_refresh_enabled=Mock(),
            statusBar=Mock(return_value=status_bar),
            update_launch_button_text=Mock(),
        )

    def test_widespread_failure_notice_is_once_per_streak_and_resets_on_recovery(self):
        window = self.window()

        MainWindow.handle_refresh_finished(window)
        self.assertEqual(window.statusBar.return_value.showMessage.call_count, 1)

        window._status_refresh_rows = {0, 1}
        window._status_refresh_outcomes = {0: "UNKNOWN", 1: "UNKNOWN"}
        MainWindow.handle_refresh_finished(window)
        self.assertEqual(window.statusBar.return_value.showMessage.call_count, 1)

        window._status_refresh_rows = {0, 1}
        window._status_refresh_outcomes = {0: "ONLINE", 1: "UNKNOWN"}
        MainWindow.handle_refresh_finished(window)
        self.assertFalse(window._status_failure_notice_shown)

        window._status_refresh_rows = {0, 1}
        window._status_refresh_outcomes = {0: "UNKNOWN", 1: "UNKNOWN"}
        MainWindow.handle_refresh_finished(window)
        self.assertEqual(window.statusBar.return_value.showMessage.call_count, 2)


if __name__ == "__main__":
    unittest.main()
