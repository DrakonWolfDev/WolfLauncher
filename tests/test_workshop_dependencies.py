import unittest
import struct
import tempfile
from pathlib import Path
from unittest.mock import patch

from wolflauncher.mods import (
    resolve_local_dayz_addon_dependencies,
    resolve_workshop_dependencies,
)


def write_pbo(path: Path, config: bytes):
    """Create the smallest PBO shape needed by the local metadata reader."""
    with path.open("wb") as handle:
        handle.write(b"\0" + struct.pack("<IIIII", 0, 0, 0, 0, 0))
        handle.write(b"prefix\0example\0\0")
        handle.write(b"config.bin\0" + struct.pack("<IIIII", 0, len(config), 0, 0, len(config)))
        handle.write(b"\0" + struct.pack("<IIIII", 0, 0, 0, 0, 0))
        handle.write(config)


class WorkshopDependencyResolutionTests(unittest.TestCase):
    def test_resolves_nested_dependencies_once_and_preserves_selection_order(self):
        responses = {
            "100": {"children": ("200", "300")},
            "200": {"children": ("300", "400")},
            "300": {"children": ()},
            "400": {"children": ("100",)},
        }

        def metadata(ids, *, include_children=False):
            self.assertTrue(include_children)
            return {item: responses[item] for item in ids if item in responses}

        with patch("wolflauncher.mods.fetch_workshop_metadata", side_effect=metadata):
            resolved, _metadata = resolve_workshop_dependencies(["100", "100"])

        self.assertEqual(resolved, ("100", "200", "300", "400"))

    def test_ignores_invalid_ids_and_honours_the_item_bound(self):
        with patch(
            "wolflauncher.mods.fetch_workshop_metadata",
            return_value={"100": {"children": ("200", "300")}},
        ):
            resolved, _metadata = resolve_workshop_dependencies(
                ["", "not-an-id", "100"], max_items=2
            )

        self.assertEqual(resolved, ("100", "200"))

    def test_local_addon_scan_matches_selected_pbo_references_to_workshop_owner(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            workshop = Path(temp_dir)
            source = workshop / "100" / "addons"
            provider = workshop / "200" / "addons"
            source.mkdir(parents=True)
            provider.mkdir(parents=True)
            write_pbo(source / "map_fix.pbo", b"uses dz_example_assets_part1\0")
            write_pbo(provider / "dz_example_assets_part1.pbo", b"config\0")

            detected = resolve_local_dayz_addon_dependencies(["100"], workshop)

        self.assertEqual(detected, ("200",))


if __name__ == "__main__":
    unittest.main()
