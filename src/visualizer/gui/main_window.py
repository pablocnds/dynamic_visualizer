from __future__ import annotations

from pathlib import Path
from typing import Optional

from PySide6 import QtCore, QtWidgets
import pyqtgraph as pg

from visualizer.data.models import Dataset
from visualizer.data.repository import DatasetRepository
from visualizer.interpretation.specs import DefaultInterpreter, PlotSpec, VisualizationType
from visualizer.viz.renderer import PlotRenderer


class MainWindow(QtWidgets.QMainWindow):
    def __init__(self, data_dir: Path) -> None:
        super().__init__()
        self.setWindowTitle("Dynamic Visualizer")
        self.resize(1200, 800)

        self._data_dir = data_dir
        self._repository = DatasetRepository()
        self._interpreter = DefaultInterpreter()
        self._renderer = PlotRenderer()
        self._current_spec: Optional[PlotSpec] = None
        self._current_dataset: Optional[Dataset] = None
        self._current_path: Optional[Path] = None

        self._build_ui()
        self._load_initial_files()

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

        reset_view_button = QtWidgets.QPushButton("Reset View")
        reset_view_button.clicked.connect(self._handle_reset_view)
        controls_layout.addWidget(reset_view_button)

        controls_layout.addStretch()

        layout.addLayout(controls_layout, 1)

        self._plot_widget = pg.PlotWidget()
        layout.addWidget(self._plot_widget, 3)

        self._status_label = QtWidgets.QLabel("Select a dataset to visualize.")
        controls_layout.addWidget(self._status_label)

    def _load_initial_files(self) -> None:
        files = self._repository.list_datasets(self._data_dir)
        for file_path in files:
            self._add_file_to_list(file_path)

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
        path = selected_items[0].data(QtCore.Qt.UserRole)
        if path:
            self._load_and_render(Path(path))

    def _handle_visualization_change(self, _: int) -> None:
        if self._current_dataset is None or self._current_path is None:
            return
        self._render_dataset(self._current_dataset, self._current_path)

    def _load_and_render(self, path: Path) -> None:
        try:
            dataset = self._repository.load(path)
            self._current_dataset = dataset
            self._current_path = path
            self._render_dataset(dataset, path)
        except Exception as exc:  # pragma: no cover - GUI feedback
            self._status_label.setText(f"Error: {exc}")

    def _render_dataset(self, dataset: Dataset, path: Path) -> None:
        override = self._resolve_visualization_override()
        spec = self._interpreter.build_plot_spec(dataset, override=override)
        self._renderer.render(self._plot_widget, spec)
        self._current_spec = spec
        self._status_label.setText(f"Loaded {path.name}")
        self._plot_widget.enableAutoRange(x=True, y=True)

    def _resolve_visualization_override(self) -> VisualizationType | None:
        choice = self._visualization_combo.currentText()
        if choice == "Line":
            return VisualizationType.LINE
        if choice == "Scatter":
            return VisualizationType.SCATTER
        return None

    def _handle_reset_view(self) -> None:
        self._plot_widget.enableAutoRange(x=True, y=True)
