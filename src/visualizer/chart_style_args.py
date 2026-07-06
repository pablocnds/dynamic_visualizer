from __future__ import annotations

import re
from typing import Mapping

from visualizer.interpretation.specs import VisualizationType
from visualizer.palettes import CHART_PALETTES, validate_color_value, validate_palette_name


_ALLOWED_ARGS_BY_VISUALIZATION: dict[VisualizationType, tuple[str, ...]] = {
    VisualizationType.LINE: ("color", "alpha", "line_width", "width"),
    VisualizationType.SCATTER: ("color", "alpha", "marker_size", "size"),
    VisualizationType.STICK: (
        "color",
        "alpha",
        "line_width",
        "width",
        "label_top_n",
        "label_threshold",
    ),
    VisualizationType.COLORMAP: ("palette", "alpha", "reverse"),
    VisualizationType.EVENTLINE: ("color", "palette", "alpha", "reverse"),
    VisualizationType.RANGE: ("colors", "palette", "alpha", "reverse"),
}


def validate_chart_style_args(
    style_name: str,
    params: Mapping[str, object] | None,
    *,
    context: str,
) -> None:
    """Validate chart-style params early so card errors are explicit."""

    visualization = VisualizationType.from_string(style_name)
    allowed = _ALLOWED_ARGS_BY_VISUALIZATION[visualization]
    if not params:
        return

    unknown = sorted(key for key in params.keys() if key not in allowed)
    if unknown:
        allowed_text = ", ".join(allowed)
        unknown_text = ", ".join(unknown)
        raise ValueError(
            f"{context} has unsupported chart_style args for '{style_name}': "
            f"{unknown_text}. Allowed args: {allowed_text}"
        )

    _validate_arg_types(style_name, params, context=context)


def _validate_arg_types(style_name: str, params: Mapping[str, object], *, context: str) -> None:
    alpha = params.get("alpha")
    if alpha is not None and (isinstance(alpha, bool) or not isinstance(alpha, (int, float))):
        raise ValueError(f"{context} chart_style '{style_name}' arg 'alpha' must be numeric")

    color = params.get("color")
    if color is not None:
        validate_color_value(color, context=f"{context} chart_style '{style_name}' arg 'color'")

    reverse = params.get("reverse")
    if reverse is not None and not isinstance(reverse, bool):
        raise ValueError(f"{context} chart_style '{style_name}' arg 'reverse' must be boolean")

    for key in ("line_width", "width", "marker_size", "size"):
        value = params.get(key)
        if value is None:
            continue
        if isinstance(value, bool) or not isinstance(value, (int, float)) or float(value) <= 0:
            raise ValueError(
                f"{context} chart_style '{style_name}' arg '{key}' must be a positive number"
            )

    palette = params.get("palette")
    if palette is not None:
        if not isinstance(palette, str):
            raise ValueError(f"{context} chart_style '{style_name}' arg 'palette' must be a string")
        validate_palette_name(
            palette,
            context=f"{context} chart_style '{style_name}' arg 'palette'",
            allowed=CHART_PALETTES,
        )

    colors = params.get("colors")
    if colors is not None:
        if not isinstance(colors, (list, tuple)) or not colors:
            raise ValueError(
                f"{context} chart_style '{style_name}' arg 'colors' must be a non-empty list"
            )
        for idx, value in enumerate(colors):
            validate_color_value(
                value,
                context=f"{context} chart_style '{style_name}' arg 'colors[{idx}]'",
            )

    label_top_n = params.get("label_top_n")
    if label_top_n is not None and (
        isinstance(label_top_n, bool)
        or not isinstance(label_top_n, int)
        or label_top_n <= 0
    ):
        raise ValueError(
            f"{context} chart_style '{style_name}' arg 'label_top_n' "
            "must be a positive integer"
        )

    label_threshold = params.get("label_threshold")
    if label_threshold is not None:
        is_number = (
            not isinstance(label_threshold, bool)
            and isinstance(label_threshold, (int, float))
        )
        relative_match = (
            re.fullmatch(r"(?:\d+(?:\.\d*)?|\.\d+)%", label_threshold.strip())
            if isinstance(label_threshold, str)
            else None
        )
        relative_in_range = (
            relative_match is not None
            and 0.0 <= float(label_threshold.strip()[:-1]) <= 100.0
        )
        if not is_number and not relative_in_range:
            raise ValueError(
                f"{context} chart_style '{style_name}' arg 'label_threshold' "
                'must be numeric or a percentage string between "0%" and "100%"'
            )
