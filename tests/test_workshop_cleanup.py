import tempfile
import unittest
from pathlib import Path

from wolflauncher.workshop_cleanup import remove_local_workshop_mod


class WorkshopCleanupTests(unittest.TestCase):
    def test_removes_only_selected_mod(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "111").mkdir()
            (root / "111" / "data.pbo").write_text("mod data")
            (root / "222").mkdir()
            remove_local_workshop_mod(root, "111")
            self.assertFalse((root / "111").exists())
            self.assertTrue((root / "222").is_dir())

    def test_rejects_paths_and_invalid_ids(self):
        with tempfile.TemporaryDirectory() as directory:
            for item in ("../111", "0", "", "/111", "111/222", "１２３"):
                with self.subTest(item=item), self.assertRaises(ValueError):
                    remove_local_workshop_mod(Path(directory), item)

    def test_rejects_linked_mod_folder(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "outside").mkdir()
            try:
                (root / "111").symlink_to(root / "outside", target_is_directory=True)
            except OSError:
                self.skipTest("Creating symlinks is unavailable")
            with self.assertRaises(ValueError):
                remove_local_workshop_mod(root, "111")
            self.assertTrue((root / "outside").is_dir())
