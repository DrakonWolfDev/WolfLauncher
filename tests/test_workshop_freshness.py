import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from wolflauncher.mods import RequiredMod, workshop_install_timestamps
from wolflauncher.workshop_freshness import (
    apply_completed_checks,
    capture_update_targets,
    record_completed_checks,
)
from wolflauncher.workshop_subscription import WorkshopSubscriptionResult


class WorkshopFreshnessTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.install = self.make_install("one")
        self.metadata = {"111": {"result": 1, "time_updated": 200, "file_size": 100}}
        self.mod = RequiredMod(
            "111",
            "Example",
            installed=True,
            workshop_state=5,
            installed_updated_at=100,
            workshop_updated_at=200,
            workshop_file_size=100,
        )
        patched = patch(
            "wolflauncher.workshop_freshness.user_data_dir", return_value=self.root / "data"
        )
        patched.start()
        self.addCleanup(patched.stop)

    def make_install(self, name):
        steamapps = self.root / name / "steamapps"
        directory = steamapps / "workshop" / "content" / "221100"
        (directory / "111").mkdir(parents=True)
        (directory / "111" / "mod.pbo").write_bytes(b"content")
        (directory.parent.parent / "appworkshop_221100.acf").write_text(
            '"AppWorkshop" { "WorkshopItemsInstalled" { '
            '"111" { "manifest" "abc" "timeupdated" "100" } } '
            '"WorkshopItemDetails" { "111" { "manifest" "def" "timeupdated" "999" } } }'
        )
        return SimpleNamespace(
            workshop_dir=directory, steamapps=steamapps, product=SimpleNamespace(key="stable")
        )

    def complete(self, result=None):
        targets = capture_update_targets(self.install, ["111"], self.metadata)
        record_completed_checks(
            self.install, result or WorkshopSubscriptionResult(("111",), ()), targets
        )

    def test_successful_noop_resolves_only_the_captured_revision(self):
        self.assertFalse(self.mod.ready)
        self.complete()
        apply_completed_checks(self.install, [self.mod])
        self.assertTrue(self.mod.ready)
        self.mod.workshop_updated_at = 201
        apply_completed_checks(self.install, [self.mod])
        self.assertFalse(self.mod.ready)

    def test_cancelled_or_failed_result_is_not_acknowledged(self):
        for result in (
            WorkshopSubscriptionResult((), ("111",), cancelled=True),
            WorkshopSubscriptionResult((), ("111",), error="failed"),
        ):
            self.complete(result)
            apply_completed_checks(self.install, [self.mod])
            self.assertFalse(self.mod.ready)

    def test_active_or_unavailable_live_state_cannot_reuse_acknowledgement(self):
        self.complete()
        for state in (None, 1, 5 | 8, 5 | 16, 5 | 32):
            self.mod.workshop_state = state
            apply_completed_checks(self.install, [self.mod])
            self.assertFalse(self.mod.ready)

    def test_changed_files_invalidate_acknowledgement(self):
        self.complete()
        (self.install.workshop_dir / "111" / "mod.pbo").write_bytes(b"changed content")
        apply_completed_checks(self.install, [self.mod])
        self.assertFalse(self.mod.ready)

    def test_changed_content_during_download_cannot_be_recorded_as_noop(self):
        targets = capture_update_targets(self.install, ["111"], self.metadata)
        (self.install.workshop_dir / "111" / "mod.pbo").write_bytes(b"new content")
        record_completed_checks(self.install, WorkshopSubscriptionResult(("111",), ()), targets)
        apply_completed_checks(self.install, [self.mod])
        self.assertFalse(self.mod.ready)

    def test_other_library_or_edition_cannot_reuse_acknowledgement(self):
        self.complete()
        other = self.make_install("two")
        apply_completed_checks(other, [self.mod])
        self.assertFalse(self.mod.ready)
        self.install.product.key = "experimental"
        apply_completed_checks(self.install, [self.mod])
        self.assertFalse(self.mod.ready)

    def test_published_size_change_invalidates_acknowledgement(self):
        self.complete()
        self.mod.workshop_file_size += 1
        apply_completed_checks(self.install, [self.mod])
        self.assertFalse(self.mod.ready)

    def test_reads_only_selected_installed_revision_not_remote_details_or_other_library(self):
        other = self.make_install("two")
        self.install.library_steamapps = (other.steamapps,)
        self.assertEqual(workshop_install_timestamps(self.install), {"111": 100})

    def test_missing_metadata_or_manifest_does_not_create_acknowledgement(self):
        self.assertEqual(capture_update_targets(self.install, ["111"], {}), {})
        path = self.install.workshop_dir.parent.parent / "appworkshop_221100.acf"
        path.write_text('"AppWorkshop" { "WorkshopItemsInstalled" {')
        self.assertEqual(capture_update_targets(self.install, ["111"], self.metadata), {})

    def test_manifest_change_invalidates_previous_noop(self):
        self.complete()
        path = self.install.workshop_dir.parent.parent / "appworkshop_221100.acf"
        path.write_text(path.read_text().replace('"manifest" "abc"', '"manifest" "changed"'))
        apply_completed_checks(self.install, [self.mod])
        self.assertFalse(self.mod.ready)

    def test_subscription_worker_captures_target_and_records_only_success(self):
        from wolflauncher.workers import WorkshopSubscriptionWorker

        worker = WorkshopSubscriptionWorker(["111"], self.install, force_update=True)
        with (
            patch("wolflauncher.workers.fetch_workshop_metadata", return_value=self.metadata),
            patch(
                "wolflauncher.workers.subscribe_workshop_items_isolated",
                return_value=WorkshopSubscriptionResult(("111",), ()),
            ),
        ):
            worker.run()
        apply_completed_checks(self.install, [self.mod])
        self.assertTrue(self.mod.ready)
