from __future__ import annotations

from typing import Iterable

import pyqtgraph as pg
import numpy as np

from visualizer.interpretation.specs import PlotSpec, VisualizationType

_MAX_1D_SAMPLES = 10000
_MAX_EVENT_BINS = 800
_EVENT_BAR_WIDTH_PX = 2.0
_BACKGROUND_ALPHA = 90


class PlotRenderer:
    """Renders PlotSpec objects onto a PyQtGraph widget."""

    def __init__(self) -> None:
        pg.setConfigOption("background", "w")
        pg.setConfigOption("foreground", "k")
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
            widget.plot(
                spec.x,
                spec.y,
                pen=pg.mkPen(color=(50, 110, 240), width=2),
                symbol=None,
            )
        elif spec.visualization == VisualizationType.SCATTER:
            widget.plot(
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
        elif spec.visualization == VisualizationType.RANGE:
            self._render_range(widget, spec)
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
        one_dim_specs = [spec for spec in specs if self._is_one_dimensional(spec)]
        two_dim_specs = [spec for spec in specs if not self._is_one_dimensional(spec)]
        if len(specs) > 1 and one_dim_specs and not two_dim_specs:
            self._render_one_dimensional_overlay(widget, specs)
            return
        if one_dim_specs and two_dim_specs:
            self._render_mixed_overlay(widget, one_dim_specs, two_dim_specs)
            return
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
                widget.plot(
                    spec.x,
                    spec.y,
                    pen=pg.mkPen(color=color, width=2),
                    symbol=None,
                    name=label,
                )
            else:
                widget.plot(
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
        self._style_1d_plot(plot_item)
        values = self._coerce_array(spec.y)
        if values.size == 0:
            widget.setLabel("bottom", spec.x_label or "X Axis")
            widget.setLabel("left", spec.y_label or "Y Axis")
            widget.showGrid(x=True, y=True, alpha=0.2)
            return

        x_full = self._coerce_array(spec.x, fallback_range=True)
        target_bins = min(_MAX_1D_SAMPLES, max(1, values.size))
        x_numeric, values = self._resample_colormap(x_full, values, target_bins)
        rect = self._compute_rect(x_numeric, len(values))

        image = values.reshape(1, -1)
        image_item = pg.ImageItem()
        image_item.setImage(image, axisOrder="row-major")
        image_item.setRect(rect)
        cmap = pg.colormap.get("viridis")
        image_item.setLookupTable(cmap.getLookupTable(alpha=False))
        image_item.setLevels((float(np.nanmin(values)), float(np.nanmax(values))))
        widget.addItem(image_item)
        widget.setLabel("bottom", None)
        widget.setLabel("left", None)
        widget.setYRange(0, 1, padding=0)
        widget.showGrid(x=False, y=False)

    def _render_eventline(self, widget: pg.PlotWidget, spec: PlotSpec) -> None:
        widget.clear()
        self._clear_legend(widget)
        self._clear_colorbar(widget)
        plot_item = widget.getPlotItem()
        self._style_1d_plot(plot_item)

        x_numeric = self._coerce_array(spec.x, fallback_range=True)
        if x_numeric.size == 0:
            widget.setLabel("bottom", spec.x_label or "X Axis")
            widget.setYRange(0, 1, padding=0)
            return

        x_numeric = self._coerce_eventline_x(x_numeric, _MAX_EVENT_BINS)
        if x_numeric.size == 0:
            widget.setLabel("bottom", spec.x_label or "X Axis")
            widget.setYRange(0, 1, padding=0)
            return

        x_min = float(np.nanmin(x_numeric))
        x_max = float(np.nanmax(x_numeric))
        bars = pg.BarGraphItem(
            x=x_numeric,
            height=np.ones_like(x_numeric),
            width=1.0,
            brushes=[(0, 0, 0, 180)] * len(x_numeric),
            pens=[(0, 0, 0, 180)] * len(x_numeric),
        )
        plot_item.addItem(bars)
        self._set_event_bar_width(widget, bars, x_min, x_max)

        widget.setLabel("bottom", None)
        widget.setYRange(0, 1, padding=0)
        widget.showGrid(x=False, y=False)

    def _render_range(self, widget: pg.PlotWidget, spec: PlotSpec) -> None:
        widget.clear()
        self._clear_legend(widget)
        self._clear_colorbar(widget)
        plot_item = widget.getPlotItem()
        self._style_1d_plot(plot_item)

        ranges = list(spec.ranges or [])
        if not ranges:
            widget.setLabel("bottom", spec.x_label or "X Axis")
            widget.setYRange(0, 1, padding=0)
            return

        alpha = self._resolve_alpha(spec.style_params, fallback=120)
        colors = self._resolve_range_colors(len(ranges), spec.style_params, alpha)
        self._add_range_regions(plot_item, ranges, colors, z_value=0)

        widget.setLabel("bottom", None)
        widget.setYRange(0, 1, padding=0)
        widget.showGrid(x=False, y=False)

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
        return spec.visualization in {
            VisualizationType.COLORMAP,
            VisualizationType.EVENTLINE,
            VisualizationType.RANGE,
        }

    def _coerce_array(self, values, fallback_range: bool = False) -> np.ndarray:
        coerced: list[float] = []
        if values is None:
            return np.array([], dtype=float)
        for item in values:
            try:
                coerced.append(float(item))
            except Exception:
                coerced.append(np.nan)
        arr = np.asarray(coerced, dtype=float)
        if np.isnan(arr).all() and fallback_range:
            try:
                arr = np.arange(len(coerced), dtype=float)
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
            if not y_chunk.size:
                continue
            max_idx = int(np.nanargmax(np.abs(y_chunk)))
            ys.append(float(y_chunk[max_idx]))
            xs.append(float(x_chunk[max_idx]) if x_chunk.size else float(i))
        return np.asarray(xs, dtype=float), np.asarray(ys, dtype=float)

    def _compute_rect(self, x_numeric: np.ndarray, length: int) -> pg.QtCore.QRectF:
        valid = x_numeric[np.isfinite(x_numeric)]
        if valid.size and length:
            x_min = float(np.nanmin(valid))
            x_max = float(np.nanmax(valid))
            span = x_max - x_min
            if valid.size > 1 and span > 0:
                diffs = np.diff(np.sort(valid))
                diffs = diffs[diffs > 0]
                step = float(np.median(diffs)) if diffs.size else span / max(length - 1, 1)
            else:
                step = 1.0
            pad = step / 2.0
            width = span + 2 * pad if span > 0 else step
            return pg.QtCore.QRectF(x_min - pad, 0.0, width, 1.0)
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

    def _style_1d_plot(self, plot_item: pg.PlotItem) -> None:
        plot_item.hideAxis("left")
        plot_item.getAxis("left").setStyle(showValues=False)
        plot_item.hideAxis("bottom")
        axis = plot_item.getAxis("bottom")
        try:
            axis.setStyle(showValues=False, tickLength=0)
            axis.setPen(None)
            axis.setTextPen(None)
        except Exception:
            pass
        plot_item.showGrid(x=False, y=False)
        vb = plot_item.getViewBox()
        try:
            vb.setMouseEnabled(y=False)
            vb.setLimits(yMin=0.0, yMax=1.0, minYRange=1.0, maxYRange=1.0)
        except Exception:
            pass
        plot_item.setRange(yRange=(0, 1), padding=0)

    def _resample_colormap(
        self, x_numeric: np.ndarray, values: np.ndarray, target_bins: int
    ) -> tuple[np.ndarray, np.ndarray]:
        if x_numeric.size == 0 or values.size == 0:
            return x_numeric, values
        x_min = float(np.nanmin(x_numeric))
        x_max = float(np.nanmax(x_numeric))
        if not np.isfinite(x_min) or not np.isfinite(x_max) or x_min == x_max:
            return self._downsample_1d(x_numeric, values, target_bins)
        bins = np.linspace(x_min, x_max, target_bins + 1)
        idx = np.digitize(x_numeric, bins) - 1
        agg = np.zeros(target_bins, dtype=float)
        has_val = np.zeros(target_bins, dtype=bool)
        for val, bin_idx in zip(values, idx):
            if 0 <= bin_idx < target_bins:
                if not has_val[bin_idx] or abs(val) > abs(agg[bin_idx]):
                    agg[bin_idx] = val
                    has_val[bin_idx] = True
        centers = (bins[:-1] + bins[1:]) / 2.0
        return centers, agg

    def _coerce_eventline_x(self, x_numeric: np.ndarray, max_bins: int) -> np.ndarray:
        if x_numeric.size <= max_bins:
            return x_numeric
        x_min = float(np.nanmin(x_numeric))
        x_max = float(np.nanmax(x_numeric))
        if not np.isfinite(x_min) or not np.isfinite(x_max) or x_min == x_max:
            stride = int(np.ceil(x_numeric.size / max_bins))
            return x_numeric[::stride]
        bins = np.linspace(x_min, x_max, max_bins + 1)
        idx = np.digitize(x_numeric, bins) - 1
        centers = (bins[:-1] + bins[1:]) / 2.0
        seen = np.zeros(max_bins, dtype=bool)
        kept: list[float] = []
        for bin_idx in idx:
            if 0 <= bin_idx < max_bins and not seen[bin_idx]:
                kept.append(float(centers[bin_idx]))
                seen[bin_idx] = True
        return np.asarray(kept, dtype=float)

    def _set_event_bar_width(self, widget: pg.PlotWidget, bars: pg.BarGraphItem, x_min: float, x_max: float) -> None:
        vb = widget.getPlotItem().getViewBox()
        width = self._compute_event_bar_width(vb, x_min, x_max)
        try:
            bars.setOpts(width=width)
        except Exception:
            return

        def _on_range_changed(*_args, _bars=bars, _vb=vb) -> None:
            width_local = self._compute_event_bar_width(_vb, x_min, x_max)
            try:
                _bars.setOpts(width=width_local)
            except Exception:
                return

        try:
            vb.sigRangeChanged.connect(_on_range_changed)
        except Exception:
            pass

    def _compute_event_bar_width(self, view_box: pg.ViewBox, x_min: float, x_max: float) -> float:
        try:
            px_size = view_box.viewPixelSize()
            width_data = float(px_size[0]) * _EVENT_BAR_WIDTH_PX
            if width_data > 0:
                return width_data
        except Exception:
            pass
        span = x_max - x_min if x_max != x_min else 1.0
        return max(span * 0.001, span / 1000.0)

    def _render_one_dimensional_overlay(self, widget: pg.PlotWidget, specs: list[PlotSpec]) -> None:
        self._clear_legend(widget)
        self._clear_colorbar(widget)
        widget.clear()
        plot_item = widget.getPlotItem()
        self._style_1d_plot(plot_item)
        cmap_names = ["viridis", "plasma", "cividis", "magma", "turbo"]

        for idx, spec in enumerate(specs):
            cmap = pg.colormap.get(cmap_names[idx % len(cmap_names)])
            if spec.visualization == VisualizationType.COLORMAP:
                self._render_colormap_with(widget, spec, cmap)
            elif spec.visualization == VisualizationType.EVENTLINE:
                self._render_eventline_with(widget, spec, cmap)
            elif spec.visualization == VisualizationType.RANGE:
                self._render_range_with(widget, spec)

        widget.setLabel("bottom", None)
        widget.setYRange(0, 1, padding=0)
        widget.showGrid(x=False, y=False)

    def _render_colormap_with(self, widget: pg.PlotWidget, spec: PlotSpec, cmap: pg.ColorMap) -> None:
        values = self._coerce_array(spec.y)
        if values.size == 0:
            return
        x_numeric = self._coerce_array(spec.x, fallback_range=True)
        target_bins = min(_MAX_1D_SAMPLES, max(1, values.size))
        x_numeric, values = self._resample_colormap(x_numeric, values, target_bins)
        rect = self._compute_rect(x_numeric, len(values))

        image = values.reshape(1, -1)
        image_item = pg.ImageItem()
        image_item.setImage(image, axisOrder="row-major")
        image_item.setRect(rect)
        image_item.setLookupTable(cmap.getLookupTable(alpha=False))
        levels = (float(np.nanmin(values)), float(np.nanmax(values)))
        image_item.setLevels(levels)
        widget.addItem(image_item)

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

        lut = cmap.getLookupTable(nPts=512, alpha=False)
        levels = (float(np.nanmin(intensities)), float(np.nanmax(intensities)))
        if levels[0] == levels[1]:
            levels = (levels[0], levels[0] + 1e-9)
        scale = (intensities - levels[0]) / (levels[1] - levels[0])
        idx = np.clip((scale * (len(lut) - 1)).astype(int), 0, len(lut) - 1)
        colors = [pg.mkColor(lut[i]) for i in idx]

        bars = pg.BarGraphItem(x=x_numeric, height=np.ones_like(x_numeric), width=1.0, brushes=colors, pens=colors)
        widget.addItem(bars)
        self._set_event_bar_width(widget, bars, x_min, x_max)

    def _render_range_with(self, widget: pg.PlotWidget, spec: PlotSpec) -> None:
        ranges = list(spec.ranges or [])
        if not ranges:
            return
        alpha = self._resolve_alpha(spec.style_params, fallback=120)
        colors = self._resolve_range_colors(len(ranges), spec.style_params, alpha)
        plot_item = widget.getPlotItem()
        self._add_range_regions(plot_item, ranges, colors, z_value=0)

    def _render_mixed_overlay(
        self,
        widget: pg.PlotWidget,
        one_dim_specs: list[PlotSpec],
        two_dim_specs: list[PlotSpec],
    ) -> None:
        self._clear_legend(widget)
        widget.clear()
        plot_item = widget.getPlotItem()
        legend = widget.addLegend()
        legend.setParentItem(plot_item)
        legend.setBrush(pg.mkBrush(255, 255, 255, 220))
        legend.setPen(pg.mkPen(color=(30, 30, 30), width=1))
        legend.anchor(itemPos=(1, 0), parentPos=(1, 0), offset=(-10, 10))
        widget.legend = legend  # type: ignore[attr-defined]

        y_min, y_max = self._compute_y_bounds(two_dim_specs)
        for spec in one_dim_specs:
            self._render_one_dimensional_background(widget, plot_item, spec, y_min, y_max)

        for index, spec in enumerate(two_dim_specs):
            color = pg.intColor(index, hues=len(two_dim_specs) * 2)
            label = getattr(spec, "label", None) or spec.dataset_id
            if spec.visualization == VisualizationType.LINE:
                widget.plot(
                    spec.x,
                    spec.y,
                    pen=pg.mkPen(color=color, width=2),
                    symbol=None,
                    name=label,
                )
            else:
                widget.plot(
                    spec.x,
                    spec.y,
                    pen=None,
                    symbol="o",
                    symbolBrush=color,
                    symbolSize=6,
                    name=label,
                )

        first = two_dim_specs[0]
        widget.setLabel("bottom", first.x_label or "X Axis")
        widget.setLabel("left", first.y_label or "Y Axis")
        widget.showGrid(x=True, y=True, alpha=0.2)

    def _render_one_dimensional_background(
        self,
        widget: pg.PlotWidget,
        plot_item: pg.PlotItem,
        spec: PlotSpec,
        y_min: float,
        y_max: float,
    ) -> None:
        if spec.visualization == VisualizationType.COLORMAP:
            self._render_colormap_background(plot_item, spec, y_min, y_max)
            return
        if spec.visualization == VisualizationType.EVENTLINE:
            self._render_eventline_background(widget, plot_item, spec, y_min, y_max)
            return
        if spec.visualization == VisualizationType.RANGE:
            ranges = list(spec.ranges or [])
            if not ranges:
                return
            alpha = self._resolve_alpha(spec.style_params, fallback=_BACKGROUND_ALPHA)
            colors = self._resolve_range_colors(len(ranges), spec.style_params, alpha)
            self._add_range_regions(plot_item, ranges, colors, z_value=-20)

    def _render_colormap_background(
        self,
        plot_item: pg.PlotItem,
        spec: PlotSpec,
        y_min: float,
        y_max: float,
    ) -> None:
        values = self._coerce_array(spec.y)
        if values.size == 0:
            return
        x_numeric = self._coerce_array(spec.x, fallback_range=True)
        target_bins = min(_MAX_1D_SAMPLES, max(1, values.size))
        x_numeric, values = self._resample_colormap(x_numeric, values, target_bins)
        rect = self._compute_rect(x_numeric, len(values))
        y_span = y_max - y_min if y_max != y_min else 1.0
        rect = pg.QtCore.QRectF(rect.left(), y_min, rect.width(), y_span)

        image = values.reshape(1, -1)
        image_item = pg.ImageItem()
        image_item.setImage(image, axisOrder="row-major")
        image_item.setRect(rect)
        cmap = pg.colormap.get("viridis")
        lut = cmap.getLookupTable(nPts=512, alpha=True).copy()
        lut[:, 3] = _BACKGROUND_ALPHA
        image_item.setLookupTable(lut)
        image_item.setLevels((float(np.nanmin(values)), float(np.nanmax(values))))
        image_item.setZValue(-20)
        plot_item.addItem(image_item)
        self._bind_image_to_view_range(plot_item.getViewBox(), image_item, rect.left(), rect.width())

    def _render_eventline_background(
        self,
        widget: pg.PlotWidget,
        plot_item: pg.PlotItem,
        spec: PlotSpec,
        y_min: float,
        y_max: float,
    ) -> None:
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
        cmap = pg.colormap.get("viridis")
        lut = cmap.getLookupTable(nPts=512, alpha=True).copy()
        lut[:, 3] = _BACKGROUND_ALPHA
        levels = (float(np.nanmin(intensities)), float(np.nanmax(intensities)))
        if levels[0] == levels[1]:
            levels = (levels[0], levels[0] + 1e-9)
        scale = (intensities - levels[0]) / (levels[1] - levels[0])
        idx = np.clip((scale * (len(lut) - 1)).astype(int), 0, len(lut) - 1)
        colors = [pg.mkColor(lut[i]) for i in idx]
        y_span = y_max - y_min if y_max != y_min else 1.0

        bars = pg.BarGraphItem(
            x=x_numeric,
            y=y_min,
            height=y_span,
            width=1.0,
            brushes=colors,
            pens=colors,
        )
        bars.setZValue(-20)
        plot_item.addItem(bars)
        self._set_event_bar_width(widget, bars, x_min, x_max)
        self._bind_bars_to_view_range(plot_item.getViewBox(), bars)

    def _bind_image_to_view_range(
        self,
        view_box: pg.ViewBox,
        image_item: pg.ImageItem,
        x_left: float,
        width: float,
    ) -> None:
        def _on_range_changed(*_args) -> None:
            _, (y_min, y_max) = view_box.viewRange()
            y_span = y_max - y_min if y_max != y_min else 1.0
            image_item.setRect(pg.QtCore.QRectF(x_left, y_min, width, y_span))

        try:
            view_box.sigRangeChanged.connect(_on_range_changed)
        except Exception:
            pass

    def _bind_bars_to_view_range(self, view_box: pg.ViewBox, bars: pg.BarGraphItem) -> None:
        def _on_range_changed(*_args) -> None:
            _, (y_min, y_max) = view_box.viewRange()
            y_span = y_max - y_min if y_max != y_min else 1.0
            try:
                bars.setOpts(y=y_min, height=y_span)
            except Exception:
                return

        try:
            view_box.sigRangeChanged.connect(_on_range_changed)
        except Exception:
            pass

    def _compute_y_bounds(self, specs: list[PlotSpec]) -> tuple[float, float]:
        values: list[float] = []
        for spec in specs:
            y_numeric = self._coerce_array(spec.y)
            if y_numeric.size:
                finite = y_numeric[np.isfinite(y_numeric)]
                values.extend(finite.tolist())
        if not values:
            return 0.0, 1.0
        y_min = min(values)
        y_max = max(values)
        if y_min == y_max:
            y_max = y_min + 1.0
        return y_min, y_max

    def _resolve_alpha(self, style_params: dict | None, fallback: int) -> int:
        if not style_params:
            return fallback
        if "alpha" not in style_params:
            return fallback
        alpha = style_params.get("alpha")
        if isinstance(alpha, bool):
            return fallback
        if isinstance(alpha, (int, float)):
            value = float(alpha)
            if value <= 1.0:
                value = value * 255.0
            return int(max(0.0, min(255.0, value)))
        return fallback

    def _resolve_range_colors(
        self,
        count: int,
        style_params: dict | None,
        alpha: int,
    ) -> list[pg.QtGui.QColor]:
        if count <= 0:
            return []
        colors_value = None
        palette_name = None
        if style_params:
            colors_value = style_params.get("colors")
            palette_name = style_params.get("palette")

        colors: list[pg.QtGui.QColor] = []
        if colors_value and isinstance(colors_value, (list, tuple)):
            for value in colors_value:
                color = pg.mkColor(value)
                color.setAlpha(alpha)
                colors.append(color)
            if len(colors) < count:
                colors += [colors[-1]] * (count - len(colors))
        elif palette_name:
            try:
                cmap = pg.colormap.get(str(palette_name))
                lut = cmap.getLookupTable(nPts=count, alpha=False)
                for entry in lut:
                    color = pg.mkColor(entry)
                    color.setAlpha(alpha)
                    colors.append(color)
            except Exception:
                colors = []

        if not colors:
            for idx in range(count):
                color = pg.intColor(idx, hues=count * 2)
                color.setAlpha(alpha)
                colors.append(color)
        return colors[:count]

    def _add_range_regions(
        self,
        plot_item: pg.PlotItem,
        ranges: list[tuple[float, float]],
        colors: list[pg.QtGui.QColor],
        z_value: float,
    ) -> None:
        transparent_pen = pg.mkPen(color=(0, 0, 0, 0))
        for (start, end), color in zip(ranges, colors):
            region = pg.LinearRegionItem(
                values=(start, end),
                orientation="vertical",
                brush=pg.mkBrush(color),
                pen=transparent_pen,
                movable=False,
            )
            region.setZValue(z_value)
            plot_item.addItem(region)
