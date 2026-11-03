import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from wolflauncher.connect_preflight import ConnectPreflightCoordinator
from wolflauncher.dayz_mod_query import DayzRequiredMod
from wolflauncher.mod_presenter import mod_readiness_text, mod_row
from wolflauncher.models import Server
from wolflauncher.mods import ModCheckResult, RequiredMod, check_server_mods
from wolflauncher.mods_feature import ModsFeatureMixin
from wolflauncher.native_launcher import NativeLaunchError, prepare_mod_links
from wolflauncher.workshop_resolution_controller import WorkshopResolutionCoordinator


class UnpublishedModIntegrationTests(unittest.TestCase):
    def test_mixed_manifest_keeps_valid_workshop_items_and_blocks_readiness(self):
        with (
            patch("wolflauncher.mods.resolve_host", return_value="127.0.0.1"),
            patch(
                "wolflauncher.mods.query_dayz_required_mods",
                return_value=[
                    DayzRequiredMod(None, "Local One", 0),
                    DayzRequiredMod(111, "CF", 0xFF0100FF),
                    DayzRequiredMod(None, "Local Two"),
                ],
            ),
        ):
            result = check_server_mods(
                Server("LAN", "LAN", "localhost", 2302, 2305), None, installed_mods={"111": "CF"}
            )
        self.assertTrue(result.ok)
        self.assertEqual([mod.server_hash for mod in result.required_mods], [0, 0xFF0100FF, None])
        self.assertEqual([mod.workshop_id for mod in result.required_mods], ["", "111", ""])
        self.assertEqual(
            [mod.name for mod in result.local_requirements], ["Local One", "Local Two"]
        )
        self.assertEqual(len(result.missing_mods), 2)
        self.assertTrue(result.required_mods[1].ready)
        self.assertIn("Local Two", mod_readiness_text(result))

    def test_manual_row_has_no_fake_workshop_id_or_link(self):
        mod = RequiredMod("", "Local Example", installed=True)
        self.assertFalse(mod.ready)
        row = mod_row(mod)
        self.assertEqual(
            row.values[:3], ["Manual/local mod required", "Local Example", "Not published"]
        )
        self.assertEqual(row.workshop_id, "")

    def test_preflight_does_not_subscribe_or_launch_with_local_requirement(self):
        server = Server("LAN", "LAN", "localhost", 2302, 2305)
        window = SimpleNamespace(
            preflight_mod_worker=None,
            preflight_server=server,
            preflight_dialog=Mock(isVisible=Mock(return_value=True)),
            launch_button=Mock(),
            display_mods_result=Mock(),
        )
        coordinator = ConnectPreflightCoordinator(window)
        coordinator.finish = Mock()
        with patch("wolflauncher.connect_preflight.WorkshopSubscriptionWorker") as worker:
            coordinator.finish_mod_check(ModCheckResult(True, server, [RequiredMod("", "Local")]))
        worker.assert_not_called()
        coordinator.finish.assert_not_called()
        self.assertIn("unpublished/local", window.preflight_dialog.set_failed.call_args.args[1])

    def test_native_mod_setup_rejects_local_requirement_before_filesystem_changes(self):
        with self.assertRaisesRegex(NativeLaunchError, "unpublished/local"):
            prepare_mod_links(
                Path("unused-dayz"), Path("unused-workshop"), [RequiredMod("", "Local")]
            )

    def test_resolution_guard_rejects_local_ids_before_steam(self):
        coordinator = WorkshopResolutionCoordinator(SimpleNamespace())
        with patch("wolflauncher.workshop_resolution_controller.QMessageBox.warning") as warning:
            coordinator.start_resolution([RequiredMod("", "Local")], None, None)
        warning.assert_called_once()

    def test_manual_row_never_opens_a_fabricated_workshop_url(self):
        window = SimpleNamespace(
            selected_required_mod=Mock(return_value=None),
            _mods_cell=Mock(return_value="Not published"),
        )
        with (
            patch("wolflauncher.mods_feature.QMessageBox.warning") as warning,
            patch("wolflauncher.mods_feature.QDesktopServices.openUrl") as opened,
        ):
            ModsFeatureMixin.open_workshop_page_for_mod_row(window, 0)
        warning.assert_called_once()
        opened.assert_not_called()
