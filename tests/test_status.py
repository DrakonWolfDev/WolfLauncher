import json
import subprocess
import unittest
from unittest.mock import patch

from wolflauncher.models import Server
from wolflauncher.status import ServerStatus, check_server, resolve_host


class ResolveHostTests(unittest.TestCase):
    def test_resolve_host_returns_ip_addresses_unchanged(self):
        self.assertEqual(resolve_host("203.0.113.10"), "203.0.113.10")

    @patch("wolflauncher.status.socket.gethostbyname", return_value="203.0.113.10")
    def test_resolve_host_looks_up_dns_names(self, gethostbyname):
        self.assertEqual(resolve_host("dayz.example.test"), "203.0.113.10")
        gethostbyname.assert_called_once_with("dayz.example.test")


class CheckServerTests(unittest.TestCase):
    def make_server(self) -> Server:
        return Server(
            name="Example",
            group="Tests",
            host="dayz.example.test",
            game_port=2302,
            query_port=27016,
        )

    @patch("wolflauncher.status.resolve_host", return_value="203.0.113.10")
    @patch("wolflauncher.status.shutil.which", return_value="/usr/bin/gamedig")
    @patch("wolflauncher.status.subprocess.run")
    def test_online_server_maps_gamedig_response(self, run, which, resolve_host_mock):
        run.return_value = subprocess.CompletedProcess(
            args=[],
            returncode=0,
            stdout=json.dumps(
                {
                    "name": "Example DayZ",
                    "map": "chernarusplus",
                    "numplayers": 12,
                    "maxplayers": 60,
                    "ping": 42,
                    "password": True,
                    "connect": "203.0.113.10:2302",
                    "raw": {
                        "tags": ["battleye", "mod"],
                        "time": "10:30",
                        "version": "1.26",
                    },
                }
            ),
            stderr="",
        )

        status = check_server(self.make_server())

        self.assertEqual(
            status,
            ServerStatus(
                online=True,
                resolved_ip="203.0.113.10",
                server_name="Example DayZ",
                map_name="chernarusplus",
                players="12/60",
                time="10:30",
                version="1.26",
                ping="42",
                password=True,
                modded=True,
                connect="203.0.113.10:2302",
            ),
        )
        resolve_host_mock.assert_called_once_with("dayz.example.test")
        which.assert_called_once_with("gamedig")
        run.assert_called_once()

    @patch("wolflauncher.status.resolve_host", return_value="203.0.113.10")
    @patch("wolflauncher.status.shutil.which", return_value="/usr/bin/gamedig")
    @patch("wolflauncher.status.subprocess.run")
    def test_connect_address_falls_back_to_game_port(self, run, which, resolve_host_mock):
        run.return_value = subprocess.CompletedProcess(
            args=[],
            returncode=0,
            stdout=json.dumps(
                {
                    "name": "Example DayZ",
                    "numplayers": 0,
                    "maxplayers": 60,
                    "raw": {},
                }
            ),
            stderr="",
        )

        status = check_server(self.make_server())

        self.assertTrue(status.online)
        self.assertEqual(status.connect, "203.0.113.10:2302")
        self.assertEqual(status.map_name, "Unknown")
        self.assertEqual(status.time, "N/A")

    @patch("wolflauncher.status.resolve_host", side_effect=OSError("no host"))
    def test_dns_failure_returns_offline_status(self, resolve_host_mock):
        status = check_server(self.make_server())

        self.assertFalse(status.online)
        self.assertIn("DNS failed", status.error)

    @patch("wolflauncher.status.resolve_host", return_value="203.0.113.10")
    @patch("wolflauncher.status.shutil.which", return_value=None)
    def test_missing_gamedig_returns_offline_status(self, which, resolve_host_mock):
        status = check_server(self.make_server())

        self.assertFalse(status.online)
        self.assertEqual(status.resolved_ip, "203.0.113.10")
        self.assertEqual(status.error, "gamedig not installed")

    @patch("wolflauncher.status.resolve_host", return_value="203.0.113.10")
    @patch("wolflauncher.status.shutil.which", return_value="/usr/bin/gamedig")
    @patch("wolflauncher.status.subprocess.run", side_effect=subprocess.TimeoutExpired("gamedig", 5))
    def test_gamedig_timeout_returns_offline_status(self, run, which, resolve_host_mock):
        status = check_server(self.make_server())

        self.assertFalse(status.online)
        self.assertEqual(status.resolved_ip, "203.0.113.10")
        self.assertEqual(status.error, "status check timed out")

    @patch("wolflauncher.status.resolve_host", return_value="203.0.113.10")
    @patch("wolflauncher.status.shutil.which", return_value="/usr/bin/gamedig")
    @patch("wolflauncher.status.subprocess.run")
    def test_gamedig_error_uses_stderr(self, run, which, resolve_host_mock):
        run.return_value = subprocess.CompletedProcess(
            args=[],
            returncode=1,
            stdout="",
            stderr="socket closed",
        )

        status = check_server(self.make_server())

        self.assertFalse(status.online)
        self.assertEqual(status.resolved_ip, "203.0.113.10")
        self.assertEqual(status.error, "socket closed")

    @patch("wolflauncher.status.resolve_host", return_value="203.0.113.10")
    @patch("wolflauncher.status.shutil.which", return_value="/usr/bin/gamedig")
    @patch("wolflauncher.status.subprocess.run")
    def test_invalid_json_returns_offline_status(self, run, which, resolve_host_mock):
        run.return_value = subprocess.CompletedProcess(
            args=[],
            returncode=0,
            stdout="not json",
            stderr="",
        )

        status = check_server(self.make_server())

        self.assertFalse(status.online)
        self.assertEqual(status.resolved_ip, "203.0.113.10")
        self.assertEqual(status.error, "invalid gamedig response")

    @patch("wolflauncher.status.resolve_host", return_value="203.0.113.10")
    @patch("wolflauncher.status.shutil.which", return_value="/usr/bin/gamedig")
    @patch("wolflauncher.status.subprocess.run")
    def test_partial_restart_response_returns_offline_status(self, run, which, resolve_host_mock):
        run.return_value = subprocess.CompletedProcess(
            args=[],
            returncode=0,
            stdout=json.dumps({"name": "", "raw": {}}),
            stderr="",
        )

        status = check_server(self.make_server())

        self.assertFalse(status.online)
        self.assertEqual(status.resolved_ip, "203.0.113.10")
        self.assertEqual(status.error, "offline, restarting, or incomplete query response")


if __name__ == "__main__":
    unittest.main()
