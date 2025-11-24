from __future__ import annotations

from typing import Dict, Iterable

import pyqtgraph as pg

from visualizer.interpretation.specs import PlotSpec, VisualizationType


class PlotRenderer:
    """Renders PlotSpec objects onto a PyQtGraph widget."""

    def __init__(self) -> None:
        pg.setConfigOption("background", "w")
        pg.setConfigOption("foreground", "k")
        self._cache: Dict[tuple, PlotSpec] = {}

    def render(self, widget: pg.PlotWidget, spec: PlotSpec) -> None:
        cache_key = spec.cache_key()
        if cache_key not in self._cache:
            self._cache[cache_key] = spec
        widget.clear()
        if spec.visualization == VisualizationType.LINE:
            widget.plot(
                spec.x,
                spec.y,
                pen=pg.mkPen(color=(50, 110, 240), width=2),
                symbol=None,
            )
        else:
            widget.plot(
                spec.x,
                spec.y,
                pen=None,
                symbol="o",
                symbolBrush=(50, 110, 240, 180),
                symbolSize=6,
            )
        widget.setLabel("bottom", spec.x_label or "X Axis")
        widget.setLabel("left", spec.y_label or "Y Axis")
        widget.showGrid(x=True, y=True, alpha=0.2)

    def render_multiple(self, widget: pg.PlotWidget, specs: Iterable[PlotSpec]) -> None:
        specs = list(specs)
        if not specs:
            widget.clear()
            return
        widget.clear()
        for index, spec in enumerate(specs):
            color = pg.intColor(index, hues=len(specs) * 2)
            if spec.visualization == VisualizationType.LINE:
                widget.plot(
                    spec.x,
                    spec.y,
                    pen=pg.mkPen(color=color, width=2),
                    symbol=None,
                )
            else:
                widget.plot(
                    spec.x,
                    spec.y,
                    pen=None,
                    symbol="o",
                    symbolBrush=color,
                    symbolSize=6,
                )
        first = specs[0]
        widget.setLabel("bottom", first.x_label or "X Axis")
        widget.setLabel("left", first.y_label or "Y Axis")
        widget.showGrid(x=True, y=True, alpha=0.2)
