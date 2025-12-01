from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from visualizer.cards.loader import CardLoader
from visualizer.cards.models import CardSession, ChartStyle, SeriesDefinition, SubcardDefinition
from visualizer.data.models import Dataset
from visualizer.data.repository import DatasetRepository


@dataclass(frozen=True)
class PanelSeries:
    dataset: Optional[Dataset]
    path: Path
    chart_style: ChartStyle | None
    label: Optional[str]


@dataclass(frozen=True)
class PanelPlan:
    subcard: SubcardDefinition
    series: List[PanelSeries]
    paths: List[Path]


class SessionController:
    """Headless orchestrator for card sessions and dataset loading."""

    def __init__(self, repository: DatasetRepository, cards_dir: Path | None = None) -> None:
        self._repository = repository
        self._cards_dir = cards_dir
        self._card_loader = CardLoader(cards_dir) if cards_dir else None
        self.card_session: CardSession | None = None
        self.active_card_path: Path | None = None

    @property
    def card_loader(self) -> CardLoader | None:
        return self._card_loader

    @property
    def cards_dir(self) -> Path | None:
        return self._cards_dir

    def set_cards_dir(self, cards_dir: Path | None) -> None:
        self._cards_dir = cards_dir
        self._card_loader = CardLoader(cards_dir) if cards_dir else None
        self.card_session = None
        self.active_card_path = None

    def list_cards(self) -> List[Path]:
        if not self._card_loader:
            return []
        return self._card_loader.list_card_files()

    def activate_card(self, card_path: Path) -> CardSession:
        if not self._card_loader:
            self.set_cards_dir(card_path.parent)
        if not self._card_loader:
            raise ValueError("No cards directory configured")
        definition = self._card_loader.load_definition(card_path)
        matches = self._card_loader.resolve_paths(definition)
        if not any(matches.values()):
            raise ValueError("Card has no matching datasets.")
        session = CardSession(definition=definition, matches=matches)
        self.card_session = session
        self.active_card_path = card_path
        return session

    def clear_card(self) -> None:
        self.card_session = None
        self.active_card_path = None

    def cycle_pivot(self, step: int) -> None:
        if not self.card_session:
            return
        self.card_session.cycle_pivot(step)

    def update_selection(self, variable: str, value: str) -> None:
        if not self.card_session:
            return
        self.card_session.update_selection(variable, value)

    def available_values(self, variable: str, constrained: bool = False) -> List[str]:
        if not self.card_session:
            return []
        return self.card_session.available_values(variable, constrained=constrained)

    def build_panel_plans(self) -> Tuple[List[PanelPlan], List[str]]:
        """Resolve the current card selection into datasets ready for rendering."""

        if not self.card_session:
            return [], []

        match_map = self.card_session.current_matches()
        plans: List[PanelPlan] = []
        missing: List[str] = []

        for subcard in self.card_session.definition.subcards:
            match = match_map.get(subcard.name)
            series_payloads: List[PanelSeries] = []
            panel_paths: List[Path] = []
            if not match:
                missing.append(subcard.name)
                plans.append(PanelPlan(subcard=subcard, series=series_payloads, paths=panel_paths))
                continue

            overlay_def = self.card_session.definition.overlay_panels.get(subcard.name)
            if overlay_def:
                overlay_series = self.card_session._build_overlay_series(
                    overlay_def,
                    match.variables,
                    fallback_style=subcard.chart_style,
                ).series
                series_defs = overlay_series
            else:
                series_defs = [
                    SeriesDefinition(
                        path=match.path,
                        chart_style=subcard.chart_style or self.card_session.definition.chart_style,
                    )
                ]

            for series_def in series_defs:
                panel_paths.append(series_def.path)
                try:
                    dataset = self._repository.load(series_def.path)
                except Exception as exc:
                    missing.append(f"{series_def.path.name} ({exc})")
                    series_payloads.append(
                        PanelSeries(
                            dataset=None,
                            path=series_def.path,
                            chart_style=series_def.chart_style,
                            label=series_def.label,
                        )
                    )
                    continue
                series_payloads.append(
                    PanelSeries(
                        dataset=dataset,
                        path=series_def.path,
                        chart_style=series_def.chart_style,
                        label=series_def.label,
                    )
                )

            plans.append(PanelPlan(subcard=subcard, series=series_payloads, paths=panel_paths))

        return plans, missing
