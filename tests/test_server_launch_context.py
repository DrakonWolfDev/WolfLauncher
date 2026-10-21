import tempfile
import threading
import unittest
from dataclasses import FrozenInstanceError, replace
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from tests.test_product_availability import make_install
from wolflauncher.dayz_product import EXPERIMENTAL, STABLE
from wolflauncher.launch_execution import LaunchExecutionCoordinator
from wolflauncher.models import DiscoveredServer, Server
from wolflauncher.mods import ModCheckResult
from wolflauncher.server_launch_context import IdentityResolutionError, resolve_context
from wolflauncher.server_launch_coordinator import ServerLaunchCoordinator
from wolflauncher.status import ServerStatus


class ServerLaunchContextTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        self.installs = {p.key: make_install(self.root, p) for p in (STABLE, EXPERIMENTAL)}
        self.server = Server("Misleading Stable name", "Favourite", "dayz.test", 2302, 27016)

    def resolve(self, app_id=1024020, **kwargs):
        checker = kwargs.pop(
            "checker",
            Mock(
                return_value=ServerStatus(
                    True, resolved_ip="203.0.113.2", connect="203.0.113.2:2302", app_id=app_id
                )
            ),
        )
        return resolve_context(
            kwargs.pop("server", self.server),
            "request",
            "native",
            "external",
            checker=checker,
            detector=kwargs.pop("detector", lambda product: [self.installs[product.key]]),
            resolver=kwargs.pop("resolver", lambda *args, **kwargs: []),
            monotonic=lambda: 100,
            **kwargs,
        )

    def test_stable_experimental_stable_uses_exact_install_and_engine(self):
        for app_id, product, engine in (
            (221100, STABLE, "external"),
            (1024020, EXPERIMENTAL, "native"),
            (221100, STABLE, "external"),
        ):
            context = self.resolve(app_id)
            self.assertEqual(context.product, product)
            self.assertEqual(context.install.dayz_dir, self.installs[product.key].dayz_dir)
            self.assertEqual(context.engine, engine)
            self.assertEqual(context.server.product, product.key)
            self.assertTrue(context.fresh(130))
            self.assertFalse(context.fresh(130.001))

    def test_context_is_immutable_and_restored_install_is_an_independent_copy(self):
        context = self.resolve()
        with self.assertRaises(FrozenInstanceError):
            context.engine = "external"
        install = context.install
        install.dayz_dir = Path("wrong")
        server = context.server
        server.product = "stable"
        self.assertEqual(context.server.product, "experimental")
        self.assertEqual(context.install.dayz_dir, self.installs["experimental"].dayz_dir)

    def test_fresh_install_without_workshop_can_check_required_mods(self):
        from wolflauncher.mods import RequiredMod, check_server_mods

        for app_id, product in ((221100, STABLE), (1024020, EXPERIMENTAL)):
            install = replace(self.installs[product.key], workshop_dir=None)
            self.installs[product.key] = install
            context = self.resolve(app_id)
            expected = install.steamapps / "workshop" / "content" / "221100"
            self.assertEqual(context.install.workshop_dir, expected)
            self.assertFalse(expected.exists())
            with patch(
                "wolflauncher.mods.fetch_required_mods",
                return_value=[RequiredMod("123", "Required mod")],
            ):
                result = check_server_mods(context.server, expected)
            self.assertTrue(result.ok)
            self.assertEqual(result.installed_count, 0)
            self.assertEqual([mod.workshop_id for mod in result.missing_mods], ["123"])
            self.assertFalse(expected.exists())

    def test_missing_library_is_distinct_from_missing_workshop(self):
        self.installs["experimental"] = replace(
            self.installs["experimental"], steamapps=None, workshop_dir=None
        )
        with self.assertRaisesRegex(IdentityResolutionError, "could not locate the Steam library"):
            self.resolve()


    def test_missing_malformed_truncated_and_unsupported_ids_never_prepare_install(self):
        for app_id in (None, "1024020", True, 46868, 42):
            detector = Mock()
            with self.subTest(app_id=app_id), self.assertRaises(IdentityResolutionError):
                self.resolve(app_id, detector=detector)
            detector.assert_not_called()

    def test_manual_directory_query_port_is_separate_from_game_port(self):
        resolver = Mock(return_value=[DiscoveredServer("EXP", "203.0.113.2", 2302, 29000)])
        checker = Mock(
            side_effect=[
                ServerStatus(False, error="wrong query port"),
                ServerStatus(
                    True, resolved_ip="203.0.113.2", connect="203.0.113.2:2302", app_id=1024020
                ),
            ]
        )
        context = self.resolve(checker=checker, resolver=resolver)
        resolver.assert_called_once_with("dayz.test", game_port=2302, product="all", timeout=4)
        self.assertEqual(context.live_identity.endpoint, ("203.0.113.2", 2302, 29000))
        self.assertEqual(checker.call_args.args[0].query_port, 29000)

    def test_timeout_does_not_guess_and_directory_failure_can_use_direct_live_id(self):
        resolver = Mock(side_effect=RuntimeError("directory timeout"))
        self.assertEqual(self.resolve(resolver=resolver).product, EXPERIMENTAL)
        with self.assertRaisesRegex(IdentityResolutionError, "directory timeout"):
            self.resolve(
                checker=Mock(return_value=ServerStatus(False, error="query timeout")),
                resolver=resolver,
            )

    def test_misfiled_known_stable_label_is_settled_by_live_experimental(self):
        context = self.resolve(
            server=replace(self.server, product="stable", identity_state="conflict")
        )
        self.assertEqual(context.server.identity_state, "known")
        self.assertEqual(context.server.product, "experimental")
        self.assertTrue(context.server.identity_evidence[-1]["verified"])

    def test_missing_experimental_and_cancelled_requests_never_fall_back(self):
        self.installs["experimental"] = replace(self.installs["experimental"], dayz_dir=None)
        with self.assertRaisesRegex(IdentityResolutionError, "Install DayZ Experimental") as caught:
            self.resolve()
        self.assertEqual(caught.exception.resolved_server.product, "experimental")
        self.assertTrue(caught.exception.resolved_server.identity_evidence[-1]["verified"])
        event = threading.Event()
        event.set()
        with self.assertRaisesRegex(IdentityResolutionError, "cancelled"):
            self.resolve(cancel_event=event)

    def test_stale_resolution_cannot_replace_context_or_call_continuation(self):
        window = SimpleNamespace(active_server_context=lambda: self.server, _shutting_down=False)
        coordinator = ServerLaunchCoordinator(window)
        coordinator.request_id = "newer"
        callback = Mock()
        coordinator._ready("old", self.server, self.resolve(), "", callback, True)
        callback.assert_not_called()
        self.assertIsNone(coordinator.context)
        coordinator.request_id = "request"
        window.active_server_context = lambda: replace(self.server, host="other.test")
        coordinator._ready("request", self.server, self.resolve(), "", callback, True)
        callback.assert_not_called()

    def test_successful_resolution_clears_its_verification_message(self):
        status_bar = Mock()
        message = f"Verifying the DayZ edition for {self.server.name}…"
        status_bar.currentMessage.return_value = message
        window = SimpleNamespace(
            active_server_context=lambda: self.server,
            _shutting_down=False,
            statusBar=lambda: status_bar,
            saved_server_repository=None,
            active_discovered_server=None,
        )
        coordinator = ServerLaunchCoordinator(window)
        coordinator.request_id = "request"
        coordinator.identity_status_request = "request"
        coordinator.identity_status_message = message
        continuation = Mock()

        coordinator._ready("request", self.server, self.resolve(), "", continuation, True)

        status_bar.clearMessage.assert_called_once_with()
        continuation.assert_called_once()

    def test_mod_worker_failure_retains_request_and_does_not_stall(self):
        from wolflauncher.workers import ModWorker

        context = self.resolve()
        worker = ModWorker(context.server, context.install.workshop_dir, launch_context=context)
        results = []
        worker.mods_ready.connect(results.append)
        with patch("wolflauncher.workers.check_server_mods", side_effect=OSError("unavailable")):
            worker.run()
        self.assertEqual(len(results), 1)
        self.assertFalse(results[0].ok)
        self.assertEqual(results[0].request_id, context.request_id)
        self.assertEqual(results[0].launch_context_key, context.mod_context_key)
        self.assertIn("unavailable", results[0].error)

    def test_commands_require_the_matching_mod_context_and_install(self):
        context = self.resolve()
        result = ModCheckResult(
            True,
            context.server,
            [],
            request_id=context.request_id,
            launch_context_key=context.mod_context_key,
        )
        window = SimpleNamespace(
            active_server_context=lambda: self.server,
            _shutting_down=False,
            last_mod_result=result,
            player_name=Mock(),
            launcher_path=Mock(),
        )
        window.player_name.text.return_value = "Survivor"
        window.server_launch = ServerLaunchCoordinator(window)
        window.server_launch.context = context
        window.server_launch.request_id = context.request_id
        execution = LaunchExecutionCoordinator(window)
        with (
            patch("wolflauncher.server_launch_context.time.monotonic", return_value=101),
            patch(
                "wolflauncher.launch_execution.prepare_native_launch",
                return_value=SimpleNamespace(command=["steam", "-applaunch", "1024020"]),
            ) as prepare,
        ):
            self.assertEqual(
                execution.build_command(self.server), ["steam", "-applaunch", "1024020"]
            )
            self.assertEqual(prepare.call_args.args[0].product, EXPERIMENTAL)
            result.launch_context_key = ("old stable mods",)
            with self.assertRaisesRegex(Exception, "Required mods"):
                execution.build_command(self.server)
        self.installs["experimental"].dayz_dir.joinpath("DayZ_BE.exe").unlink()
        with patch("wolflauncher.server_launch_context.time.monotonic", return_value=101):
            with self.assertRaisesRegex(Exception, "installation"):
                execution.build_command(self.server)

    def test_missing_installation_still_updates_favourite_identity_without_launching(self):
        self.installs["experimental"] = replace(self.installs["experimental"], dayz_dir=None)
        with self.assertRaises(IdentityResolutionError) as caught:
            self.resolve()
        window = SimpleNamespace(
            active_server_context=lambda: self.server,
            statusBar=Mock(return_value=Mock()),
            saved_server_repository=Mock(),
            servers=[self.server],
            refresh_curated_server_cards=Mock(),
            active_discovered_server=None,
        )
        coordinator = ServerLaunchCoordinator(window)
        coordinator.request_id = "request"
        continuation = Mock()
        coordinator._ready(
            "request",
            self.server,
            caught.exception.resolved_server,
            str(caught.exception),
            continuation,
            True,
        )
        self.assertEqual(window.servers[0].product, "experimental")
        self.assertEqual(window.servers[0].host, "dayz.test")
        continuation.assert_not_called()
        self.assertIsNone(coordinator.context)

    def test_shutdown_does_not_start_queued_identity_worker(self):
        coordinator = ServerLaunchCoordinator(SimpleNamespace(_shutting_down=True))
        worker = Mock()
        coordinator.pending_identity = (worker, "pending")
        coordinator._run_pending_identity()
        worker.start.assert_not_called()
        self.assertIsNone(coordinator.pending_identity)

    def test_duplicate_handoff_callback_does_not_launch_again(self):
        from wolflauncher.connect_preflight import ConnectPreflightCoordinator

        window = SimpleNamespace(preflight_dialog=Mock())
        coordinator = ConnectPreflightCoordinator(window)
        coordinator.handoff_at = 100
        with patch("wolflauncher.connect_preflight.time.monotonic", return_value=101):
            coordinator._handoff(None)
        window.preflight_dialog.start_launch.assert_not_called()

    def test_preview_join_rechecks_original_hostname_target(self):
        context = self.resolve()
        window = SimpleNamespace(
            active_server_context=lambda: self.server, connect_preflight=Mock()
        )
        window.server_launch = ServerLaunchCoordinator(window)
        window.server_launch.context = context
        window.server_launch.request_id = context.request_id
        LaunchExecutionCoordinator(window)._launch_from_preview(context)
        window.connect_preflight.start.assert_called_once_with(
            self.server, engine_override="native"
        )

    def test_stable_external_launch_pins_library_and_rejects_unsupported_layout(self):
        from wolflauncher.launcher import LaunchError

        context = self.resolve(221100)
        window = SimpleNamespace(
            active_server_context=lambda: self.server,
            player_name=Mock(),
            launcher_path=Mock(),
        )
        window.player_name.text.return_value = "Survivor"
        window.server_launch = ServerLaunchCoordinator(window)
        window.server_launch.request_id = context.request_id
        execution = LaunchExecutionCoordinator(window)

        def use_context(value):
            window.server_launch.context = value
            window.last_mod_result = ModCheckResult(
                True,
                value.server,
                [],
                request_id=value.request_id,
                launch_context_key=value.mod_context_key,
            )

        use_context(context)
        with patch("wolflauncher.server_launch_context.time.monotonic", return_value=101):
            with self.assertRaisesRegex(LaunchError, "Choose Native"):
                execution.build_command(self.server)
        install = self.installs["stable"]
        folder = install.steamapps / "common" / "DayZ"
        install.dayz_dir.rename(folder)
        (install.steamapps / "appmanifest_221100.acf").write_text(
            '"AppState" { "installdir" "DayZ" }'
        )
        workshop = install.steamapps / "workshop" / "content" / "221100"
        workshop.mkdir(parents=True)
        self.installs["stable"] = replace(install, dayz_dir=folder, workshop_dir=workshop)
        context = self.resolve(221100)
        use_context(context)
        with (
            patch("wolflauncher.server_launch_context.time.monotonic", return_value=101),
            patch(
                "wolflauncher.launch_execution.build_launch_command",
                return_value=["launcher", "join"],
            ),
        ):
            command = execution.build_command(self.server)
        self.assertEqual(
            command, ["env", f"STEAM_ROOT={install.steamapps.parent}", "launcher", "join"]
        )
