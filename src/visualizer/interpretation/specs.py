from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Sequence

from visualizer.data.models import Dataset


class VisualizationType(str, Enum):
    LINE = "line"
    SCATTER = "scatter"
    COLORMAP = "colormap"
    EVENTLINE = "eventline"

    @classmethod
    def from_string(cls, value: str) -> VisualizationType:
        normalized = value.strip().lower()
        aliases = {
            "colormap_line": cls.COLORMAP,
            "colormap": cls.COLORMAP,
            "heatmap1d": cls.COLORMAP,
            "eventline": cls.EVENTLINE,
            "events": cls.EVENTLINE,
            "spikes": cls.EVENTLINE,
        }
        if normalized in aliases:
            return aliases[normalized]
        for member in cls:
            if member.value == normalized:
                return member
        raise ValueError(f"Unsupported visualization type: {value}")


@dataclass(frozen=True)
class PlotSpec:
    dataset_id: str
    label: str | None
    x: Sequence[float | str]
    y: Sequence[float]
    x_label: str | None
    y_label: str | None
    visualization: VisualizationType

    def cache_key(self) -> tuple:
        return (
            self.dataset_id,
            self.label,
            tuple(self.x),
            tuple(self.y),
            self.x_label,
            self.y_label,
            self.visualization,
        )


class DefaultInterpreter:
    """Maps datasets to plot specs using simple heuristics."""

    def build_plot_spec(
        self,
        dataset: Dataset,
        override: VisualizationType | None = None,
        label: str | None = None,
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
        )

    def _infer_visualization(self, dataset: Dataset) -> VisualizationType:
        if self._is_monotonic_numeric(dataset.x):
            return VisualizationType.LINE
        return VisualizationType.SCATTER

    @staticmethod
    def _is_monotonic_numeric(values: Sequence[float | str]) -> bool:
        numeric_values: list[float] = []
        for value in values:
            try:
                numeric_values.append(float(value))
            except (TypeError, ValueError):
                return False
        return all(a <= b for a, b in zip(numeric_values, numeric_values[1:]))

    @staticmethod
    def _sort_by_numeric_x(
        x_values: Sequence[float | str], y_values: Sequence[float]
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
