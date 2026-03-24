from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Dict, Sequence

from visualizer.table_style import TableColorConfig


class DataKind(str, Enum):
    SERIES = "series"
    TABLE = "table"
    RANGE = "ranges"


@dataclass(frozen=True)
class Dataset:
    """Canonical representation of numeric data to be visualized."""

    identifier: str
    source_path: Path
    x: Sequence[float | str | bool]
    y: Sequence[float]
    x_label: str | None = None
    y_label: str | None = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    kind: DataKind = DataKind.SERIES

    def cache_key(self) -> tuple[Any, ...]:
        """Stable key for caching downstream plot specs."""

        return (
            self.kind,
            self.identifier,
            tuple(self.x),
            tuple(self.y),
            self.x_label,
            self.y_label,
        )


@dataclass(frozen=True)
class TableColumnGroup:
    """Display grouping for table columns.

    When ``subcolumns`` is empty, the group represents a regular single column.
    When ``subcolumns`` is populated, ``label`` is the top-level group label and
    the subcolumn entries define the flattened leaf columns.
    """

    label: float | str | bool
    subcolumns: Sequence[float | str | bool] = field(default_factory=tuple)

    def leaf_labels(self) -> tuple[float | str | bool, ...]:
        if self.subcolumns:
            return tuple(self.subcolumns)
        return (self.label,)

    def cache_key(self) -> tuple[Any, ...]:
        return (self.label, tuple(self.subcolumns))


@dataclass(frozen=True)
class TableDataset:
    """Canonical representation of tabular data for table views."""

    identifier: str
    source_path: Path
    column_names: Sequence[float | str | bool]
    row_names: Sequence[float | str | bool]
    content: Sequence[Sequence[float | str | bool]]
    column_groups: Sequence[TableColumnGroup] | None = None
    table_title: str | None = None
    table_style: TableColorConfig | None = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    kind: DataKind = DataKind.TABLE

    def cache_key(self) -> tuple[Any, ...]:
        return (
            self.kind,
            self.identifier,
            tuple(self.column_names),
            tuple(self.row_names),
            tuple(tuple(row) for row in self.content),
            tuple(group.cache_key() for group in self.column_groups) if self.column_groups else None,
            self.table_title,
            self.table_style.cache_key() if self.table_style else None,
        )


@dataclass(frozen=True)
class RangeDataset:
    """Canonical representation of range data along the X axis."""

    identifier: str
    source_path: Path
    ranges: Sequence[tuple[float, float]]
    range_info: Sequence[str | None] = field(default_factory=tuple)
    x_label: str | None = None
    y_label: str | None = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    kind: DataKind = DataKind.RANGE

    def cache_key(self) -> tuple[Any, ...]:
        return (
            self.kind,
            self.identifier,
            tuple(tuple(pair) for pair in self.ranges),
            tuple(self.range_info),
            self.x_label,
            self.y_label,
        )


DataPayload = Dataset | TableDataset | RangeDataset
