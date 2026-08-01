import unittest

from wolflauncher.thumbnail_safety import (
    THUMBNAIL_REQUEST_TIMEOUT_MS,
    is_safe_thumbnail_content_type,
    is_safe_thumbnail_dimensions,
    is_safe_thumbnail_url,
    normalize_thumbnail_url,
)


class ThumbnailSafetyTests(unittest.TestCase):
    def test_accepts_https_image_urls_only(self):
        self.assertTrue(is_safe_thumbnail_url("https://cdn.example.test/preview.png"))
        self.assertFalse(is_safe_thumbnail_url("http://cdn.example.test/preview.png"))
        self.assertFalse(is_safe_thumbnail_url("file:///tmp/preview.png"))
        self.assertFalse(is_safe_thumbnail_url("https:///missing-host"))

    def test_upgrades_only_recognised_steam_cdn_urls_to_https(self):
        self.assertEqual(
            normalize_thumbnail_url("http://images.akamai.steamusercontent.com/ugc/preview.jpg"),
            "https://images.akamai.steamusercontent.com/ugc/preview.jpg",
        )
        self.assertEqual(
            normalize_thumbnail_url("http://cdn.example.test/preview.jpg"),
            "http://cdn.example.test/preview.jpg",
        )

    def test_accepts_raster_image_content_types_and_bounded_dimensions(self):
        self.assertTrue(is_safe_thumbnail_content_type("image/jpeg; charset=binary"))
        self.assertTrue(is_safe_thumbnail_content_type("image/png"))
        self.assertTrue(is_safe_thumbnail_content_type("image/webp"))
        self.assertFalse(is_safe_thumbnail_content_type("text/html"))
        self.assertFalse(is_safe_thumbnail_content_type("image/svg+xml"))
        self.assertTrue(is_safe_thumbnail_dimensions(2048, 1))
        self.assertFalse(is_safe_thumbnail_dimensions(2049, 1))
        self.assertFalse(is_safe_thumbnail_dimensions(0, 200))

    def test_thumbnail_timeout_is_bounded(self):
        self.assertEqual(THUMBNAIL_REQUEST_TIMEOUT_MS, 10_000)
