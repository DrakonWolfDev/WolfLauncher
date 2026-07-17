import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from wolflauncher.server_map_atmosphere import (
    ServerMapAtmosphereFrame,
    map_atmosphere_flavour,
)


class ServerMapAtmosphereTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_known_maps_select_broad_environment_flavours(self):
        self.assertEqual(map_atmosphere_flavour("Namalsk"), "snow")
        self.assertEqual(map_atmosphere_flavour("chernarusplus"), "conifer")
        self.assertEqual(map_atmosphere_flavour("Enoch"), "wetland")
        self.assertEqual(map_atmosphere_flavour("Livonia Experimental"), "wetland")
        self.assertEqual(map_atmosphere_flavour("Sakhal"), "volcanic")
        self.assertEqual(map_atmosphere_flavour("Deer Isle"), "neutral")

    def test_portrait_atlas_is_packaged_and_columns_exclude_the_gutters(self):
        frame = ServerMapAtmosphereFrame()
        self.assertFalse(frame._atlas.isNull())
        self.assertGreater(frame._atlas.width(), frame._atlas.height())
        for flavour in ("snow", "conifer", "wetland", "volcanic", "neutral"):
            frame._flavour = flavour
            source = frame._source_rect()
            self.assertGreater(source.width(), 0)
            self.assertGreater(source.height(), 0)
            self.assertGreaterEqual(source.x(), 0)
            self.assertGreaterEqual(source.y(), 0)
            self.assertLessEqual(source.right(), frame._atlas.width())
            self.assertLessEqual(source.bottom(), frame._atlas.height())
