import json
import os
import shutil
import subprocess
import tempfile
import time
import unittest
from dataclasses import asdict
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QDialog

from wolflauncher.models import DiscoveredServer, Server
from wolflauncher.server_link_controller import (
    LinkMetadataWorker,
    ServerLinkCoordinator,
    ServerLinkReviewDialog,
    resolve_link_metadata,
)
from wolflauncher.server_links import (
    ServerLinkError,
    build_server_link,
    parse_server_link,
    parse_startup_arguments,
)

LINK = "wolflauncher://join?v=1&host=203.0.113.10&game_port=2302&query_port=27016"


class ServerLinkSchemaTests(unittest.TestCase):
    @unittest.skipUnless(
        os.name == "posix" and shutil.which("gio"), "GIO desktop launching is unavailable"
    )
    def test_linux_desktop_entry_delivers_url_as_one_argument_to_a_stub_application(self):
        with tempfile.TemporaryDirectory(prefix="wolflauncher link test ") as temporary:
            root = Path(temporary)
            output = root / "arguments.json"
            capture = root / "capture"
            capture.write_text(
                "#!/usr/bin/python3\nimport json, sys\nfrom pathlib import Path\n"
                f"Path({str(output)!r}).write_text(json.dumps(sys.argv[1:]))\n"
            )
            capture.chmod(0o755)
            source = Path(__file__).resolve().parents[1] / "packaging/linux/wolflauncher.desktop"
            desktop = root / "wolflauncher.desktop"
            desktop.write_text(
                source.read_text().replace("Exec=wolflauncher %u", f'Exec="{capture}" %u')
            )
            result = subprocess.run(
                ["gio", "launch", str(desktop), LINK], capture_output=True, text=True
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            deadline = time.monotonic() + 2
            while not output.exists() and time.monotonic() < deadline:
                time.sleep(0.005)
            self.assertTrue(output.exists())
            delivered = json.loads(output.read_text())
            self.assertEqual(len(delivered), 1)
            self.assertEqual(parse_server_link(delivered[0]), parse_server_link(LINK))

    def test_shared_browser_and_launcher_contract_vectors(self):
        vectors = json.loads(
            (Path(__file__).parent / "fixtures/server_link_vectors.json").read_text()
        )
        for item in vectors["valid"]:
            with self.subTest(url=item["url"]):
                target = parse_server_link(item["url"])
                self.assertEqual(asdict(target), item["expected"])
                self.assertEqual(parse_server_link(target.url()), target)
                self.assertEqual(parse_server_link(target.url(https=False)), target)
        for number, value in enumerate(vectors["invalid"]):
            with self.subTest(invalid_case=number), self.assertRaises(ServerLinkError):
                parse_server_link(value)

    def test_share_link_retains_directory_reference_and_distinct_ports_but_no_secrets(self):
        server = Server(
            "Private display name",
            "Group",
            "203.0.113.10",
            2302,
            3303,
            stable_server_id="directory:abc",
            product="experimental",
        )
        link = build_server_link(server)
        self.assertTrue(link.startswith("https://wolf-forge.co.uk/join/"))
        self.assertNotIn("Private", link)
        parsed = parse_server_link(link)
        self.assertEqual((parsed.game_port, parsed.query_port), (2302, 3303))
        self.assertEqual(parsed.server_id, "directory:abc")
        self.assertEqual(parsed.product, "experimental")

    def test_cli_supports_one_positional_or_explicit_url_and_rejects_other_arguments(self):
        self.assertIsNone(parse_startup_arguments([]))
        self.assertEqual(parse_startup_arguments([LINK]), LINK)
        self.assertEqual(parse_startup_arguments(["--open-url", LINK]), LINK)
        for args in ([LINK, LINK], ["--open-url", LINK, LINK], ["--open-url"], ["--mod=evil"]):
            with patch("sys.stderr"), self.assertRaises(SystemExit):
                parse_startup_arguments(args)

    def test_directory_metadata_cannot_turn_an_edition_hint_into_launch_authority(self):
        target = parse_server_link(LINK + "&server_id=expected&product=stable")
        row = DiscoveredServer(
            "Live name",
            "203.0.113.10",
            2302,
            3303,
            stable_server_id="expected",
            product="experimental",
        )
        resolver = Mock(return_value=[row])
        result = resolve_link_metadata(target, resolver=resolver, host_resolver=lambda host: host)
        self.assertEqual(result.server.stable_server_id, "expected")
        self.assertEqual(result.server.query_port, 3303)
        self.assertEqual(result.server.product, "unknown")
        self.assertEqual(result.server.identity_evidence, ())
        self.assertFalse(result.server.favourite)
        resolver.assert_called_once_with("203.0.113.10", game_port=2302, product="all", timeout=4)

    def test_unconfirmed_ids_and_moved_addresses_use_an_explicit_untrusted_endpoint_fallback(self):
        target = parse_server_link(LINK + "&server_id=expected")
        rows = [
            DiscoveredServer("Other", "203.0.113.10", 2302, 3303, stable_server_id="different"),
            DiscoveredServer("Moved", "203.0.113.99", 2302, 3303, stable_server_id="expected"),
            DiscoveredServer("Other port", "203.0.113.10", 2402, 3303, stable_server_id="expected"),
        ]
        for row in rows:
            with self.subTest(name=row.name):
                result = resolve_link_metadata(
                    target, resolver=lambda *a, **kw: [row], host_resolver=lambda host: host
                )
                self.assertEqual(result.server.host, target.host)
                self.assertEqual(result.server.game_port, target.game_port)
                self.assertEqual(result.server.query_port, target.query_port)
                self.assertEqual(result.server.stable_server_id, "")
                self.assertIn("could not be confirmed", result.notice)

    def test_directory_failure_preserves_reviewable_fallback_without_live_probing(self):
        resolver = Mock(side_effect=RuntimeError("unavailable"))
        result = resolve_link_metadata(
            parse_server_link(LINK + "&server_id=expected"), resolver=resolver
        )
        self.assertEqual(result.server.host, "203.0.113.10")
        self.assertEqual(result.server.product, "unknown")
        self.assertIn("out of date", result.notice)
        with patch("wolflauncher.server_discovery.resolve_dayz_server_wolfapi_v1") as lookup:
            resolve_link_metadata(parse_server_link(LINK))
        lookup.assert_not_called()


class ServerLinkFlowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def window(self):
        return SimpleNamespace(
            server_launch=Mock(),
            tabs=Mock(),
            mods_tab_index=2,
            check_server_mods=Mock(),
            update_launch_button_text=Mock(),
            statusBar=Mock(return_value=Mock()),
            launch_selected=Mock(),
            connect_preflight=Mock(),
            subscribe_missing_workshop_mods=Mock(),
            active_discovered_server=None,
            last_mod_result="old result",
        )

    def test_accepting_link_review_inspects_only_and_keeps_join_and_download_confirmation(self):
        window = self.window()
        server = resolve_link_metadata(parse_server_link(LINK)).server
        with patch("wolflauncher.server_link_controller.ServerLinkReviewDialog") as dialog:
            dialog.return_value.exec.return_value = QDialog.Accepted
            dialog.return_value.server = server
            ServerLinkCoordinator(window).receive(LINK)
        self.assertIs(window.active_discovered_server, server)
        self.assertIsNone(window.last_mod_result)
        window.check_server_mods.assert_called_once_with(server, force=True)
        window.tabs.setCurrentIndex.assert_called_once_with(2)
        window.launch_selected.assert_not_called()
        window.connect_preflight.start.assert_not_called()
        window.subscribe_missing_workshop_mods.assert_not_called()

    def test_rejected_and_malformed_links_do_not_change_selection_or_probe(self):
        window = self.window()
        coordinator = ServerLinkCoordinator(window)
        with patch("wolflauncher.server_link_controller.ServerLinkReviewDialog") as dialog:
            dialog.return_value.exec.return_value = QDialog.Rejected
            coordinator.receive(LINK)
        with patch("wolflauncher.server_link_controller.QMessageBox.warning") as warning:
            coordinator.receive(LINK + "&password=private-password")
        self.assertNotIn("private-password", warning.call_args.args[-1])
        self.assertIsNone(window.active_discovered_server)
        window.check_server_mods.assert_not_called()
        window.server_launch.invalidate.assert_not_called()

    def test_busy_join_play_workshop_or_existing_review_is_not_replaced(self):
        for field, value in (
            ("_game_session_active", True),
            ("preflight_dialog", Mock(isVisible=Mock(return_value=True))),
            ("workshop_subscription_worker", Mock(isRunning=Mock(return_value=True))),
        ):
            with self.subTest(field=field):
                window = self.window()
                setattr(window, field, value)
                with patch("wolflauncher.server_link_controller.ServerLinkReviewDialog") as dialog:
                    ServerLinkCoordinator(window).receive(LINK)
                dialog.assert_not_called()
                window.check_server_mods.assert_not_called()

    def test_review_displays_metadata_as_plain_text_and_keeps_inspect_disabled_until_ready(self):
        target = parse_server_link(LINK + "&server_id=expected&product=experimental")
        dialog = ServerLinkReviewDialog(None, target)
        self.addCleanup(dialog.deleteLater)
        self.assertFalse(dialog.inspect.isEnabled())
        self.assertIn("not verified", dialog.details.text())
        result = resolve_link_metadata(parse_server_link(LINK))
        result.server.name = "<b>A server name</b>"
        dialog.show_metadata(result)
        self.assertEqual(dialog.details.textFormat(), Qt.PlainText)
        self.assertIn("<b>", dialog.details.text())
        self.assertTrue(dialog.inspect.isEnabled())
        self.assertEqual(dialog.inspect.text(), "Inspect supplied address")

    def test_cancellation_suppresses_late_directory_results(self):
        worker = LinkMetadataWorker(parse_server_link(LINK + "&server_id=expected"))
        results = []
        worker.metadata_ready.connect(results.append)
        with (
            patch.object(worker, "isInterruptionRequested", return_value=True),
            patch("wolflauncher.server_link_controller.resolve_link_metadata") as resolve,
        ):
            worker.run()
        resolve.assert_not_called()
        self.assertEqual(results, [])

    def test_unexpected_directory_error_produces_a_reviewable_unknown_result(self):
        worker = LinkMetadataWorker(parse_server_link(LINK + "&server_id=expected"))
        results = []
        worker.metadata_ready.connect(results.append)
        with patch(
            "wolflauncher.server_link_controller.resolve_link_metadata", side_effect=Exception
        ):
            worker.run()
        self.assertEqual(results[0].server.product, "unknown")
        self.assertIn("could not be checked", results[0].notice)

    def test_cold_start_dispatches_after_show_and_secondary_start_only_forwards(self):
        import wolflauncher.app as application

        for primary in (True, False):
            callbacks = []
            with (
                patch("sys.argv", ["wolflauncher", LINK]),
                patch.object(application, "QApplication") as app,
                patch.object(application, "SingleInstanceGuard") as guard,
                patch.object(application, "MainWindow") as create_window,
                patch.object(application, "run_local_retention"),
                patch.object(application, "configure_local_logging"),
                patch.object(application, "apply_application_theme"),
                patch.object(application, "install_exception_hook"),
                patch.object(application, "configure_packaged_smoke_test"),
                patch.object(
                    application.QTimer,
                    "singleShot",
                    side_effect=lambda delay, fn: callbacks.append(fn),
                ),
            ):
                guard.return_value.start_or_notify.return_value = primary
                guard.return_value.delivery_error = ""
                app.return_value.exec.return_value = 0
                if primary:
                    with self.assertRaises(SystemExit) as exit_code:
                        application.main()
                    self.assertEqual(exit_code.exception.code, 0)
                    window = create_window.return_value
                    window.show.assert_called_once()
                    window.server_links.receive.assert_not_called()
                    for callback in callbacks:
                        callback()
                    window.server_links.receive.assert_called_once_with(LINK)
                    guard.return_value.set_url_handler.assert_called_once_with(
                        window.server_links.receive
                    )
                else:
                    application.main()
                    create_window.assert_not_called()
                app.assert_called_once_with(["wolflauncher"])
                guard.return_value.start_or_notify.assert_called_once_with(LINK)
