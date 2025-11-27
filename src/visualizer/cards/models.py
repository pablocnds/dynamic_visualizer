from __future__ import annotations

import glob
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import re

from .utils import _template_to_glob, _template_to_regex


@dataclass(frozen=True)
class SubcardDefinition:
    name: str
    filepath_template: str
    variables: Tuple[str, ...]
    filepaths: List[str]
    overlay_variable: Optional[str] = None
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
    variable_filters: Dict[str, str] = field(default_factory=dict)

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
        self,
        overlay_def: OverlayDefinition,
        variables: Dict[str, str],
        fallback_style: Optional[str] = None,
    ) -> OverlaySeries:
        series_defs: List[SeriesDefinition] = []
        styles = overlay_def.chart_styles
        default_style = fallback_style or self.definition.chart_style
        if not styles:
            styles = [default_style] * len(overlay_def.filepaths)
        elif len(styles) < len(overlay_def.filepaths):
            styles = styles + [styles[-1]] * (len(overlay_def.filepaths) - len(styles))
        styles = [style if style is not None else default_style for style in styles]
        labels = overlay_def.overlay_labels or [None] * len(overlay_def.filepaths)
        if len(labels) < len(overlay_def.filepaths):
            labels = labels + [labels[-1]] * (len(overlay_def.filepaths) - len(labels))
        card_dir = str(self.definition.path.parent)
        for path_str, style, series_label in zip(overlay_def.filepaths, styles, labels):
            template = path_str.replace("<CARD_DIR>", card_dir)
            overlay_var = overlay_def.overlay_variable
            if overlay_var and f"{{{{{overlay_var}}}}}" in template:
                expanded_paths = _enumerate_overlay_paths(
                    template,
                    overlay_var,
                    variables,
                    overlay_def.overlay_path_filter,
                    self.definition.variable_filters,
                )
                for path in expanded_paths:
                    series_defs.append(
                        SeriesDefinition(
                            path=path,
                            chart_style=style,
                            label=series_label or path.stem,
                        )
                    )
            else:
                replaced = _replace_variables(template, variables)
                expanded = _expand_wildcard_paths(replaced)
                if not expanded:
                    continue
                series_defs.append(
                    SeriesDefinition(
                        path=expanded,
                        chart_style=style,
                        label=series_label or expanded.stem,
                    )
                )
        return OverlaySeries(series=series_defs)


@dataclass(frozen=True)
class OverlayDefinition:
    name: str
    filepaths: List[str]
    chart_styles: List[Optional[str]]
    overlay_variable: Optional[str] = None
    overlay_labels: Optional[List[Optional[str]]] = None
    overlay_path_filter: Optional[str] = None


@dataclass(frozen=True)
class SeriesDefinition:
    path: Path
    chart_style: Optional[str]
    label: Optional[str] = None


@dataclass(frozen=True)
class OverlaySeries:
    series: List[SeriesDefinition]


def _replace_variables(template: str, values: Dict[str, str]) -> str:
    result = template
    for key, value in values.items():
        result = result.replace(f"{{{{{key}}}}}", value)
        result = result.replace(f"{{{{ {key} }}}}", value)
    return result


def _expand_wildcard_paths(path_template: str) -> Path | None:
    if "*" not in path_template and "?" not in path_template:
        return Path(path_template)
    matches = sorted(Path(p) for p in glob.glob(path_template))
    if not matches:
        return None
    if len(matches) > 1:
        raise ValueError(f"Wildcard path matched multiple files: {path_template}")
    return matches[0]


def _enumerate_overlay_paths(
    template: str,
    overlay_variable: str,
    values: Dict[str, str],
    overlay_path_filter: str | None = None,
    variable_filters: Dict[str, str] | None = None,
) -> List[Path]:
    replaced = os.path.normpath(_replace_variables(template, values))
    glob_pattern = _template_to_glob(replaced)
    regex, alias_map = _template_to_regex(replaced)
    paths: List[Path] = []
    filters = {k: re.compile(v) for k, v in (variable_filters or {}).items()}
    compiled_path_filter = re.compile(overlay_path_filter) if overlay_path_filter else None
    for match in glob.glob(glob_pattern):
        normalized = os.path.normpath(match)
        if compiled_path_filter and not compiled_path_filter.search(normalized):
            continue
        match_obj = regex.match(normalized)
        if not match_obj:
            continue
        var_value = match_obj.groupdict().get(overlay_variable) or match_obj.groupdict().get(
            alias_map.get(overlay_variable, "")
        )
        overlay_filter = filters.get(overlay_variable)
        if overlay_filter:
            target = var_value if var_value is not None else Path(normalized).stem
            if not overlay_filter.fullmatch(target):
                continue
        for var_name, var_pattern in filters.items():
            captured = match_obj.groupdict().get(var_name)
            if captured is None:
                continue
            if not var_pattern.fullmatch(captured):
                break
        else:
            paths.append(Path(normalized))
    return sorted(paths)
