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
class TableDataset:
    """Canonical representation of tabular data for table views."""

    identifier: str
    source_path: Path
    column_names: Sequence[float | str | bool]
    row_names: Sequence[float | str | bool]
    content: Sequence[Sequence[float | str | bool]]
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
            self.table_style.cache_key() if self.table_style else None,
        )


@dataclass(frozen=True)
class RangeDataset:
    """Canonical representation of range data along the X axis."""

    identifier: str
    source_path: Path
    ranges: Sequence[tuple[float, float]]
    x_label: str | None = None
    y_label: str | None = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    kind: DataKind = DataKind.RANGE

    def cache_key(self) -> tuple[Any, ...]:
        return (
            self.kind,
            self.identifier,
            tuple(tuple(pair) for pair in self.ranges),
            self.x_label,
            self.y_label,
        )


DataPayload = Dataset | TableDataset | RangeDataset
