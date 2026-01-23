from __future__ import annotations

import glob
import os
import re
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import tomllib

from .models import (
    CardDefinition,
    CardMatch,
    ChartStyle,
    OverlayDefinition,
    SubcardDefinition,
    SeriesDefinition,
)
from .utils import _template_to_glob, _template_to_regex

MAX_MATCHES = 1000
VAR_PATTERN = re.compile(r"{{\s*([A-Za-z0-9_]+)\s*}}")


class CardLoader:
    def __init__(self, cards_dir: Path) -> None:
        self._cards_dir = cards_dir

    def list_card_files(self) -> List[Path]:
        if not self._cards_dir.exists():
            return []
        return sorted(self._cards_dir.glob("*.toml"))

    def load_definition(self, path: Path) -> CardDefinition:
        path = path.resolve()
        with path.open("rb") as handle:
            data = tomllib.load(handle)
        global_section = data.get("global", {})
        filepath_template = (
            data.get("filepath")
            or global_section.get("filepath")
            or data.get("card", {}).get("filepath")
        )
        chart_style_raw = data.get("chart_style") or global_section.get("chart_style")
        chart_style = _maybe_first_style(chart_style_raw)
        pivot = data.get("pivot_chart") or global_section.get("pivot_chart")
        synchronize_axis = bool(global_section.get("synchronize_axis", False))
        show_x_axis = _parse_optional_bool(data.get("show_x_axis") or global_section.get("show_x_axis"))
        show_y_axis = _parse_optional_bool(data.get("show_y_axis") or global_section.get("show_y_axis"))
        subcards_section = data.get("subcards") or {}

        subcards: List[SubcardDefinition] = []
        overlay_panels: Dict[str, OverlayDefinition] = {}
        overlay_var_global = _normalize_variable(global_section.get("overlay_variable"))
        variable_filters = _normalize_filter_map(data.get("variable_filters", {}))
        if subcards_section:
            for name, config in subcards_section.items():
                template = config.get("filepath")
                if not template:
                    raise ValueError(f"Subcard '{name}' missing filepath")
                overlay_var = _normalize_variable(config.get("overlay_variable"))
                if isinstance(template, list):
                    filepaths = [_ensure_string(path) for path in template]
                    extracted_vars = _collect_variables(filepaths)
                    if overlay_var and overlay_var not in extracted_vars:
                        raise ValueError(
                            f"Overlay variable '{overlay_var}' not found in any filepath for subcard '{name}'"
                        )
                    match_template = filepaths[0]
                    for candidate in filepaths:
                        vars_in_candidate = _extract_variables(candidate)
                        if any(var != overlay_var for var in vars_in_candidate):
                            match_template = candidate
                            break
                    overlay_panels[name] = OverlayDefinition(
                        name=name,
                        filepaths=filepaths,
                        chart_styles=_normalize_style_list(
                            config.get("chart_style"), len(filepaths)
                        ),
                        overlay_variable=overlay_var,
                        overlay_labels=_normalize_label_list(config.get("series_label"), len(filepaths)),
                        overlay_path_filter=_normalize_variable(config.get("overlay_path_filter")),
                    )
                    template = filepaths[0]
                else:
                    filepaths = [_ensure_string(template)]
                    extracted_vars = _extract_variables(template)
                    if overlay_var and overlay_var not in extracted_vars:
                        raise ValueError(
                            f"Overlay variable '{overlay_var}' not found in template for subcard '{name}'"
                        )
                    overlay_var = overlay_var or None
                    match_template = template
                subcards.append(
                    SubcardDefinition(
                        name=name,
                        filepath_template=str(match_template),
                        variables=_remove_overlay_variable(extracted_vars, overlay_var),
                        chart_style=_maybe_first_style(config.get("chart_style")),
                        chart_height=_parse_chart_height(config.get("chart_height")),
                        filepaths=filepaths,
                        overlay_variable=overlay_var,
                        show_x_axis=_parse_optional_bool(config.get("show_x_axis")),
                        show_y_axis=_parse_optional_bool(config.get("show_y_axis")),
                    )
                )
        elif filepath_template:
            overlay_var = _normalize_variable(data.get("overlay_variable") or overlay_var_global)
            if isinstance(filepath_template, list):
                filepaths = [_ensure_string(path) for path in filepath_template]
                extracted_vars = _collect_variables(filepaths)
                if overlay_var and overlay_var not in extracted_vars:
                    raise ValueError(f"Overlay variable '{overlay_var}' not found in any filepath")
                match_template = filepaths[0]
                for candidate in filepaths:
                    vars_in_candidate = _extract_variables(candidate)
                    if any(var != overlay_var for var in vars_in_candidate):
                        match_template = candidate
                        break
                overlay_panels["overlay"] = OverlayDefinition(
                    name="overlay",
                    filepaths=filepaths,
                    chart_styles=_normalize_style_list(chart_style_raw, len(filepaths)),
                    overlay_variable=overlay_var,
                    overlay_labels=_normalize_label_list(data.get("series_label"), len(filepaths)),
                    overlay_path_filter=_normalize_variable(data.get("overlay_path_filter")),
                )
                template = match_template
                subcards.append(
                    SubcardDefinition(
                        name="overlay",
                        filepath_template=template,
                        variables=_remove_overlay_variable(extracted_vars, overlay_var),
                        chart_style=_maybe_first_style(chart_style),
                        filepaths=filepaths,
                        overlay_variable=overlay_var,
                        show_x_axis=show_x_axis,
                        show_y_axis=show_y_axis,
                    )
                )
            else:
                template = _ensure_string(filepath_template)
                subcards.append(
                    SubcardDefinition(
                        name="default",
                        filepath_template=template,
                        variables=_extract_variables(template),
                        chart_style=_maybe_first_style(chart_style),
                        filepaths=[template],
                        overlay_variable=None,
                        show_x_axis=show_x_axis,
                        show_y_axis=show_y_axis,
                    )
                )
        elif not filepath_template:
            raise ValueError("Card must define either 'filepath' or '[subcards]' sections")

        all_variables = sorted({var for subcard in subcards for var in subcard.variables})
        normalized_pivot = _normalize_variable(pivot)
        if normalized_pivot and normalized_pivot not in all_variables:
            raise ValueError(
                f"Pivot variable '{normalized_pivot}' is not present in the filepath template"
            )
        if not normalized_pivot and len(all_variables) == 1:
            normalized_pivot = all_variables[0]
        if len(all_variables) > 1 and not normalized_pivot:
            raise ValueError("Cards with multiple variables must define 'pivot_chart'")

        return CardDefinition(
            path=path,
            subcards=tuple(subcards),
            variables=tuple(all_variables),
            chart_style=chart_style,
            pivot_variable=normalized_pivot,
            overlay_panels=overlay_panels,
            variable_filters=variable_filters,
            synchronize_axis=synchronize_axis,
            show_x_axis=show_x_axis,
            show_y_axis=show_y_axis,
        )

    def resolve_paths(self, definition: CardDefinition) -> Dict[str, List[CardMatch]]:
        resolved: Dict[str, List[CardMatch]] = {}
        compiled_filters = {k: re.compile(v) for k, v in (definition.variable_filters or {}).items()}
        for subcard in definition.subcards:
            normalized_template = _normalize_template(subcard, definition.path)
            glob_pattern = _template_to_glob(normalized_template)
            regex, alias_map = _template_to_regex(normalized_template)
            matches: List[CardMatch] = []
            uses_wildcard = "*" in normalized_template
            for match in glob.glob(glob_pattern):
                match_path = Path(match).resolve()
                normalized_match = os.path.normpath(str(match_path))
                match_groups = regex.match(normalized_match)
                if not match_groups:
                    continue
                if compiled_filters and not _match_filters(match_groups.groupdict(), alias_map, compiled_filters):
                    continue
                groups: Dict[str, str] = {}
                for key, value in match_groups.groupdict().items():
                    if not value:
                        continue
                    if key.startswith("_wildcard_"):
                        continue
                    original_key = alias_map.get(key, key)
                    if subcard.overlay_variable and original_key == subcard.overlay_variable:
                        continue
                    groups[original_key] = value
                matches.append(CardMatch(path=match_path, variables=groups))

            if len(matches) > MAX_MATCHES:
                raise ValueError(
                    f"Subcard '{subcard.name}' resolved to {len(matches)} matches which exceeds the limit of {MAX_MATCHES}"
            )
            matches.sort(
                key=lambda match_obj: (
                    tuple(match_obj.variables.get(var, "") for var in subcard.variables),
                    str(match_obj.path),
                )
            )
            if uses_wildcard and subcard.variables:
                seen: Dict[tuple[str, ...], int] = {}
                for match in matches:
                    key = tuple(match.variables.get(var, "") for var in subcard.variables)
                    seen[key] = seen.get(key, 0) + 1
                duplicates = [key for key, count in seen.items() if count > 1]
                if duplicates:
                    raise ValueError(
                        f"Subcard '{subcard.name}' wildcard matched multiple files for variables {duplicates[0]}"
                    )
            if uses_wildcard and not subcard.variables and len(matches) > 1:
                raise ValueError(
                    f"Subcard '{subcard.name}' wildcard matched multiple files; refine the pattern or add a variable."
                )
            resolved[subcard.name] = matches
        return resolved


def _normalize_variable(value: object | None) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    if text.startswith("{{") and text.endswith("}}"):
        text = text[2:-2].strip()
    return text or None


def _normalize_template(subcard: SubcardDefinition, card_path: Path) -> str:
    resolved = subcard.filepath_template.replace("<CARD_DIR>", str(card_path.parent))
    return os.path.normpath(resolved)


def _parse_chart_height(value: object | None) -> Optional[float]:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    if text.endswith("%"):
        text = text[:-1]
    try:
        height = float(text)
    except ValueError:
        raise ValueError(f"Invalid chart_height value: {value}") from None
    if height <= 0:
        return None
    return min(height, 100.0)


def _parse_optional_bool(value: object | None) -> Optional[bool]:
    if value is None:
        return None
    if isinstance(value, bool):
        return value
    text = str(value).strip().lower()
    if text in {"true", "yes", "1", "on"}:
        return True
    if text in {"false", "no", "0", "off"}:
        return False
    raise ValueError(f"Invalid boolean value: {value}")


def _ensure_string(value: object) -> str:
    if isinstance(value, str):
        return value
    raise ValueError(f"Expected string in filepath, got {type(value)!r}")


def _extract_variables(template: object) -> Tuple[str, ...]:
    return tuple(VAR_PATTERN.findall(str(template)))


def _parse_chart_style(value: object | None) -> ChartStyle | None:
    if value is None:
        return None
    if isinstance(value, ChartStyle):
        return value
    if isinstance(value, dict):
        if "name" not in value:
            raise ValueError("chart_style object must include 'name'")
        params = {k: v for k, v in value.items() if k != "name"}
        return ChartStyle(name=str(value["name"]), params=params)
    return ChartStyle(name=str(value))


def _maybe_first_style(value: object | None) -> Optional[ChartStyle]:
    if value is None:
        return None
    if isinstance(value, list) and value:
        return _parse_chart_style(value[0])
    return _parse_chart_style(value)


def _normalize_style_list(value: object | None, expected: int) -> List[Optional[ChartStyle]]:
    if value is None:
        return [None] * expected
    if isinstance(value, list):
        styles = [_parse_chart_style(item) for item in value]
        if len(styles) < expected:
            styles += [styles[-1] if styles else None] * (expected - len(styles))
        return styles
    return [_parse_chart_style(value)] * expected


def _remove_overlay_variable(variables: Tuple[str, ...], overlay_variable: str | None) -> Tuple[str, ...]:
    if not overlay_variable:
        return variables
    return tuple(var for var in variables if var != overlay_variable)


def _collect_variables(filepaths: List[str]) -> Tuple[str, ...]:
    vars_set = set()
    for path in filepaths:
        vars_set.update(_extract_variables(path))
    return tuple(sorted(vars_set))


def _normalize_label_list(value: object | None, expected: int) -> List[Optional[str]]:
    if value is None:
        return [None] * expected
    if isinstance(value, list):
        labels = [str(item) if item is not None else None for item in value]
        if len(labels) < expected:
            labels += [labels[-1] if labels else None] * (expected - len(labels))
        return labels
    return [str(value)] * expected


def _normalize_filter_map(raw: object) -> Dict[str, str]:
    if raw is None:
        return {}
    if isinstance(raw, dict):
        return {str(k): str(v) for k, v in raw.items()}
    raise ValueError("variable_filters must be a table of key/value regex strings")


def _match_filters(
    groupdict: Dict[str, str], alias_map: Dict[str, str], filters: Dict[str, re.Pattern[str]]
) -> bool:
    for var_name, pattern in filters.items():
        values = [
            value
            for alias, value in groupdict.items()
            if value and alias_map.get(alias, alias) == var_name
        ]
        if not values:
            continue
        if not all(pattern.fullmatch(value) for value in values):
            return False
    return True
