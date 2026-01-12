from __future__ import annotations

from PySide6 import QtCore, QtGui, QtWidgets
import pyqtgraph as pg

from visualizer.viz.table_renderer import TableView


class ElidedLabel(QtWidgets.QLabel):
    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self._full_text = ""
        self.setWordWrap(False)
        self.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Fixed)

    def set_full_text(self, text: str) -> None:
        self._full_text = text
        self.setToolTip(text)
        self._update_elision()

    def resizeEvent(self, event: QtGui.QResizeEvent) -> None:  # type: ignore[override]
        super().resizeEvent(event)
        self._update_elision()

    def _update_elision(self) -> None:
        available = self._available_width()
        if available <= 0:
            super().setText("")
            return
        text = self._full_text or ""
        if not text:
            super().setText("")
            return
        fm = self.fontMetrics()
        if fm.horizontalAdvance(text) <= available:
            super().setText(text)
            return
        ellipsis = "..."
        ellipsis_width = fm.horizontalAdvance(ellipsis)
        if ellipsis_width >= available:
            super().setText(ellipsis if ellipsis_width <= available else "")
            return
        cut = self._binary_search_cut(text, available - ellipsis_width)
        super().setText(text[:cut] + ellipsis)

    def _available_width(self) -> int:
        margins = self.contentsMargins()
        return max(0, self.width() - margins.left() - margins.right())

    def _binary_search_cut(self, text: str, max_width: int) -> int:
        fm = self.fontMetrics()
        low, high = 0, len(text)
        while low < high:
            mid = (low + high) // 2
            if fm.horizontalAdvance(text[:mid]) <= max_width:
                low = mid + 1
            else:
                high = mid
        return max(0, low - 1)


class ControlsPanel(QtWidgets.QWidget):
    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self.setFixedWidth(320)
        self.setObjectName("sidebar")
        self._expanded_width = 320
        self._collapsed_width = 56
        self._collapsed = False
        self._empty_state_active = False
        layout = QtWidgets.QVBoxLayout(self)

        self.header_widget = QtWidgets.QWidget()
        header_layout = QtWidgets.QHBoxLayout(self.header_widget)
        self.source_label = ElidedLabel()
        self.source_label.setObjectName("sidebarPathLabel")
        header_layout.addWidget(self.source_label)
        self.sidebar_toggle_button = QtWidgets.QToolButton()
        self.sidebar_toggle_button.setObjectName("sidebarToggleButton")
        self.sidebar_toggle_button.setAutoRaise(True)
        self.sidebar_toggle_button.setIcon(self.style().standardIcon(QtWidgets.QStyle.SP_TitleBarMenuButton))
        self.sidebar_toggle_button.setIconSize(QtCore.QSize(22, 22))
        self.sidebar_toggle_button.setFixedSize(34, 34)
        self.sidebar_toggle_button.setText("")
        self.sidebar_toggle_button.setToolTip("Collapse sidebar")
        header_layout.addWidget(self.sidebar_toggle_button)
        layout.addWidget(self.header_widget)

        self.content_widget = QtWidgets.QWidget()
        content_layout = QtWidgets.QVBoxLayout(self.content_widget)
        content_layout.setContentsMargins(0, 0, 0, 0)

        self.mode_label = QtWidgets.QLabel("Data Files")
        self.mode_label.setObjectName("sidebarModeLabel")
        content_layout.addWidget(self.mode_label)

        self.list_stack = QtWidgets.QStackedWidget()
        self.file_list = QtWidgets.QListWidget()
        self.card_list = QtWidgets.QListWidget()
        self.list_stack.addWidget(self.file_list)
        self.list_stack.addWidget(self.card_list)
        content_layout.addWidget(self.list_stack)

        self.add_file_button = QtWidgets.QPushButton("Add File…")
        content_layout.addWidget(self.add_file_button)

        self.variable_group = QtWidgets.QGroupBox("Card Variables")
        self.variable_group.setObjectName("cardVariablesGroup")
        self.variable_form_layout = QtWidgets.QFormLayout()
        self.variable_group.setLayout(self.variable_form_layout)
        self.variable_group.setVisible(False)
        content_layout.addWidget(self.variable_group)

        navigation_layout = QtWidgets.QHBoxLayout()
        self.prev_view_button = QtWidgets.QPushButton("Prev View")
        self.next_view_button = QtWidgets.QPushButton("Next View")
        navigation_layout.addWidget(self.prev_view_button)
        navigation_layout.addWidget(self.next_view_button)
        content_layout.addLayout(navigation_layout)

        self.reset_view_button = QtWidgets.QPushButton("Reset View")
        content_layout.addWidget(self.reset_view_button)

        content_layout.addStretch()
        layout.addWidget(self.content_widget)

        self.empty_state_widget = QtWidgets.QWidget()
        empty_layout = QtWidgets.QVBoxLayout(self.empty_state_widget)
        empty_layout.setContentsMargins(0, 0, 0, 0)
        self.empty_data_button = QtWidgets.QPushButton("Open Data Folder…")
        self.empty_card_button = QtWidgets.QPushButton("Open Card File…")
        empty_layout.addWidget(self.empty_data_button)
        empty_layout.addWidget(self.empty_card_button)
        empty_layout.addStretch()
        self.empty_state_widget.setVisible(False)
        layout.addWidget(self.empty_state_widget)

        layout.addStretch()

    def set_collapsed(self, collapsed: bool) -> None:
        self._collapsed = collapsed
        self.setFixedWidth(self._collapsed_width if collapsed else self._expanded_width)
        self._apply_visibility()
        self.sidebar_toggle_button.setToolTip("Expand sidebar" if collapsed else "Collapse sidebar")

    def is_collapsed(self) -> bool:
        return self._collapsed

    def set_empty_state(self, active: bool) -> None:
        self._empty_state_active = active
        self._apply_visibility()
        if active:
            self.source_label.set_full_text("")

    def _apply_visibility(self) -> None:
        if self._collapsed:
            self.source_label.setVisible(False)
            self.mode_label.setVisible(False)
            self.content_widget.setVisible(False)
            self.empty_state_widget.setVisible(False)
            return
        self.source_label.setVisible(not self._empty_state_active)
        self.mode_label.setVisible(not self._empty_state_active)
        self.content_widget.setVisible(not self._empty_state_active)
        self.empty_state_widget.setVisible(self._empty_state_active)


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
        self.title_label.setObjectName("statusTitleLabel")
        layout.addWidget(self.title_label)

        self.status_label = QtWidgets.QLabel("Select a dataset to visualize.")
        self.status_label.setObjectName("statusLabel")
        self.status_label.setWordWrap(True)
        self.status_label.setFrameShape(QtWidgets.QFrame.Panel)
        self.status_label.setFrameShadow(QtWidgets.QFrame.Sunken)
        self.status_label.setContentsMargins(8, 4, 8, 4)
        self.status_label.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
        self.status_label.customContextMenuRequested.connect(self._show_status_context_menu)
        self.status_label.installEventFilter(self)
        layout.addWidget(self.status_label)

        self.warning_label = QtWidgets.QLabel("")
        self.warning_label.setObjectName("warningLabel")
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
