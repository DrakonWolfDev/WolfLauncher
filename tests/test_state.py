import tempfile
import unittest
from pathlib import Path

from wolf_update.state import JsonFileStateStore, UpdateState


class StateTests(unittest.TestCase):
    def setUp(self):
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary_directory.name)

    def tearDown(self):
        self.temporary_directory.cleanup()

    def test_json_state_round_trip(self):
        store = JsonFileStateStore(self.root / "update-state.json")
        state = UpdateState("2026-10-13T10:00:00+00:00", "1.2.3")
        store.save(state)
        self.assertEqual(store.load(), state)

    def test_damaged_state_fails_to_safe_defaults(self):
        path = self.root / "update-state.json"
        path.write_text("not json", encoding="utf-8")
        self.assertEqual(JsonFileStateStore(path).load(), UpdateState())


if __name__ == "__main__":
    unittest.main()
