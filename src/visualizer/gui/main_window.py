from __future__ import annotations

from pathlib import Path
from typing import Dict, List, Optional, Tuple

from PySide6 import QtCore, QtGui, QtWidgets
import pyqtgraph as pg

from visualizer.cards.loader import CardLoader
from visualizer.cards.models import (
    CardDefinition,
    CardSession,
    SeriesDefinition,
    SubcardDefinition,
)
from visualizer.data.models import Dataset
from visualizer.data.repository import DatasetRepository
from visualizer.interpretation.specs import DefaultInterpreter, PlotSpec, VisualizationType
from visualizer.viz.renderer import PlotRenderer


class MainWindow(QtWidgets.QMainWindow):
    def __init__(self, data_dir: Path | None, cards_dir: Path | None = None) -> None:
        super().__init__()
        self.setWindowTitle("Dynamic Visualizer")
        self.resize(1200, 800)

        self._data_dir = data_dir
        self._cards_dir = cards_dir
        self._repository = DatasetRepository()
        self._interpreter = DefaultInterpreter()
        self._renderer = PlotRenderer()
        self._current_spec: Optional[PlotSpec] = None
        self._current_dataset: Optional[Dataset] = None
        self._current_path: Optional[Path] = None
        self._card_loader = CardLoader(cards_dir) if cards_dir else None
        self._card_session: Optional[CardSession] = None
        self._variable_controls: dict[str, QtWidgets.QComboBox] = {}
        self._active_card_path: Optional[Path] = None
        self._panel_overrides: Dict[str, VisualizationType | None] = {}
        self._panel_plot_by_name: Dict[str, pg.PlotWidget] = {}
        self._panel_title_by_name: Dict[str, QtWidgets.QLabel] = {}
        self._latest_panel_data: Dict[
            str, List[tuple[Optional[Dataset], Path, Optional[str]]]
        ] = {}
        self._panel_order: List[str] = []
        self._data_dir_label: Optional[QtWidgets.QLabel] = None
        self._cards_dir_label: Optional[QtWidgets.QLabel] = None

        self._build_ui()
        self._load_initial_sources()

    def _build_ui(self) -> None:
        central_widget = QtWidgets.QWidget()
        self.setCentralWidget(central_widget)

        main_layout = QtWidgets.QVBoxLayout(central_widget)

        content_layout = QtWidgets.QHBoxLayout()
        main_layout.addLayout(content_layout)

        controls_widget = QtWidgets.QWidget()
        controls_widget.setFixedWidth(320)
        controls_layout = QtWidgets.QVBoxLayout(controls_widget)
        content_layout.addWidget(controls_widget)

        controls_layout.addWidget(QtWidgets.QLabel("Data Folder"))
        self._data_dir_label = QtWidgets.QLabel("No folder selected")
        controls_layout.addWidget(self._data_dir_label)
        choose_folder_button = QtWidgets.QPushButton("Choose Data Folder…")
        choose_folder_button.clicked.connect(self._handle_choose_folder)
        controls_layout.addWidget(choose_folder_button)

        controls_layout.addWidget(QtWidgets.QLabel("Cards"))
        self._cards_dir_label = QtWidgets.QLabel("No card folder selected")
        controls_layout.addWidget(self._cards_dir_label)
        choose_card_file_button = QtWidgets.QPushButton("Open Card File…")
        choose_card_file_button.clicked.connect(self._handle_choose_card_file)
        controls_layout.addWidget(choose_card_file_button)

        self._file_list = QtWidgets.QListWidget()
        self._file_list.itemSelectionChanged.connect(self._handle_file_selection)

        controls_layout.addWidget(QtWidgets.QLabel("Available Data Files"))
        controls_layout.addWidget(self._file_list)

        add_button = QtWidgets.QPushButton("Add File…")
        add_button.clicked.connect(self._handle_add_file)
        controls_layout.addWidget(add_button)

        self._visualization_combo = QtWidgets.QComboBox()
        self._visualization_combo.addItems(["Auto", "Line", "Scatter"])
        self._visualization_combo.currentIndexChanged.connect(self._handle_visualization_change)
        controls_layout.addWidget(QtWidgets.QLabel("Visualization Mode"))
        controls_layout.addWidget(self._visualization_combo)

        self._variable_group = QtWidgets.QGroupBox("Card Variables")
        self._variable_form_layout = QtWidgets.QFormLayout()
        self._variable_group.setLayout(self._variable_form_layout)
        self._variable_group.setVisible(False)
        controls_layout.addWidget(self._variable_group)

        self._card_list = QtWidgets.QListWidget()
        self._card_list.itemSelectionChanged.connect(self._handle_card_selection)
        controls_layout.addWidget(self._card_list)

        navigation_layout = QtWidgets.QHBoxLayout()
        self._prev_view_button = QtWidgets.QPushButton("Prev View")
        self._next_view_button = QtWidgets.QPushButton("Next View")
        self._prev_view_button.clicked.connect(self._handle_prev_view)
        self._next_view_button.clicked.connect(self._handle_next_view)
        navigation_layout.addWidget(self._prev_view_button)
        navigation_layout.addWidget(self._next_view_button)
        controls_layout.addLayout(navigation_layout)

        reset_view_button = QtWidgets.QPushButton("Reset View")
        reset_view_button.clicked.connect(self._handle_reset_view)
        controls_layout.addWidget(reset_view_button)

        controls_layout.addStretch()

        self._plot_stack = QtWidgets.QStackedWidget()
        self._single_plot_widget = pg.PlotWidget()
        self._plot_stack.addWidget(self._single_plot_widget)
        self._multi_plot_container = QtWidgets.QWidget()
        self._multi_plot_layout = QtWidgets.QVBoxLayout(self._multi_plot_container)
        self._multi_plot_layout.setContentsMargins(0, 0, 0, 0)
        self._multi_plot_layout.setSpacing(12)
        self._plot_stack.addWidget(self._multi_plot_container)
        self._panel_widgets: List[QtWidgets.QWidget] = []
        self._panel_plots: List[pg.PlotWidget] = []

        content_layout.addWidget(self._plot_stack, 3)

        self._status_label = QtWidgets.QLabel("Select a dataset to visualize.")
        self._status_label.setWordWrap(True)
        self._status_label.setFrameShape(QtWidgets.QFrame.Panel)
        self._status_label.setFrameShadow(QtWidgets.QFrame.Sunken)
        self._status_label.setContentsMargins(8, 4, 8, 4)
        main_layout.addWidget(self._status_label)
        self._update_navigation_buttons()

    def _load_initial_sources(self) -> None:
        self._load_cards()
        if self._data_dir:
            self._refresh_file_list()
        else:
            self._status_label.setText("Choose a data folder or add files to begin.")

    def _add_file_to_list(self, path: Path) -> None:
        for index in range(self._file_list.count()):
            existing_item = self._file_list.item(index)
            if existing_item.data(QtCore.Qt.UserRole) == path:
                return
        item = QtWidgets.QListWidgetItem(path.name)
        item.setData(QtCore.Qt.UserRole, path)
        self._file_list.addItem(item)

    def _refresh_file_list(self) -> None:
        self._file_list.clear()
        if not self._data_dir:
            if self._data_dir_label:
                self._data_dir_label.setText("No folder selected")
            return
        if self._data_dir_label:
            self._data_dir_label.setText(str(self._data_dir))
        for file_path in self._repository.list_datasets(self._data_dir):
            self._add_file_to_list(file_path)

    def _handle_add_file(self) -> None:
        dialog = QtWidgets.QFileDialog(self)
        dialog.setFileMode(QtWidgets.QFileDialog.ExistingFile)
        dialog.setNameFilters([
            "Data files (*.csv *.json)",
            "CSV (*.csv)",
            "JSON (*.json)",
        ])
        if dialog.exec():
            selected_files = dialog.selectedFiles()
            if selected_files:
                path = Path(selected_files[0])
                self._add_file_to_list(path)
                self._status_label.setText(f"Added {path.name}")

    def _handle_choose_folder(self) -> None:
        dialog = QtWidgets.QFileDialog(self)
        dialog.setFileMode(QtWidgets.QFileDialog.Directory)
        dialog.setOption(QtWidgets.QFileDialog.ShowDirsOnly, True)
        if dialog.exec():
            folders = dialog.selectedFiles()
            if folders:
                self._data_dir = Path(folders[0])
                self._refresh_file_list()
                self._status_label.setText(f"Loaded folder {self._data_dir}")

    def _handle_choose_card_file(self) -> None:
        dialog = QtWidgets.QFileDialog(self)
        dialog.setFileMode(QtWidgets.QFileDialog.ExistingFile)
        dialog.setNameFilters([
            "Card files (*.toml)",
            "All files (*)",
        ])
        if dialog.exec():
            files = dialog.selectedFiles()
            if files:
                card_path = Path(files[0])
                self._set_card_loader(card_path.parent, select_card=card_path)
                self._status_label.setText(f"Loaded card {card_path.name}")

    def _handle_file_selection(self) -> None:
        selected_items = self._file_list.selectedItems()
        if not selected_items:
            return
        self._clear_card_selection()
        path = selected_items[0].data(QtCore.Qt.UserRole)
        if path:
            self._load_and_render(Path(path))

    def _handle_visualization_change(self, _: int) -> None:
        if self._card_session:
            self._render_current_card_selection()
            return
        if self._current_dataset is None or self._current_path is None:
            return
        self._plot_stack.setCurrentWidget(self._single_plot_widget)
        self._draw_plot(self._single_plot_widget, self._current_dataset, self._current_path, card_style=None)
        self._status_label.setText(f"Loaded {self._current_path.name}")

    def _load_cards(self) -> None:
        if not self._card_loader:
            return
        self._card_list.clear()
        for card_path in self._card_loader.list_card_files():
            item = QtWidgets.QListWidgetItem(card_path.name)
            item.setData(QtCore.Qt.UserRole, card_path)
            self._card_list.addItem(item)

    def _handle_card_selection(self) -> None:
        selected_items = self._card_list.selectedItems()
        if not selected_items:
            self._card_session = None
            self._update_navigation_buttons()
            self._variable_group.setVisible(False)
            self._clear_variable_controls()
            self._clear_panel_widgets()
            self._plot_stack.setCurrentWidget(self._single_plot_widget)
            self._active_card_path = None
            return
        self._file_list.blockSignals(True)
        self._file_list.clearSelection()
        self._file_list.blockSignals(False)
        path = selected_items[0].data(QtCore.Qt.UserRole)
        if path:
            self._activate_card(Path(path))

    def _activate_card(self, card_path: Path) -> None:
        if not self._card_loader:
            return
        try:
            definition = self._card_loader.load_definition(card_path)
            matches = self._card_loader.resolve_paths(definition)
            if not any(matches.values()):
                self._card_session = None
                self._status_label.setText("Card has no matching datasets.")
                self._update_navigation_buttons()
                self._variable_group.setVisible(False)
                self._clear_panel_widgets()
                return
            self._card_session = CardSession(definition=definition, matches=matches)
            self._active_card_path = card_path
            self._panel_overrides.clear()
            self._update_navigation_buttons()
            self._populate_variable_controls()
            self._render_current_card_selection()
        except Exception as exc:  # pragma: no cover - GUI feedback
            self._card_session = None
            self._status_label.setText(f"Card error: {exc}")
            self._update_navigation_buttons()
            self._variable_group.setVisible(False)
            self._clear_panel_widgets()
            self._active_card_path = None

    def _handle_next_view(self) -> None:
        if not self._card_session or not self._card_session.has_paths():
            return
        try:
            self._card_session.cycle_pivot(1)
            self._sync_variable_controls()
            self._render_current_card_selection()
        except Exception as exc:  # pragma: no cover - GUI feedback
            self._status_label.setText(f"Card error: {exc}")

    def _handle_prev_view(self) -> None:
        if not self._card_session or not self._card_session.has_paths():
            return
        try:
            self._card_session.cycle_pivot(-1)
            self._sync_variable_controls()
            self._render_current_card_selection()
        except Exception as exc:  # pragma: no cover - GUI feedback
            self._status_label.setText(f"Card error: {exc}")

    def keyPressEvent(self, event: QtGui.QKeyEvent) -> None:  # type: ignore[override]
        if event.key() == QtCore.Qt.Key_Right and self._card_session:
            self._handle_next_view()
            event.accept()
            return
        if event.key() == QtCore.Qt.Key_Left and self._card_session:
            self._handle_prev_view()
            event.accept()
            return
        super().keyPressEvent(event)

    def _clear_card_selection(self) -> None:
        self._card_list.blockSignals(True)
        self._card_list.clearSelection()
        self._card_list.blockSignals(False)
        self._card_session = None
        self._update_navigation_buttons()
        self._variable_group.setVisible(False)
        self._clear_variable_controls()
        self._panel_overrides.clear()
        self._panel_plot_by_name.clear()
        self._panel_order.clear()
        self._panel_title_by_name.clear()
        self._latest_panel_data.clear()
        self._clear_panel_widgets()
        self._plot_stack.setCurrentWidget(self._single_plot_widget)
        self._active_card_path = None

    def _update_navigation_buttons(self) -> None:
        active = bool(
            self._card_session
            and self._card_session.has_paths()
            and self._card_session.definition.pivot_variable
        )
        self._prev_view_button.setEnabled(active)
        self._next_view_button.setEnabled(active)

    def _set_card_loader(self, path: Path, select_card: Path | None = None) -> None:
        self._card_loader = CardLoader(path)
        self._cards_dir = path
        if self._cards_dir_label:
            self._cards_dir_label.setText(str(path))
        self._clear_card_selection()
        self._load_cards()
        if select_card:
            for index in range(self._card_list.count()):
                item = self._card_list.item(index)
                if item.data(QtCore.Qt.UserRole) == select_card:
                    self._card_list.setCurrentItem(item)
                    self._handle_card_selection()
                    break

    def _load_and_render(self, path: Path, card_style: str | None = None) -> None:
        try:
            dataset = self._repository.load(path)
            self._current_dataset = dataset
            self._current_path = path
            self._plot_stack.setCurrentWidget(self._single_plot_widget)
            self._clear_panel_widgets()
            self._draw_plot(self._single_plot_widget, dataset, path, card_style)
            self._status_label.setText(f"Loaded {path.name}")
        except Exception as exc:  # pragma: no cover - GUI feedback
            self._status_label.setText(f"Error: {exc}")

    def _resolve_visualization_override(
        self,
        card_style: str | None = None,
        panel_override: VisualizationType | None = None,
    ) -> VisualizationType | None:
        if panel_override:
            return panel_override
        choice = self._visualization_combo.currentText()
        if choice == "Line":
            return VisualizationType.LINE
        if choice == "Scatter":
            return VisualizationType.SCATTER
        if card_style:
            try:
                return VisualizationType.from_string(card_style)
            except ValueError:
                return None
        return None

    def _handle_reset_view(self) -> None:
        self._single_plot_widget.enableAutoRange(x=True, y=True)
        for plot in self._panel_plots:
            plot.enableAutoRange(x=True, y=True)

    def _build_panel_layout(
        self,
        panels: List[
            tuple[
                SubcardDefinition,
                List[tuple[Optional[Dataset], Path, Optional[str]]],
                List[Path],
            ]
        ],
    ) -> Optional[str]:
        self._plot_stack.setCurrentWidget(self._multi_plot_container)
        self._clear_panel_widgets()
        subcards = [panel[0] for panel in panels]
        stretches, warning = self._calculate_panel_stretches(subcards)
        ordered_names = [panel[0].name for panel in panels]
        for (subcard, entries, paths), stretch in zip(panels, stretches):
            panel_widget = QtWidgets.QWidget()
            panel_layout = QtWidgets.QVBoxLayout(panel_widget)
            header_layout = QtWidgets.QHBoxLayout()
            title = QtWidgets.QLabel(self._format_panel_title(subcard, paths))
            self._panel_title_by_name[subcard.name] = title
            header_layout.addWidget(title)
            header_layout.addStretch()
            mode_label = QtWidgets.QLabel("Mode:")
            header_layout.addWidget(mode_label)
            style_combo = self._create_panel_style_combo(subcard.name)
            header_layout.addWidget(style_combo)
            panel_layout.addLayout(header_layout)
            plot_widget = pg.PlotWidget()
            panel_layout.addWidget(plot_widget)
            self._multi_plot_layout.addWidget(panel_widget, stretch)
            self._panel_widgets.append(panel_widget)
            self._panel_plots.append(plot_widget)
            self._panel_plot_by_name[subcard.name] = plot_widget
            self._latest_panel_data[subcard.name] = entries
            self._rerender_panel(subcard.name)
        self._panel_order = ordered_names
        return warning

    def _update_existing_panels(
        self,
        panels: List[
            tuple[
                SubcardDefinition,
                List[tuple[Optional[Dataset], Path, Optional[str]]],
                List[Path],
            ]
        ],
    ) -> Optional[str]:
        warning = None
        for subcard, entries, paths in panels:
            title = self._panel_title_by_name.get(subcard.name)
            if title:
                title.setText(self._format_panel_title(subcard, paths))
            self._latest_panel_data[subcard.name] = entries
            self._rerender_panel(subcard.name)
        return warning

    def _calculate_panel_stretches(
        self, subcards: List[SubcardDefinition]
    ) -> tuple[List[int], Optional[str]]:
        specified = [subcard.chart_height for subcard in subcards if subcard.chart_height]
        total_specified = sum(specified)
        warning: Optional[str] = None
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

    def _create_panel_style_combo(self, subcard_name: str) -> QtWidgets.QComboBox:
        combo = QtWidgets.QComboBox()
        combo.addItems(["Auto", "Line", "Scatter"])
        override = self._panel_overrides.get(subcard_name)
        if override == VisualizationType.LINE:
            combo.setCurrentText("Line")
        elif override == VisualizationType.SCATTER:
            combo.setCurrentText("Scatter")
        combo.currentTextChanged.connect(
            lambda text, name=subcard_name: self._handle_panel_visualization_change(name, text)
        )
        return combo

    def _draw_plot(
        self,
        widget: pg.PlotWidget,
        dataset: Dataset,
        path: Path,
        card_style: Optional[str],
        panel_override: VisualizationType | None = None,
    ) -> None:
        override = self._resolve_visualization_override(
            card_style=card_style,
            panel_override=panel_override,
        )
        spec = self._interpreter.build_plot_spec(dataset, override=override)
        self._renderer.render(widget, spec)
        widget.enableAutoRange(x=True, y=True)
        self._current_spec = spec

    def _handle_panel_visualization_change(self, subcard_name: str, text: str) -> None:
        if text == "Auto":
            self._panel_overrides.pop(subcard_name, None)
        else:
            self._panel_overrides[subcard_name] = (
                VisualizationType.LINE if text == "Line" else VisualizationType.SCATTER
            )
        self._rerender_panel(subcard_name)

    def _rerender_panel(self, subcard_name: str) -> None:
        plot = self._panel_plot_by_name.get(subcard_name)
        data = self._latest_panel_data.get(subcard_name)
        if not plot or not data:
            return
        override = self._panel_overrides.get(subcard_name)
        specs = []
        for dataset, path, default_style in data:
            if dataset is None:
                continue
            viz = self._resolve_visualization_override(
                card_style=default_style,
                panel_override=override,
            )
            specs.append(self._interpreter.build_plot_spec(dataset, override=viz))
        if not specs:
            plot.clear()
        elif len(specs) == 1:
            self._renderer.render(plot, specs[0])
        else:
            self._renderer.render_multiple(plot, specs)

    def _clear_panel_widgets(self) -> None:
        while self._multi_plot_layout.count():
            item = self._multi_plot_layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()
        for plot in self._panel_plots:
            plot.deleteLater()
        self._panel_widgets.clear()
        self._panel_plots.clear()
        self._panel_plot_by_name.clear()
        self._panel_title_by_name.clear()
        self._panel_order.clear()
        self._latest_panel_data.clear()

    def _populate_variable_controls(self) -> None:
        self._clear_variable_controls()
        if not self._card_session or not self._card_session.definition.variables:
            self._variable_group.setVisible(False)
            return
        self._variable_group.setVisible(True)
        pivot = self._card_session.definition.pivot_variable
        for variable in self._card_session.definition.variables:
            combo = QtWidgets.QComboBox()
            values = self._card_session.available_values(
                variable,
                constrained=(variable == pivot),
            )
            combo.addItems(values)
            combo.currentTextChanged.connect(
                lambda value, var=variable: self._handle_variable_selection(var, value)
            )
            self._variable_controls[variable] = combo
            self._variable_form_layout.addRow(variable, combo)
        self._sync_variable_controls()

    def _clear_variable_controls(self) -> None:
        while self._variable_form_layout.count():
            item = self._variable_form_layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()
        for combo in self._variable_controls.values():
            combo.deleteLater()
        self._variable_controls.clear()

    def _sync_variable_controls(self) -> None:
        if not self._card_session:
            return
        pivot = self._card_session.definition.pivot_variable
        for variable, combo in self._variable_controls.items():
            if variable == pivot:
                values = self._card_session.available_values(variable, constrained=True)
                self._set_combo_items(combo, values)
            selection_value = self._card_session.selection.get(variable)
            self._set_combo_value(combo, selection_value)

    def _set_combo_items(self, combo: QtWidgets.QComboBox, values: list[str]) -> None:
        combo.blockSignals(True)
        combo.clear()
        combo.addItems(values)
        combo.blockSignals(False)

    def _set_combo_value(self, combo: QtWidgets.QComboBox, value: Optional[str]) -> None:
        if value is None:
            return
        combo.blockSignals(True)
        index = combo.findText(value)
        if index >= 0:
            combo.setCurrentIndex(index)
        combo.blockSignals(False)

    def _handle_variable_selection(self, variable: str, value: str) -> None:
        if not self._card_session:
            return
        try:
            self._card_session.update_selection(variable, value)
            self._sync_variable_controls()
            self._render_current_card_selection()
        except Exception as exc:  # pragma: no cover - GUI feedback
            self._status_label.setText(f"Card selection error: {exc}")

    def _render_current_card_selection(self) -> None:
        if not self._card_session:
            return
        try:
            match_map = self._card_session.current_matches()
        except Exception as exc:  # pragma: no cover - GUI feedback
            self._status_label.setText(f"Card error: {exc}")
            return

        panels: List[
            tuple[
                SubcardDefinition,
                List[tuple[Optional[Dataset], Path, Optional[str]]],
                List[Path],
            ]
        ] = []
        missing: List[str] = []

        for subcard in self._card_session.definition.subcards:
            match = match_map.get(subcard.name)
            entries: List[tuple[Optional[Dataset], Path, Optional[str]]] = []
            panel_paths: List[Path] = []
            if not match:
                missing.append(subcard.name)
                panels.append((subcard, entries, panel_paths))
                continue

            overlay_def = self._card_session.definition.overlay_panels.get(subcard.name)
            if overlay_def:
                overlay_series = self._card_session._build_overlay_series(
                    overlay_def, match.variables
                )
                series_list = overlay_series.series
            else:
                series_list = [
                    SeriesDefinition(
                        path=match.path,
                        chart_style=subcard.chart_style or self._card_session.definition.chart_style,
                    )
                ]

            for series_def in series_list:
                panel_paths.append(series_def.path)
                try:
                    dataset = self._repository.load(series_def.path)
                except Exception as exc:  # pragma: no cover - GUI feedback
                    missing.append(f"{series_def.path.name} ({exc})")
                    entries.append((None, series_def.path, series_def.chart_style))
                    continue
                entries.append((dataset, series_def.path, series_def.chart_style))

            panels.append((subcard, entries, panel_paths))

        if not panels:
            self._status_label.setText("Card selection has no matching datasets.")
            return

        active_names = {subcard.name for subcard, _, _ in panels}
        for name in list(self._panel_overrides.keys()):
            if name not in active_names:
                self._panel_overrides.pop(name, None)

        panel_names = [subcard.name for subcard, _, _ in panels]
        if panel_names != self._panel_order:
            warning = self._build_panel_layout(panels)
        else:
            warning = self._update_existing_panels(panels)
        selection_text = ", ".join(
            f"{var}={value}" for var, value in sorted(self._card_session.selection.items())
        )
        card_label = self._active_card_path.name if self._active_card_path else "card"
        message = f"Card {card_label}: {selection_text}"
        if missing:
            message += f" (missing: {', '.join(missing)})"
        if warning:
            message += f" [{warning}]"
        self._status_label.setText(message)
