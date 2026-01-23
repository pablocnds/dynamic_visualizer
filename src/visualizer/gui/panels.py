from __future__ import annotations

from typing import Callable, Dict, List, Tuple
from pathlib import Path

from PySide6 import QtWidgets
import pyqtgraph as pg

from visualizer.cards.models import SubcardDefinition
from visualizer.viz.renderer import PlotRenderer
from visualizer.viz.table_renderer import TableView


class PanelManager:
    """Manages creation and teardown of plot panels for multi-plot cards."""

    def __init__(self, renderer: PlotRenderer) -> None:
        self._renderer = renderer
        self._panel_widgets: List[QtWidgets.QWidget] = []
        self._panel_plots: List[pg.PlotWidget] = []
        self._panel_tables: List[QtWidgets.QTableView] = []
        self._panel_plot_by_name: Dict[str, pg.PlotWidget] = {}
        self._panel_table_by_name: Dict[str, QtWidgets.QTableView] = {}
        self._panel_title_by_name: Dict[str, QtWidgets.QLabel] = {}
        self._panel_order: List[str] = []
        self._panel_kind_by_name: Dict[str, str] = {}
        self._latest_panel_data: Dict[
            str, List[tuple[object | None, Path, str | None, str | None]]
        ] = {}
        self._synchronize_x = False

    def clear(self, layout: QtWidgets.QVBoxLayout) -> None:
        while layout.count():
            item = layout.takeAt(0)
            widget = item.widget()
            if widget:
                if isinstance(widget, pg.PlotWidget):
                    self._renderer.reset_widget(widget)
                widget.deleteLater()
        for plot in self._panel_plots:
            self._renderer.reset_widget(plot)
            plot.deleteLater()
        for table in self._panel_tables:
            table.deleteLater()
        self._panel_widgets.clear()
        self._panel_plots.clear()
        self._panel_tables.clear()
        self._panel_plot_by_name.clear()
        self._panel_table_by_name.clear()
        self._panel_title_by_name.clear()
        self._panel_order.clear()
        self._panel_kind_by_name.clear()
        self._latest_panel_data.clear()
        self._synchronize_x = False

    def build_panels(
        self,
        container_layout: QtWidgets.QVBoxLayout,
        panels: List[
            tuple[
                SubcardDefinition,
                List[tuple[object | None, Path, str | None, str | None]],
                List[Path],
                str,
            ]
        ],
        combo_factory: Callable[[str], QtWidgets.QWidget] | None = None,
        synchronize_x_axis: bool = False,
    ) -> Tuple[List[int], str | None]:
        self._synchronize_x = synchronize_x_axis
        stretches, warning = self._calculate_panel_stretches([p[0] for p in panels])
        ordered_names = [panel[0].name for panel in panels]
        for idx, ((subcard, entries, paths, panel_kind), stretch) in enumerate(zip(panels, stretches)):
            panel_widget = QtWidgets.QWidget()
            panel_layout = QtWidgets.QVBoxLayout(panel_widget)
            panel_layout.setContentsMargins(0, 4, 0, 4)
            if panel_kind == "table":
                table_widget = TableView()
                panel_layout.addWidget(table_widget)
                self._panel_tables.append(table_widget)
                self._panel_table_by_name[subcard.name] = table_widget
            else:
                plot_widget = pg.PlotWidget()
                panel_layout.addWidget(plot_widget)
                self._panel_plots.append(plot_widget)
                self._panel_plot_by_name[subcard.name] = plot_widget
            container_layout.addWidget(panel_widget, stretch)
            self._panel_widgets.append(panel_widget)
            self._latest_panel_data[subcard.name] = entries
            self._panel_kind_by_name[subcard.name] = panel_kind
            if panel_kind != "table":
                plot_widget.enableAutoRange(x=True, y=True)
            if idx < len(panels) - 1:
                separator = QtWidgets.QFrame()
                separator.setFrameShape(QtWidgets.QFrame.HLine)
                separator.setFrameShadow(QtWidgets.QFrame.Plain)
                separator.setLineWidth(1)
                separator.setFixedHeight(1)
                container_layout.addWidget(separator)
        self._panel_order = ordered_names
        if synchronize_x_axis:
            self.synchronize_x_axes()
        return stretches, warning

    def update_titles(self, panels: List[tuple[SubcardDefinition, list, List[Path], str]]) -> None:
        # titles removed from per-panel headers; no-op retained for compatibility
        return None

    def panel_plots(self) -> List[pg.PlotWidget]:
        return self._panel_plots

    def plot_by_name(self, name: str) -> pg.PlotWidget | None:
        return self._panel_plot_by_name.get(name)

    def table_by_name(self, name: str) -> QtWidgets.QTableView | None:
        return self._panel_table_by_name.get(name)

    def table_views(self) -> List[QtWidgets.QTableView]:
        return list(self._panel_tables)

    def latest_panel_data(self) -> Dict[str, List[tuple[object | None, Path, str | None, str | None]]]:
        return self._latest_panel_data

    def set_latest_panel_data(
        self, name: str, data: List[tuple[object | None, Path, str | None, str | None]]
    ) -> None:
        self._latest_panel_data[name] = data

    def panel_order(self) -> List[str]:
        return self._panel_order

    def panel_kind_by_name(self, name: str) -> str | None:
        return self._panel_kind_by_name.get(name)

    def synchronize_x_axes(self) -> None:
        if len(self._panel_plots) < 2:
            return
        master_vb = self._panel_plots[0].getPlotItem().getViewBox()
        for plot in self._panel_plots[1:]:
            try:
                plot.getPlotItem().setXLink(master_vb)
            except Exception:
                continue
        if self._synchronize_x:
            self._equalize_x_ranges()

    def _equalize_x_ranges(self) -> None:
        """Ensure all linked plots start with a common X range covering all data."""
        bounds: List[tuple[float, float]] = []
        for plot in self._panel_plots:
            x_bounds = self._extract_plot_x_bounds(plot)
            if x_bounds:
                bounds.append(x_bounds)
        if not bounds:
            return
        global_min = min(b[0] for b in bounds)
        global_max = max(b[1] for b in bounds)
        if global_min >= global_max:
            return
        padding = max((global_max - global_min) * 0.05, 0.0)
        for plot in self._panel_plots:
            try:
                plot.getPlotItem().setXRange(global_min - padding, global_max + padding, padding=0)
            except Exception:
                continue

    def _extract_plot_x_bounds(self, plot: pg.PlotWidget) -> tuple[float, float] | None:
        x_min = None
        x_max = None
        for item in plot.getPlotItem().items:
            try:
                rect = item.mapRectToParent(item.boundingRect())
                if rect.width() == 0:
                    continue
                left = float(rect.left())
                right = float(rect.right())
            except Exception:
                continue
            x_min = left if x_min is None else min(x_min, left)
            x_max = right if x_max is None else max(x_max, right)
        if x_min is None or x_max is None:
            try:
                vr = plot.getPlotItem().getViewBox().viewRange()[0]
                return float(vr[0]), float(vr[1])
            except Exception:
                return None
        return x_min, x_max

    def _calculate_panel_stretches(
        self, subcards: List[SubcardDefinition]
    ) -> tuple[List[int], str | None]:
        specified = [subcard.chart_height for subcard in subcards if subcard.chart_height]
        total_specified = sum(specified)
        warning: str | None = None
        if total_specified > 100:
            warning = "Subcard heights exceed 100%; clamping proportions."
        remaining = max(0.0, 100.0 - total_specified)
        unspecified = [subcard for subcard in subcards if not subcard.chart_height]
        default_height = (remaining / len(unspecified)) if unspecified and remaining > 0 else 0.0
        if not specified and not unspecified:
            default_height = 100.0
        stretches: List[int] = []
        for subcard in subcards:
            height = subcard.chart_height if subcard.chart_height else default_height
            if total_specified > 100 and subcard.chart_height:
                height = subcard.chart_height * (100.0 / total_specified)
            stretches.append(max(int(height) or 1, 1))
        if not any(stretches):
            stretches = [1 for _ in subcards]
        return stretches, warning

    def _format_panel_title(self, subcard: SubcardDefinition, paths: List[Path]) -> str:
        friendly = subcard.name.replace("_", " ").title()
        if not paths:
            return f"{friendly} – (no data)"
        if len(paths) == 1:
            return f"{friendly} – {paths[0].name}"
        return f"{friendly} – {paths[0].name} (+{len(paths) - 1} more)"
