from __future__ import annotations

from pathlib import Path
from typing import Dict, List, Optional, Tuple

from PySide6 import QtCore, QtGui, QtWidgets
import pyqtgraph as pg

from visualizer.cards.models import CardSession, ChartStyle, SubcardDefinition
from visualizer.controller import SessionController
from visualizer.data.models import DataPayload, Dataset, TableDataset
from visualizer.data.repository import DatasetRepository
from visualizer.interpretation.specs import DefaultInterpreter, PlotSpec, VisualizationType
from visualizer.state import StateManager
from visualizer.gui.layout import MainWindowView
from visualizer.gui.panels import PanelManager
from visualizer.viz.renderer import PlotRenderer
from visualizer.viz.table_renderer import TableRenderer, TableView
from visualizer.viz.registry import get_default_registry


class MainWindow(QtWidgets.QMainWindow):
    def __init__(self, data_dir: Path | None, cards_dir: Path | None = None) -> None:
        super().__init__()
        self.setWindowTitle("Dynamic Visualizer")
        self.resize(1200, 800)

        self._data_dir = data_dir
        self._cards_dir = cards_dir
        self._state_manager = StateManager()
        self._saved_state = self._state_manager.load()
        self._repository = DatasetRepository()
        self._controller = SessionController(self._repository, cards_dir=cards_dir)
        self._interpreter = DefaultInterpreter()
        self._renderer = PlotRenderer()
        self._table_renderer = TableRenderer()
        self._viz_registry = get_default_registry()
        self._panel_manager = PanelManager(self._renderer)
        self._current_spec: Optional[PlotSpec] = None
        self._current_dataset: Optional[DataPayload] = None
        self._current_path: Optional[Path] = None
        self._card_loader = self._controller.card_loader
        self._card_session: Optional[CardSession] = None
        self._variable_controls: dict[str, QtWidgets.QComboBox] = {}
        self._active_card_path: Optional[Path] = None
        self._panel_overrides: Dict[str, VisualizationType | None] = {}
        self._added_files: set[Path] = set()
        self._pending_card_file: Optional[Path] = None
        self._last_variable_values: Dict[str, str] = {}
        self._view: MainWindowView | None = None

        self._build_ui()
        self._restore_state()
        self._load_initial_sources()

    def _build_ui(self) -> None:
        self._view = MainWindowView(self)
        self.setCentralWidget(self._view)

        controls = self._view.controls
        visualization = self._view.visualization
        status_panel = self._view.status_panel
        self._controls = controls
        self._visualization = visualization
        self._status_panel = status_panel

        self._data_dir_label = controls.data_dir_label
        self._cards_dir_label = controls.cards_dir_label
        self._file_list = controls.file_list
        self._visualization_combo = controls.visualization_combo
        self._variable_group = controls.variable_group
        self._variable_form_layout = controls.variable_form_layout
        self._card_list = controls.card_list
        self._prev_view_button = controls.prev_view_button
        self._next_view_button = controls.next_view_button

        self._plot_stack = visualization.plot_stack
        self._single_plot_widget = visualization.single_plot_widget
        self._single_table_widget = visualization.single_table_widget
        self._multi_plot_container = visualization.multi_plot_container
        self._multi_plot_layout = visualization.multi_plot_layout

        self._card_title_label = status_panel.title_label
        self._status_label = status_panel.status_label
        self._warning_label = status_panel.warning_label

        controls.choose_folder_button.clicked.connect(self._handle_choose_folder)
        controls.choose_card_file_button.clicked.connect(self._handle_choose_card_file)
        self._file_list.itemSelectionChanged.connect(self._handle_file_selection)
        controls.add_file_button.clicked.connect(self._handle_add_file)

        self._populate_visualization_combo(self._visualization_combo)
        self._visualization_combo.currentIndexChanged.connect(self._handle_visualization_change)

        self._card_list.itemSelectionChanged.connect(self._handle_card_selection)

        self._prev_view_button.clicked.connect(self._handle_prev_view)
        self._next_view_button.clicked.connect(self._handle_next_view)
        controls.reset_view_button.clicked.connect(self._handle_reset_view)

        self._single_table_widget.pivot_handler = self._handle_pivot_step
        self._single_table_widget.navigation_handler = self._handle_card_list_step

        self._update_navigation_buttons()

    def _load_initial_sources(self) -> None:
        self._load_cards()
        if self._data_dir:
            self._refresh_file_list()
        if self._pending_card_file and self._card_loader:
            for index in range(self._card_list.count()):
                item = self._card_list.item(index)
                if item.data(QtCore.Qt.UserRole) == self._pending_card_file:
                    self._card_list.setCurrentItem(item)
                    self._handle_card_selection()
                    break
        if not self._data_dir and not self._pending_card_file:
            self._status_label.setText("Choose a data folder or add files to begin.")
        if not self._repository.schema_validation_enabled:
            self._set_warning(
                "JSON schema validation is disabled (jsonschema not installed); JSON payloads are only lightly validated."
            )
        else:
            self._set_warning(None)

    def _add_file_to_list(self, path: Path) -> None:
        for index in range(self._file_list.count()):
            existing_item = self._file_list.item(index)
            if existing_item.data(QtCore.Qt.UserRole) == path:
                return
        item = QtWidgets.QListWidgetItem(path.name)
        item.setData(QtCore.Qt.UserRole, path)
        self._file_list.addItem(item)
        self._added_files.add(path)

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
        for extra in sorted(self._added_files):
            if extra.exists():
                self._add_file_to_list(extra)

    def _handle_add_file(self) -> None:
        dialog = QtWidgets.QFileDialog(self)
        dialog.setFileMode(QtWidgets.QFileDialog.ExistingFile)
        dialog.setNameFilters([
            "Data files (*.json)",
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
        if isinstance(self._current_dataset, TableDataset):
            self._plot_stack.setCurrentWidget(self._single_table_widget)
            self._draw_table(self._single_table_widget, self._current_dataset)
            return
        self._plot_stack.setCurrentWidget(self._single_plot_widget)
        self._draw_plot(self._single_plot_widget, self._current_dataset, self._current_path, card_style=None)
        self._status_label.setText(f"Loaded {self._current_path.name}")

    def _populate_visualization_combo(self, combo: QtWidgets.QComboBox) -> None:
        combo.blockSignals(True)
        combo.clear()
        combo.addItem("Auto", userData=None)
        for handler in self._viz_registry.handlers():
            combo.addItem(handler.label, userData=handler.visualization)
        combo.blockSignals(False)

    def _load_cards(self) -> None:
        self._card_list.clear()
        self._card_loader = self._controller.card_loader
        for card_path in self._controller.list_cards():
            item = QtWidgets.QListWidgetItem(card_path.name)
            item.setData(QtCore.Qt.UserRole, card_path)
            self._card_list.addItem(item)

    def _handle_card_selection(self) -> None:
        selected_items = self._card_list.selectedItems()
        if not selected_items:
            self._controller.clear_card()
            self._card_session = None
            self._update_navigation_buttons()
            self._variable_group.setVisible(False)
            self._clear_variable_controls()
            self._panel_manager.clear(self._multi_plot_layout)
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
        try:
            session = self._controller.activate_card(
                card_path,
                preferred_selection=self._last_variable_values if self._last_variable_values else None,
            )
            self._card_loader = self._controller.card_loader
            if not session.has_paths():
                self._card_session = None
                self._status_label.setText("Card has no matching datasets.")
                self._update_navigation_buttons()
                self._variable_group.setVisible(False)
                self._panel_manager.clear(self._multi_plot_layout)
                return
            self._card_session = session
            self._active_card_path = card_path
            self._panel_overrides.clear()
            self._update_navigation_buttons()
            self._populate_variable_controls()
            self._render_current_card_selection()
            self._update_last_variable_values(session)
        except Exception as exc:  # pragma: no cover - GUI feedback
            self._card_session = None
            self._status_label.setText(f"Card error: {exc}")
            self._update_navigation_buttons()
            self._variable_group.setVisible(False)
            self._panel_manager.clear(self._multi_plot_layout)
            self._active_card_path = None

    def _handle_next_view(self) -> None:
        self._handle_pivot_step(1)

    def _handle_prev_view(self) -> None:
        self._handle_pivot_step(-1)

    def _handle_pivot_step(self, step: int) -> bool:
        session = self._controller.card_session
        if not session or not session.has_paths():
            return False
        try:
            self._controller.cycle_pivot(step)
            self._card_session = self._controller.card_session
            self._sync_variable_controls()
            self._render_current_card_selection()
            if self._card_session:
                self._update_last_variable_values(self._card_session)
        except Exception as exc:  # pragma: no cover - GUI feedback
            self._status_label.setText(f"Card error: {exc}")
        return True

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
        self._controller.clear_card()
        self._card_session = None
        self._update_navigation_buttons()
        self._variable_group.setVisible(False)
        self._clear_variable_controls()
        self._panel_overrides.clear()
        self._panel_manager.clear(self._multi_plot_layout)
        self._plot_stack.setCurrentWidget(self._single_plot_widget)
        self._active_card_path = None
        self._pending_card_file = None

    def _update_navigation_buttons(self) -> None:
        self._card_session = self._controller.card_session
        active = bool(
            self._card_session
            and self._card_session.has_paths()
            and self._card_session.definition.pivot_variable
        )
        self._prev_view_button.setEnabled(active)
        self._next_view_button.setEnabled(active)

    def _set_card_loader(self, path: Path, select_card: Path | None = None) -> None:
        self._controller.set_cards_dir(path)
        self._card_loader = self._controller.card_loader
        self._cards_dir = path
        if self._cards_dir_label:
            self._cards_dir_label.setText(str(path))
        self._clear_card_selection()
        self._load_cards()
        if select_card:
            self._pending_card_file = select_card
            for index in range(self._card_list.count()):
                item = self._card_list.item(index)
                if item.data(QtCore.Qt.UserRole) == select_card:
                    self._card_list.setCurrentItem(item)
                    self._handle_card_selection()
                    break
        else:
            self._pending_card_file = None

    def _restore_state(self) -> None:
        data_dir = self._saved_state.get("data_dir")
        card_file = self._saved_state.get("card_file")
        added_files = self._saved_state.get("added_files", [])
        if data_dir:
            path = Path(data_dir)
            if path.exists():
                self._data_dir = path
        for file_path in added_files:
            path = Path(file_path)
            if path.exists():
                self._added_files.add(path)
        if card_file:
            path = Path(card_file)
            if path.exists():
                self._pending_card_file = path
                self._set_card_loader(path.parent, select_card=path)

    def _save_state(self) -> None:
        state = {}
        if self._data_dir and self._data_dir.exists():
            state["data_dir"] = str(self._data_dir.resolve())
        if self._active_card_path and self._active_card_path.exists():
            state["card_file"] = str(self._active_card_path.resolve())
        elif self._pending_card_file and self._pending_card_file.exists():
            state["card_file"] = str(self._pending_card_file.resolve())
        if self._cards_dir and self._cards_dir.exists():
            state["card_dir"] = str(self._cards_dir.resolve())
        extras = [str(path.resolve()) for path in self._added_files if path.exists()]
        if extras:
            state["added_files"] = extras
        self._state_manager.save(state)

    def _load_and_render(self, path: Path, card_style: ChartStyle | None = None) -> None:
        try:
            dataset = self._repository.load(path)
            self._current_dataset = dataset
            self._current_path = path
            self._panel_manager.clear(self._multi_plot_layout)
            if isinstance(dataset, TableDataset):
                self._plot_stack.setCurrentWidget(self._single_table_widget)
                self._draw_table(self._single_table_widget, dataset)
            else:
                self._plot_stack.setCurrentWidget(self._single_plot_widget)
                self._draw_plot(self._single_plot_widget, dataset, path, card_style)
            self._status_label.setText(f"Loaded {path.name}")
        except Exception as exc:  # pragma: no cover - GUI feedback
            self._status_label.setText(f"Error: {exc}")

    def _resolve_visualization_override(
        self,
        card_style: ChartStyle | None = None,
        panel_override: VisualizationType | None = None,
    ) -> VisualizationType | None:
        if panel_override:
            return panel_override
        choice = self._visualization_combo.currentData()
        if isinstance(choice, VisualizationType):
            return choice
        if card_style:
            try:
                return card_style.visualization()
            except Exception:
                return None
        return None

    def _handle_reset_view(self) -> None:
        self._single_plot_widget.enableAutoRange(x=True, y=True)
        for plot in self._panel_manager.panel_plots():
            plot.enableAutoRange(x=True, y=True)

    def _build_panel_layout(
        self,
        panels: List[
            tuple[
                SubcardDefinition,
                List[tuple[Optional[DataPayload], Path, Optional[str], Optional[str]]],
                List[Path],
                str,
            ]
        ],
    ) -> Optional[str]:
        self._plot_stack.setCurrentWidget(self._multi_plot_container)
        self._panel_manager.clear(self._multi_plot_layout)
        stretches, warning = self._panel_manager.build_panels(
            self._multi_plot_layout,
            panels,
            combo_factory=None,
            synchronize_x_axis=self._card_session.definition.synchronize_axis if self._card_session else False,
        )
        self._configure_table_pivot_handlers()
        # render newly built panels
        for subcard, entries, _, _ in panels:
            self._panel_manager.set_latest_panel_data(subcard.name, entries)
            self._rerender_panel(subcard.name)
        return warning

    def _update_existing_panels(
        self,
        panels: List[
            tuple[
                SubcardDefinition,
                List[tuple[Optional[DataPayload], Path, Optional[str], Optional[str]]],
                List[Path],
                str,
            ]
        ],
    ) -> Optional[str]:
        self._panel_manager.update_titles(panels)
        self._configure_table_pivot_handlers()
        for subcard, entries, _, _ in panels:
            self._panel_manager.set_latest_panel_data(subcard.name, entries)
            self._rerender_panel(subcard.name)
        return None

    def _create_panel_style_combo(self, subcard_name: str) -> QtWidgets.QComboBox:
        combo = QtWidgets.QComboBox()
        self._populate_visualization_combo(combo)
        override = self._panel_overrides.get(subcard_name)
        if override is not None:
            idx = combo.findData(override)
            if idx >= 0:
                combo.setCurrentIndex(idx)
        combo.currentIndexChanged.connect(
            lambda _index, name=subcard_name, combo_ref=combo: self._handle_panel_visualization_change(
                name, combo_ref
            )
        )
        return combo

    def _draw_plot(
        self,
        widget: pg.PlotWidget,
        dataset: Dataset,
        path: Path,
        card_style: Optional[ChartStyle],
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

    def _draw_table(self, view: QtWidgets.QTableView, dataset: TableDataset) -> None:
        spec = self._interpreter.build_table_spec(dataset)
        self._table_renderer.render(view, spec)
        self._current_spec = None

    def _handle_panel_visualization_change(self, subcard_name: str, combo: QtWidgets.QComboBox) -> None:
        selection = combo.currentData()
        if selection is None:
            self._panel_overrides.pop(subcard_name, None)
        else:
            self._panel_overrides[subcard_name] = selection
        self._rerender_panel(subcard_name)

    def _rerender_panel(self, subcard_name: str) -> None:
        plot = self._panel_manager.plot_by_name(subcard_name)
        table = self._panel_manager.table_by_name(subcard_name)
        data = self._panel_manager.latest_panel_data().get(subcard_name)
        if table:
            self._render_table_panel(table, data or [])
            return
        if not plot or not data:
            return
        self._renderer.reset_widget(plot)
        override = self._panel_overrides.get(subcard_name)
        specs = []
        for dataset, path, default_style, label in data:
            if dataset is None or isinstance(dataset, TableDataset):
                continue
            viz = self._resolve_visualization_override(
                card_style=default_style,
                panel_override=override,
            )
            specs.append(
                self._interpreter.build_plot_spec(
                    dataset,
                    override=viz,
                    label=label,
                )
            )
        if not specs:
            plot.clear()
        elif len(specs) == 1:
            self._renderer.render(plot, specs[0])
        else:
            try:
                self._renderer.render_multiple(plot, specs)
            except ValueError as exc:
                # Incompatible overlay (e.g., mixing 1D and 2D plots); render first spec and surface message.
                self._renderer.render(plot, specs[0])
                self._status_label.setText(str(exc))

    def _render_table_panel(
        self,
        view: QtWidgets.QTableView,
        data: List[tuple[Optional[DataPayload], Path, Optional[str], Optional[str]]],
    ) -> None:
        entry = next(
            (
                (dataset, label)
                for dataset, _path, _style, label in data
                if isinstance(dataset, TableDataset)
            ),
            None,
        )
        if not entry:
            view.setModel(None)
            return
        dataset, label = entry
        spec = self._interpreter.build_table_spec(dataset, label=label)
        self._table_renderer.render(view, spec)

    def _configure_table_pivot_handlers(self) -> None:
        for table in self._panel_manager.table_views():
            if isinstance(table, TableView):
                table.pivot_handler = self._handle_pivot_step
                table.navigation_handler = self._handle_card_list_step

    def _handle_card_list_step(self, step: int) -> bool:
        count = self._card_list.count()
        if count == 0:
            return False
        current = self._card_list.currentRow()
        if current < 0:
            next_row = 0 if step >= 0 else count - 1
        else:
            next_row = max(0, min(count - 1, current + step))
        if next_row == current:
            return True
        self._card_list.setCurrentRow(next_row)
        return True

    def _populate_variable_controls(self) -> None:
        self._clear_variable_controls()
        session = self._controller.card_session
        self._card_session = session
        if not session or not session.definition.variables:
            self._variable_group.setVisible(False)
            return
        self._variable_group.setVisible(True)
        pivot = session.definition.pivot_variable
        for variable in session.definition.variables:
            combo = QtWidgets.QComboBox()
            values = self._controller.available_values(
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

    def closeEvent(self, event: QtGui.QCloseEvent) -> None:  # type: ignore[override]
        self._save_state()
        super().closeEvent(event)

    @property
    def _panel_plots(self) -> List[pg.PlotWidget]:  # pragma: no cover - test/helper access
        return self._panel_manager.panel_plots()

    @property
    def _panel_order(self) -> List[str]:  # pragma: no cover - test/helper access
        return self._panel_manager.panel_order()

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
        session = self._controller.card_session
        self._card_session = session
        if not session:
            return
        pivot = session.definition.pivot_variable
        for variable, combo in self._variable_controls.items():
            if variable == pivot:
                values = self._controller.available_values(variable, constrained=True)
                self._set_combo_items(combo, values)
            selection_value = session.selection.get(variable)
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
        if not self._controller.card_session:
            return
        try:
            self._controller.update_selection(variable, value)
            self._card_session = self._controller.card_session
            self._sync_variable_controls()
            self._render_current_card_selection()
            if self._card_session:
                self._update_last_variable_values(self._card_session)
        except Exception as exc:  # pragma: no cover - GUI feedback
            self._status_label.setText(f"Card selection error: {exc}")

    def _render_current_card_selection(self) -> None:
        session = self._controller.card_session
        if not session:
            return
        try:
            plans, missing = self._controller.build_panel_plans()
        except Exception as exc:  # pragma: no cover - GUI feedback
            self._status_label.setText(f"Card error: {exc}")
            self._show_error_dialog("Card error", str(exc))
            return

        self._card_session = session
        if not plans:
            self._status_label.setText("Card selection has no matching datasets.")
            return

        active_names = {plan.subcard.name for plan in plans}
        for name in list(self._panel_overrides.keys()):
            if name not in active_names:
                self._panel_overrides.pop(name, None)

        panel_warnings: List[str] = []
        panels: List[
            tuple[
                SubcardDefinition,
                List[tuple[Optional[DataPayload], Path, Optional[ChartStyle], Optional[str]]],
                List[Path],
                str,
            ]
        ] = []
        for plan in plans:
            entries = [
                (series.dataset, series.path, series.chart_style, series.label)
                for series in plan.series
            ]
            panel_kind, panel_warning = self._infer_panel_kind(plan.subcard.name, entries)
            if panel_warning:
                panel_warnings.append(panel_warning)
            panels.append((plan.subcard, entries, plan.paths, panel_kind))

        panel_names = [plan.subcard.name for plan in plans]
        if panel_names != self._panel_order:
            warning = self._build_panel_layout(panels)
        else:
            warning = self._update_existing_panels(panels)
        if session.definition.synchronize_axis:
            self._panel_manager.synchronize_x_axes()
        selection_text = ", ".join(
            f"{var}={value}" for var, value in sorted(session.selection.items())
        )
        card_label = self._active_card_path.name if self._active_card_path else "card"
        message = f"Card {card_label}: {selection_text}"
        if missing:
            message += f" (missing: {', '.join(missing)})"
        warning_bits = []
        if warning:
            warning_bits.append(warning)
        if panel_warnings:
            warning_bits.extend(panel_warnings)
        if warning_bits:
            message += f" [{'; '.join(warning_bits)}]"
        self._status_label.setText(message)

    def _infer_panel_kind(
        self,
        name: str,
        entries: List[tuple[Optional[DataPayload], Path, Optional[ChartStyle], Optional[str]]],
    ) -> tuple[str, str | None]:
        datasets = [dataset for dataset, _path, _style, _label in entries if dataset is not None]
        if not datasets:
            return "plot", None
        has_table = any(isinstance(dataset, TableDataset) for dataset in datasets)
        has_plot = any(not isinstance(dataset, TableDataset) for dataset in datasets)
        if has_table and has_plot:
            kind = "table" if isinstance(datasets[0], TableDataset) else "plot"
            return kind, f"{name}: mixed table/plot data; showing first dataset only"
        if has_table and len(datasets) > 1:
            return "table", f"{name}: table overlays not supported; showing first dataset only"
        return ("table" if has_table else "plot"), None

    def _update_last_variable_values(self, session: CardSession) -> None:
        for var, value in session.selection.items():
            if value:
                self._last_variable_values[var] = value

    def _set_warning(self, message: str | None) -> None:
        if not self._warning_label:
            return
        if message:
            self._warning_label.setText(message)
            self._warning_label.setVisible(True)
        else:
            self._warning_label.clear()
            self._warning_label.setVisible(False)

    def _show_error_dialog(self, title: str, details: str) -> None:
        dialog = QtWidgets.QMessageBox(self)
        dialog.setIcon(QtWidgets.QMessageBox.Warning)
        dialog.setWindowTitle(title)
        dialog.setText(title)
        dialog.setInformativeText(details)
        dialog.setStandardButtons(QtWidgets.QMessageBox.Ok)
        dialog.exec()
