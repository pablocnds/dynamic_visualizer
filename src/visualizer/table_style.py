from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence


@dataclass(frozen=True)
class TableColorRule:
    palette: str | None = None
    value_range: tuple[float, float] | None = None

    def cache_key(self) -> tuple[object, ...]:
        return (self.palette, self.value_range)

    def merged_with(self, fallback: TableColorRule | None) -> TableColorRule:
        if fallback is None:
            return self
        return TableColorRule(
            palette=self.palette if self.palette is not None else fallback.palette,
            value_range=self.value_range if self.value_range is not None else fallback.value_range,
        )


@dataclass(frozen=True)
class TableColorConfig:
    global_rule: TableColorRule | None = None
    row_rules: tuple[TableColorRule | None, ...] = ()
    column_rules: tuple[TableColorRule | None, ...] = ()

    def cache_key(self) -> tuple[object, ...]:
        return (
            self.global_rule.cache_key() if self.global_rule else None,
            tuple(rule.cache_key() if rule else None for rule in self.row_rules),
            tuple(rule.cache_key() if rule else None for rule in self.column_rules),
        )

    def with_global_fallback(self, fallback: TableColorRule | None) -> TableColorConfig:
        if fallback is None:
            return self
        if self.global_rule is None:
            return TableColorConfig(
                global_rule=fallback,
                row_rules=self.row_rules,
                column_rules=self.column_rules,
            )
        return self

    @classmethod
    def with_global_rule(cls, rule: TableColorRule | None) -> TableColorConfig | None:
        if rule is None:
            return None
        return cls(global_rule=rule)


def parse_table_color_rule(raw: object | None, *, context: str) -> TableColorRule | None:
    if raw is None:
        return None
    if not isinstance(raw, dict):
        raise ValueError(f"{context} must be an object with optional 'palette'/'range' entries")
    allowed = {"palette", "range"}
    unknown = [key for key in raw.keys() if key not in allowed]
    if unknown:
        raise ValueError(f"{context} contains unsupported keys: {', '.join(sorted(str(k) for k in unknown))}")
    palette_value = raw.get("palette")
    palette = None if palette_value is None else str(palette_value)
    range_value = raw.get("range")
    value_range = _parse_numeric_range(range_value, context=context)
    if palette is None and value_range is None:
        return None
    return TableColorRule(palette=palette, value_range=value_range)


def parse_table_color_config(
    raw: object | None,
    *,
    row_count: int,
    column_count: int,
    context: str,
) -> TableColorConfig | None:
    if raw is None:
        return None
    if not isinstance(raw, dict):
        raise ValueError(
            f"{context} must be an object with optional 'global', 'rows', and 'columns' entries"
        )

    allowed = {"global", "rows", "columns"}
    unknown = [key for key in raw.keys() if key not in allowed]
    if unknown:
        raise ValueError(f"{context} contains unsupported keys: {', '.join(sorted(str(k) for k in unknown))}")

    global_rule = parse_table_color_rule(raw.get("global"), context=f"{context}.global")
    row_rules = _parse_rule_sequence(raw.get("rows"), expected=row_count, context=f"{context}.rows")
    column_rules = _parse_rule_sequence(
        raw.get("columns"),
        expected=column_count,
        context=f"{context}.columns",
    )

    if global_rule is None and row_rules is None and column_rules is None:
        return None
    return TableColorConfig(
        global_rule=global_rule,
        row_rules=tuple(row_rules or ()),
        column_rules=tuple(column_rules or ()),
    )


def merge_table_color_config(
    dataset_config: TableColorConfig | None,
    global_override: TableColorRule | None,
) -> TableColorConfig | None:
    if dataset_config is None:
        return TableColorConfig.with_global_rule(global_override)
    return dataset_config.with_global_fallback(global_override)


def _parse_rule_sequence(
    raw: object | None,
    *,
    expected: int,
    context: str,
) -> list[TableColorRule | None] | None:
    if raw is None:
        return None
    if not isinstance(raw, Sequence) or isinstance(raw, (str, bytes)):
        raise ValueError(f"{context} must be an array with {expected} entries")
    if len(raw) != expected:
        raise ValueError(f"{context} must contain exactly {expected} entries")
    parsed: list[TableColorRule | None] = []
    for idx, entry in enumerate(raw):
        parsed.append(parse_table_color_rule(entry, context=f"{context}[{idx}]"))
    return parsed


def _parse_numeric_range(value: object | None, *, context: str) -> tuple[float, float] | None:
    if value is None:
        return None
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)) or len(value) != 2:
        raise ValueError(f"{context}.range must be an array with exactly two numbers")
    try:
        start = float(value[0])
        end = float(value[1])
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{context}.range values must be numeric") from exc
    if start <= end:
        return start, end
    return end, start
