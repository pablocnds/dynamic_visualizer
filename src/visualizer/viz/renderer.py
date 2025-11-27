from __future__ import annotations

from typing import Iterable

import pyqtgraph as pg
import numpy as np

from visualizer.interpretation.specs import PlotSpec, VisualizationType

_MAX_1D_SAMPLES = 1200
_MAX_EVENT_BINS = 800


class PlotRenderer:
    """Renders PlotSpec objects onto a PyQtGraph widget."""

    def __init__(self) -> None:
        pg.setConfigOption("background", "w")
        pg.setConfigOption("foreground", "k")
        self._colorbars: dict[int, list[pg.ColorBarItem]] = {}
        self._colorbars: dict[int, list[pg.ColorBarItem]] = {}

    def render(self, widget: pg.PlotWidget, spec: PlotSpec) -> None:
        self._clear_legend(widget)
        self._clear_colorbar(widget)
        widget.clear()
        plot_item = widget.getPlotItem()
        plot_item.showAxis("left")
        plot_item.getAxis("left").setStyle(showValues=True)
        plot_item.showAxis("bottom")

        if spec.visualization == VisualizationType.LINE:
            curve = widget.plot(
                spec.x,
                spec.y,
                pen=pg.mkPen(color=(50, 110, 240), width=2),
                symbol=None,
            )
        elif spec.visualization == VisualizationType.SCATTER:
            curve = widget.plot(
                spec.x,
                spec.y,
                pen=None,
                symbol="o",
                symbolBrush=(50, 110, 240, 180),
                symbolSize=6,
            )
        elif spec.visualization == VisualizationType.EVENTLINE:
            self._render_eventline(widget, spec)
            return
        elif spec.visualization == VisualizationType.COLORMAP:
            self._render_colormap(widget, spec)
            return
        widget.setLabel("bottom", spec.x_label or "X Axis")
        widget.setLabel("left", spec.y_label or "Y Axis")
        widget.showGrid(x=True, y=True, alpha=0.2)
        # Single-spec legend is optional; only add when multiple

    def render_multiple(self, widget: pg.PlotWidget, specs: Iterable[PlotSpec]) -> None:
        specs = list(specs)
        if not specs:
            widget.clear()
            return
        self._clear_colorbar(widget)
        if len(specs) > 1 and all(self._is_one_dimensional(spec) for spec in specs):
            self._render_one_dimensional_overlay(widget, specs)
            return
        if len(specs) > 1 and any(self._is_one_dimensional(spec) for spec in specs):
            raise ValueError("Cannot overlay one-dimensional plots with other plot types")
        self._clear_legend(widget)
        widget.clear()
        legend = widget.addLegend()
        legend.setParentItem(widget.getPlotItem())
        legend.setBrush(pg.mkBrush(255, 255, 255, 220))
        legend.setPen(pg.mkPen(color=(30, 30, 30), width=1))
        # top-right anchor with padding
        legend.anchor(itemPos=(1, 0), parentPos=(1, 0), offset=(-10, 10))
        widget.legend = legend  # type: ignore[attr-defined]
        for index, spec in enumerate(specs):
            color = pg.intColor(index, hues=len(specs) * 2)
            label = getattr(spec, "label", None) or spec.dataset_id
            if spec.visualization == VisualizationType.LINE:
                curve = widget.plot(
                    spec.x,
                    spec.y,
                    pen=pg.mkPen(color=color, width=2),
                    symbol=None,
                    name=label,
                )
            else:
                curve = widget.plot(
                    spec.x,
                    spec.y,
                    pen=None,
                    symbol="o",
                    symbolBrush=color,
                    symbolSize=6,
                    name=label,
                )
        first = specs[0]
        widget.setLabel("bottom", first.x_label or "X Axis")
        widget.setLabel("left", first.y_label or "Y Axis")
        widget.showGrid(x=True, y=True, alpha=0.2)

    def _clear_legend(self, widget: pg.PlotWidget) -> None:
        legend = getattr(widget, "legend", None)
        if legend and legend.scene():
            legend.scene().removeItem(legend)
        if hasattr(widget, "legend"):
            widget.legend = None  # type: ignore[attr-defined]

    def reset_widget(self, widget: pg.PlotWidget) -> None:
        self._clear_legend(widget)
        self._clear_colorbar(widget)
        widget.clear()
        try:
            widget.enableAutoRange(x=True, y=True)
        except Exception:
            pass

    def clear_colorbars(self, widget: pg.PlotWidget) -> None:
        self._clear_colorbar(widget)

    def _render_colormap(self, widget: pg.PlotWidget, spec: PlotSpec) -> None:
        widget.clear()
        self._clear_legend(widget)
        self._clear_colorbar(widget)
        plot_item = widget.getPlotItem()
        plot_item.hideAxis("left")
        plot_item.getAxis("left").setStyle(showValues=False)
        plot_item.showAxis("bottom")
        plot_item.showGrid(x=False, y=False)
        values = self._coerce_array(spec.y)
        if values.size == 0:
            widget.setLabel("bottom", spec.x_label or "X Axis")
            widget.setLabel("left", spec.y_label or "Y Axis")
            widget.showGrid(x=True, y=True, alpha=0.2)
            return

        x_numeric, values = self._downsample_1d(self._coerce_array(spec.x, fallback_range=True), values, _MAX_1D_SAMPLES)
        rect = self._compute_rect(x_numeric, len(values))

        image = values.reshape(1, -1)
        image_item = pg.ImageItem()
        image_item.setImage(image, axisOrder="row-major")
        image_item.setRect(rect)
        cmap = pg.colormap.get("viridis")
        image_item.setLookupTable(cmap.getLookupTable(alpha=False))
        image_item.setLevels((float(np.nanmin(values)), float(np.nanmax(values))))
        widget.addItem(image_item)
        self._insert_colorbar(
            widget,
            pg.ColorBarItem(
                values=(float(np.nanmin(values)), float(np.nanmax(values))),
                colorMap=cmap,
            ),
            image_item=image_item,
            label=spec.y_label or "Intensity",
        )
        widget.setLabel("bottom", spec.x_label or "X Axis")
        widget.setLabel("left", spec.y_label or "Intensity")
        widget.setYRange(0, 1, padding=0)
        widget.showGrid(x=True, y=True, alpha=0.1)

    def _render_eventline(self, widget: pg.PlotWidget, spec: PlotSpec) -> None:
        widget.clear()
        self._clear_legend(widget)
        self._clear_colorbar(widget)
        plot_item = widget.getPlotItem()
        plot_item.hideAxis("left")
        plot_item.getAxis("left").setStyle(showValues=False)
        plot_item.showAxis("bottom")
        plot_item.showGrid(x=False, y=False)

        x_numeric = self._coerce_array(spec.x, fallback_range=True)
        intensities = self._coerce_array(spec.y)
        if intensities.shape[0] != x_numeric.shape[0]:
            intensities = np.ones_like(x_numeric, dtype=float)

        if x_numeric.size == 0:
            widget.setLabel("bottom", spec.x_label or "X Axis")
            widget.setYRange(0, 1, padding=0)
            return

        x_numeric, intensities = self._bin_events(x_numeric, intensities, _MAX_EVENT_BINS)
        if x_numeric.size == 0:
            widget.setLabel("bottom", spec.x_label or "X Axis")
            widget.setYRange(0, 1, padding=0)
            return

        x_min = float(np.nanmin(x_numeric))
        x_max = float(np.nanmax(x_numeric))
        span = x_max - x_min if x_max != x_min else 1.0
        bar_width = max(span * 0.01, span / max(len(x_numeric) * 2, 1))

        cmap = pg.colormap.get("viridis")
        levels = (float(np.nanmin(intensities)), float(np.nanmax(intensities)))
        if levels[0] == levels[1]:
            levels = (levels[0], levels[0] + 1e-9)
        lut = cmap.getLookupTable(nPts=512, alpha=False)
        scale = (intensities - levels[0]) / (levels[1] - levels[0])
        idx = np.clip((scale * (len(lut) - 1)).astype(int), 0, len(lut) - 1)
        colors = [pg.mkColor(lut[i]) for i in idx]

        bars = pg.BarGraphItem(x=x_numeric, height=np.ones_like(x_numeric), width=bar_width, brushes=colors, pens=colors)
        plot_item.addItem(bars)

        self._insert_colorbar(
            widget,
            pg.ColorBarItem(values=levels, colorMap=cmap),
            label=spec.y_label or "Intensity",
        )

        widget.setLabel("bottom", spec.x_label or "X Axis")
        widget.setYRange(0, 1, padding=0)
        widget.showGrid(x=True, y=True, alpha=0.1)

    def _clear_colorbar(self, widget: pg.PlotWidget) -> None:
        colorbars = self._colorbars.pop(id(widget), [])
        for colorbar in colorbars:
            try:
                if colorbar.scene():
                    colorbar.scene().removeItem(colorbar)
            except Exception:
                pass
        # Fallback: purge any ColorBarItem still in the scene
        try:
            scene = widget.getPlotItem().scene()
            for item in list(scene.items()):
                if isinstance(item, pg.ColorBarItem):
                    scene.removeItem(item)
        except Exception:
            pass

    def _insert_colorbar(
        self,
        widget: pg.PlotWidget,
        colorbar: pg.ColorBarItem,
        image_item: pg.ImageItem | None = None,
        label: str | None = None,
    ) -> None:
        plot_item = widget.getPlotItem()
        existing_list = self._colorbars.get(id(widget), [])

        try:
            plot_item.scene().addItem(colorbar)
        except Exception:
            return
        try:
            if image_item is not None:
                colorbar.setImageItem(image_item)
            else:
                colorbar.setLevels(colorbar.levels)
            if label:
                colorbar.setLabel(label)
        except Exception:
            # keep the colorbar even if linking fails
            pass

        # Position colorbars to the right of the viewbox with vertical stacking.
        view_rect = plot_item.getViewBox().sceneBoundingRect()
        offset_x = 10
        offset_y = 0
        if existing_list:
            offset_y = sum(cb.boundingRect().height() + 6 for cb in existing_list)
        colorbar.setPos(view_rect.right() + offset_x, view_rect.top() + offset_y)

        existing_list.append(colorbar)
        self._colorbars[id(widget)] = existing_list

    @staticmethod
    def _is_one_dimensional(spec: PlotSpec) -> bool:
        return spec.visualization in {VisualizationType.COLORMAP, VisualizationType.EVENTLINE}

    def _coerce_array(self, values, fallback_range: bool = False) -> np.ndarray:
        try:
            arr = np.asarray(values, dtype=float)
        except Exception:
            arr = np.array([], dtype=float)
        if arr.size == 0 and fallback_range and values is not None:
            try:
                arr = np.arange(len(values), dtype=float)
            except Exception:
                arr = np.array([], dtype=float)
        return arr

    def _downsample_1d(self, x_values, y_values: np.ndarray, max_samples: int) -> tuple[np.ndarray, np.ndarray]:
        try:
            x_numeric = np.asarray(x_values, dtype=float)
        except Exception:
            x_numeric = np.arange(len(y_values), dtype=float)
        if y_values.size <= max_samples:
            return x_numeric, y_values
        window = int(np.ceil(y_values.size / max_samples))
        segments = int(np.ceil(y_values.size / window))
        xs: list[float] = []
        ys: list[float] = []
        for i in range(segments):
            start = i * window
            end = min(start + window, y_values.size)
            if start >= end:
                break
            y_chunk = y_values[start:end]
            x_chunk = x_numeric[start:end]
            ys.append(float(np.nanmax(y_chunk)))
            xs.append(float(np.nanmean(x_chunk)) if x_chunk.size else float(i))
        return np.asarray(xs, dtype=float), np.asarray(ys, dtype=float)

    def _compute_rect(self, x_numeric: np.ndarray, length: int) -> pg.QtCore.QRectF:
        if x_numeric.size == length and x_numeric.size > 0:
            x_min = float(np.nanmin(x_numeric))
            x_max = float(np.nanmax(x_numeric))
            span = x_max - x_min
            return pg.QtCore.QRectF(x_min, 0.0, span if span else 1.0, 1.0)
        return pg.QtCore.QRectF(0.0, 0.0, float(length if length > 0 else 1), 1.0)

    def _bin_events(self, x_numeric: np.ndarray, intensities: np.ndarray, max_bins: int) -> tuple[np.ndarray, np.ndarray]:
        if x_numeric.size <= max_bins or x_numeric.size == 0:
            return x_numeric, intensities
        x_min = float(np.nanmin(x_numeric))
        x_max = float(np.nanmax(x_numeric))
        if not np.isfinite(x_min) or not np.isfinite(x_max) or x_min == x_max:
            stride = int(np.ceil(x_numeric.size / max_bins))
            return x_numeric[::stride], intensities[::stride]
        bins = np.linspace(x_min, x_max, max_bins + 1)
        idx = np.digitize(x_numeric, bins) - 1
        agg = np.zeros(max_bins, dtype=float)
        for value, bin_idx in zip(intensities, idx):
            if 0 <= bin_idx < max_bins:
                if value > agg[bin_idx]:
                    agg[bin_idx] = value
        centers = (bins[:-1] + bins[1:]) / 2.0
        return centers, agg

    def _render_one_dimensional_overlay(self, widget: pg.PlotWidget, specs: list[PlotSpec]) -> None:
        self._clear_legend(widget)
        self._clear_colorbar(widget)
        widget.clear()
        plot_item = widget.getPlotItem()
        plot_item.hideAxis("left")
        plot_item.getAxis("left").setStyle(showValues=False)
        plot_item.showAxis("bottom")
        plot_item.showGrid(x=False, y=False)
        cmap_names = ["viridis", "plasma", "cividis", "magma", "turbo"]

        for idx, spec in enumerate(specs):
            cmap = pg.colormap.get(cmap_names[idx % len(cmap_names)])
            if spec.visualization == VisualizationType.COLORMAP:
                self._render_colormap_with(widget, spec, cmap)
            elif spec.visualization == VisualizationType.EVENTLINE:
                self._render_eventline_with(widget, spec, cmap)

        widget.setLabel("bottom", specs[0].x_label or "X Axis")
        widget.setYRange(0, 1, padding=0)
        widget.showGrid(x=True, y=True, alpha=0.1)

    def _render_colormap_with(self, widget: pg.PlotWidget, spec: PlotSpec, cmap: pg.ColorMap) -> None:
        values = self._coerce_array(spec.y)
        if values.size == 0:
            return
        x_numeric = self._coerce_array(spec.x, fallback_range=True)
        x_numeric, values = self._downsample_1d(x_numeric, values, _MAX_1D_SAMPLES)
        rect = self._compute_rect(x_numeric, len(values))

        image = values.reshape(1, -1)
        image_item = pg.ImageItem()
        image_item.setImage(image, axisOrder="row-major")
        image_item.setRect(rect)
        image_item.setLookupTable(cmap.getLookupTable(alpha=False))
        levels = (float(np.nanmin(values)), float(np.nanmax(values)))
        image_item.setLevels(levels)
        widget.addItem(image_item)
        self._insert_colorbar(
            widget,
            pg.ColorBarItem(values=levels, colorMap=cmap),
            image_item=image_item,
            label=(spec.label or spec.y_label or "Intensity"),
        )

    def _render_eventline_with(self, widget: pg.PlotWidget, spec: PlotSpec, cmap: pg.ColorMap) -> None:
        x_numeric = self._coerce_array(spec.x, fallback_range=True)
        intensities = self._coerce_array(spec.y)
        if intensities.shape[0] != x_numeric.shape[0]:
            intensities = np.ones_like(x_numeric, dtype=float)

        if x_numeric.size == 0:
            return

        x_numeric, intensities = self._bin_events(x_numeric, intensities, _MAX_EVENT_BINS)
        if x_numeric.size == 0:
            return

        x_min = float(np.nanmin(x_numeric))
        x_max = float(np.nanmax(x_numeric))
        span = x_max - x_min if x_max != x_min else 1.0
        bar_width = max(span * 0.01, span / max(len(x_numeric) * 2, 1))

        lut = cmap.getLookupTable(nPts=512, alpha=False)
        levels = (float(np.nanmin(intensities)), float(np.nanmax(intensities)))
        if levels[0] == levels[1]:
            levels = (levels[0], levels[0] + 1e-9)
        scale = (intensities - levels[0]) / (levels[1] - levels[0])
        idx = np.clip((scale * (len(lut) - 1)).astype(int), 0, len(lut) - 1)
        colors = [pg.mkColor(lut[i]) for i in idx]

        bars = pg.BarGraphItem(x=x_numeric, height=np.ones_like(x_numeric), width=bar_width, brushes=colors, pens=colors)
        widget.addItem(bars)

        self._insert_colorbar(
            widget,
            pg.ColorBarItem(values=levels, colorMap=cmap),
            label=(spec.label or spec.y_label or "Intensity"),
        )
