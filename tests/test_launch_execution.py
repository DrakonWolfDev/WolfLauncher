import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from wolflauncher.launch_execution import LaunchExecutionCoordinator
from wolflauncher.models import Server


class LaunchExecutionCoordinatorTests(unittest.TestCase):
    @patch("wolflauncher.launch_execution.build_launch_command", return_value=["external"])
    def test_external_command_uses_a_valid_cached_resolved_ipv4_address(self, build_command):
        server = Server("Example", "Tests", "dayz.example.test", 2302, 27016)
        resolved_item = Mock()
        resolved_item.text.return_value = "203.0.113.10"
        table = Mock()
        table.item.return_value = resolved_item
        window = SimpleNamespace(
            active_discovered_server=None,
            table=table,
            player_name=Mock(),
            launcher_path=Mock(),
            launch_engine_key=Mock(return_value="external"),
        )
        window.player_name.text.return_value = "Survivor"
        window.launcher_path.text.return_value = "/launcher/dayz-launcher.sh"

        command = LaunchExecutionCoordinator(window).build_command(server, row=0)

        self.assertEqual(command, ["external"])
        self.assertEqual(build_command.call_args.args[2].host, "203.0.113.10")

    @patch("wolflauncher.launch_execution.build_launch_command", return_value=["external"])
    def test_external_command_preserves_host_when_cached_value_is_not_an_ipv4_address(
        self, build_command
    ):
        server = Server("Example", "Tests", "dayz.example.test", 2302, 27016)
        resolved_item = Mock()
        resolved_item.text.return_value = "Checking..."
        table = Mock()
        table.item.return_value = resolved_item
        window = SimpleNamespace(
            active_discovered_server=None,
            table=table,
            player_name=Mock(),
            launcher_path=Mock(),
            launch_engine_key=Mock(return_value="external"),
        )
        window.player_name.text.return_value = "Survivor"
        window.launcher_path.text.return_value = "/launcher/dayz-launcher.sh"

        command = LaunchExecutionCoordinator(window).build_command(server, row=0)

        self.assertEqual(command, ["external"])
        self.assertEqual(build_command.call_args.args[2].host, "dayz.example.test")


if __name__ == "__main__":
    unittest.main()
