import unittest

from wolflauncher.app import MainWindow
from wolflauncher.curated_servers_controller import CuratedServersMixin
from wolflauncher.launch_feature import LaunchFeatureMixin
from wolflauncher.mods_feature import ModsFeatureMixin
from wolflauncher.server_browser_feature import ServerBrowserMixin
from wolflauncher.settings_feature import SettingsFeatureMixin


class MainWindowFeatureSplitTests(unittest.TestCase):
    def test_main_window_composes_the_five_feature_mixins(self):
        self.assertEqual(
            MainWindow.__mro__[1:6],
            (
                CuratedServersMixin,
                ServerBrowserMixin,
                ModsFeatureMixin,
                SettingsFeatureMixin,
                LaunchFeatureMixin,
            ),
        )

    def test_representative_workflows_are_owned_by_their_feature(self):
        expected_owners = {
            "_build_servers_tab": CuratedServersMixin,
            "_build_server_browser_tab": ServerBrowserMixin,
            "_build_mods_tab": ModsFeatureMixin,
            "_build_settings_tab": SettingsFeatureMixin,
            "launch_selected": LaunchFeatureMixin,
        }
        for method_name, owner in expected_owners.items():
            with self.subTest(method=method_name):
                self.assertIn(method_name, owner.__dict__)
                self.assertNotIn(method_name, MainWindow.__dict__)
