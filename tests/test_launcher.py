import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from wolflauncher.launcher import DEFAULT_PLAYER_NAME, LaunchError, build_launch_command
from wolflauncher.models import Server


class BuildLaunchCommandTests(unittest.TestCase):
    def make_server(self, host: str = "dayz.example.test") -> Server:
        return Server(
            name="Example",
            group="Tests",
            host=host,
            game_port=2302,
            query_port=27016,
        )

    def test_builds_external_launcher_command_with_resolved_ip(self):
        with tempfile.NamedTemporaryFile() as launcher:
            with patch("wolflauncher.launcher.resolve_host", return_value="203.0.113.10") as resolve_host:
                command = build_launch_command(launcher.name, "PlayerOne", self.make_server())

        self.assertEqual(
            command,
            [
                "bash",
                launcher.name,
                "-s",
                "203.0.113.10:2302",
                "-p",
                "27016",
                "-n",
                "PlayerOne",
                "--launch",
            ],
        )
        resolve_host.assert_called_once_with("dayz.example.test")

    def test_blank_player_name_falls_back_to_survivor(self):
        with tempfile.NamedTemporaryFile() as launcher:
            with patch("wolflauncher.launcher.resolve_host", return_value="203.0.113.10"):
                command = build_launch_command(launcher.name, "   ", self.make_server())

        self.assertEqual(command[command.index("-n") + 1], DEFAULT_PLAYER_NAME)

    def test_non_default_game_and_query_ports_are_not_confused(self):
        server = Server(
            name="High Port",
            group="Tests",
            host="dayz.example.test",
            game_port=3302,
            query_port=3303,
        )
        with tempfile.NamedTemporaryFile() as launcher:
            with patch("wolflauncher.launcher.resolve_host", return_value="203.0.113.10"):
                command = build_launch_command(launcher.name, "PlayerOne", server)

        self.assertEqual(command[command.index("-s") + 1], "203.0.113.10:3302")
        self.assertEqual(command[command.index("-p") + 1], "3303")

    def test_player_name_is_preserved_as_single_argument(self):
        with tempfile.NamedTemporaryFile() as launcher:
            with patch("wolflauncher.launcher.resolve_host", return_value="203.0.113.10"):
                command = build_launch_command(
                    launcher.name,
                    "Wolf Player; echo nope",
                    self.make_server(),
                )

        self.assertEqual(command[command.index("-n") + 1], "Wolf Player; echo nope")

    def test_launcher_path_expands_user_home(self):
        with tempfile.TemporaryDirectory() as home:
            launcher_path = Path(home) / "dayz-launcher.sh"
            launcher_path.write_text("#!/usr/bin/env bash\n", encoding="utf-8")

            with patch.dict("os.environ", {"HOME": home}):
                with patch("wolflauncher.launcher.resolve_host", return_value="203.0.113.10"):
                    command = build_launch_command("~/dayz-launcher.sh", "PlayerOne", self.make_server())

        self.assertEqual(command[1], str(launcher_path))

    def test_missing_launcher_path_raises_launch_error(self):
        missing_path = str(Path(tempfile.gettempdir()) / "wolflauncher-missing-launcher.sh")

        with self.assertRaisesRegex(LaunchError, "Launcher script not found"):
            build_launch_command(missing_path, "PlayerOne", self.make_server())

    def test_directory_launcher_path_raises_launch_error(self):
        with tempfile.TemporaryDirectory() as launcher_dir:
            with self.assertRaisesRegex(LaunchError, "Launcher path is not a file"):
                build_launch_command(launcher_dir, "PlayerOne", self.make_server())

    def test_dns_failure_is_reported_as_launch_error(self):
        with tempfile.NamedTemporaryFile() as launcher:
            with patch("wolflauncher.launcher.resolve_host", side_effect=OSError("no host")):
                with self.assertRaisesRegex(LaunchError, "Could not resolve server host"):
                    build_launch_command(launcher.name, "PlayerOne", self.make_server())


if __name__ == "__main__":
    unittest.main()
