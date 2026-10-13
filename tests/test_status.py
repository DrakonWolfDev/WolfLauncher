import json
import subprocess
import threading
import unittest
from unittest.mock import call, patch

from wolflauncher.models import Server
from wolflauncher.status import (
    ServerStatus,
    ServerStatusOutcome,
    _hidden_process_kwargs,
    _run_cancellable,
    check_server,
    gamedig_command,
    resolve_host,
)


class ResolveHostTests(unittest.TestCase):
    def test_resolve_host_returns_ip_addresses_unchanged(self):
        self.assertEqual(resolve_host("203.0.113.10"), "203.0.113.10")

    @patch("wolflauncher.status.socket.gethostbyname", return_value="203.0.113.10")
    def test_resolve_host_looks_up_dns_names(self, gethostbyname):
        self.assertEqual(resolve_host("dayz.example.test"), "203.0.113.10")
        gethostbyname.assert_called_once_with("dayz.example.test")


class CancellableProcessTests(unittest.TestCase):
    @patch("wolflauncher.status.os.name", "nt")
    @patch("wolflauncher.status.subprocess.CREATE_NO_WINDOW", 0x08000000, create=True)
    def test_windows_processes_are_started_without_console_windows(self):
        self.assertEqual(_hidden_process_kwargs(), {"creationflags": 0x08000000})

    @patch("wolflauncher.status.subprocess.Popen")
    def test_cancel_terminates_an_inflight_gamedig_process(self, popen):
        process = popen.return_value
        process.poll.return_value = None
        process.wait.return_value = 0
        cancelled = threading.Event()
        cancelled.set()

        result = _run_cancellable(["gamedig"], 2, cancelled)

        self.assertIsNone(result)
        self.assertEqual(popen.call_args.kwargs["encoding"], "utf-8")
        process.terminate.assert_called_once_with()
        process.wait.assert_called_once_with(timeout=0.25)


class GameDigCommandTests(unittest.TestCase):
    @patch("wolflauncher.status.Path.is_file", return_value=True)
    @patch("wolflauncher.status.shutil.which", return_value=r"C:\\bundle\\node.exe")
    def test_bundled_script_runs_through_bundled_node(self, which, is_file):
        with patch.dict(
            "wolflauncher.status.os.environ",
            {"WOLFLAUNCHER_GAMEDIG_SCRIPT": r"C:\\bundle\\gamedig.js"},
            clear=True,
        ):
            command = gamedig_command()

        self.assertEqual(command, [r"C:\\bundle\\node.exe", r"C:\\bundle\\gamedig.js"])
        which.assert_called_once_with("node")
        is_file.assert_called_once()

    @patch("wolflauncher.status.SOURCE_GAMEDIG_SCRIPT")
    @patch("wolflauncher.status.shutil.which", return_value="/usr/bin/gamedig")
    def test_path_gamedig_remains_the_source_runtime_fallback(self, which, source_script):
        source_script.is_file.return_value = False
        with patch.dict("wolflauncher.status.os.environ", {}, clear=True):
            command = gamedig_command()

        self.assertEqual(command, ["/usr/bin/gamedig"])
        which.assert_has_calls([call("node"), call("gamedig")])

    @patch("wolflauncher.status.SOURCE_GAMEDIG_SCRIPT")
    @patch("wolflauncher.status.shutil.which", return_value=r"C:\\Program Files\\nodejs\\node.exe")
    def test_source_checkout_uses_lockfile_pinned_gamedig(self, which, source_script):
        source_script.is_file.return_value = True
        source_script.__str__.return_value = (
            r"C:\\repo\\packaging\\npm\\node_modules\\gamedig\\bin\\gamedig.js"
        )
        with patch.dict("wolflauncher.status.os.environ", {}, clear=True):
            command = gamedig_command()

        self.assertEqual(
            command,
            [r"C:\\Program Files\\nodejs\\node.exe", str(source_script)],
        )
        which.assert_called_once_with("node")


class CheckServerTests(unittest.TestCase):
    def setUp(self):
        source_patcher = patch("wolflauncher.status.SOURCE_GAMEDIG_SCRIPT")
        source_script = source_patcher.start()
        source_script.is_file.return_value = False
        self.addCleanup(source_patcher.stop)

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
                        "dayAcceleration": 6,
                        "nightAcceleration": 4,
                        "version": "1.26",
                    },
                }
            ),
            stderr="",
        )

        status = check_server(self.make_server())

        expected = ServerStatus(
            online=True,
            resolved_ip="203.0.113.10",
            server_name="Example DayZ",
            map_name="chernarusplus",
            players="12/60",
            time="10:30",
            day_acceleration=6,
            night_acceleration=4,
            version="1.26",
            ping="42",
            password=True,
            modded=True,
            connect="203.0.113.10:2302",
        )
        expected.query_started_at = status.query_started_at
        expected.duration_ms = status.duration_ms
        expected.last_successful_query = status.last_successful_query
        self.assertEqual(status, expected)
        resolve_host_mock.assert_called_once_with("dayz.example.test")
        which.assert_has_calls([call("node"), call("gamedig")])
        run.assert_called_once()
        self.assertEqual(run.call_args.kwargs["encoding"], "utf-8")

    @patch("wolflauncher.status.resolve_host", return_value="203.0.113.10")
    @patch("wolflauncher.status.shutil.which", return_value="/usr/bin/gamedig")
    @patch("wolflauncher.status.subprocess.run")
    def test_online_server_preserves_unicode_gamedig_name(self, run, _which, _resolve_host):
        run.return_value = subprocess.CompletedProcess(
            args=[],
            returncode=0,
            stdout=json.dumps(
                {"name": "测试 DayZ", "numplayers": 1, "maxplayers": 60, "raw": {}},
                ensure_ascii=False,
            ),
            stderr="",
        )

        status = check_server(self.make_server())

        self.assertTrue(status.online)
        self.assertEqual(status.server_name, "测试 DayZ")
        self.assertTrue(status.query_started_at.endswith("+00:00"))
        self.assertGreaterEqual(status.duration_ms, 0)
        self.assertEqual(status.last_successful_query, status.query_started_at)
        self.assertEqual(status.consecutive_failures, 0)

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
    def test_dns_failure_returns_unknown_network_status(self, resolve_host_mock):
        status = check_server(self.make_server())

        self.assertFalse(status.online)
        self.assertIs(status.outcome, ServerStatusOutcome.NETWORK_ERROR)
        self.assertEqual(status.display_state, "UNKNOWN")
        self.assertIn("Unable to check server", status.user_message())
        self.assertIn("DNS failed", status.error)

    @patch("wolflauncher.status.resolve_host", return_value="203.0.113.10")
    @patch("wolflauncher.status.shutil.which", return_value=None)
    def test_missing_gamedig_returns_unknown_check_status(self, which, resolve_host_mock):
        status = check_server(self.make_server())

        self.assertFalse(status.online)
        self.assertIs(status.outcome, ServerStatusOutcome.CHECK_ERROR)
        self.assertEqual(status.resolved_ip, "203.0.113.10")
        self.assertEqual(status.error, "gamedig not installed")

    @patch("wolflauncher.status.resolve_host", return_value="203.0.113.10")
    @patch("wolflauncher.status.shutil.which", return_value="/usr/bin/gamedig")
    @patch(
        "wolflauncher.status.subprocess.run", side_effect=subprocess.TimeoutExpired("gamedig", 5)
    )
    def test_gamedig_timeout_returns_unknown_timeout_status(self, run, which, resolve_host_mock):
        status = check_server(self.make_server())

        self.assertFalse(status.online)
        self.assertIs(status.outcome, ServerStatusOutcome.TIMEOUT)
        self.assertIn("isn't responding", status.user_message())
        self.assertEqual(status.resolved_ip, "203.0.113.10")
        self.assertEqual(status.error, "status check timed out")

    @patch("wolflauncher.status.resolve_host", return_value="203.0.113.10")
    @patch("wolflauncher.status.shutil.which", return_value="/usr/bin/gamedig")
    @patch("wolflauncher.status.subprocess.run", side_effect=OSError("process unavailable"))
    def test_process_failure_returns_unknown_check_status(self, _run, _which, _resolve_host):
        status = check_server(self.make_server())

        self.assertFalse(status.online)
        self.assertIs(status.outcome, ServerStatusOutcome.CHECK_ERROR)
        self.assertIn("process unavailable", status.error)
        self.assertTrue(status.query_started_at)

    @patch("wolflauncher.status.resolve_host", return_value="203.0.113.10")
    @patch("wolflauncher.status.shutil.which", return_value="/usr/bin/gamedig")
    @patch("wolflauncher.status._run_cancellable", return_value=None)
    def test_cancelled_query_returns_unknown_cancelled_status(
        self, _run_cancellable_mock, _which, _resolve_host
    ):
        status = check_server(self.make_server(), cancel_event=threading.Event())

        self.assertFalse(status.online)
        self.assertIs(status.outcome, ServerStatusOutcome.CANCELLED)
        self.assertEqual(status.display_state, "UNKNOWN")
        self.assertEqual(status.user_message(), "Status check cancelled")

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
        self.assertIs(status.outcome, ServerStatusOutcome.CHECK_ERROR)
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
        self.assertIs(status.outcome, ServerStatusOutcome.INVALID_RESPONSE)
        self.assertEqual(status.resolved_ip, "203.0.113.10")
        self.assertEqual(status.error, "invalid gamedig response")

    @patch("wolflauncher.status.resolve_host", return_value="203.0.113.10")
    @patch("wolflauncher.status.shutil.which", return_value="/usr/bin/gamedig")
    @patch("wolflauncher.status.subprocess.run")
    def test_partial_restart_response_returns_unknown_status(self, run, which, resolve_host_mock):
        run.return_value = subprocess.CompletedProcess(
            args=[],
            returncode=0,
            stdout=json.dumps({"name": "", "raw": {}}),
            stderr="",
        )

        status = check_server(self.make_server())

        self.assertFalse(status.online)
        self.assertIs(status.outcome, ServerStatusOutcome.INVALID_RESPONSE)
        self.assertEqual(status.resolved_ip, "203.0.113.10")
        self.assertEqual(status.error, "offline, restarting, or incomplete query response")


if __name__ == "__main__":
    unittest.main()
