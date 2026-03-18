from __future__ import annotations

from typing import Iterable, Sequence

import pyqtgraph as pg
import numpy as np

from visualizer.interpretation.specs import PlotSpec, RenderInteraction, VisualizationType
from visualizer.viz.interactions import InteractionManager, ItemInteraction

_MAX_1D_SAMPLES = 10000
_MAX_EVENT_BINS = 800
_EVENT_BAR_WIDTH_PX = 2.0
_BACKGROUND_ALPHA = 90
_DEFAULT_SERIES_COLOR = (50, 110, 240)
_DEFAULT_SCATTER_ALPHA = 180
_DEFAULT_STICK_ALPHA = 220


class _TopAxisOverlay:
    def __init__(self, widget: pg.PlotWidget) -> None:
        self._widget = widget
        self._plot_item = widget.getPlotItem()
        self._view_box = self._plot_item.getViewBox()
        self._axis_helper = pg.AxisItem(orientation="top")
        self._items: list[pg.QtWidgets.QGraphicsItem] = []
        self._pen = pg.mkPen(color=(20, 20, 20, 160), width=1)
        self._outline_pen = pg.mkPen(color=(255, 255, 255, 160), width=3)
        self._text_color = pg.mkColor(20, 20, 20, 200)
        self._text_shadow_color = pg.mkColor(255, 255, 255, 160)
        self._font = pg.QtGui.QFont()
        self._font.setPointSize(9)
        self._tick_length = 6
        self._padding = 2
        self._label_padding = 2
        self._z_value = 50

    def clear(self) -> None:
        for item in self._items:
            try:
                if item.scene():
                    item.scene().removeItem(item)
            except Exception:
                pass
        self._items.clear()

    def set_colors(self, foreground: pg.QtGui.QColor, outline: pg.QtGui.QColor) -> None:
        fg = pg.mkColor(foreground)
        outline_color = pg.mkColor(outline)
        self._pen = pg.mkPen(fg, width=1)
        self._outline_pen = pg.mkPen(outline_color, width=3)
        self._text_color = pg.mkColor(fg)
        shadow = pg.mkColor(outline_color)
        shadow.setAlpha(min(180, shadow.alpha() + 20))
        self._text_shadow_color = shadow

    def update(self) -> None:
        self.clear()
        scene = self._plot_item.scene()
        if scene is None:
            return
        rect = self._view_box.sceneBoundingRect()
        if rect.width() <= 0 or rect.height() <= 0:
            return
        (x_min, x_max), _ = self._view_box.viewRange()
        if not np.isfinite(x_min) or not np.isfinite(x_max) or x_min == x_max:
            return
        tick_levels = self._axis_helper.tickValues(x_min, x_max, rect.width())
        if not tick_levels:
            return
        spacing, ticks = tick_levels[0]
        if not ticks:
            return
        labels = self._axis_helper.tickStrings(ticks, scale=1.0, spacing=spacing)
        y_top = rect.top() + self._padding
        tick_end = y_top + self._tick_length

        baseline_outline = pg.QtWidgets.QGraphicsLineItem(rect.left(), y_top, rect.right(), y_top)
        baseline_outline.setPen(self._outline_pen)
        baseline_outline.setZValue(self._z_value)
        scene.addItem(baseline_outline)
        self._items.append(baseline_outline)
        baseline = pg.QtWidgets.QGraphicsLineItem(rect.left(), y_top, rect.right(), y_top)
        baseline.setPen(self._pen)
        baseline.setZValue(self._z_value)
        scene.addItem(baseline)
        self._items.append(baseline)

        for tick, label in zip(ticks, labels):
            if not label:
                continue
            scene_point = self._view_box.mapViewToScene(pg.Point(tick, 0))
            x_scene = scene_point.x()
            if x_scene < rect.left() - 1 or x_scene > rect.right() + 1:
                continue
            line_outline = pg.QtWidgets.QGraphicsLineItem(x_scene, y_top, x_scene, tick_end)
            line_outline.setPen(self._outline_pen)
            line_outline.setZValue(self._z_value)
            scene.addItem(line_outline)
            line = pg.QtWidgets.QGraphicsLineItem(x_scene, y_top, x_scene, tick_end)
            line.setPen(self._pen)
            line.setZValue(self._z_value)
            scene.addItem(line)
            text = pg.TextItem(label, color=self._text_color, anchor=(0, 0))
            text.setFont(self._font)
            text_rect = text.boundingRect()
            text_x = x_scene - (text_rect.width() / 2.0)
            text_y = tick_end + self._label_padding

            shadow = pg.TextItem(label, color=self._text_shadow_color, anchor=(0, 0))
            shadow.setFont(self._font)
            shadow.setPos(text_x + 1, text_y + 1)
            shadow.setZValue(self._z_value - 1)
            scene.addItem(shadow)

            text.setPos(text_x, text_y)
            text.setZValue(self._z_value)
            scene.addItem(text)
            self._items.extend([line_outline, line, shadow, text])


class PlotRenderer:
    """Renders PlotSpec objects onto a PyQtGraph widget."""

    def __init__(self) -> None:
        pg.setConfigOption("background", "w")
        pg.setConfigOption("foreground", "k")
        self._colorbars: dict[int, list[pg.ColorBarItem]] = {}
        self._axis_overlays: dict[int, _TopAxisOverlay] = {}
        self._interaction_manager = InteractionManager()

    def render(
        self,
        widget: pg.PlotWidget,
        spec: PlotSpec,
        show_x_axis: bool | None = None,
        show_y_axis: bool | None = None,
    ) -> None:
        self._interaction_manager.clear_widget(widget)
        self._clear_viewbox_handlers(widget)
        self._clear_legend(widget)
        self._clear_colorbar(widget)
        self._clear_axis_overlay(widget)
        widget.clear()
        plot_item = widget.getPlotItem()
        plot_item.showAxis("left")
        plot_item.getAxis("left").setStyle(showValues=True)
        plot_item.showAxis("bottom")

        if spec.visualization == VisualizationType.EVENTLINE:
            self._render_eventline(widget, spec, show_axis=show_x_axis)
            return
        elif spec.visualization == VisualizationType.RANGE:
            self._render_range(widget, spec, show_axis=show_x_axis)
            return
        elif spec.visualization == VisualizationType.COLORMAP:
            self._render_colormap(widget, spec, show_axis=show_x_axis)
            return
        self._render_two_dimensional_series(
            widget,
            spec,
            color=pg.mkColor(_DEFAULT_SERIES_COLOR),
        )
        widget.setLabel("bottom", spec.x_label or "X Axis")
        widget.setLabel("left", spec.y_label or "Y Axis")
        widget.showGrid(x=True, y=True, alpha=0.2)
        self._apply_axis_visibility(
            plot_item,
            show_x_axis,
            show_y_axis,
            spec.x_label or "X Axis",
            spec.y_label or "Y Axis",
        )
        # Single-spec legend is optional; only add when multiple

    def render_multiple(
        self,
        widget: pg.PlotWidget,
        specs: Iterable[PlotSpec],
        show_x_axis: bool | None = None,
        show_y_axis: bool | None = None,
    ) -> None:
        specs = list(specs)
        self._interaction_manager.clear_widget(widget)
        self._clear_viewbox_handlers(widget)
        if not specs:
            widget.clear()
            return
        self._clear_colorbar(widget)
        self._clear_axis_overlay(widget)
        one_dim_specs = [spec for spec in specs if self._is_one_dimensional(spec)]
        two_dim_specs = [spec for spec in specs if not self._is_one_dimensional(spec)]
        if len(specs) > 1 and one_dim_specs and not two_dim_specs:
            self._render_one_dimensional_overlay(widget, specs, show_axis=show_x_axis)
            return
        if one_dim_specs and two_dim_specs:
            self._clear_axis_overlay(widget)
            self._render_mixed_overlay(
                widget,
                one_dim_specs,
                two_dim_specs,
                show_x_axis=show_x_axis,
                show_y_axis=show_y_axis,
            )
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
            self._render_two_dimensional_series(widget, spec, color=color, name=label)
        first = specs[0]
        widget.setLabel("bottom", first.x_label or "X Axis")
        widget.setLabel("left", first.y_label or "Y Axis")
        widget.showGrid(x=True, y=True, alpha=0.2)
        self._apply_axis_visibility(
            widget.getPlotItem(),
            show_x_axis,
            show_y_axis,
            first.x_label or "X Axis",
            first.y_label or "Y Axis",
        )

    def _clear_legend(self, widget: pg.PlotWidget) -> None:
        legend = getattr(widget, "legend", None)
        if legend and legend.scene():
            legend.scene().removeItem(legend)
        if hasattr(widget, "legend"):
            widget.legend = None  # type: ignore[attr-defined]

    def reset_widget(self, widget: pg.PlotWidget) -> None:
        self._interaction_manager.clear_widget(widget)
        self._clear_legend(widget)
        self._clear_colorbar(widget)
        self._clear_viewbox_handlers(widget)
        self._clear_axis_overlay(widget)
        widget.clear()
        try:
            widget.enableAutoRange(x=True, y=True)
        except Exception:
            pass

    def apply_axis_visibility(
        self, widget: pg.PlotWidget, show_x_axis: bool | None, show_y_axis: bool | None
    ) -> None:
        plot_item = widget.getPlotItem()
        self._apply_axis_visibility(plot_item, show_x_axis, show_y_axis, None, None)

    def clear_colorbars(self, widget: pg.PlotWidget) -> None:
        self._clear_colorbar(widget)

    def _render_colormap(self, widget: pg.PlotWidget, spec: PlotSpec, show_axis: bool | None) -> None:
        widget.clear()
        self._clear_legend(widget)
        self._clear_colorbar(widget)
        self._clear_axis_overlay(widget)
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
        cmap = self._resolve_colormap(spec.style_params, fallback_name="viridis")
        alpha = self._resolve_alpha(spec.style_params, fallback=255)
        lut = self._colormap_lookup_table(
            cmap,
            npts=512,
            alpha=alpha,
            reverse=self._style_reverse_enabled(spec.style_params),
        )
        image_item.setLookupTable(lut)
        image_item.setLevels((float(np.nanmin(values)), float(np.nanmax(values))))
        widget.addItem(image_item)
        widget.setLabel("bottom", None)
        widget.setLabel("left", None)
        widget.setYRange(0, 1, padding=0)
        widget.showGrid(x=False, y=False)
        if show_axis is not False:
            axis_colors = self._axis_colors_for_base_colors([self._color_from_cmap(cmap, 0.5)])
            self._ensure_top_axis_overlay(widget, axis_colors)

    def _render_eventline(self, widget: pg.PlotWidget, spec: PlotSpec, show_axis: bool | None) -> None:
        widget.clear()
        self._clear_legend(widget)
        self._clear_colorbar(widget)
        self._clear_axis_overlay(widget)
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
        event_color = self._resolve_eventline_color(
            spec.style_params,
            fallback_color=pg.mkColor(0, 0, 0),
            fallback_alpha=180,
        )
        colors = [event_color] * len(x_numeric)
        bars = pg.BarGraphItem(
            x=x_numeric,
            height=np.ones_like(x_numeric),
            width=1.0,
            brushes=colors,
            pens=colors,
        )
        plot_item.addItem(bars)
        self._set_event_bar_width(widget, bars, x_min, x_max)

        widget.setLabel("bottom", None)
        widget.setYRange(0, 1, padding=0)
        widget.showGrid(x=False, y=False)
        if show_axis is not False:
            axis_colors = self._axis_colors_for_base_colors([event_color])
            self._ensure_top_axis_overlay(widget, axis_colors)

    def _render_range(self, widget: pg.PlotWidget, spec: PlotSpec, show_axis: bool | None) -> None:
        widget.clear()
        self._clear_legend(widget)
        self._clear_colorbar(widget)
        self._clear_axis_overlay(widget)
        plot_item = widget.getPlotItem()
        self._style_1d_plot(plot_item)

        ranges = list(spec.ranges or [])
        if not ranges:
            widget.setLabel("bottom", spec.x_label or "X Axis")
            widget.setYRange(0, 1, padding=0)
            return

        alpha = self._resolve_alpha(spec.style_params, fallback=120)
        colors = self._resolve_range_colors(len(ranges), spec.style_params, alpha)
        self._add_range_regions(
            widget,
            plot_item,
            ranges,
            colors,
            z_value=0,
            interactions=spec.interactions,
        )

        widget.setLabel("bottom", None)
        widget.setYRange(0, 1, padding=0)
        widget.showGrid(x=False, y=False)
        if show_axis is not False:
            axis_colors = self._axis_colors_for_base_colors(colors)
            self._ensure_top_axis_overlay(widget, axis_colors)

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

    def _clear_axis_overlay(self, widget: pg.PlotWidget) -> None:
        overlay = self._axis_overlays.pop(id(widget), None)
        if overlay:
            overlay.clear()

    def _ensure_top_axis_overlay(
        self, widget: pg.PlotWidget, axis_colors: tuple[pg.QtGui.QColor, pg.QtGui.QColor]
    ) -> None:
        overlay = self._axis_overlays.get(id(widget))
        if overlay is None:
            overlay = _TopAxisOverlay(widget)
            self._axis_overlays[id(widget)] = overlay
        overlay.set_colors(*axis_colors)
        overlay.update()

        view_box = widget.getPlotItem().getViewBox()

        def _on_view_changed(*_args, _overlay=overlay) -> None:
            _overlay.update()

        try:
            view_box.sigRangeChanged.connect(_on_view_changed)
            self._register_viewbox_handler(view_box, _on_view_changed)
        except Exception:
            pass
        try:
            view_box.sigResized.connect(_on_view_changed)
            self._register_viewbox_handler(view_box, _on_view_changed, signal="resize")
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

    def _render_two_dimensional_series(
        self,
        widget: pg.PlotWidget,
        spec: PlotSpec,
        color: pg.QtGui.QColor,
        name: str | None = None,
    ) -> None:
        if spec.visualization == VisualizationType.LINE:
            pen_color = self._resolve_series_color(spec.style_params, color, fallback_alpha=255)
            line_width = self._resolve_line_width(spec.style_params, fallback=2.0)
            kwargs = {"name": name} if name else {}
            widget.plot(
                spec.x,
                spec.y,
                pen=pg.mkPen(color=pen_color, width=line_width),
                symbol=None,
                **kwargs,
            )
            return
        if spec.visualization == VisualizationType.SCATTER:
            brush_color = self._resolve_series_color(
                spec.style_params,
                color,
                fallback_alpha=_DEFAULT_SCATTER_ALPHA,
            )
            marker_size = self._resolve_marker_size(spec.style_params, fallback=6.0)
            kwargs = {"name": name} if name else {}
            widget.plot(
                spec.x,
                spec.y,
                pen=None,
                symbol="o",
                symbolBrush=brush_color,
                symbolSize=marker_size,
                **kwargs,
            )
            return
        if spec.visualization == VisualizationType.STICK:
            self._render_stick_series(widget, spec, color=color, name=name)
            return
        raise ValueError(f"Unsupported two-dimensional visualization type: {spec.visualization.value}")

    def _render_stick_series(
        self,
        widget: pg.PlotWidget,
        spec: PlotSpec,
        color: pg.QtGui.QColor,
        name: str | None = None,
    ) -> None:
        x_numeric = self._coerce_array(spec.x, fallback_range=True)
        y_numeric = self._coerce_array(spec.y)
        if x_numeric.size == 0 or y_numeric.size == 0:
            return
        count = min(x_numeric.size, y_numeric.size)
        x_values = x_numeric[:count]
        y_values = y_numeric[:count]
        valid = np.isfinite(x_values) & np.isfinite(y_values)
        if not np.any(valid):
            return
        x_values = x_values[valid]
        y_values = y_values[valid]
        x_pairs = np.repeat(x_values, 2)
        y_pairs = np.empty(x_pairs.size, dtype=float)
        y_pairs[0::2] = 0.0
        y_pairs[1::2] = y_values

        pen_color = self._resolve_series_color(
            spec.style_params,
            color,
            fallback_alpha=_DEFAULT_STICK_ALPHA,
        )
        line_width = self._resolve_line_width(spec.style_params, fallback=1.0)
        kwargs = {"name": name} if name else {}
        widget.plot(
            x_pairs,
            y_pairs,
            pen=pg.mkPen(color=pen_color, width=line_width),
            connect="pairs",
            symbol=None,
            **kwargs,
        )

    def _resolve_series_color(
        self,
        style_params: dict | None,
        fallback_color: pg.QtGui.QColor | tuple[int, int, int] | tuple[int, int, int, int],
        fallback_alpha: int,
    ) -> pg.QtGui.QColor:
        color = pg.mkColor(fallback_color)
        color.setAlpha(max(0, min(255, int(fallback_alpha))))
        if style_params and "color" in style_params:
            try:
                color = pg.mkColor(style_params.get("color"))
            except Exception:
                pass
        alpha = self._resolve_alpha(style_params, fallback=color.alpha())
        color.setAlpha(alpha)
        return color

    def _resolve_line_width(self, style_params: dict | None, fallback: float) -> float:
        if not style_params:
            return fallback
        for key in ("line_width", "width"):
            width = self._coerce_positive_float(style_params.get(key))
            if width is not None:
                return width
        return fallback

    def _resolve_marker_size(self, style_params: dict | None, fallback: float) -> float:
        if not style_params:
            return fallback
        for key in ("marker_size", "size"):
            size = self._coerce_positive_float(style_params.get(key))
            if size is not None:
                return size
        return fallback

    @staticmethod
    def _coerce_positive_float(value: object | None) -> float | None:
        if isinstance(value, bool) or value is None:
            return None
        if isinstance(value, (int, float)):
            numeric = float(value)
        else:
            try:
                numeric = float(str(value))
            except (TypeError, ValueError):
                return None
        if numeric <= 0:
            return None
        return numeric

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
        left_axis = plot_item.getAxis("left")
        left_axis.setStyle(showValues=False)
        try:
            left_axis.setWidth(0)
            left_axis.setTicks([])
        except Exception:
            pass
        plot_item.hideAxis("bottom")
        axis = plot_item.getAxis("bottom")
        try:
            axis.setStyle(showValues=False, tickLength=0)
            axis.setPen(None)
            axis.setTextPen(None)
            axis.setHeight(0)
            axis.setTicks([])
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
            self._register_viewbox_handler(vb, _on_range_changed)
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

    def _render_one_dimensional_overlay(
        self, widget: pg.PlotWidget, specs: list[PlotSpec], show_axis: bool | None
    ) -> None:
        self._clear_legend(widget)
        self._clear_colorbar(widget)
        self._clear_axis_overlay(widget)
        widget.clear()
        plot_item = widget.getPlotItem()
        self._style_1d_plot(plot_item)
        cmap_names = ["viridis", "plasma", "cividis", "magma", "turbo"]
        base_colors: list[pg.QtGui.QColor] = []

        for idx, spec in enumerate(specs):
            cmap = pg.colormap.get(cmap_names[idx % len(cmap_names)])
            resolved_cmap = self._resolve_colormap(spec.style_params, fallback=cmap)
            if spec.visualization == VisualizationType.COLORMAP:
                self._render_colormap_with(widget, spec, resolved_cmap)
                base_colors.append(
                    self._color_from_cmap(
                        resolved_cmap,
                        0.5,
                        reverse=self._style_reverse_enabled(spec.style_params),
                    )
                )
            elif spec.visualization == VisualizationType.EVENTLINE:
                event_color = self._render_eventline_with(widget, spec, resolved_cmap)
                base_colors.append(event_color)
            elif spec.visualization == VisualizationType.RANGE:
                colors = self._render_range_with(widget, spec)
                if colors:
                    base_colors.extend(colors)

        widget.setLabel("bottom", None)
        widget.setYRange(0, 1, padding=0)
        widget.showGrid(x=False, y=False)
        if show_axis is not False:
            axis_colors = self._axis_colors_for_base_colors(base_colors)
            self._ensure_top_axis_overlay(widget, axis_colors)

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
        alpha = self._resolve_alpha(spec.style_params, fallback=255)
        lut = self._colormap_lookup_table(
            cmap,
            npts=512,
            alpha=alpha,
            reverse=self._style_reverse_enabled(spec.style_params),
        )
        image_item.setLookupTable(lut)
        levels = (float(np.nanmin(values)), float(np.nanmax(values)))
        image_item.setLevels(levels)
        widget.addItem(image_item)

    def _render_eventline_with(
        self, widget: pg.PlotWidget, spec: PlotSpec, cmap: pg.ColorMap
    ) -> pg.QtGui.QColor:
        reverse = self._style_reverse_enabled(spec.style_params)
        x_numeric = self._coerce_array(spec.x, fallback_range=True)
        if x_numeric.size == 0:
            return self._eventline_color(cmap, alpha=180, reverse=reverse)

        x_numeric = self._coerce_eventline_x(x_numeric, _MAX_EVENT_BINS)
        if x_numeric.size == 0:
            return self._eventline_color(cmap, alpha=180, reverse=reverse)

        x_min = float(np.nanmin(x_numeric))
        x_max = float(np.nanmax(x_numeric))

        fallback_color = self._eventline_color(cmap, alpha=180, reverse=reverse)
        color = self._resolve_eventline_color(
            spec.style_params,
            fallback_color=fallback_color,
            fallback_alpha=fallback_color.alpha(),
        )
        colors = [color] * len(x_numeric)
        bars = pg.BarGraphItem(
            x=x_numeric,
            height=np.ones_like(x_numeric),
            width=1.0,
            brushes=colors,
            pens=colors,
        )
        widget.addItem(bars)
        self._set_event_bar_width(widget, bars, x_min, x_max)
        return color

    def _render_range_with(self, widget: pg.PlotWidget, spec: PlotSpec) -> list[pg.QtGui.QColor]:
        ranges = list(spec.ranges or [])
        if not ranges:
            return []
        alpha = self._resolve_alpha(spec.style_params, fallback=120)
        colors = self._resolve_range_colors(len(ranges), spec.style_params, alpha)
        plot_item = widget.getPlotItem()
        self._add_range_regions(
            widget,
            plot_item,
            ranges,
            colors,
            z_value=0,
            interactions=spec.interactions,
        )
        return colors

    def _render_mixed_overlay(
        self,
        widget: pg.PlotWidget,
        one_dim_specs: list[PlotSpec],
        two_dim_specs: list[PlotSpec],
        show_x_axis: bool | None,
        show_y_axis: bool | None,
    ) -> None:
        self._clear_legend(widget)
        self._clear_axis_overlay(widget)
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
            self._render_two_dimensional_series(widget, spec, color=color, name=label)

        first = two_dim_specs[0]
        widget.setLabel("bottom", first.x_label or "X Axis")
        widget.setLabel("left", first.y_label or "Y Axis")
        widget.showGrid(x=True, y=True, alpha=0.2)
        self._apply_axis_visibility(
            plot_item,
            show_x_axis,
            show_y_axis,
            first.x_label or "X Axis",
            first.y_label or "Y Axis",
        )

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
            self._add_range_regions(
                widget,
                plot_item,
                ranges,
                colors,
                z_value=-20,
                interactions=spec.interactions,
            )

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
        cmap = self._resolve_colormap(spec.style_params, fallback_name="viridis")
        alpha = self._resolve_alpha(spec.style_params, fallback=_BACKGROUND_ALPHA)
        lut = self._colormap_lookup_table(
            cmap,
            npts=512,
            alpha=alpha,
            reverse=self._style_reverse_enabled(spec.style_params),
        )
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
        if x_numeric.size == 0:
            return

        x_numeric = self._coerce_eventline_x(x_numeric, _MAX_EVENT_BINS)
        if x_numeric.size == 0:
            return

        x_min = float(np.nanmin(x_numeric))
        x_max = float(np.nanmax(x_numeric))
        cmap = self._resolve_colormap(spec.style_params, fallback_name="viridis")
        fallback_color = self._eventline_color(
            cmap,
            alpha=_BACKGROUND_ALPHA,
            reverse=self._style_reverse_enabled(spec.style_params),
        )
        color = self._resolve_eventline_color(
            spec.style_params,
            fallback_color=fallback_color,
            fallback_alpha=_BACKGROUND_ALPHA,
        )
        colors = [color] * len(x_numeric)
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

    def _eventline_color(
        self, cmap: pg.ColorMap, alpha: int, *, reverse: bool = False
    ) -> pg.QtGui.QColor:
        lut = self._colormap_lookup_table(cmap, npts=2, alpha=alpha, reverse=reverse)
        color = pg.mkColor(lut[-1])
        color.setAlpha(alpha)
        return color

    def _resolve_colormap(
        self,
        style_params: dict | None,
        *,
        fallback_name: str = "viridis",
        fallback: pg.ColorMap | None = None,
    ) -> pg.ColorMap:
        if style_params and "palette" in style_params:
            palette_name = style_params.get("palette")
            if palette_name is not None:
                try:
                    return pg.colormap.get(str(palette_name))
                except Exception:
                    pass
        if fallback is not None:
            return fallback
        return pg.colormap.get(fallback_name)

    def _resolve_eventline_color(
        self,
        style_params: dict | None,
        *,
        fallback_color: pg.QtGui.QColor,
        fallback_alpha: int,
    ) -> pg.QtGui.QColor:
        color = pg.mkColor(fallback_color)
        if style_params and "color" in style_params:
            try:
                color = pg.mkColor(style_params.get("color"))
            except Exception:
                pass
        elif style_params and "palette" in style_params:
            palette_name = style_params.get("palette")
            if palette_name is not None:
                try:
                    cmap = pg.colormap.get(str(palette_name))
                    color = self._eventline_color(
                        cmap,
                        alpha=fallback_alpha,
                        reverse=self._style_reverse_enabled(style_params),
                    )
                except Exception:
                    pass
        alpha = self._resolve_alpha(style_params, fallback=fallback_alpha)
        color.setAlpha(alpha)
        return color

    @staticmethod
    def _style_reverse_enabled(style_params: dict | None) -> bool:
        if not style_params:
            return False
        reverse = style_params.get("reverse")
        return reverse if isinstance(reverse, bool) else False

    def _colormap_lookup_table(
        self,
        cmap: pg.ColorMap,
        *,
        npts: int,
        alpha: int,
        reverse: bool = False,
    ) -> np.ndarray:
        lut = cmap.getLookupTable(nPts=npts, alpha=True).copy()
        if reverse:
            lut = lut[::-1].copy()
        lut[:, 3] = alpha
        return lut

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
            self._register_viewbox_handler(view_box, _on_range_changed)
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
            self._register_viewbox_handler(view_box, _on_range_changed)
        except Exception:
            pass

    def _clear_viewbox_handlers(self, widget: pg.PlotWidget) -> None:
        try:
            view_box = widget.getPlotItem().getViewBox()
        except Exception:
            return
        handlers = getattr(view_box, "_range_handlers", None)
        if not handlers:
            return
        for entry in list(handlers):
            if isinstance(entry, tuple) and len(entry) == 2:
                signal_name, handler = entry
            else:
                signal_name, handler = "range", entry
            try:
                if signal_name == "resize":
                    view_box.sigResized.disconnect(handler)
                else:
                    view_box.sigRangeChanged.disconnect(handler)
            except Exception:
                continue
        view_box._range_handlers = []  # type: ignore[attr-defined]

    @staticmethod
    def _register_viewbox_handler(view_box: pg.ViewBox, handler, signal: str = "range") -> None:
        handlers = getattr(view_box, "_range_handlers", None)
        if handlers is None:
            handlers = []
            view_box._range_handlers = handlers  # type: ignore[attr-defined]
        handlers.append((signal, handler))

    @staticmethod
    def _color_from_cmap(
        cmap: pg.ColorMap, position: float, *, reverse: bool = False
    ) -> pg.QtGui.QColor:
        position = max(0.0, min(1.0, float(position)))
        lut = cmap.getLookupTable(nPts=256, alpha=True)
        if reverse:
            lut = lut[::-1]
        idx = int(position * (len(lut) - 1))
        return pg.mkColor(lut[idx])

    @staticmethod
    def _average_colors(colors: list[pg.QtGui.QColor]) -> pg.QtGui.QColor:
        if not colors:
            return pg.mkColor(255, 255, 255, 255)
        total_r = total_g = total_b = total_a = 0.0
        for color in colors:
            c = pg.mkColor(color)
            total_r += c.red()
            total_g += c.green()
            total_b += c.blue()
            total_a += c.alpha()
        count = float(len(colors))
        return pg.mkColor(
            int(total_r / count),
            int(total_g / count),
            int(total_b / count),
            int(total_a / count) if total_a else 255,
        )

    def _axis_colors_for_base_colors(
        self, base_colors: list[pg.QtGui.QColor]
    ) -> tuple[pg.QtGui.QColor, pg.QtGui.QColor]:
        background = self._average_colors(base_colors)
        return self._contrast_axis_colors(background)

    @staticmethod
    def _contrast_axis_colors(
        background: pg.QtGui.QColor,
    ) -> tuple[pg.QtGui.QColor, pg.QtGui.QColor]:
        bg = pg.mkColor(background)
        luminance = 0.299 * bg.red() + 0.587 * bg.green() + 0.114 * bg.blue()
        if luminance < 140:
            foreground = pg.mkColor(245, 245, 245, 200)
            outline = pg.mkColor(10, 10, 10, 160)
        else:
            foreground = pg.mkColor(20, 20, 20, 200)
            outline = pg.mkColor(255, 255, 255, 160)
        return foreground, outline

    def _apply_axis_visibility(
        self,
        plot_item: pg.PlotItem,
        show_x_axis: bool | None,
        show_y_axis: bool | None,
        x_label: str | None,
        y_label: str | None,
    ) -> None:
        if show_x_axis is not None:
            self._set_axis_visible(plot_item, "bottom", show_x_axis)
            if not show_x_axis:
                plot_item.setLabel("bottom", None)
            elif x_label is not None:
                plot_item.setLabel("bottom", x_label)
        if show_y_axis is not None:
            self._set_axis_visible(plot_item, "left", show_y_axis)
            if not show_y_axis:
                plot_item.setLabel("left", None)
            elif y_label is not None:
                plot_item.setLabel("left", y_label)

    @staticmethod
    def _set_axis_visible(plot_item: pg.PlotItem, axis_name: str, visible: bool) -> None:
        axis = plot_item.getAxis(axis_name)
        if visible:
            plot_item.showAxis(axis_name, show=True)
            try:
                axis.setStyle(showValues=True)
                axis.setPen(axis.textPen())
                axis.setTextPen(axis.textPen())
                axis.setTicks(None)
                if axis_name == "bottom":
                    axis.setHeight(None)
                elif axis_name == "left":
                    axis.setWidth(None)
            except Exception:
                pass
            return
        plot_item.showAxis(axis_name, show=False)
        try:
            axis.setStyle(showValues=False, tickLength=0)
            axis.setPen(None)
            axis.setTextPen(None)
            axis.setTicks([])
            if axis_name == "bottom":
                axis.setHeight(0)
            elif axis_name == "left":
                axis.setWidth(0)
        except Exception:
            pass

    def _compute_y_bounds(self, specs: list[PlotSpec]) -> tuple[float, float]:
        values: list[float] = []
        for spec in specs:
            if spec.visualization == VisualizationType.STICK:
                values.append(0.0)
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
        reverse = self._style_reverse_enabled(style_params)

        colors: list[pg.QtGui.QColor] = []
        if colors_value and isinstance(colors_value, (list, tuple)):
            values = list(colors_value)
            if reverse:
                values.reverse()
            for value in values:
                color = pg.mkColor(value)
                color.setAlpha(alpha)
                colors.append(color)
            if len(colors) < count:
                colors += [colors[-1]] * (count - len(colors))
        elif palette_name:
            try:
                cmap = pg.colormap.get(str(palette_name))
                lut = cmap.getLookupTable(nPts=count, alpha=False)
                if reverse:
                    lut = lut[::-1]
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
            if reverse:
                colors.reverse()
        return colors[:count]

    def _add_range_regions(
        self,
        widget: pg.PlotWidget,
        plot_item: pg.PlotItem,
        ranges: list[tuple[float, float]],
        colors: list[pg.QtGui.QColor],
        z_value: float,
        interactions: Sequence[RenderInteraction] | None = None,
    ) -> None:
        transparent_pen = pg.mkPen(color=(0, 0, 0, 0))
        for index, ((start, end), color) in enumerate(zip(ranges, colors)):
            region = pg.LinearRegionItem(
                values=(start, end),
                orientation="vertical",
                brush=pg.mkBrush(color),
                pen=transparent_pen,
                movable=False,
            )
            region.setZValue(z_value)
            plot_item.addItem(region)
            interaction = None
            if interactions and index < len(interactions):
                interaction = ItemInteraction(hover_text=interactions[index].hover_text)
            self._interaction_manager.bind_item(widget, region, interaction)
