import unittest
from unittest.mock import patch

from wolflauncher.mods import resolve_workshop_dependencies


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


if __name__ == "__main__":
    unittest.main()
