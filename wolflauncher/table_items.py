from PySide6.QtWidgets import QTableWidgetItem

_DEFAULT_SORT_VALUE = object()


class SortableTableWidgetItem(QTableWidgetItem):
    def __init__(self, text: str, sort_value=_DEFAULT_SORT_VALUE):
        super().__init__(text)
        self.sort_value = text.casefold() if sort_value is _DEFAULT_SORT_VALUE else sort_value

    def __lt__(self, other):
        if isinstance(other, SortableTableWidgetItem):
            return self._normalized_sort_value() < other._normalized_sort_value()
        return super().__lt__(other)

    def _normalized_sort_value(self):
        value = self.sort_value
        if value is None or value == "":
            return (2, "")
        if isinstance(value, (int, float)):
            return (0, value)
        if isinstance(value, str):
            return (1, value.casefold())
        return (1, str(value).casefold())
