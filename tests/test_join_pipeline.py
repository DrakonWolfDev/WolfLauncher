"""Exercise the real join coordinators with side effects confined to test boundaries."""

import tempfile
import unittest
from contextlib import ExitStack
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from PySide6.QtWidgets import QApplication

from tests.test_product_availability import make_install
from wolflauncher.connect_preflight import ConnectPreflightCoordinator
from wolflauncher.launch_execution import LaunchExecutionCoordinator
from wolflauncher.models import Server
from wolflauncher.platform_detection import ProcessCheck
from wolflauncher.platforms.linux import LinuxPlatformBackend
from wolflauncher.server_launch_coordinator import IdentityWorker, ServerLaunchCoordinator
from wolflauncher.server_links import parse_server_link
from wolflauncher.status import ServerStatus
from wolflauncher.workers import ModWorker


class JoinPipelineTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        directory = self.stack.enter_context(tempfile.TemporaryDirectory())
        self.install = make_install(Path(directory))
        link = parse_server_link(
            "wolflauncher://join?v=1&host=203.0.113.10&game_port=2302&query_port=2303"
        )
        self.server = Server(
            "Shared server",
            "Link",
            link.host,
            link.game_port,
            link.query_port,
            strict_endpoint=True,
        )
        self.running = False
        self.scheduled = []
        self.dialog = Mock()
        self.dialog.isVisible.return_value = True
        self.window = SimpleNamespace(
            _shutting_down=False,
            preflight_dialog=None,
            preflight_server=None,
            preflight_mod_worker=None,
            preflight_workshop_worker=None,
            native_steam_mode_key=lambda: "native",
            launch_engine_key=lambda: "native",
            active_server_context=lambda: self.server,
            statusBar=Mock(return_value=Mock()),
            launch_button=Mock(),
            persist_launch_report=Mock(),
            player_name=Mock(),
            display_mods_result=Mock(),
            last_mod_result=None,
        )
        self.window.player_name.text.return_value = "Test player Ω"
        self.window.server_launch = ServerLaunchCoordinator(self.window)
        self.window.connect_preflight = ConnectPreflightCoordinator(self.window)
        self.window.launch_execution = LaunchExecutionCoordinator(self.window)
        backend = LinuxPlatformBackend()
        backend.process_running = lambda _name: self.running
        patches = {
            "wolflauncher.platforms._BACKEND": backend,
            "wolflauncher.server_launch_context.check_server": Mock(
                return_value=ServerStatus(
                    True,
                    resolved_ip=self.server.host,
                    connect=self.server.connect_target,
                    app_id=221100,
                )
            ),
            "wolflauncher.server_launch_context.detect_steam": lambda product: [self.install],
            "wolflauncher.server_discovery.resolve_dayz_server_wolfapi_v1": Mock(return_value=[]),
            "wolflauncher.connect_preflight.dayz_process_check": Mock(
                return_value=ProcessCheck(False, "Not running")
            ),
            "wolflauncher.connect_preflight.PreflightLaunchDialog": Mock(return_value=self.dialog),
            "wolflauncher.connect_preflight.start_host_detached": Mock(return_value=(True, 123)),
            "wolflauncher.connect_preflight.QTimer.singleShot": lambda _delay, callback: (
                self.scheduled.append(callback)
            ),
            "wolflauncher.mods.fetch_required_mods": Mock(return_value=[]),
        }
        for target, replacement in patches.items():
            self.stack.enter_context(patch(target, replacement))

        # Run real worker bodies synchronously. Network/filesystem discovery above
        # is the external boundary; no production test-mode switch is introduced.
        def run_inline(worker):
            worker.run()
            worker.finished.emit()

        self.stack.enter_context(patch.object(IdentityWorker, "start", run_inline))
        self.stack.enter_context(patch.object(ModWorker, "start", run_inline))

    def test_link_to_stopped_steam_mod_check_and_guarded_native_command(self):
        self.window.connect_preflight.start(self.server)
        self.dialog.start_launch.assert_not_called()
        self.assertEqual(len(self.scheduled), 1)
        self.running = True
        self.scheduled.pop(0)()
        self.dialog.start_launch.assert_called_once()
        command = self.dialog.start_launch.call_args.args[0]
        self.assertEqual(command[:3], ["steam", "-applaunch", "221100"])
        self.assertIn("-connect=203.0.113.10:2302", command)
        self.assertIn("-name=Test player Ω", command)
        self.assertEqual(
            self.window.last_mod_result.request_id, self.window.server_launch.request_id
        )
        self.assertEqual(
            self.dialog.process.setWorkingDirectory.call_args.args[0], str(self.install.dayz_dir)
        )

    def test_cancel_before_steam_ready_rejects_late_callback_and_never_launches(self):
        self.window.connect_preflight.start(self.server)
        self.assertEqual(len(self.scheduled), 1)
        self.window.connect_preflight.cancel()
        self.running = True
        self.scheduled.pop(0)()
        self.assertIsNone(self.window.server_launch.context)
        self.dialog.start_launch.assert_not_called()
        self.window.display_mods_result.assert_not_called()

    def test_mismatched_shared_link_game_endpoint_stops_before_steam_handoff(self):
        checker = Mock(
            return_value=ServerStatus(
                True, resolved_ip=self.server.host, connect="203.0.113.10:2402", app_id=221100
            )
        )
        with (
            patch("wolflauncher.server_launch_context.check_server", checker),
            patch("wolflauncher.server_launch_coordinator.QMessageBox.warning") as warning,
        ):
            self.window.connect_preflight.start(self.server)
        warning.assert_called_once()
        self.assertFalse(self.scheduled)
        self.dialog.start_launch.assert_not_called()

    def test_manifest_failure_never_reaches_command_or_workshop_handoff(self):
        self.running = True
        with patch(
            "wolflauncher.mods.fetch_required_mods", side_effect=ValueError("Malformed manifest")
        ):
            self.window.connect_preflight.start(self.server)
        self.dialog.set_failed.assert_called_once_with("mods", "Malformed manifest")
        self.dialog.start_launch.assert_not_called()

    def test_unpublished_requirement_blocks_before_workshop_download_or_command(self):
        from wolflauncher.mods import RequiredMod

        self.running = True
        with (
            patch(
                "wolflauncher.mods.fetch_required_mods",
                return_value=[RequiredMod("", name="Manual mod")],
            ),
            patch("wolflauncher.workers.fetch_workshop_metadata", return_value={}),
            patch(
                "wolflauncher.workers.query_workshop_item_states_isolated",
                return_value=SimpleNamespace(error="", items=[]),
            ),
            patch("wolflauncher.connect_preflight.WorkshopSubscriptionWorker") as downloader,
        ):
            self.window.connect_preflight.start(self.server)
        downloader.assert_not_called()
        self.dialog.start_launch.assert_not_called()
        self.assertEqual(self.dialog.set_failed.call_args.args[0], "mods")
        self.assertIn("Manual mod", self.dialog.set_failed.call_args.args[1])
