import tempfile
import unittest
from unittest.mock import patch

from wolflauncher.diagnostics import run_diagnostics
from wolflauncher.models import Server


class DiagnosticsTests(unittest.TestCase):
    def test_reports_prime_environment_without_reading_steam_launch_options(self):
        with tempfile.NamedTemporaryFile() as launcher:
            with patch("wolflauncher.diagnostics.detect_steam", return_value=[]):
                with patch("wolflauncher.diagnostics.resolve_host", return_value="203.0.113.10"):
                    with patch.dict(
                        "wolflauncher.diagnostics.os.environ",
                        {
                            "__NV_PRIME_RENDER_OFFLOAD": "1",
                            "__GLX_VENDOR_LIBRARY_NAME": "nvidia",
                        },
                        clear=True,
                    ):
                        report = run_diagnostics(
                            launcher.name,
                            [
                                Server(
                                    name="Example",
                                    group="Tests",
                                    host="example.test",
                                    game_port=2302,
                                    query_port=27016,
                                )
                            ],
                        )

        self.assertIn("Launch option environment:", report)
        self.assertIn("__NV_PRIME_RENDER_OFFLOAD: 1", report)
        self.assertIn("__GLX_VENDOR_LIBRARY_NAME: nvidia", report)
        self.assertIn("DRI_PRIME: not set", report)
        self.assertIn("Steam launch options: not readable by WolfLauncher", report)


if __name__ == "__main__":
    unittest.main()
