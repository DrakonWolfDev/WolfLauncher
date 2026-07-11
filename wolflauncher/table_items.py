from PySide6.QtWidgets import QTableWidgetItem


class SortableTableWidgetItem(QTableWidgetItem):
    def __init__(self, text: str, sort_value=None):
        super().__init__(text)
        self.sort_value = sort_value if sort_value is not None else text.casefold()

    def __lt__(self, other):
        if isinstance(other, SortableTableWidgetItem):
            return self._normalized_sort_value() < other._normalized_sort_value()
        return super().__lt__(other)

    def _normalized_sort_value(self):
        value = self.sort_value
        if value is None or value == "":
            return (1, "")
        if isinstance(value, str):
            return (0, value.casefold())
        return (0, value)
