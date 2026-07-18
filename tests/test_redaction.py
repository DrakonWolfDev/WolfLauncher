import os
import unittest
from pathlib import Path
from unittest.mock import patch

from wolflauncher.redaction import redact_support_text


class RedactionTests(unittest.TestCase):
    def test_redacts_explicit_and_environment_secrets(self):
        with patch.dict(os.environ, {"STEAM_WEB_API_KEY": "environment-secret"}):
            text = redact_support_text(
                "explicit-secret environment-secret", secrets=["explicit-secret"]
            )
        self.assertEqual(text, "<redacted> <redacted>")

    def test_redacts_labelled_and_query_credentials(self):
        text = redact_support_text(
            "API key: abcdefgh https://example.test/?key=secret-value&limit=1"
        )
        self.assertNotIn("abcdefgh", text)
        self.assertNotIn("secret-value", text)
        self.assertIn("API key: <redacted>", text)

    def test_redacts_home_and_steam_account_path(self):
        text = redact_support_text(f"{Path.home()}/.steam/steam/userdata/123456789/config")
        self.assertEqual(text, "~/.steam/steam/userdata/<steam-account>/config")


if __name__ == "__main__":
    unittest.main()
