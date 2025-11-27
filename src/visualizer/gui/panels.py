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
    ) -> Tuple[List[int], str | None]:
        stretches, warning = self._calculate_panel_stretches([p[0] for p in panels])
        ordered_names = [panel[0].name for panel in panels]
        for (subcard, entries, paths), stretch in zip(panels, stretches):
            panel_widget = QtWidgets.QWidget()
            panel_layout = QtWidgets.QVBoxLayout(panel_widget)
            header_layout = QtWidgets.QHBoxLayout()
            title = QtWidgets.QLabel(self._format_panel_title(subcard, paths))
            self._panel_title_by_name[subcard.name] = title
            header_layout.addWidget(title)
            header_layout.addStretch()
            if combo_factory:
                mode_label = QtWidgets.QLabel("Mode:")
                header_layout.addWidget(mode_label)
                header_layout.addWidget(combo_factory(subcard.name))
            panel_layout.addLayout(header_layout)
            plot_widget = pg.PlotWidget()
            panel_layout.addWidget(plot_widget)
            container_layout.addWidget(panel_widget, stretch)
            self._panel_widgets.append(panel_widget)
            self._panel_plots.append(plot_widget)
            self._panel_plot_by_name[subcard.name] = plot_widget
            self._latest_panel_data[subcard.name] = entries
            plot_widget.enableAutoRange(x=True, y=True)
        self._panel_order = ordered_names
        return stretches, warning

    def update_titles(self, panels: List[tuple[SubcardDefinition, list, List[Path]]]) -> None:
        for subcard, _, paths in panels:
            title = self._panel_title_by_name.get(subcard.name)
            if title:
                title.setText(self._format_panel_title(subcard, paths))

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

    def panel_titles(self) -> Dict[str, QtWidgets.QLabel]:
        return self._panel_title_by_name

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
