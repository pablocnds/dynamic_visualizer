from __future__ import annotations

import glob
import os
import re
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import tomllib

from .models import CardDefinition, CardMatch, OverlayDefinition, SubcardDefinition, SeriesDefinition

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
        filepath_template = data.get("filepath") or global_section.get("filepath")
        chart_style = data.get("chart_style") or global_section.get("chart_style")
        pivot = data.get("pivot_chart") or global_section.get("pivot_chart")
        subcards_section = data.get("subcards") or {}

        subcards: List[SubcardDefinition] = []
        overlay_panels: Dict[str, OverlayDefinition] = {}
        if subcards_section:
            for name, config in subcards_section.items():
                template = config.get("filepath")
                if not template:
                    raise ValueError(f"Subcard '{name}' missing filepath")
                if isinstance(template, list):
                    filepaths = [_ensure_string(path) for path in template]
                    overlay_panels[name] = OverlayDefinition(
                        name=name,
                        filepaths=filepaths,
                        chart_styles=_normalize_style_list(
                            config.get("chart_style"), len(filepaths)
                        ),
                    )
                    template = filepaths[0]
                else:
                    filepaths = [_ensure_string(template)]
                subcards.append(
                    SubcardDefinition(
                        name=name,
                        filepath_template=str(template),
                        variables=_extract_variables(template),
                        chart_style=_maybe_list_first(config.get("chart_style")),
                        chart_height=_parse_chart_height(config.get("chart_height")),
                        filepaths=filepaths,
                    )
                )
        elif filepath_template:
            if isinstance(filepath_template, list):
                filepaths = [_ensure_string(path) for path in filepath_template]
                overlay_panels["overlay"] = OverlayDefinition(
                    name="overlay",
                    filepaths=filepaths,
                    chart_styles=_normalize_style_list(chart_style, len(filepaths)),
                )
                template = filepaths[0]
                subcards.append(
                    SubcardDefinition(
                        name="overlay",
                        filepath_template=template,
                        variables=_extract_variables(template),
                        chart_style=_maybe_list_first(chart_style),
                        filepaths=filepaths,
                    )
                )
            else:
                template = _ensure_string(filepath_template)
                subcards.append(
                    SubcardDefinition(
                        name="default",
                        filepath_template=template,
                        variables=_extract_variables(template),
                        chart_style=_maybe_list_first(chart_style),
                        filepaths=[template],
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
        if len(all_variables) > 1 and not normalized_pivot:
            raise ValueError("Cards with multiple variables must define 'pivot_chart'")

        return CardDefinition(
            path=path,
            subcards=tuple(subcards),
            variables=tuple(all_variables),
            chart_style=str(chart_style) if chart_style else None,
            pivot_variable=normalized_pivot,
            overlay_panels=overlay_panels,
        )

    def resolve_paths(self, definition: CardDefinition) -> Dict[str, List[CardMatch]]:
        resolved: Dict[str, List[CardMatch]] = {}
        for subcard in definition.subcards:
            normalized_template = _normalize_template(subcard, definition.path)
            glob_pattern = _template_to_glob(normalized_template)
            regex, alias_map = _template_to_regex(normalized_template)
            matches: List[CardMatch] = []
            for match in glob.glob(glob_pattern):
                match_path = Path(match).resolve()
                normalized_match = os.path.normpath(str(match_path))
                match_groups = regex.match(normalized_match)
                if not match_groups:
                    continue
                groups: Dict[str, str] = {}
                for key, value in match_groups.groupdict().items():
                    if not value:
                        continue
                    if key.startswith("_wildcard_"):
                        continue
                    original_key = alias_map.get(key, key)
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


def _ensure_string(value: object) -> str:
    if isinstance(value, str):
        return value
    raise ValueError(f"Expected string in filepath, got {type(value)!r}")


def _extract_variables(template: object) -> Tuple[str, ...]:
    return tuple(VAR_PATTERN.findall(str(template)))


def _maybe_list_first(value: object | None) -> Optional[str]:
    if value is None:
        return None
    if isinstance(value, list) and value:
        return str(value[0])
    return str(value)


def _normalize_style_list(value: object | None, expected: int) -> List[Optional[str]]:
    if value is None:
        return [None] * expected
    if isinstance(value, list):
        styles = [str(item) if item is not None else None for item in value]
        if len(styles) < expected:
            styles += [styles[-1] if styles else None] * (expected - len(styles))
        return styles
    return [str(value)] * expected
