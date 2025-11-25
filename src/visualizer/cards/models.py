from __future__ import annotations

import glob
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import re


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
            styles = [self.definition.chart_style] * len(overlay_def.filepaths)
        elif len(styles) < len(overlay_def.filepaths):
            styles = styles + [styles[-1]] * (len(overlay_def.filepaths) - len(styles))
        styles = [
            style if style is not None else self.definition.chart_style for style in styles
        ]
        labels = overlay_def.overlay_labels or [None] * len(overlay_def.filepaths)
        if len(labels) < len(overlay_def.filepaths):
            labels = labels + [labels[-1]] * (len(overlay_def.filepaths) - len(labels))
        card_dir = str(self.definition.path.parent)
        for path_str, style, series_label in zip(overlay_def.filepaths, styles, labels):
            template = path_str.replace("<CARD_DIR>", card_dir)
            overlay_var = overlay_def.overlay_variable
            if overlay_var:
                expanded_paths = _enumerate_overlay_paths(
                    template,
                    overlay_var,
                    variables,
                    overlay_def.overlay_filter,
                    overlay_def.overlay_path_filter,
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
                series_defs.append(
                    SeriesDefinition(
                        path=Path(replaced),
                        chart_style=style,
                        label=series_label or Path(replaced).stem,
                    )
                )
        return OverlaySeries(series=series_defs)


@dataclass(frozen=True)
class OverlayDefinition:
    name: str
    filepaths: List[str]
    chart_styles: List[Optional[str]]
    overlay_variable: Optional[str] = None
    overlay_filter: Optional[str] = None
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


def _template_to_glob(template: str) -> str:
    pattern: List[str] = []
    i = 0
    length = len(template)
    while i < length:
        if template.startswith("{{", i):
            end = template.find("}}", i)
            if end == -1:
                raise ValueError("Unclosed variable in template")
            pattern.append("*")
            i = end + 2
        else:
            pattern.append(template[i])
            i += 1
    return "".join(pattern)


def _template_to_regex(template: str) -> tuple[re.Pattern[str], Dict[str, str]]:
    pattern_parts: List[str] = []
    i = 0
    wildcard_index = 0
    var_counts: Dict[str, int] = {}
    alias_map: Dict[str, str] = {}
    length = len(template)
    while i < length:
        if template.startswith("{{", i):
            end = template.find("}}", i)
            if end == -1:
                raise ValueError("Unclosed variable in template")
            var_name = template[i + 2 : end].strip()
            count = var_counts.get(var_name, 0)
            alias = var_name if count == 0 else f"{var_name}__{count}"
            var_counts[var_name] = count + 1
            alias_map[alias] = var_name
            pattern_parts.append(f"(?P<{alias}>[^/\\\\]+)")
            i = end + 2
        elif template[i] == "*":
            pattern_parts.append(f"(?P<_wildcard_{wildcard_index}>[^/\\\\]+)")
            wildcard_index += 1
            i += 1
        else:
            ch = template[i]
            if ch in ".^$+?{}[]|()":
                pattern_parts.append("\\" + ch)
            else:
                pattern_parts.append(ch)
            i += 1
    regex = "".join(pattern_parts)
    return re.compile(f"^{regex}$"), alias_map


def _enumerate_overlay_paths(
    template: str,
    overlay_variable: str,
    values: Dict[str, str],
    overlay_filter: str | None = None,
    overlay_path_filter: str | None = None,
) -> List[Path]:
    replaced = _replace_variables(template, values)
    glob_pattern = _template_to_glob(replaced)
    regex, alias_map = _template_to_regex(replaced)
    paths: List[Path] = []
    compiled_filter = re.compile(overlay_filter) if overlay_filter else None
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
        if compiled_filter and var_value is not None:
            if not compiled_filter.match(var_value):
                continue
        paths.append(Path(normalized))
    return sorted(paths)
