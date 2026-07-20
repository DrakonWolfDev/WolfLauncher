import unittest
from unittest.mock import patch

import main


class FrozenEntryPointTests(unittest.TestCase):
    @patch("wolflauncher.app.main")
    @patch("main.multiprocessing.freeze_support")
    def test_freeze_support_runs_before_application_main(self, freeze_support, app_main):
        main.run()

        freeze_support.assert_called_once_with()
        app_main.assert_called_once_with()


if __name__ == "__main__":
    unittest.main()
