import os
import unittest
from pathlib import Path
from unittest.mock import patch

from wolflauncher.paths import user_config_dir, user_data_dir


class XdgPathTests(unittest.TestCase):
    @unittest.skipIf(os.name == "nt", "XDG paths are Linux-only")
    def test_xdg_overrides_are_honoured(self):
        with patch.dict(
            os.environ,
            {"XDG_CONFIG_HOME": "/tmp/wolf-config", "XDG_DATA_HOME": "/tmp/wolf-data"},
        ):
            self.assertEqual(user_config_dir(), Path("/tmp/wolf-config/wolflauncher"))
            self.assertEqual(user_data_dir(), Path("/tmp/wolf-data/wolflauncher"))


if __name__ == "__main__":
    unittest.main()
