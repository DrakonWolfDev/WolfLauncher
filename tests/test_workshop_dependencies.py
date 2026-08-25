import unittest
from unittest.mock import patch

from wolflauncher.mods import (
    _WorkshopRequiredItemsParser,
    cached_workshop_dependencies,
    resolve_workshop_dependencies,
)


class WorkshopDependencyResolutionTests(unittest.TestCase):
    def test_uses_ready_wolfapi_cached_graph(self):
        payload = {
            "graphs": {
                "2572331007": {
                    "status": "ready",
                    "dependencies": ["1559212036", "2545327648", "2116157322"],
                    "metadata": {"1559212036": {"title": "CF"}},
                }
            }
        }
        with patch("wolflauncher.mods.fetch_json", return_value=payload) as fetch_json:
            resolved, metadata = cached_workshop_dependencies(["2572331007"])

        self.assertEqual(
            resolved, ("2572331007", "1559212036", "2545327648", "2116157322")
        )
        self.assertEqual(metadata, {"1559212036": {"title": "CF"}})
        self.assertIn("ids=2572331007", fetch_json.call_args.args[0])

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

        with patch("wolflauncher.mods.fetch_workshop_metadata", side_effect=metadata), patch(
            "wolflauncher.mods.fetch_workshop_page_required_items", return_value=()
        ):
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

    def test_uses_required_items_page_links_when_steam_metadata_has_no_children(self):
        with patch("wolflauncher.mods.fetch_workshop_metadata", return_value={}), patch(
            "wolflauncher.mods.fetch_workshop_page_required_items",
            side_effect=lambda workshop_id: {"2878980498": ("3556131153",)}.get(workshop_id, ()),
        ):
            resolved, _metadata = resolve_workshop_dependencies(["2878980498"])

        self.assertEqual(resolved, ("2878980498", "3556131153"))

    def test_parses_only_required_item_workshop_links(self):
        parser = _WorkshopRequiredItemsParser()
        parser.feed(
            '<a href="?id=999">Unrelated</a>'
            '<div class="requiredItemsContainer"><a href="?id=200">Core</a></div>'
        )
        self.assertEqual(parser.workshop_ids, ["200"])

if __name__ == "__main__":
    unittest.main()
