from __future__ import annotations

from dataclasses import dataclass, field
from types import MethodType
from typing import Callable

import pyqtgraph as pg


@dataclass(frozen=True)
class ItemInteraction:
    hover_text: str | None = None


class _HoverInfoBox(pg.QtWidgets.QFrame):
    """Floating hover info container styled through the main application stylesheet."""

    def __init__(self, parent: pg.QtWidgets.QWidget) -> None:
        super().__init__(parent)
        self.setObjectName("plotHoverInfoBox")
        self.setAttribute(pg.QtCore.Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self.setFocusPolicy(pg.QtCore.Qt.FocusPolicy.NoFocus)
        self.hide()

        layout = pg.QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(8, 6, 8, 6)
        layout.setSpacing(0)

        self._label = pg.QtWidgets.QLabel(self)
        self._label.setObjectName("plotHoverInfoLabel")
        self._label.setTextFormat(pg.QtCore.Qt.TextFormat.PlainText)
        self._label.setWordWrap(True)
        self._label.setAlignment(
            pg.QtCore.Qt.AlignmentFlag.AlignLeft | pg.QtCore.Qt.AlignmentFlag.AlignVCenter
        )
        layout.addWidget(self._label)

    def set_text(self, text: str) -> None:
        parent = self.parentWidget()
        max_width = 260
        if parent is not None and parent.width() > 0:
            max_width = max(160, min(320, parent.width() - 24))
        self._label.setMaximumWidth(max_width)
        self._label.setText(text)
        self.adjustSize()

    def move_near(self, global_pos: pg.QtCore.QPoint | pg.QtCore.QPointF) -> None:
        parent = self.parentWidget()
        if parent is None:
            return
        point = self._as_global_point(global_pos)
        local = parent.mapFromGlobal(point)
        target = local + pg.QtCore.QPoint(14, 18)
        bounds = parent.rect().adjusted(6, 6, -6, -6)
        max_x = max(bounds.left(), bounds.right() - self.width())
        max_y = max(bounds.top(), bounds.bottom() - self.height())
        self.move(
            min(max(target.x(), bounds.left()), max_x),
            min(max(target.y(), bounds.top()), max_y),
        )

    def text(self) -> str:
        return self._label.text()

    @staticmethod
    def _as_global_point(point: pg.QtCore.QPoint | pg.QtCore.QPointF) -> pg.QtCore.QPoint:
        if isinstance(point, pg.QtCore.QPoint):
            return point
        return pg.QtCore.QPoint(round(point.x()), round(point.y()))


@dataclass
class _InteractiveItemBinding:
    item: pg.QtWidgets.QGraphicsItem
    original_hover_event: Callable | None = None


class _HoverViewportFilter(pg.QtCore.QObject):
    def __init__(self, manager: InteractionManager, widget: pg.PlotWidget) -> None:
        super().__init__(widget)
        self._manager = manager
        self._widget = widget

    def eventFilter(self, watched: object, event: pg.QtCore.QEvent | None) -> bool:  # noqa: N802
        if event is None:
            return False
        event_type = event.type()
        if event_type in (
            pg.QtCore.QEvent.Type.Leave,
            pg.QtCore.QEvent.Type.Hide,
            pg.QtCore.QEvent.Type.WindowDeactivate,
        ):
            self._manager._hide_hover_box(self._widget)
        elif event_type == pg.QtCore.QEvent.Type.Resize:
            self._manager._reposition_hover_box(self._widget)
        return False


@dataclass
class _WidgetInteractionState:
    hover_box: _HoverInfoBox
    event_filter: _HoverViewportFilter
    bindings: list[_InteractiveItemBinding] = field(default_factory=list)
    last_global_pos: pg.QtCore.QPoint | None = None


class InteractionManager:
    """Attach and clear per-item interactions in a widget-scoped way."""

    def __init__(self) -> None:
        self._widget_states: dict[int, _WidgetInteractionState] = {}

    def clear_widget(self, widget: pg.PlotWidget) -> None:
        state = self._widget_states.get(id(widget))
        if state is None:
            return
        self._hide_hover_box(widget)
        for binding in state.bindings:
            try:
                binding.item.setToolTip("")
            except Exception:
                pass
            if binding.original_hover_event is None:
                continue
            try:
                binding.item.hoverEvent = binding.original_hover_event
            except Exception:
                continue
        state.bindings.clear()

    def bind_item(
        self,
        widget: pg.PlotWidget,
        item: pg.QtWidgets.QGraphicsItem,
        interaction: ItemInteraction | None,
    ) -> None:
        if interaction is None or not interaction.hover_text:
            return
        tooltip = interaction.hover_text.strip()
        if not tooltip:
            return
        state = self._state_for_widget(widget)
        original_hover_event = getattr(item, "hoverEvent", None)
        if not callable(original_hover_event):
            try:
                item.setToolTip(tooltip)
            except Exception:
                pass
            state.bindings.append(_InteractiveItemBinding(item=item))
            return
        try:
            item.hoverEvent = MethodType(
                self._build_hover_wrapper(widget, tooltip, original_hover_event),
                item,
            )
        except Exception:
            try:
                item.setToolTip(tooltip)
            except Exception:
                pass
            state.bindings.append(_InteractiveItemBinding(item=item))
            return
        try:
            item.setToolTip("")
        except Exception:
            pass
        state.bindings.append(
            _InteractiveItemBinding(item=item, original_hover_event=original_hover_event)
        )

    def hover_box(self, widget: pg.PlotWidget) -> pg.QtWidgets.QFrame | None:
        state = self._widget_states.get(id(widget))
        return state.hover_box if state is not None else None

    def _state_for_widget(self, widget: pg.PlotWidget) -> _WidgetInteractionState:
        state = self._widget_states.get(id(widget))
        if state is not None:
            return state
        viewport = widget.viewport()
        hover_box = _HoverInfoBox(viewport)
        event_filter = _HoverViewportFilter(self, widget)
        viewport.installEventFilter(event_filter)
        state = _WidgetInteractionState(hover_box=hover_box, event_filter=event_filter)
        self._widget_states[id(widget)] = state
        widget.destroyed.connect(lambda _obj=None, key=id(widget): self._widget_states.pop(key, None))
        return state

    def _build_hover_wrapper(
        self,
        widget: pg.PlotWidget,
        tooltip: str,
        original_hover_event: Callable,
    ) -> Callable:
        def _hover_event(_item: pg.QtWidgets.QGraphicsItem, event: object) -> None:
            try:
                original_hover_event(event)
            finally:
                self._handle_hover_event(widget, tooltip, event)

        return _hover_event

    def _handle_hover_event(self, widget: pg.PlotWidget, tooltip: str, event: object) -> None:
        if self._is_exit_event(event):
            self._hide_hover_box(widget)
            return
        global_pos = self._event_global_pos(event)
        if global_pos is None:
            self._hide_hover_box(widget)
            return
        state = self._state_for_widget(widget)
        state.last_global_pos = global_pos
        state.hover_box.set_text(tooltip)
        state.hover_box.move_near(global_pos)
        state.hover_box.show()
        state.hover_box.raise_()

    def _hide_hover_box(self, widget: pg.PlotWidget) -> None:
        state = self._widget_states.get(id(widget))
        if state is None:
            return
        state.hover_box.hide()
        state.last_global_pos = None

    def _reposition_hover_box(self, widget: pg.PlotWidget) -> None:
        state = self._widget_states.get(id(widget))
        if state is None or not state.hover_box.isVisible() or state.last_global_pos is None:
            return
        state.hover_box.move_near(state.last_global_pos)

    @staticmethod
    def _is_exit_event(event: object) -> bool:
        is_exit = getattr(event, "isExit", None)
        return bool(callable(is_exit) and is_exit())

    @staticmethod
    def _event_global_pos(event: object) -> pg.QtCore.QPoint | None:
        screen_pos = getattr(event, "screenPos", None)
        if callable(screen_pos):
            point = screen_pos()
            if isinstance(point, pg.QtCore.QPoint):
                return point
            if isinstance(point, pg.QtCore.QPointF):
                return pg.QtCore.QPoint(round(point.x()), round(point.y()))
        return None
