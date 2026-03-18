from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Iterable, List, Sequence

from visualizer.interpretation.specs import VisualizationType


@dataclass(frozen=True)
class VisualizationHandler:
    name: str
    label: str
    visualization: VisualizationType
    aliases: Sequence[str] = field(default_factory=tuple)


class VisualizationRegistry:
    """Central map of visualization names/aliases to handlers."""

    def __init__(self, handlers: Iterable[VisualizationHandler] | None = None) -> None:
        default_handlers = list(handlers) if handlers is not None else self._default_handlers()
        self._handlers: Dict[str, VisualizationHandler] = {}
        self._alias_map: Dict[str, str] = {}
        for handler in default_handlers:
            key = self._normalize(handler.name)
            self._handlers[key] = handler
            for alias in handler.aliases:
                alias_key = self._normalize(alias)
                self._alias_map[alias_key] = key

    def handler_for_name(self, name: str) -> VisualizationHandler:
        key = self._normalize(name)
        key = self._alias_map.get(key, key)
        if key not in self._handlers:
            raise ValueError(f"Unsupported visualization type: {name}")
        return self._handlers[key]

    def visualization_for_style(self, style_name: str) -> VisualizationType:
        return self.handler_for_name(style_name).visualization

    def handlers(self) -> List[VisualizationHandler]:
        return list(self._handlers.values())

    @staticmethod
    def _normalize(name: str) -> str:
        return name.strip().lower()

    @staticmethod
    def _default_handlers() -> List[VisualizationHandler]:
        return [
            VisualizationHandler(
                name="line",
                label="Line",
                visualization=VisualizationType.LINE,
                aliases=(),
            ),
            VisualizationHandler(
                name="scatter",
                label="Scatter",
                visualization=VisualizationType.SCATTER,
                aliases=(),
            ),
            VisualizationHandler(
                name="stick",
                label="Stick",
                visualization=VisualizationType.STICK,
                aliases=(),
            ),
            VisualizationHandler(
                name="colormap",
                label="Colormap (1D)",
                visualization=VisualizationType.COLORMAP,
                aliases=("colormap_line", "heatmap1d"),
            ),
            VisualizationHandler(
                name="eventline",
                label="Event Line (1D)",
                visualization=VisualizationType.EVENTLINE,
                aliases=("events", "spikes"),
            ),
            VisualizationHandler(
                name="ranges",
                label="Ranges (1D)",
                visualization=VisualizationType.RANGE,
                aliases=("range",),
            ),
        ]


_DEFAULT_REGISTRY: VisualizationRegistry | None = None


def get_default_registry() -> VisualizationRegistry:
    global _DEFAULT_REGISTRY
    if _DEFAULT_REGISTRY is None:
        _DEFAULT_REGISTRY = VisualizationRegistry()
    return _DEFAULT_REGISTRY


__all__ = ["VisualizationRegistry", "VisualizationHandler", "get_default_registry"]
