from __future__ import annotations

import io
import json
import unittest
import urllib.error
from datetime import datetime, timedelta, timezone

from wolf_update.core import (
    CheckStatus,
    UpdateApplication,
    UpdateService,
    safe_release_notes,
    validate_destination,
)
from wolf_update.github import GitHubReleaseSource, ReleaseSourceError, select_release
from wolf_update.state import MemoryStateStore, UpdateState


def release(tag, *, prerelease=False, draft=False, body="notes"):
    return {"tag_name": tag, "prerelease": prerelease, "draft": draft, "body": body}


class Source:
    def __init__(self, payload=None, error=None):
        self.payload = payload or []
        self.error = error
        self.calls = 0

    def releases(self):
        self.calls += 1
        if self.error:
            raise self.error
        return self.payload


def app():
    return UpdateApplication(
        current_version="0.9.0b2",
        repository="DrakonWolfDev/WolfLauncher",
        update_url="https://wolf-forge.co.uk/wolf-launcher.html",
        channel="experimental",
    )


class Response:
    def __init__(self, payload):
        self.payload = payload
        self.headers = {}

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return None

    def read(self, _size):
        return self.payload


class WolfUpdateTests(unittest.TestCase):
    def test_stable_selects_highest_final_and_ignores_invalid_releases(self):
        selected = select_release(
            [
                release("v1.1.0b2", prerelease=True),
                release("broken"),
                release("v9.0.0", draft=True),
                release("v1.0.1"),
                release("v1.0.2"),
            ],
            current_version="1.0.0",
            channel="stable",
        )
        self.assertEqual(str(selected.version), "1.0.2")

    def test_experimental_uses_pep440_prerelease_ordering(self):
        selected = select_release(
            [release("v0.9.0b10", prerelease=True), release("v0.9.0b3", prerelease=True)],
            current_version="0.9.0b2",
            channel="experimental",
        )
        self.assertEqual(str(selected.version), "0.9.0b10")

    def test_unsafe_destinations_are_rejected(self):
        urls = [
            "http://wolf-forge.co.uk/wolf-launcher.html",
            "/wolf-launcher.html",
            "https://user:pass@wolf-forge.co.uk/page",
            "https://wolf-forge.co.uk/page#download",
            "https://localhost/page",
            "https://wolf-forge.co.uk:bad/page",
        ]
        for url in urls:
            with self.subTest(url=url), self.assertRaises(ValueError):
                validate_destination(url)

    def test_destination_is_canonical_and_opened_without_github_fallback(self):
        opened = []
        application = UpdateApplication(
            current_version="1.0.0",
            repository="owner/project",
            update_url="https://wolf-forge.co.uk/wolf-launcher.html",
        )
        service = UpdateService(
            application,
            MemoryStateStore(),
            browser_open=lambda url: opened.append(url) or True,
        )
        self.assertTrue(service.view_update())
        self.assertEqual(opened, ["https://wolf-forge.co.uk/wolf-launcher.html"])

    def test_successful_automatic_checks_are_throttled_for_24_hours(self):
        now = datetime(2026, 10, 13, 10, tzinfo=timezone.utc)
        source = Source()
        store = MemoryStateStore()
        service = UpdateService(app(), store, source=source, clock=lambda: now)
        self.assertIs(service.check().status, CheckStatus.UP_TO_DATE)
        self.assertIs(service.check().status, CheckStatus.THROTTLED)
        self.assertEqual(source.calls, 1)
        later = UpdateService(app(), store, source=source, clock=lambda: now + timedelta(hours=24))
        self.assertIs(later.check().status, CheckStatus.UP_TO_DATE)
        self.assertEqual(source.calls, 2)

    def test_future_check_timestamp_does_not_suppress_updates(self):
        now = datetime(2026, 10, 13, 10, tzinfo=timezone.utc)
        future = (now + timedelta(days=30)).isoformat()
        source = Source()
        service = UpdateService(
            app(),
            MemoryStateStore(UpdateState(last_successful_check=future)),
            source=source,
            clock=lambda: now,
        )
        self.assertIs(service.check().status, CheckStatus.UP_TO_DATE)
        self.assertEqual(source.calls, 1)

    def test_failed_check_is_not_recorded_or_throttled(self):
        source = Source(error=ReleaseSourceError("network", "offline"))
        service = UpdateService(app(), MemoryStateStore(), source=source)
        self.assertIs(service.check().status, CheckStatus.FAILED)
        self.assertIs(service.check().status, CheckStatus.FAILED)
        self.assertEqual(source.calls, 2)

    def test_dismissal_hides_automatic_notice_but_manual_check_shows_it(self):
        source = Source([release("v0.9.0b3")])
        store = MemoryStateStore(UpdateState(dismissed_version="0.9.0b3"))
        service = UpdateService(app(), store, source=source)
        self.assertIs(service.check().status, CheckStatus.DISMISSED)
        self.assertIs(service.check(manual=True).status, CheckStatus.AVAILABLE)

    def test_newer_release_is_not_hidden_by_older_dismissal(self):
        source = Source([release("v0.9.0b4")])
        store = MemoryStateStore(UpdateState(dismissed_version="0.9.0b3"))
        result = UpdateService(app(), store, source=source).check()
        self.assertIs(result.status, CheckStatus.AVAILABLE)
        self.assertEqual(str(result.release.version), "0.9.0b4")

    def test_release_notes_are_inert_plain_text(self):
        notes = safe_release_notes(
            "## What's new\n[Install now](https://evil.invalid) <script>run()</script> **fixed**"
        )
        self.assertNotIn("https://", notes)
        self.assertNotIn("<script>", notes)
        self.assertIn("Install now", notes)
        self.assertIn("fixed", notes)

    def test_github_source_handles_invalid_json(self):
        source = GitHubReleaseSource(
            "owner/project", opener=lambda *_args, **_kwargs: Response(b"{")
        )
        with self.assertRaisesRegex(ReleaseSourceError, "invalid"):
            source.releases()

    def test_github_source_maps_api_failures(self):
        cases = [
            (urllib.error.HTTPError("url", 403, "rate", {}, io.BytesIO()), "rate_limit"),
            (urllib.error.URLError("offline"), "network"),
            (TimeoutError(), "network"),
        ]
        for error, category in cases:
            with self.subTest(category=category, error=type(error).__name__):

                def fail(*_args, **_kwargs):
                    raise error

                source = GitHubReleaseSource("owner/project", opener=fail)
                with self.assertRaises(ReleaseSourceError) as caught:
                    source.releases()
                self.assertEqual(caught.exception.category, category)

    def test_github_source_only_reads_metadata_and_has_no_download_api(self):
        payload = json.dumps([release("v1.0.0")]).encode()
        source = GitHubReleaseSource("owner/project", opener=lambda *_a, **_k: Response(payload))
        self.assertEqual(source.releases()[0]["tag_name"], "v1.0.0")
        self.assertFalse(hasattr(source, "download"))
        self.assertIn("/releases?", source.api_url)
        self.assertNotIn("/assets", source.api_url)


if __name__ == "__main__":
    unittest.main()
