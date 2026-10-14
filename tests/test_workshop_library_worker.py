import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from wolflauncher.workers import load_installed_workshop_library


class WorkshopLibraryWorkerTests(unittest.TestCase):
    def test_library_uses_workshop_title_only_when_local_name_is_missing(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            workshop = Path(temp_dir)
            for workshop_id in ("111", "222", "333", "444"):
                (workshop / workshop_id).mkdir()
            (workshop / "222" / "meta.cpp").write_text('name = "Local Mod Name"', encoding="utf-8")
            install = SimpleNamespace(workshop_dir=workshop, running=False)
            with (
                patch(
                    "wolflauncher.workers.fetch_workshop_metadata",
                    return_value={
                        "111": {"title": "  Workshop Mod Name  "},
                        "222": {"title": "Different Workshop Name"},
                        "333": {"title": "  "},
                    },
                ),
                patch("wolflauncher.workers.workshop_install_timestamps", return_value={}),
            ):
                mods, _ = load_installed_workshop_library(install)

        by_id = {mod.workshop_id: mod for mod in mods}
        self.assertEqual(by_id["111"].name, "Workshop Mod Name")
        self.assertEqual(by_id["222"].name, "Local Mod Name")
        self.assertEqual(by_id["333"].name, "333")
        self.assertEqual(by_id["444"].name, "444")
        self.assertTrue(all(mod.installed for mod in mods))

    def test_library_compares_local_manifest_with_published_revision(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            workshop = Path(temp_dir) / "workshop"
            mod_dir = workshop / "111"
            mod_dir.mkdir(parents=True)
            (mod_dir / "meta.cpp").write_text('name = "Example Mod"', encoding="utf-8")
            install = SimpleNamespace(workshop_dir=workshop, running=False)
            with (
                patch(
                    "wolflauncher.workers.fetch_workshop_metadata",
                    return_value={"111": {"file_size": 42, "time_updated": 200}},
                ),
                patch(
                    "wolflauncher.workers.workshop_install_timestamps", return_value={"111": 100}
                ),
            ):
                mods, state_error = load_installed_workshop_library(install)

        self.assertIn("Start Steam", state_error)
        self.assertEqual(len(mods), 1)
        self.assertEqual(mods[0].name, "Example Mod")
        self.assertTrue(mods[0].remote_update_available)


if __name__ == "__main__":
    unittest.main()
