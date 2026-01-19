from __future__ import annotations

import math
from typing import Callable

from PySide6 import QtCore, QtGui, QtWidgets

from visualizer.interpretation.specs import TableSpec


class TableModel(QtCore.QAbstractTableModel):
    def __init__(self, spec: TableSpec) -> None:
        super().__init__()
        self._spec = spec
        self._rows = [list(row) for row in spec.content]
        self._row_names = [str(name) for name in spec.row_names]
        self._column_names = [str(name) for name in spec.column_names]
        self._column_ranges = self._compute_column_ranges()

    def rowCount(self, parent: QtCore.QModelIndex = QtCore.QModelIndex()) -> int:  # noqa: B008
        return len(self._rows)

    def columnCount(self, parent: QtCore.QModelIndex = QtCore.QModelIndex()) -> int:  # noqa: B008
        return len(self._column_names)

    def data(self, index: QtCore.QModelIndex, role: int = QtCore.Qt.DisplayRole) -> object | None:
        if not index.isValid():
            return None
        if role == QtCore.Qt.DisplayRole:
            value = self._rows[index.row()][index.column()]
            return "" if value is None else str(value)
        if role == QtCore.Qt.BackgroundRole:
            value = self._rows[index.row()][index.column()]
            brush = self._background_brush(value, index.column())
            return brush
        if role == QtCore.Qt.ForegroundRole:
            value = self._rows[index.row()][index.column()]
            brush = self._foreground_brush(value, index.column())
            return brush
        return None

    def headerData(
        self,
        section: int,
        orientation: QtCore.Qt.Orientation,
        role: int = QtCore.Qt.DisplayRole,
    ) -> str | None:
        if role != QtCore.Qt.DisplayRole:
            return None
        if orientation == QtCore.Qt.Horizontal:
            if 0 <= section < len(self._column_names):
                return self._column_names[section]
            return None
        if 0 <= section < len(self._row_names):
            return self._row_names[section]
        return None

    def flags(self, index: QtCore.QModelIndex) -> QtCore.Qt.ItemFlags:
        if not index.isValid():
            return QtCore.Qt.NoItemFlags
        return QtCore.Qt.ItemIsEnabled | QtCore.Qt.ItemIsSelectable

    def _compute_column_ranges(self) -> list[tuple[float | None, float | None]]:
        ranges: list[tuple[float | None, float | None]] = []
        for col_idx in range(len(self._column_names)):
            minimum = None
            maximum = None
            for row in self._rows:
                if col_idx >= len(row):
                    continue
                numeric = self._coerce_numeric(row[col_idx])
                if numeric is None:
                    continue
                minimum = numeric if minimum is None else min(minimum, numeric)
                maximum = numeric if maximum is None else max(maximum, numeric)
            ranges.append((minimum, maximum))
        return ranges

    def _coerce_numeric(self, value: object) -> float | None:
        if value is None:
            return None
        if isinstance(value, bool):
            return None
        if isinstance(value, (int, float)):
            numeric = float(value)
        else:
            try:
                numeric = float(value)
            except (TypeError, ValueError):
                return None
        if not math.isfinite(numeric):
            return None
        return numeric

    def _background_brush(self, value: object, column: int) -> QtGui.QBrush | None:
        color = self._background_color(value, column)
        if color is None:
            return None
        return QtGui.QBrush(color)

    def _foreground_brush(self, value: object, column: int) -> QtGui.QBrush | None:
        color = self._background_color(value, column)
        if color is None:
            return None
        luminance = (0.299 * color.red() + 0.587 * color.green() + 0.114 * color.blue())
        text_color = QtGui.QColor(20, 20, 20) if luminance > 140 else QtGui.QColor(250, 250, 250)
        return QtGui.QBrush(text_color)

    def _background_color(self, value: object, column: int) -> QtGui.QColor | None:
        if isinstance(value, bool):
            if value:
                return QtGui.QColor(198, 239, 206)
            return QtGui.QColor(255, 199, 206)
        numeric = self._coerce_numeric(value)
        if numeric is not None:
            min_val, max_val = self._column_ranges[column] if column < len(self._column_ranges) else (None, None)
            return self._numeric_color(numeric, min_val, max_val)
        if value is None:
            return None
        return QtGui.QColor(235, 235, 235)

    def _numeric_color(self, value: float, minimum: float | None, maximum: float | None) -> QtGui.QColor:
        if minimum is None or maximum is None:
            return QtGui.QColor(235, 235, 235)
        if maximum == minimum:
            t = 0.5
        else:
            t = (value - minimum) / (maximum - minimum)
        t = max(0.0, min(1.0, t))
        low = QtGui.QColor(230, 245, 255)
        high = QtGui.QColor(8, 88, 158)
        r = low.red() + (high.red() - low.red()) * t
        g = low.green() + (high.green() - low.green()) * t
        b = low.blue() + (high.blue() - low.blue()) * t
        return QtGui.QColor(int(r), int(g), int(b))


class TableView(QtWidgets.QTableView):
    def __init__(self) -> None:
        super().__init__()
        self.pivot_handler: Callable[[int], bool] | None = None
        self.navigation_handler: Callable[[int], bool] | None = None

    def keyPressEvent(self, event: QtGui.QKeyEvent) -> None:  # type: ignore[override]
        if event.key() in (QtCore.Qt.Key_Left, QtCore.Qt.Key_Right) and self.pivot_handler:
            step = -1 if event.key() == QtCore.Qt.Key_Left else 1
            handled = bool(self.pivot_handler(step))
            if handled:
                event.accept()
                return
        if event.key() in (QtCore.Qt.Key_Up, QtCore.Qt.Key_Down) and self.navigation_handler:
            step = -1 if event.key() == QtCore.Qt.Key_Up else 1
            handled = bool(self.navigation_handler(step))
            if handled:
                event.accept()
                return
        super().keyPressEvent(event)


class TableRenderer:
    def render(self, view: QtWidgets.QTableView, spec: TableSpec) -> None:
        model = TableModel(spec)
        view.setModel(model)
        view.setAlternatingRowColors(True)
        view.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)
        view.setSelectionMode(QtWidgets.QAbstractItemView.SingleSelection)
        view.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)
        header = view.horizontalHeader()
        header.setStretchLastSection(False)
        header.setSectionResizeMode(QtWidgets.QHeaderView.Stretch)
        view._table_model = model  # type: ignore[attr-defined]
