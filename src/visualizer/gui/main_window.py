from __future__ import annotations

from pathlib import Path
from typing import Optional

from PySide6 import QtCore, QtWidgets
import pyqtgraph as pg

from visualizer.cards.loader import CardLoader
from visualizer.cards.models import CardDefinition, CardSession
from visualizer.data.models import Dataset
from visualizer.data.repository import DatasetRepository
from visualizer.interpretation.specs import DefaultInterpreter, PlotSpec, VisualizationType
from visualizer.viz.renderer import PlotRenderer


class MainWindow(QtWidgets.QMainWindow):
    def __init__(self, data_dir: Path, cards_dir: Path | None = None) -> None:
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

        self._build_ui()
        self._load_initial_sources()

    def _build_ui(self) -> None:
        central_widget = QtWidgets.QWidget()
        self.setCentralWidget(central_widget)

        layout = QtWidgets.QHBoxLayout(central_widget)
        self._file_list = QtWidgets.QListWidget()
        self._file_list.itemSelectionChanged.connect(self._handle_file_selection)

        controls_layout = QtWidgets.QVBoxLayout()
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

        controls_layout.addWidget(QtWidgets.QLabel("Cards"))
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

        layout.addLayout(controls_layout, 1)

        self._plot_widget = pg.PlotWidget()
        layout.addWidget(self._plot_widget, 3)

        self._status_label = QtWidgets.QLabel("Select a dataset to visualize.")
        controls_layout.addWidget(self._status_label)
        self._update_navigation_buttons()

    def _load_initial_sources(self) -> None:
        files = self._repository.list_datasets(self._data_dir)
        for file_path in files:
            self._add_file_to_list(file_path)
        self._load_cards()

    def _add_file_to_list(self, path: Path) -> None:
        for index in range(self._file_list.count()):
            existing_item = self._file_list.item(index)
            if existing_item.data(QtCore.Qt.UserRole) == path:
                return
        item = QtWidgets.QListWidgetItem(path.name)
        item.setData(QtCore.Qt.UserRole, path)
        self._file_list.addItem(item)

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

    def _handle_file_selection(self) -> None:
        selected_items = self._file_list.selectedItems()
        if not selected_items:
            return
        self._clear_card_selection()
        path = selected_items[0].data(QtCore.Qt.UserRole)
        if path:
            self._load_and_render(Path(path))

    def _handle_visualization_change(self, _: int) -> None:
        if self._current_dataset is None or self._current_path is None:
            return
        card_style = self._card_session.definition.chart_style if self._card_session else None
        self._render_dataset(self._current_dataset, self._current_path, card_style=card_style)

    def _load_cards(self) -> None:
        if not self._card_loader:
            return
        for card_path in self._card_loader.list_card_files():
            item = QtWidgets.QListWidgetItem(card_path.name)
            item.setData(QtCore.Qt.UserRole, card_path)
            self._card_list.addItem(item)

    def _handle_card_selection(self) -> None:
        selected_items = self._card_list.selectedItems()
        if not selected_items:
            self._card_session = None
            self._update_navigation_buttons()
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
            matches = self._card_loader.resolve_simple_matches(definition)
            if not matches:
                self._card_session = None
                self._status_label.setText("Card has no matching datasets.")
                self._update_navigation_buttons()
                return
            self._card_session = CardSession(definition=definition, resolved_paths=matches, index=0)
            self._update_navigation_buttons()
            self._load_and_render(matches[0], card_style=definition.chart_style)
        except Exception as exc:  # pragma: no cover - GUI feedback
            self._card_session = None
            self._status_label.setText(f"Card error: {exc}")
            self._update_navigation_buttons()

    def _handle_next_view(self) -> None:
        if not self._card_session or not self._card_session.has_paths():
            return
        path = self._card_session.advance(1)
        self._load_and_render(path, card_style=self._card_session.definition.chart_style)

    def _handle_prev_view(self) -> None:
        if not self._card_session or not self._card_session.has_paths():
            return
        path = self._card_session.advance(-1)
        self._load_and_render(path, card_style=self._card_session.definition.chart_style)

    def _clear_card_selection(self) -> None:
        self._card_list.blockSignals(True)
        self._card_list.clearSelection()
        self._card_list.blockSignals(False)
        self._card_session = None
        self._update_navigation_buttons()

    def _update_navigation_buttons(self) -> None:
        active = bool(self._card_session and self._card_session.has_paths())
        self._prev_view_button.setEnabled(active)
        self._next_view_button.setEnabled(active)

    def _load_and_render(self, path: Path, card_style: str | None = None) -> None:
        try:
            dataset = self._repository.load(path)
            self._current_dataset = dataset
            self._current_path = path
            self._render_dataset(dataset, path, card_style=card_style)
        except Exception as exc:  # pragma: no cover - GUI feedback
            self._status_label.setText(f"Error: {exc}")

    def _render_dataset(self, dataset: Dataset, path: Path, card_style: str | None = None) -> None:
        override = self._resolve_visualization_override(card_style=card_style)
        spec = self._interpreter.build_plot_spec(dataset, override=override)
        self._renderer.render(self._plot_widget, spec)
        self._current_spec = spec
        self._status_label.setText(f"Loaded {path.name}")
        self._plot_widget.enableAutoRange(x=True, y=True)

    def _resolve_visualization_override(self, card_style: str | None = None) -> VisualizationType | None:
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
        self._plot_widget.enableAutoRange(x=True, y=True)
