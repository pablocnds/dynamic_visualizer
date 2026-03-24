from __future__ import annotations

from importlib import resources
from pathlib import Path
from typing import Any, Dict, List, Optional

from PySide6 import QtCore, QtGui, QtWidgets
import pyqtgraph as pg

from visualizer.cards.models import CardSession, ChartStyle, SubcardDefinition
from visualizer.controller import SessionController
from visualizer.data.models import DataPayload, Dataset, TableDataset
from visualizer.data.repository import DatasetRepository
from visualizer.interpretation.specs import DefaultInterpreter, PlotSpec, VisualizationType
from visualizer.table_style import TableColorRule
from visualizer.state import StateManager
from visualizer.gui.layout import MainWindowView
from visualizer.gui.theme import build_stylesheet
from visualizer.gui.panels import PanelManager
from visualizer.viz.renderer import PlotRenderer
from visualizer.viz.table_renderer import TableRenderer, TableView
from visualizer.viz.registry import get_default_registry


class MainWindow(QtWidgets.QMainWindow):
    _MAX_RECENT_SESSIONS = 12

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
        self._panel_axis_visibility: Dict[str, tuple[bool | None, bool | None]] = {}
        self._added_files: set[Path] = set()
        self._pending_card_file: Optional[Path] = None
        self._pending_card_selection: Dict[str, str] | None = None
        self._last_variable_values: Dict[str, str] = {}
        self._view: MainWindowView | None = None
        self._visualization_override: VisualizationType | None = None
        self._list_stack: QtWidgets.QStackedWidget | None = None
        self._mode_label: QtWidgets.QLabel | None = None
        self._source_label: QtWidgets.QLabel | None = None
        self._add_file_button: QtWidgets.QPushButton | None = None
        self._empty_data_button: QtWidgets.QPushButton | None = None
        self._empty_card_button: QtWidgets.QPushButton | None = None
        self._loaded_files_group: QtWidgets.QGroupBox | None = None
        self._loaded_files_list: QtWidgets.QListWidget | None = None
        self._toggle_sidebar_action: QtGui.QAction | None = None
        self._recent_sessions_menu: QtWidgets.QMenu | None = None
        self._visualization_action_group: QtGui.QActionGroup | None = None
        self._sidebar_mode = "data"
        self._sidebar_icon_expand: QtGui.QIcon | None = None
        self._sidebar_icon_collapse: QtGui.QIcon | None = None
        self._up_shortcut: QtWidgets.QShortcut | None = None
        self._down_shortcut: QtWidgets.QShortcut | None = None
        self._pending_data_file: Path | None = None
        self._recent_sessions: List[Dict[str, Any]] = []

        self._build_ui()
        self._apply_theme()
        self._load_sidebar_icons()
        self._restore_state()
        self._load_initial_sources()
        self._sync_initial_view_state()

    def _build_ui(self) -> None:
        self._view = MainWindowView(self)
        self.setCentralWidget(self._view)

        controls = self._view.controls
        visualization = self._view.visualization
        status_panel = self._view.status_panel
        self._controls = controls
        self._visualization = visualization
        self._status_panel = status_panel

        self._source_label = controls.source_label
        self._mode_label = controls.mode_label
        self._list_stack = controls.list_stack
        self._file_list = controls.file_list
        self._add_file_button = controls.add_file_button
        self._variable_group = controls.variable_group
        self._variable_form_layout = controls.variable_form_layout
        self._card_list = controls.card_list
        self._prev_view_button = controls.prev_view_button
        self._next_view_button = controls.next_view_button
        self._empty_data_button = controls.empty_data_button
        self._empty_card_button = controls.empty_card_button
        self._loaded_files_group = controls.loaded_files_group
        self._loaded_files_list = controls.loaded_files_list

        self._plot_stack = visualization.plot_stack
        self._single_plot_widget = visualization.single_plot_widget
        self._single_table_widget = visualization.single_table_widget
        self._multi_plot_container = visualization.multi_plot_container
        self._multi_plot_layout = visualization.multi_plot_layout

        self._card_title_label = status_panel.title_label
        self._status_label = status_panel.status_label
        self._warning_label = status_panel.warning_label

        self._file_list.itemSelectionChanged.connect(self._handle_file_selection)
        controls.add_file_button.clicked.connect(self._handle_add_file)

        self._card_list.itemSelectionChanged.connect(self._handle_card_selection)

        self._prev_view_button.clicked.connect(self._handle_prev_view)
        self._next_view_button.clicked.connect(self._handle_next_view)
        controls.reset_view_button.clicked.connect(self._handle_reset_view)
        controls.sidebar_toggle_button.clicked.connect(self._handle_sidebar_toggle_button)
        self._empty_data_button.clicked.connect(self._handle_choose_folder)
        self._empty_card_button.clicked.connect(self._handle_choose_card_file)

        self._single_table_widget.pivot_handler = self._handle_pivot_step
        self._single_table_widget.navigation_handler = self._handle_card_list_step

        self._install_navigation_shortcuts()
        self._build_menu()
        self._update_sidebar_mode()
        self._update_navigation_buttons()

    def _apply_theme(self) -> None:
        self.setStyleSheet(build_stylesheet())

    def _install_navigation_shortcuts(self) -> None:
        self._up_shortcut = QtGui.QShortcut(QtGui.QKeySequence(QtCore.Qt.Key_Up), self)
        self._up_shortcut.setContext(QtCore.Qt.ApplicationShortcut)
        self._up_shortcut.activated.connect(lambda: self._handle_list_navigation_shortcut(-1))
        self._down_shortcut = QtGui.QShortcut(QtGui.QKeySequence(QtCore.Qt.Key_Down), self)
        self._down_shortcut.setContext(QtCore.Qt.ApplicationShortcut)
        self._down_shortcut.activated.connect(lambda: self._handle_list_navigation_shortcut(1))

    def _load_sidebar_icons(self) -> None:
        self._sidebar_icon_collapse = self._load_icon_from_package("sidebar-collapse.png")
        self._sidebar_icon_expand = self._load_icon_from_package("sidebar-expand.png")
        self._update_sidebar_toggle_icon()

    def _load_icon_from_package(self, name: str) -> QtGui.QIcon | None:
        try:
            icon_path = resources.files("visualizer.assets.icons").joinpath(name)
            data = icon_path.read_bytes()
        except Exception:
            return None
        pixmap = QtGui.QPixmap()
        if not pixmap.loadFromData(data):
            return None
        return QtGui.QIcon(pixmap)

    def _update_sidebar_toggle_icon(self) -> None:
        if not self._controls:
            return
        collapsed = self._controls.is_collapsed()
        icon = self._sidebar_icon_expand if collapsed else self._sidebar_icon_collapse
        if icon:
            self._controls.sidebar_toggle_button.setIcon(icon)

    def _build_menu(self) -> None:
        menu_bar = self.menuBar()
        file_menu = menu_bar.addMenu("File")
        open_data_action = QtGui.QAction("Open Data Folder…", self)
        open_data_action.triggered.connect(self._handle_choose_folder)
        file_menu.addAction(open_data_action)

        add_file_action = QtGui.QAction("Add Data File…", self)
        add_file_action.triggered.connect(self._handle_add_file)
        file_menu.addAction(add_file_action)

        open_card_action = QtGui.QAction("Open Card File…", self)
        open_card_action.triggered.connect(self._handle_choose_card_file)
        file_menu.addAction(open_card_action)
        self._recent_sessions_menu = file_menu.addMenu("Open Previous Session")
        self._refresh_recent_sessions_menu()

        file_menu.addSeparator()
        exit_action = QtGui.QAction("Quit", self)
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)

        view_menu = menu_bar.addMenu("View")
        self._toggle_sidebar_action = QtGui.QAction("Collapse Sidebar", self)
        self._toggle_sidebar_action.setCheckable(True)
        self._toggle_sidebar_action.setChecked(True)
        self._toggle_sidebar_action.toggled.connect(self._handle_toggle_sidebar)
        view_menu.addAction(self._toggle_sidebar_action)

        viz_menu = view_menu.addMenu("Visualization Mode")
        self._visualization_action_group = QtGui.QActionGroup(self)
        self._visualization_action_group.setExclusive(True)

        auto_action = QtGui.QAction("Auto", self)
        auto_action.setCheckable(True)
        auto_action.setChecked(True)
        auto_action.setData(None)
        viz_menu.addAction(auto_action)
        self._visualization_action_group.addAction(auto_action)

        for handler in self._viz_registry.handlers():
            action = QtGui.QAction(handler.label, self)
            action.setCheckable(True)
            action.setData(handler.visualization)
            viz_menu.addAction(action)
            self._visualization_action_group.addAction(action)

        self._visualization_action_group.triggered.connect(self._handle_visualization_action)

    def _refresh_recent_sessions_menu(self) -> None:
        if not self._recent_sessions_menu:
            return
        self._recent_sessions = self._sanitize_recent_sessions(self._recent_sessions)
        menu = self._recent_sessions_menu
        menu.clear()
        if not self._recent_sessions:
            action = menu.addAction("No previous sessions")
            action.setEnabled(False)
            return
        for index, session in enumerate(self._recent_sessions):
            action = menu.addAction(self._session_label(session))
            action.triggered.connect(
                lambda _checked=False, idx=index: self._open_recent_session(idx)
            )
        menu.addSeparator()
        clear_action = menu.addAction("Clear History")
        clear_action.triggered.connect(self._clear_recent_sessions)

    def _clear_recent_sessions(self) -> None:
        self._recent_sessions = []
        self._refresh_recent_sessions_menu()
        state = self._current_session_snapshot()
        state["recent_sessions"] = []
        self._state_manager.save(state)

    def _session_label(self, session: Dict[str, Any]) -> str:
        card_file = session.get("card_file")
        if isinstance(card_file, str):
            path = Path(card_file)
            return f"Card: {path.name} ({self._format_path(path.parent)})"
        card_dir = session.get("card_dir")
        if isinstance(card_dir, str):
            return f"Cards: {self._format_path(Path(card_dir))}"
        data_dir = session.get("data_dir")
        if isinstance(data_dir, str):
            return f"Data: {self._format_path(Path(data_dir))}"
        data_file = session.get("data_file")
        if isinstance(data_file, str):
            path = Path(data_file)
            return f"File: {path.name} ({self._format_path(path.parent)})"
        return "Previous Session"

    def _open_recent_session(self, index: int) -> None:
        if index < 0 or index >= len(self._recent_sessions):
            return
        normalized = self._normalize_session_entry(self._recent_sessions[index])
        if not normalized:
            self._recent_sessions = self._sanitize_recent_sessions(self._recent_sessions)
            self._refresh_recent_sessions_menu()
            self._set_status_message("Selected previous session is no longer available.")
            return
        self._apply_session_snapshot(normalized)
        self._remember_recent_session(normalized)
        self._refresh_recent_sessions_menu()
        self._set_status_message("Loaded previous session.")

    def _apply_session_snapshot(self, snapshot: Dict[str, Any]) -> None:
        self._clear_card_selection()
        self._reset_data_state()
        self._data_dir = None
        self._cards_dir = None
        self._controller.set_cards_dir(None)
        self._card_loader = self._controller.card_loader
        self._card_list.clear()
        self._pending_card_file = None
        self._pending_card_selection = None
        self._pending_data_file = None
        self._added_files.clear()

        self._restore_snapshot_fields(snapshot)
        self._load_initial_sources()
        self._sync_initial_view_state()
        self._update_sidebar_mode()

    def _restore_snapshot_fields(self, snapshot: Dict[str, Any]) -> None:
        data_dir = snapshot.get("data_dir")
        card_file = snapshot.get("card_file")
        card_dir = snapshot.get("card_dir")
        data_file = snapshot.get("data_file")
        card_selection = self._normalize_card_selection(snapshot.get("card_selection"))
        added_files = snapshot.get("added_files", [])
        if isinstance(data_dir, str):
            path = Path(data_dir)
            if path.exists():
                self._data_dir = path
        if isinstance(added_files, list):
            for file_path in added_files:
                if not isinstance(file_path, str):
                    continue
                path = Path(file_path)
                if path.exists():
                    self._added_files.add(path)
        card_file_restored = False
        if isinstance(card_file, str):
            path = Path(card_file)
            if path.exists():
                self._pending_card_selection = card_selection or None
                self._pending_card_file = path
                self._set_card_loader(path.parent, select_card=path)
                card_file_restored = True
        if not card_file_restored and isinstance(card_dir, str):
            self._pending_card_selection = None
            path = Path(card_dir)
            if path.exists() and path.is_dir():
                self._set_card_loader(path)
        if isinstance(data_file, str):
            path = Path(data_file)
            if path.exists():
                self._pending_data_file = path

    def _remember_recent_session(self, session: Dict[str, Any]) -> None:
        if not session:
            return
        sessions = [session]
        incoming_key = self._session_key(session)
        for existing in self._recent_sessions:
            if self._session_key(existing) == incoming_key:
                continue
            sessions.append(existing)
            if len(sessions) >= self._MAX_RECENT_SESSIONS:
                break
        self._recent_sessions = sessions

    def _session_key(self, session: Dict[str, Any]) -> tuple:
        return (
            session.get("data_dir"),
            session.get("data_file"),
            session.get("card_dir"),
            session.get("card_file"),
            tuple(session.get("added_files", [])) if isinstance(session.get("added_files"), list) else (),
        )

    def _sanitize_recent_sessions(self, entries: object) -> List[Dict[str, Any]]:
        if not isinstance(entries, list):
            return []
        sanitized: List[Dict[str, Any]] = []
        seen: set[tuple] = set()
        for entry in entries:
            if not isinstance(entry, dict):
                continue
            normalized = self._normalize_session_entry(entry)
            if not normalized:
                continue
            key = self._session_key(normalized)
            if key in seen:
                continue
            seen.add(key)
            sanitized.append(normalized)
            if len(sanitized) >= self._MAX_RECENT_SESSIONS:
                break
        return sanitized

    def _normalize_session_entry(self, entry: Dict[str, Any]) -> Dict[str, Any] | None:
        normalized: Dict[str, Any] = {}

        data_dir = entry.get("data_dir")
        if isinstance(data_dir, str):
            path = Path(data_dir).expanduser().resolve()
            if path.is_dir() and self._repository.list_datasets(path):
                normalized["data_dir"] = str(path)

        data_file = entry.get("data_file")
        if isinstance(data_file, str):
            path = Path(data_file).expanduser().resolve()
            if path.is_file():
                normalized["data_file"] = str(path)

        card_file = entry.get("card_file")
        if isinstance(card_file, str):
            path = Path(card_file).expanduser().resolve()
            if path.is_file():
                normalized["card_file"] = str(path)

        card_dir = entry.get("card_dir")
        if isinstance(card_dir, str):
            path = Path(card_dir).expanduser().resolve()
            if path.is_dir() and any(path.glob("*.toml")):
                normalized["card_dir"] = str(path)

        added_files = entry.get("added_files", [])
        if isinstance(added_files, list):
            valid_added = []
            for raw in added_files:
                if not isinstance(raw, str):
                    continue
                path = Path(raw).expanduser().resolve()
                if path.is_file():
                    valid_added.append(str(path))
            if valid_added:
                normalized["added_files"] = valid_added

        card_selection = self._normalize_card_selection(entry.get("card_selection"))
        if card_selection:
            normalized["card_selection"] = card_selection

        if "card_file" in normalized and "card_dir" not in normalized:
            normalized["card_dir"] = str(Path(normalized["card_file"]).parent)

        if not normalized:
            return None
        return normalized

    def _normalize_card_selection(self, selection: object) -> Dict[str, str]:
        if not isinstance(selection, dict):
            return {}
        normalized: Dict[str, str] = {}
        for variable, value in selection.items():
            if not isinstance(variable, str) or not isinstance(value, str):
                continue
            if not variable or not value:
                continue
            normalized[variable] = value
        return normalized

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
        if not self._card_session and self._pending_data_file:
            if self._pending_data_file.exists():
                self._add_file_to_list(self._pending_data_file)
                row = self._find_file_row(self._pending_data_file)
                if row >= 0:
                    self._file_list.setCurrentRow(row)
                    self._handle_file_selection()
            self._pending_data_file = None
        if not self._data_dir and not self._pending_card_file:
            self._set_status_message(None)
        if not self._repository.schema_validation_enabled:
            self._set_warning(
                "JSON schema validation is disabled (jsonschema not installed); JSON payloads are only lightly validated."
            )
        else:
            self._set_warning(None)
        self._update_sidebar_mode()
        self._update_loaded_files()
        self._refresh_recent_sessions_menu()

    def _sync_initial_view_state(self) -> None:
        if self._pending_card_file:
            return
        if self._card_session:
            self._render_current_card_selection()
            return
        if self._current_path and self._current_dataset:
            self._load_and_render(self._current_path)

    def _set_status_message(self, message: str | None) -> None:
        if not self._status_label:
            return
        text = message if message else "All good."
        self._status_label.setText(text)
        self._status_label.setVisible(True)

    def _handle_toggle_sidebar(self, checked: bool) -> None:
        if not self._view:
            return
        self._view.controls.set_collapsed(not checked)
        self._update_sidebar_toggle_icon()
        if self._toggle_sidebar_action:
            self._toggle_sidebar_action.setText("Collapse Sidebar" if checked else "Expand Sidebar")

    def _handle_sidebar_toggle_button(self) -> None:
        if self._toggle_sidebar_action:
            self._toggle_sidebar_action.setChecked(not self._toggle_sidebar_action.isChecked())

    def _handle_visualization_action(self, action: QtGui.QAction) -> None:
        data = action.data()
        self._visualization_override = data if isinstance(data, VisualizationType) else None
        self._handle_visualization_change()

    def _handle_list_navigation_shortcut(self, step: int) -> None:
        if self._sidebar_mode == "card":
            self._handle_card_list_step(step)
        else:
            self._handle_file_list_step(step)

    def _update_sidebar_mode(self) -> None:
        if not self._list_stack or not self._mode_label:
            return
        has_cards = bool(self._cards_dir or self._card_list.count())
        has_data = bool(self._data_dir or self._file_list.count() or self._added_files)
        if self._controls:
            self._controls.set_empty_state(not has_cards and not has_data)
        mode = self._sidebar_mode
        if mode == "card" and not has_cards:
            mode = "data"
        if mode == "data" and not has_data and has_cards:
            mode = "card"
        self._set_sidebar_mode(mode)

    def _set_sidebar_mode(self, mode: str) -> None:
        if not self._list_stack or not self._mode_label:
            return
        self._sidebar_mode = mode
        if mode == "card":
            self._list_stack.setCurrentWidget(self._card_list)
            self._mode_label.setText("Cards")
            if self._add_file_button:
                self._add_file_button.setVisible(False)
        else:
            self._list_stack.setCurrentWidget(self._file_list)
            self._mode_label.setText("Data Files")
            if self._add_file_button:
                self._add_file_button.setVisible(True)
        self._update_source_label(mode)

    def _update_source_label(self, mode: str) -> None:
        if not self._source_label:
            return
        if mode == "card":
            if self._cards_dir:
                text = self._format_path(self._cards_dir)
            elif self._active_card_path:
                text = self._format_path(self._active_card_path)
            else:
                text = ""
        else:
            if self._data_dir:
                text = self._format_path(self._data_dir)
            else:
                text = ""
        if hasattr(self._source_label, "set_full_text"):
            self._source_label.set_full_text(text)  # type: ignore[call-arg]
        else:
            self._source_label.setText(text)

    def _update_loaded_files(self, paths: List[Path] | None = None) -> None:
        if not self._loaded_files_list:
            return
        self._loaded_files_list.clear()
        if paths is None:
            paths = []
        if not paths:
            self._loaded_files_list.addItem("No data loaded")
            return
        for path in paths:
            self._loaded_files_list.addItem(self._format_path(path))

    def _format_path(self, path: Path) -> str:
        raw = str(path)
        try:
            home = str(Path.home())
            if raw == home:
                return "~"
            if raw.startswith(home + "/"):
                return "~/" + raw[len(home) + 1 :]
        except Exception:
            pass
        return raw

    def _reset_data_state(self) -> None:
        self._file_list.clear()
        self._added_files.clear()
        self._current_dataset = None
        self._current_path = None
        self._pending_data_file = None
        self._update_loaded_files([])

    def _add_file_to_list(self, path: Path) -> None:
        for index in range(self._file_list.count()):
            existing_item = self._file_list.item(index)
            if existing_item.data(QtCore.Qt.UserRole) == path:
                return
        item = QtWidgets.QListWidgetItem(path.name)
        item.setData(QtCore.Qt.UserRole, path)
        self._file_list.addItem(item)
        self._added_files.add(path)

    def _find_file_row(self, path: Path) -> int:
        for index in range(self._file_list.count()):
            item = self._file_list.item(index)
            if item.data(QtCore.Qt.UserRole) == path:
                return index
        return -1

    def _refresh_file_list(self) -> None:
        self._file_list.clear()
        if not self._data_dir:
            self._update_source_label("data")
            return
        self._update_source_label("data")
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
                self._sidebar_mode = "data"
                self._update_sidebar_mode()

    def _handle_choose_folder(self) -> None:
        dialog = QtWidgets.QFileDialog(self)
        dialog.setFileMode(QtWidgets.QFileDialog.Directory)
        dialog.setOption(QtWidgets.QFileDialog.ShowDirsOnly, True)
        if dialog.exec():
            folders = dialog.selectedFiles()
            if folders:
                self._clear_card_selection()
                self._reset_data_state()
                self._data_dir = Path(folders[0])
                self._refresh_file_list()
                self._sidebar_mode = "data"
                self._update_sidebar_mode()

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
                self._reset_data_state()
                self._data_dir = None
                card_path = Path(files[0])
                self._set_card_loader(card_path.parent, select_card=card_path)
                self._update_sidebar_mode()

    def _handle_file_selection(self) -> None:
        selected_items = self._file_list.selectedItems()
        if not selected_items:
            return
        self._sidebar_mode = "data"
        self._clear_card_selection()
        path = selected_items[0].data(QtCore.Qt.UserRole)
        if path:
            self._load_and_render(Path(path))
        self._update_sidebar_mode()

    def _handle_visualization_change(self) -> None:
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
        self._set_status_message(None)

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

    def _activate_card(
        self, card_path: Path, preferred_selection: Dict[str, str] | None = None
    ) -> None:
        selection = preferred_selection
        if selection is None and self._pending_card_selection:
            selection = dict(self._pending_card_selection)
        elif selection is None and self._last_variable_values:
            selection = dict(self._last_variable_values)
        try:
            self._sidebar_mode = "card"
            session = self._controller.activate_card(
                card_path,
                preferred_selection=selection,
            )
            self._card_loader = self._controller.card_loader
            if not session.has_paths():
                self._card_session = None
                self._set_status_message("Card has no matching datasets.")
                self._update_navigation_buttons()
                self._variable_group.setVisible(False)
                self._panel_manager.clear(self._multi_plot_layout)
                self._update_loaded_files([])
                return
            self._card_session = session
            self._active_card_path = card_path
            self._panel_overrides.clear()
            self._panel_axis_visibility.clear()
            self._update_navigation_buttons()
            self._populate_variable_controls()
            self._render_current_card_selection()
            self._update_last_variable_values(session)
            self._update_sidebar_mode()
        except Exception as exc:  # pragma: no cover - GUI feedback
            self._card_session = None
            self._set_status_message(f"Card error: {exc}")
            self._update_navigation_buttons()
            self._variable_group.setVisible(False)
            self._panel_manager.clear(self._multi_plot_layout)
            self._active_card_path = None
            self._update_loaded_files([])
            self._update_sidebar_mode()
        finally:
            self._pending_card_selection = None

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
            self._set_status_message(f"Card error: {exc}")
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
        if event.key() in (QtCore.Qt.Key_Up, QtCore.Qt.Key_Down):
            step = -1 if event.key() == QtCore.Qt.Key_Up else 1
            if self._sidebar_mode == "card":
                handled = self._handle_card_list_step(step)
            else:
                handled = self._handle_file_list_step(step)
            if handled:
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
        self._panel_axis_visibility.clear()
        self._panel_manager.clear(self._multi_plot_layout)
        self._plot_stack.setCurrentWidget(self._single_plot_widget)
        self._active_card_path = None
        self._pending_card_file = None
        self._update_loaded_files([])

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
        self._sidebar_mode = "card"
        self._update_source_label("card")
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
            self._pending_card_selection = None
        self._update_sidebar_mode()

    def _restore_state(self) -> None:
        self._recent_sessions = self._sanitize_recent_sessions(
            self._saved_state.get("recent_sessions", [])
        )
        current_snapshot = self._normalize_session_entry(self._saved_state)
        if current_snapshot:
            self._restore_snapshot_fields(current_snapshot)
            self._remember_recent_session(current_snapshot)

    def _save_state(self) -> None:
        state = self._current_session_snapshot()
        self._remember_recent_session(state)
        state["recent_sessions"] = self._recent_sessions
        self._refresh_recent_sessions_menu()
        self._state_manager.save(state)

    def _current_session_snapshot(self) -> Dict[str, Any]:
        snapshot: Dict[str, Any] = {}
        if self._data_dir and self._data_dir.exists():
            snapshot["data_dir"] = str(self._data_dir.resolve())
        if self._current_path and self._current_path.exists():
            snapshot["data_file"] = str(self._current_path.resolve())
        if self._active_card_path and self._active_card_path.exists():
            snapshot["card_file"] = str(self._active_card_path.resolve())
            if self._card_session and self._card_session.selection:
                snapshot["card_selection"] = dict(self._card_session.selection)
        elif self._pending_card_file and self._pending_card_file.exists():
            snapshot["card_file"] = str(self._pending_card_file.resolve())
        if self._cards_dir and self._cards_dir.exists():
            snapshot["card_dir"] = str(self._cards_dir.resolve())
        extras = [str(path.resolve()) for path in self._added_files if path.exists()]
        if extras:
            snapshot["added_files"] = extras
        normalized = self._normalize_session_entry(snapshot)
        return normalized or {}

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
            self._set_status_message(None)
            self._update_loaded_files([path])
        except Exception as exc:  # pragma: no cover - GUI feedback
            self._set_status_message(f"Error: {exc}")
            self._update_loaded_files([])

    def _resolve_visualization_override(
        self,
        card_style: ChartStyle | None = None,
        panel_override: VisualizationType | None = None,
    ) -> VisualizationType | None:
        if panel_override:
            return panel_override
        if self._visualization_override:
            return self._visualization_override
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
        dataset: DataPayload,
        path: Path,
        card_style: Optional[ChartStyle],
        panel_override: VisualizationType | None = None,
    ) -> None:
        override = self._resolve_visualization_override(
            card_style=card_style,
            panel_override=panel_override,
        )
        style_params = card_style.params if card_style else None
        spec = self._interpreter.build_spec(
            dataset,
            override=override,
            style_params=style_params,
        )
        if not isinstance(spec, PlotSpec):
            return
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
        axis_visibility = self._panel_axis_visibility.get(subcard_name, (None, None))
        show_x_axis, show_y_axis = axis_visibility
        if table:
            self._render_table_panel(subcard_name, table, data or [])
            return
        if not plot:
            return
        if not data:
            self._renderer.reset_widget(plot)
            self._renderer.apply_axis_visibility(plot, show_x_axis, show_y_axis)
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
            style_params = default_style.params if default_style else None
            specs.append(
                self._interpreter.build_spec(
                    dataset,
                    override=viz,
                    label=label,
                    style_params=style_params,
                )
            )
        if not specs:
            plot.clear()
            self._renderer.apply_axis_visibility(plot, show_x_axis, show_y_axis)
        elif len(specs) == 1:
            self._renderer.render(plot, specs[0], show_x_axis=show_x_axis, show_y_axis=show_y_axis)
        else:
            try:
                self._renderer.render_multiple(
                    plot, specs, show_x_axis=show_x_axis, show_y_axis=show_y_axis
                )
            except ValueError as exc:
                # Incompatible overlay (e.g., mixing 1D and 2D plots); render first spec and surface message.
                self._renderer.render(plot, specs[0], show_x_axis=show_x_axis, show_y_axis=show_y_axis)
                self._set_status_message(str(exc))

    def _render_table_panel(
        self,
        subcard_name: str,
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
        table_style_override = self._resolve_table_style_override(subcard_name)
        spec = self._interpreter.build_table_spec(
            dataset,
            label=label,
            table_style_global_override=table_style_override,
        )
        self._table_renderer.render(view, spec)

    def _resolve_table_style_override(self, subcard_name: str) -> TableColorRule | None:
        session = self._controller.card_session
        if not session:
            return None
        subcard = next(
            (candidate for candidate in session.definition.subcards if candidate.name == subcard_name),
            None,
        )
        if subcard and subcard.table_style is not None:
            return subcard.table_style
        return session.definition.table_style

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

    def _handle_file_list_step(self, step: int) -> bool:
        count = self._file_list.count()
        if count == 0:
            return False
        current = self._file_list.currentRow()
        if current < 0:
            next_row = 0 if step >= 0 else count - 1
        else:
            next_row = max(0, min(count - 1, current + step))
        if next_row == current:
            return True
        self._file_list.setCurrentRow(next_row)
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
            self._set_status_message(f"Card selection error: {exc}")

    def _render_current_card_selection(self) -> None:
        session = self._controller.card_session
        if not session:
            return
        try:
            plans, missing, incompatible = self._controller.build_panel_plans()
        except Exception as exc:  # pragma: no cover - GUI feedback
            self._set_status_message(f"Card error: {exc}")
            self._show_error_dialog("Card error", str(exc))
            return

        self._card_session = session
        if not plans:
            self._set_status_message("Card selection has no matching datasets.")
            self._update_loaded_files([])
            return

        active_names = {plan.subcard.name for plan in plans}
        for name in list(self._panel_overrides.keys()):
            if name not in active_names:
                self._panel_overrides.pop(name, None)
        for name in list(self._panel_axis_visibility.keys()):
            if name not in active_names:
                self._panel_axis_visibility.pop(name, None)

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
            self._panel_axis_visibility[plan.subcard.name] = self._resolve_axis_visibility(
                plan.subcard, panel_kind
            )
            panels.append((plan.subcard, entries, plan.paths, panel_kind))

        panel_names = [plan.subcard.name for plan in plans]
        kind_mismatch = any(
            panel_kind != self._panel_manager.panel_kind_by_name(subcard.name)
            for subcard, _entries, _paths, panel_kind in panels
        )
        if panel_names != self._panel_order or kind_mismatch:
            warning = self._build_panel_layout(panels)
        else:
            warning = self._update_existing_panels(panels)
        if session.definition.synchronize_axis:
            self._panel_manager.synchronize_x_axes()
        warning_bits = []
        if warning:
            warning_bits.append(warning)
        if panel_warnings:
            warning_bits.extend(panel_warnings)
        if missing:
            warning_bits.append(f"missing: {', '.join(missing)}")
        if incompatible:
            warning_bits.append(f"incompatible: {', '.join(incompatible)}")
        if warning_bits:
            self._set_status_message("; ".join(warning_bits))
        else:
            self._set_status_message(None)
        unique_paths = []
        seen = set()
        for _subcard, _entries, paths, _kind in panels:
            for path in paths:
                if path not in seen:
                    seen.add(path)
                    unique_paths.append(path)
        self._update_loaded_files(unique_paths)

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

    def _resolve_axis_visibility(
        self, subcard: SubcardDefinition, panel_kind: str
    ) -> tuple[bool | None, bool | None]:
        session = self._controller.card_session
        if not session or panel_kind == "table":
            return None, None
        card_def = session.definition
        show_x = (
            subcard.show_x_axis
            if subcard.show_x_axis is not None
            else card_def.show_x_axis
        )
        show_y = (
            subcard.show_y_axis
            if subcard.show_y_axis is not None
            else card_def.show_y_axis
        )
        if show_x is None:
            show_x = False if card_def.synchronize_axis else True
        if show_y is None:
            show_y = True
        return show_x, show_y

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
