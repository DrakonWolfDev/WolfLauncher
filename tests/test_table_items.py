import unittest

from wolflauncher.table_items import SortableTableWidgetItem


class SortableTableWidgetItemTests(unittest.TestCase):
    def test_numeric_values_sort_numerically(self):
        low = SortableTableWidgetItem("9", 9)
        high = SortableTableWidgetItem("10", 10)

        self.assertLess(low, high)

    def test_text_values_sort_case_insensitively(self):
        alpha = SortableTableWidgetItem("alpha", "alpha")
        beta = SortableTableWidgetItem("Beta", "Beta")

        self.assertLess(alpha, beta)

    def test_empty_values_sort_after_populated_values(self):
        populated = SortableTableWidgetItem("Online", "Online")
        empty = SortableTableWidgetItem("", "")

        self.assertLess(populated, empty)

    def test_text_is_default_sort_value(self):
        item = SortableTableWidgetItem("Mixed Case")

        self.assertEqual(item.sort_value, "mixed case")

    def test_explicit_none_is_empty_even_when_display_has_placeholder(self):
        known = SortableTableWidgetItem("17", 17)
        unknown = SortableTableWidgetItem("–", None)

        self.assertLess(known, unknown)

    def test_mixed_numeric_and_text_values_have_stable_type_order(self):
        numeric = SortableTableWidgetItem("17", 17)
        text = SortableTableWidgetItem("Unknown", "Unknown")

        self.assertLess(numeric, text)


if __name__ == "__main__":
    unittest.main()
