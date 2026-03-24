from __future__ import annotations

import re
from typing import Iterable, Sequence


CHART_PALETTES: tuple[str, ...] = ("viridis", "plasma", "cividis", "magma", "turbo")
TABLE_PALETTES: tuple[str, ...] = ("blue", "viridis", "plasma", "cividis", "magma")

_HEX_COLOR_PATTERN = re.compile(r"^#(?:[0-9a-fA-F]{3}|[0-9a-fA-F]{4}|[0-9a-fA-F]{6}|[0-9a-fA-F]{8})$")
_NAMED_COLOR_PATTERN = re.compile(r"^[A-Za-z][A-Za-z0-9_ -]*$")


def normalize_palette_name(value: object) -> str:
    return str(value).strip().lower()


def validate_palette_name(
    value: object,
    *,
    context: str,
    allowed: Iterable[str],
) -> str:
    normalized = normalize_palette_name(value)
    allowed_names = tuple(normalize_palette_name(name) for name in allowed)
    if normalized not in allowed_names:
        supported = ", ".join(allowed_names)
        raise ValueError(f"{context} must be one of: {supported}")
    return normalized


def validate_color_value(value: object, *, context: str) -> None:
    if isinstance(value, str):
        text = value.strip()
        if not text:
            raise ValueError(f"{context} must not be empty")
        if _HEX_COLOR_PATTERN.fullmatch(text) or _NAMED_COLOR_PATTERN.fullmatch(text):
            return
        raise ValueError(
            f"{context} must be a named color, hex string, or RGB/RGBA sequence"
        )

    if not isinstance(value, Sequence) or isinstance(value, (bytes, bytearray)):
        raise ValueError(
            f"{context} must be a named color, hex string, or RGB/RGBA sequence"
        )
    if len(value) not in {3, 4}:
        raise ValueError(f"{context} RGB/RGBA sequences must have length 3 or 4")
    for idx, channel in enumerate(value):
        if isinstance(channel, bool) or not isinstance(channel, (int, float)):
            raise ValueError(f"{context} channel {idx} must be numeric")

