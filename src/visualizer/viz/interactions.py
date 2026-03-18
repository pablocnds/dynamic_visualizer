from __future__ import annotations

from dataclasses import dataclass

import pyqtgraph as pg


@dataclass(frozen=True)
class ItemInteraction:
    hover_text: str | None = None


class InteractionManager:
    """Attach and clear per-item interactions in a widget-scoped way."""

    def __init__(self) -> None:
        self._interactive_items: dict[int, list[pg.QtWidgets.QGraphicsItem]] = {}

    def clear_widget(self, widget: pg.PlotWidget) -> None:
        for item in self._interactive_items.pop(id(widget), []):
            try:
                item.setToolTip("")
            except Exception:
                continue

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
        try:
            item.setToolTip(tooltip)
        except Exception:
            return
        self._interactive_items.setdefault(id(widget), []).append(item)
