import unittest

from wolflauncher.known_issues import (
    NVIDIA_PRIME_OPTION,
    NVIDIA_PRIME_TITLE,
    known_external_issues_text,
)


class KnownIssuesTests(unittest.TestCase):
    def test_nvidia_prime_issue_is_an_explicit_external_warning(self):
        text = known_external_issues_text()
        self.assertIn(NVIDIA_PRIME_TITLE, text)
        self.assertIn(NVIDIA_PRIME_OPTION, text)
        self.assertIn("does not set, read, or change", text)
