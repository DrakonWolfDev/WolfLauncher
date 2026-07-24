import logging
import sys
import tempfile
import unittest
from pathlib import Path

from wolflauncher.logging_setup import configure_local_logging, install_exception_hook


class LoggingSetupTests(unittest.TestCase):
    def test_local_log_is_redacted_and_reused(self):
        with tempfile.TemporaryDirectory() as directory:
            path = configure_local_logging(Path(directory))
            logging.getLogger("wolflauncher").warning("api_key=super-secret-value /userdata/123456")
            for handler in logging.getLogger("wolflauncher").handlers:
                handler.flush()
            text = path.read_text(encoding="utf-8")
            self.assertIn("<redacted>", text)
            self.assertIn("<steam-account>", text)
            self.assertNotIn("super-secret-value", text)
            self.assertEqual(configure_local_logging(Path(directory)), path)
            logger = logging.getLogger("wolflauncher")
            for handler in logger.handlers[:]:
                handler.close()
                logger.removeHandler(handler)

    def test_exception_hook_logs_and_notifies_without_uploading(self):
        original_hook = sys.excepthook
        self.addCleanup(setattr, sys, "excepthook", original_hook)
        notices = []
        with tempfile.TemporaryDirectory() as directory:
            path = configure_local_logging(Path(directory))
            install_exception_hook(path, notices.append)
            try:
                raise RuntimeError("api_key=super-secret-value")
            except RuntimeError:
                sys.excepthook(*sys.exc_info())
            for handler in logging.getLogger("wolflauncher").handlers:
                handler.flush()
            self.assertEqual(notices, ["wolflauncher.log"])
            self.assertNotIn("super-secret-value", path.read_text(encoding="utf-8"))
            logger = logging.getLogger("wolflauncher")
            for handler in logger.handlers[:]:
                handler.close()
                logger.removeHandler(handler)
