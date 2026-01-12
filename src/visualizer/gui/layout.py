from __future__ import annotations

from PySide6 import QtCore, QtGui, QtWidgets
import pyqtgraph as pg

from visualizer.viz.table_renderer import TableView


class ControlsPanel(QtWidgets.QWidget):
    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self.setFixedWidth(320)
        layout = QtWidgets.QVBoxLayout(self)

        layout.addWidget(QtWidgets.QLabel("Data Folder"))
        self.data_dir_label = QtWidgets.QLabel("No folder selected")
        layout.addWidget(self.data_dir_label)
        self.choose_folder_button = QtWidgets.QPushButton("Choose Data Folder…")
        layout.addWidget(self.choose_folder_button)

        layout.addWidget(QtWidgets.QLabel("Cards"))
        self.cards_dir_label = QtWidgets.QLabel("No card folder selected")
        layout.addWidget(self.cards_dir_label)
        self.choose_card_file_button = QtWidgets.QPushButton("Open Card File…")
        layout.addWidget(self.choose_card_file_button)

        self.file_list = QtWidgets.QListWidget()
        layout.addWidget(QtWidgets.QLabel("Available Data Files"))
        layout.addWidget(self.file_list)

        self.add_file_button = QtWidgets.QPushButton("Add File…")
        layout.addWidget(self.add_file_button)

        self.visualization_combo = QtWidgets.QComboBox()
        layout.addWidget(QtWidgets.QLabel("Visualization Mode"))
        layout.addWidget(self.visualization_combo)

        self.variable_group = QtWidgets.QGroupBox("Card Variables")
        self.variable_form_layout = QtWidgets.QFormLayout()
        self.variable_group.setLayout(self.variable_form_layout)
        self.variable_group.setVisible(False)
        layout.addWidget(self.variable_group)

        self.card_list = QtWidgets.QListWidget()
        layout.addWidget(self.card_list)

        navigation_layout = QtWidgets.QHBoxLayout()
        self.prev_view_button = QtWidgets.QPushButton("Prev View")
        self.next_view_button = QtWidgets.QPushButton("Next View")
        navigation_layout.addWidget(self.prev_view_button)
        navigation_layout.addWidget(self.next_view_button)
        layout.addLayout(navigation_layout)

        self.reset_view_button = QtWidgets.QPushButton("Reset View")
        layout.addWidget(self.reset_view_button)

        layout.addStretch()


class VisualizationPanel(QtWidgets.QWidget):
    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self.plot_stack = QtWidgets.QStackedWidget()
        self.single_plot_widget = pg.PlotWidget()
        self.plot_stack.addWidget(self.single_plot_widget)

        self.single_table_widget = TableView()
        self.plot_stack.addWidget(self.single_table_widget)

        self.multi_plot_container = QtWidgets.QWidget()
        self.multi_plot_layout = QtWidgets.QVBoxLayout(self.multi_plot_container)
        self.multi_plot_layout.setContentsMargins(0, 0, 0, 0)
        self.multi_plot_layout.setSpacing(0)
        self.plot_stack.addWidget(self.multi_plot_container)

        layout.addWidget(self.plot_stack)


class StatusPanel(QtWidgets.QWidget):
    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self.title_label = QtWidgets.QLabel("")
        self.title_label.setAlignment(QtCore.Qt.AlignCenter)
        self.title_label.setStyleSheet("font-weight: bold;")
        layout.addWidget(self.title_label)

        self.status_label = QtWidgets.QLabel("Select a dataset to visualize.")
        self.status_label.setWordWrap(True)
        self.status_label.setFrameShape(QtWidgets.QFrame.Panel)
        self.status_label.setFrameShadow(QtWidgets.QFrame.Sunken)
        self.status_label.setContentsMargins(8, 4, 8, 4)
        self.status_label.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
        self.status_label.customContextMenuRequested.connect(self._show_status_context_menu)
        self.status_label.installEventFilter(self)
        layout.addWidget(self.status_label)

        self.warning_label = QtWidgets.QLabel("")
        self.warning_label.setStyleSheet("color: #b58900;")
        self.warning_label.setWordWrap(True)
        self.warning_label.setVisible(False)
        layout.addWidget(self.warning_label)

    def set_title(self, title: str) -> None:
        self.title_label.setText(title)

    def set_status(self, message: str) -> None:
        self.status_label.setText(message)

    def status_text(self) -> str:
        return self.status_label.text()

    def set_warning(self, message: str | None) -> None:
        if message:
            self.warning_label.setText(message)
            self.warning_label.setVisible(True)
        else:
            self.warning_label.clear()
            self.warning_label.setVisible(False)

    def eventFilter(self, obj: QtCore.QObject, event: QtCore.QEvent) -> bool:  # type: ignore[override]
        if obj is self.status_label and event.type() == QtCore.QEvent.MouseButtonPress:
            if isinstance(event, QtGui.QMouseEvent) and event.button() == QtCore.Qt.LeftButton:
                self._show_status_context_menu(event.pos())
                return True
        return super().eventFilter(obj, event)

    def _show_status_context_menu(self, pos: QtCore.QPoint) -> None:
        menu = QtWidgets.QMenu(self)
        copy_action = menu.addAction("Copy message")
        copy_action.triggered.connect(self._copy_status_to_clipboard)
        global_pos = self.status_label.mapToGlobal(pos)
        menu.exec(global_pos)

    def _copy_status_to_clipboard(self) -> None:
        clipboard = QtWidgets.QApplication.clipboard()
        if clipboard:
            clipboard.setText(self.status_label.text())


class MainWindowView(QtWidgets.QWidget):
    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QtWidgets.QVBoxLayout(self)

        content_layout = QtWidgets.QHBoxLayout()
        layout.addLayout(content_layout)

        self.controls = ControlsPanel(self)
        self.visualization = VisualizationPanel(self)
        self.status_panel = StatusPanel(self)

        content_layout.addWidget(self.controls)
        content_layout.addWidget(self.visualization, 3)
        layout.addWidget(self.status_panel)
