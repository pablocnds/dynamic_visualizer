from __future__ import annotations

from typing import Callable, Dict, List, Tuple
from pathlib import Path

from PySide6 import QtWidgets
import pyqtgraph as pg

from visualizer.cards.models import SubcardDefinition
from visualizer.interpretation.specs import VisualizationType
from visualizer.viz.renderer import PlotRenderer


class PanelManager:
    """Manages creation and teardown of plot panels for multi-plot cards."""

    def __init__(self, renderer: PlotRenderer) -> None:
        self._renderer = renderer
        self._panel_widgets: List[QtWidgets.QWidget] = []
        self._panel_plots: List[pg.PlotWidget] = []
        self._panel_plot_by_name: Dict[str, pg.PlotWidget] = {}
        self._panel_title_by_name: Dict[str, QtWidgets.QLabel] = {}
        self._panel_order: List[str] = []
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
        self._panel_widgets.clear()
        self._panel_plots.clear()
        self._panel_plot_by_name.clear()
        self._panel_title_by_name.clear()
        self._panel_order.clear()
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
            ]
        ],
        combo_factory: Callable[[str], QtWidgets.QWidget] | None = None,
        synchronize_x_axis: bool = False,
    ) -> Tuple[List[int], str | None]:
        self._synchronize_x = synchronize_x_axis
        stretches, warning = self._calculate_panel_stretches([p[0] for p in panels])
        ordered_names = [panel[0].name for panel in panels]
        for idx, ((subcard, entries, paths), stretch) in enumerate(zip(panels, stretches)):
            panel_widget = QtWidgets.QWidget()
            panel_layout = QtWidgets.QVBoxLayout(panel_widget)
            plot_widget = pg.PlotWidget()
            panel_layout.addWidget(plot_widget)
            container_layout.addWidget(panel_widget, stretch)
            self._panel_widgets.append(panel_widget)
            self._panel_plots.append(plot_widget)
            self._panel_plot_by_name[subcard.name] = plot_widget
            self._latest_panel_data[subcard.name] = entries
            plot_widget.enableAutoRange(x=True, y=True)
            if synchronize_x_axis and idx < len(panels) - 1:
                plot_widget.showAxis("bottom", show=False)
            if idx < len(panels) - 1:
                separator = QtWidgets.QFrame()
                separator.setFrameShape(QtWidgets.QFrame.HLine)
                separator.setFrameShadow(QtWidgets.QFrame.Plain)
                separator.setLineWidth(1)
                separator.setMaximumHeight(2)
                container_layout.addWidget(separator)
        self._panel_order = ordered_names
        if synchronize_x_axis:
            self.synchronize_x_axes()
        return stretches, warning

    def update_titles(self, panels: List[tuple[SubcardDefinition, list, List[Path]]]) -> None:
        # titles removed from per-panel headers; no-op retained for compatibility
        return None

    def panel_plots(self) -> List[pg.PlotWidget]:
        return self._panel_plots

    def plot_by_name(self, name: str) -> pg.PlotWidget | None:
        return self._panel_plot_by_name.get(name)

    def latest_panel_data(self) -> Dict[str, List[tuple[object | None, Path, str | None, str | None]]]:
        return self._latest_panel_data

    def set_latest_panel_data(
        self, name: str, data: List[tuple[object | None, Path, str | None, str | None]]
    ) -> None:
        self._latest_panel_data[name] = data

    def panel_order(self) -> List[str]:
        return self._panel_order

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
            for idx, plot in enumerate(self._panel_plots):
                plot.showAxis("bottom", show=(idx == len(self._panel_plots) - 1))

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
