from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Sequence

from visualizer.data.models import DataPayload, Dataset, RangeDataset, TableDataset


class VisualizationType(str, Enum):
    LINE = "line"
    SCATTER = "scatter"
    STICK = "stick"
    COLORMAP = "colormap"
    EVENTLINE = "eventline"
    RANGE = "ranges"

    @classmethod
    def from_string(cls, value: str) -> VisualizationType:
        from visualizer.viz.registry import get_default_registry  # lazy import to avoid cycle

        registry = get_default_registry()
        return registry.visualization_for_style(value)


@dataclass(frozen=True)
class PlotSpec:
    dataset_id: str
    label: str | None
    x: Sequence[float | str | bool]
    y: Sequence[float] | Sequence[float | str | bool]
    x_label: str | None
    y_label: str | None
    visualization: VisualizationType
    ranges: Sequence[tuple[float, float]] | None = None
    style_params: dict[str, Any] | None = None

    def cache_key(self) -> tuple:
        params_key = None
        if self.style_params:
            params_key = tuple(sorted((key, repr(value)) for key, value in self.style_params.items()))
        return (
            self.dataset_id,
            self.label,
            tuple(self.x),
            tuple(self.y),
            self.x_label,
            self.y_label,
            self.visualization,
            tuple(self.ranges) if self.ranges else None,
            params_key,
        )


@dataclass(frozen=True)
class TableSpec:
    dataset_id: str
    label: str | None
    column_names: Sequence[float | str | bool]
    row_names: Sequence[float | str | bool]
    content: Sequence[Sequence[float | str | bool]]

    def cache_key(self) -> tuple:
        return (
            self.dataset_id,
            self.label,
            tuple(self.column_names),
            tuple(self.row_names),
            tuple(tuple(row) for row in self.content),
        )


class DefaultInterpreter:
    """Maps datasets to plot specs using simple heuristics."""

    def build_spec(
        self,
        dataset: DataPayload,
        override: VisualizationType | None = None,
        label: str | None = None,
        style_params: dict[str, Any] | None = None,
    ) -> PlotSpec | TableSpec:
        if isinstance(dataset, TableDataset):
            return self.build_table_spec(dataset, label=label)
        if isinstance(dataset, RangeDataset):
            return self.build_range_spec(dataset, override=override, label=label, style_params=style_params)
        return self.build_plot_spec(
            dataset,
            override=override,
            label=label,
            style_params=style_params,
        )

    def build_plot_spec(
        self,
        dataset: Dataset,
        override: VisualizationType | None = None,
        label: str | None = None,
        style_params: dict[str, Any] | None = None,
    ) -> PlotSpec:
        visualization = override or self._infer_visualization(dataset)
        x_values = list(dataset.x)
        y_values = list(dataset.y)
        if visualization == VisualizationType.LINE:
            sorted_pairs = self._sort_by_numeric_x(x_values, y_values)
            if sorted_pairs:
                x_values, y_values = zip(*sorted_pairs)
                x_values = list(x_values)
                y_values = list(y_values)

        return PlotSpec(
            dataset_id=dataset.identifier,
            label=label or dataset.identifier,
            x=x_values,
            y=y_values,
            x_label=dataset.x_label or "X Axis",
            y_label=dataset.y_label or "Y Axis",
            visualization=visualization,
            style_params=style_params,
        )

    def build_table_spec(self, dataset: TableDataset, label: str | None = None) -> TableSpec:
        return TableSpec(
            dataset_id=dataset.identifier,
            label=label or dataset.identifier,
            column_names=list(dataset.column_names),
            row_names=list(dataset.row_names),
            content=[list(row) for row in dataset.content],
        )

    def build_range_spec(
        self,
        dataset: RangeDataset,
        override: VisualizationType | None = None,
        label: str | None = None,
        style_params: dict[str, Any] | None = None,
    ) -> PlotSpec:
        visualization = override or VisualizationType.RANGE
        return PlotSpec(
            dataset_id=dataset.identifier,
            label=label or dataset.identifier,
            x=[],
            y=[],
            x_label=dataset.x_label or "X Axis",
            y_label=dataset.y_label or "Y Axis",
            visualization=visualization,
            ranges=list(dataset.ranges),
            style_params=style_params,
        )

    def _infer_visualization(self, dataset: Dataset) -> VisualizationType:
        if self._is_monotonic_numeric(dataset.x):
            return VisualizationType.LINE
        return VisualizationType.SCATTER

    @staticmethod
    def _is_monotonic_numeric(values: Sequence[float | str | bool]) -> bool:
        numeric_values: list[float] = []
        for value in values:
            try:
                numeric_values.append(float(value))
            except (TypeError, ValueError):
                return False
        return all(a <= b for a, b in zip(numeric_values, numeric_values[1:]))

    @staticmethod
    def _sort_by_numeric_x(
        x_values: Sequence[float | str | bool], y_values: Sequence[float]
    ) -> list[tuple[float | str, float]] | None:
        if len(x_values) != len(y_values):
            return None
        sortable_pairs: list[tuple[float, float]] = []
        try:
            for x, y in zip(x_values, y_values):
                sortable_pairs.append((float(x), y))
        except (TypeError, ValueError):
            return None
        sortable_pairs.sort(key=lambda pair: pair[0])
        return [(numeric_x, y) for numeric_x, y in sortable_pairs]
