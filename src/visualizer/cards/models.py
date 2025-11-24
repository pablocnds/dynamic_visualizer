from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple


@dataclass(frozen=True)
class SubcardDefinition:
    name: str
    filepath_template: str
    variables: Tuple[str, ...]
    filepaths: List[str]
    chart_style: Optional[str] = None
    chart_height: Optional[float] = None


@dataclass(frozen=True)
class CardDefinition:
    path: Path
    subcards: Tuple[SubcardDefinition, ...]
    variables: Tuple[str, ...]
    chart_style: Optional[str] = None
    pivot_variable: Optional[str] = None
    overlay_panels: Dict[str, "OverlayDefinition"] = field(default_factory=dict)

    def has_subcards(self) -> bool:
        return bool(self.subcards)


@dataclass(frozen=True)
class CardMatch:
    path: Path
    variables: Dict[str, str]


@dataclass
class CardSession:
    definition: CardDefinition
    matches: Dict[str, List[CardMatch]]
    selection: Dict[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.variable_values: Dict[str, List[str]] = self._compute_variable_values()
        if not self.selection:
            self.selection = {
                var: values[0]
                for var, values in self.variable_values.items()
                if values
            }
        self._ensure_valid_selection()

    def has_paths(self) -> bool:
        return any(self.matches.values())

    def current_matches(self) -> Dict[str, CardMatch]:
        return self._ensure_valid_selection()

    def current_paths(self) -> Dict[str, Path]:
        matches = self.current_matches()
        return {name: match.path for name, match in matches.items()}

    def cycle_pivot(self, step: int) -> Dict[str, Path]:
        pivot = self.definition.pivot_variable
        if not pivot:
            raise ValueError("Card does not define a pivot variable")
        values = self.available_values(pivot, constrained=True)
        if not values:
            raise ValueError("No values available for pivot variable")
        current = self.selection.get(pivot, values[0])
        try:
            idx = values.index(current)
        except ValueError:
            idx = 0
        idx = (idx + step) % len(values)
        self.selection[pivot] = values[idx]
        return self.current_paths()

    def update_selection(self, variable: str, value: str) -> Dict[str, Path]:
        if variable not in self.definition.variables:
            raise ValueError(f"Unknown variable {variable}")
        self.selection[variable] = value
        return self.current_paths()

    def available_values(self, variable: str, constrained: bool = False) -> List[str]:
        if not constrained:
            return self.variable_values.get(variable, [])
        constraints = {
            var: val
            for var, val in self.selection.items()
            if var != variable
        }
        values = {
            match.variables.get(variable, "")
            for match_list in self.matches.values()
            for match in match_list
            if self._match_constraints(match.variables, constraints)
        }
        return sorted(v for v in values if v)

    def _compute_variable_values(self) -> Dict[str, List[str]]:
        value_map: Dict[str, set[str]] = {var: set() for var in self.definition.variables}
        for match_list in self.matches.values():
            for match in match_list:
                for var, value in match.variables.items():
                    if var in value_map and value:
                        value_map[var].add(value)
        return {var: sorted(values) for var, values in value_map.items()}

    def _match_constraints(self, values: Dict[str, str], constraints: Dict[str, str]) -> bool:
        for var, expected in constraints.items():
            actual = values.get(var)
            if actual is None:
                continue
            if actual != expected:
                return False
        return True

    def _ensure_valid_selection(self) -> Dict[str, CardMatch]:
        matches = self._collect_matches(self.selection)
        if matches:
            return matches
        pivot = self.definition.pivot_variable
        if pivot:
            for value in self.available_values(pivot, constrained=True):
                self.selection[pivot] = value
                matches = self._collect_matches(self.selection)
                if matches:
                    return matches
        raise ValueError("No dataset matches the current card selection")

    def _collect_matches(self, criteria: Dict[str, str]) -> Dict[str, CardMatch]:
        collected: Dict[str, CardMatch] = {}
        for subcard in self.definition.subcards:
            match = self._find_match(subcard.name, criteria)
            if match:
                collected[subcard.name] = match
        return collected

    def _find_match(self, subcard_name: str, criteria: Dict[str, str]) -> Optional[CardMatch]:
        match_list = self.matches.get(subcard_name, [])
        for match in match_list:
            if self._match_constraints(match.variables, criteria):
                return match
        return None

    def _build_overlay_series(
        self, overlay_def: OverlayDefinition, variables: Dict[str, str]
    ) -> OverlaySeries:
        series_defs: List[SeriesDefinition] = []
        styles = overlay_def.chart_styles
        if not styles:
            styles = [None] * len(overlay_def.filepaths)
        elif len(styles) < len(overlay_def.filepaths):
            styles = styles + [styles[-1]] * (len(overlay_def.filepaths) - len(styles))
        card_dir = str(self.definition.path.parent)
        for path_str, style in zip(overlay_def.filepaths, styles):
            template = path_str.replace("<CARD_DIR>", card_dir)
            replaced = _replace_variables(template, variables)
            series_defs.append(SeriesDefinition(path=Path(replaced), chart_style=style))
        return OverlaySeries(series=series_defs)


@dataclass(frozen=True)
class OverlayDefinition:
    name: str
    filepaths: List[str]
    chart_styles: List[Optional[str]]


@dataclass(frozen=True)
class SeriesDefinition:
    path: Path
    chart_style: Optional[str]


@dataclass(frozen=True)
class OverlaySeries:
    series: List[SeriesDefinition]


def _replace_variables(template: str, values: Dict[str, str]) -> str:
    result = template
    for key, value in values.items():
        result = result.replace(f"{{{{{key}}}}}", value)
        result = result.replace(f"{{{{ {key} }}}}", value)
    return result
