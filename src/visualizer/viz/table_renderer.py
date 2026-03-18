from __future__ import annotations

import math
from typing import Callable

from PySide6 import QtCore, QtGui, QtWidgets

from visualizer.interpretation.specs import TableSpec
from visualizer.table_style import TableColorConfig


_DEFAULT_NUMERIC_PALETTE = (
    QtGui.QColor(230, 245, 255),
    QtGui.QColor(8, 88, 158),
)
_NAMED_NUMERIC_PALETTES = {
    "blue": _DEFAULT_NUMERIC_PALETTE,
    "viridis": (QtGui.QColor(68, 1, 84), QtGui.QColor(253, 231, 37)),
    "plasma": (QtGui.QColor(13, 8, 135), QtGui.QColor(240, 249, 33)),
    "cividis": (QtGui.QColor(0, 34, 78), QtGui.QColor(253, 231, 55)),
    "magma": (QtGui.QColor(0, 0, 4), QtGui.QColor(252, 253, 191)),
}


class TableModel(QtCore.QAbstractTableModel):
    def __init__(self, spec: TableSpec) -> None:
        super().__init__()
        self._spec = spec
        self._rows = [list(row) for row in spec.content]
        self._row_names = [str(name) for name in spec.row_names]
        self._column_names = [str(name) for name in spec.column_names]
        self._table_style = spec.table_style or TableColorConfig()
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
            brush = self._background_brush(value, index.row(), index.column())
            return brush
        if role == QtCore.Qt.ForegroundRole:
            value = self._rows[index.row()][index.column()]
            brush = self._foreground_brush(value, index.row(), index.column())
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

    def _background_brush(self, value: object, row: int, column: int) -> QtGui.QBrush | None:
        color = self._background_color(value, row, column)
        if color is None:
            return None
        return QtGui.QBrush(color)

    def _foreground_brush(self, value: object, row: int, column: int) -> QtGui.QBrush | None:
        color = self._background_color(value, row, column)
        if color is None:
            return None
        luminance = (0.299 * color.red() + 0.587 * color.green() + 0.114 * color.blue())
        text_color = QtGui.QColor(20, 20, 20) if luminance > 140 else QtGui.QColor(250, 250, 250)
        return QtGui.QBrush(text_color)

    def _background_color(self, value: object, row: int, column: int) -> QtGui.QColor | None:
        if isinstance(value, bool):
            if value:
                return QtGui.QColor(198, 239, 206)
            return QtGui.QColor(255, 199, 206)
        numeric = self._coerce_numeric(value)
        if numeric is not None:
            minimum, maximum, palette, reverse = self._resolved_numeric_style(row=row, column=column)
            return self._numeric_color(numeric, minimum, maximum, palette, reverse)
        if value is None:
            return None
        return QtGui.QColor(235, 235, 235)

    def _resolved_numeric_style(
        self, row: int, column: int
    ) -> tuple[float | None, float | None, str | None, bool]:
        min_val, max_val = self._column_ranges[column] if column < len(self._column_ranges) else (None, None)
        palette = None
        reverse = False
        rule = self._table_style.global_rule
        if rule:
            if rule.value_range is not None:
                min_val, max_val = rule.value_range
            if rule.palette is not None:
                palette = rule.palette
            if rule.reverse is not None:
                reverse = rule.reverse

        if column < len(self._table_style.column_rules):
            col_rule = self._table_style.column_rules[column]
            if col_rule:
                if col_rule.value_range is not None:
                    min_val, max_val = col_rule.value_range
                if col_rule.palette is not None:
                    palette = col_rule.palette
                if col_rule.reverse is not None:
                    reverse = col_rule.reverse

        if row < len(self._table_style.row_rules):
            row_rule = self._table_style.row_rules[row]
            if row_rule:
                if row_rule.value_range is not None:
                    min_val, max_val = row_rule.value_range
                if row_rule.palette is not None:
                    palette = row_rule.palette
                if row_rule.reverse is not None:
                    reverse = row_rule.reverse

        return min_val, max_val, palette, reverse

    def _numeric_color(
        self,
        value: float,
        minimum: float | None,
        maximum: float | None,
        palette: str | None,
        reverse: bool,
    ) -> QtGui.QColor:
        if minimum is None or maximum is None:
            return QtGui.QColor(235, 235, 235)
        if maximum == minimum:
            t = 0.5
        else:
            t = (value - minimum) / (maximum - minimum)
        t = max(0.0, min(1.0, t))
        low, high = self._palette_endpoints(palette, reverse=reverse)
        r = low.red() + (high.red() - low.red()) * t
        g = low.green() + (high.green() - low.green()) * t
        b = low.blue() + (high.blue() - low.blue()) * t
        return QtGui.QColor(int(r), int(g), int(b))

    def _palette_endpoints(
        self, palette: str | None, *, reverse: bool = False
    ) -> tuple[QtGui.QColor, QtGui.QColor]:
        if not palette:
            endpoints = _DEFAULT_NUMERIC_PALETTE
            return (endpoints[1], endpoints[0]) if reverse else endpoints
        key = str(palette).strip().lower()
        endpoints = _NAMED_NUMERIC_PALETTES.get(key, _DEFAULT_NUMERIC_PALETTE)
        return (endpoints[1], endpoints[0]) if reverse else endpoints


class TableView(QtWidgets.QTableView):
    def __init__(self) -> None:
        super().__init__()
        self.pivot_handler: Callable[[int], bool] | None = None
        self.navigation_handler: Callable[[int], bool] | None = None
        self._title_label = QtWidgets.QLabel(self)
        self._title_label.setObjectName("tableTitleLabel")
        self._title_label.setVisible(False)
        self._title_label.setAlignment(QtCore.Qt.AlignLeft | QtCore.Qt.AlignVCenter)
        self._title_label.setContentsMargins(4, 0, 4, 0)
        self._title_height = 18

    def set_table_title(self, title: str | None) -> None:
        text = (title or "").strip()
        if text:
            self._title_label.setText(text)
            self._title_label.setVisible(True)
            self.setViewportMargins(0, self._title_height, 0, 0)
        else:
            self._title_label.clear()
            self._title_label.setVisible(False)
            self.setViewportMargins(0, 0, 0, 0)
        self._position_title_label()

    def table_title(self) -> str:
        return self._title_label.text()

    def resizeEvent(self, event: QtGui.QResizeEvent) -> None:  # type: ignore[override]
        super().resizeEvent(event)
        self._position_title_label()

    def _position_title_label(self) -> None:
        if not self._title_label.isVisible():
            return
        frame = self.frameWidth()
        width = max(0, self.width() - (frame * 2))
        self._title_label.setGeometry(frame, frame, width, self._title_height)

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
        if isinstance(view, TableView):
            view.set_table_title(spec.label)
        view.setAlternatingRowColors(True)
        view.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)
        view.setSelectionMode(QtWidgets.QAbstractItemView.SingleSelection)
        view.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)
        header = view.horizontalHeader()
        header.setStretchLastSection(False)
        header.setSectionResizeMode(QtWidgets.QHeaderView.Stretch)
        view._table_model = model  # type: ignore[attr-defined]
