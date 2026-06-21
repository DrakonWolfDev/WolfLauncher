import unittest
from pathlib import Path


LEGACY_LAUNCHER = Path(__file__).resolve().parents[1] / "external" / "dayz-linux-cli-launcher" / "dayz-launcher.sh"


class LegacyLauncherContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.script = LEGACY_LAUNCHER.read_text(encoding="utf-8")

    def test_vendored_launcher_exposes_expected_dayz_defaults(self):
        self.assertIn("DAYZ_ID=221100", self.script)
        self.assertIn("DEFAULT_GAMEPORT=2302", self.script)
        self.assertIn("DEFAULT_QUERYPORT=27016", self.script)

    def test_vendored_launcher_accepts_wolflauncher_handoff_options(self):
        for option in [
            "-s|--server)",
            "-p|--port)",
            "-n|--name)",
            "-l|--launch)",
        ]:
            with self.subTest(option=option):
                self.assertIn(option, self.script)

    def test_vendored_launcher_queries_dayzsa_api_with_server_address_and_query_port(self):
        self.assertIn("API_URL=\"https://dayzsalauncher.com/api/v1/query/@ADDRESS@/@PORT@\"", self.script)
        self.assertIn("s/@ADDRESS@/${SERVER%:*}/", self.script)
        self.assertIn("s/@PORT@/${PORT}/", self.script)

    def test_vendored_launcher_launches_steam_with_connect_target_and_profile_name(self):
        self.assertIn('cmdline+=("-connect=${SERVER}" -nolauncher -world=empty)', self.script)
        self.assertIn('cmdline+=("-name=${NAME}")', self.script)
        self.assertIn('run_steam -applaunch "${DAYZ_ID}" "${cmdline[@]}" "${PARAMS[@]}"', self.script)


if __name__ == "__main__":
    unittest.main()
