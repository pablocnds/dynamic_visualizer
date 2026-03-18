from __future__ import annotations

from typing import Mapping

from visualizer.interpretation.specs import VisualizationType


_ALLOWED_ARGS_BY_VISUALIZATION: dict[VisualizationType, tuple[str, ...]] = {
    VisualizationType.LINE: ("color", "alpha", "line_width", "width"),
    VisualizationType.SCATTER: ("color", "alpha", "marker_size", "size"),
    VisualizationType.STICK: ("color", "alpha", "line_width", "width"),
    VisualizationType.COLORMAP: ("palette", "alpha"),
    VisualizationType.EVENTLINE: ("color", "palette", "alpha"),
    VisualizationType.RANGE: ("colors", "palette", "alpha"),
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

    for key in ("line_width", "width", "marker_size", "size"):
        value = params.get(key)
        if value is None:
            continue
        if isinstance(value, bool) or not isinstance(value, (int, float)) or float(value) <= 0:
            raise ValueError(
                f"{context} chart_style '{style_name}' arg '{key}' must be a positive number"
            )

    palette = params.get("palette")
    if palette is not None and not isinstance(palette, str):
        raise ValueError(f"{context} chart_style '{style_name}' arg 'palette' must be a string")

    colors = params.get("colors")
    if colors is not None:
        if not isinstance(colors, (list, tuple)) or not colors:
            raise ValueError(
                f"{context} chart_style '{style_name}' arg 'colors' must be a non-empty list"
            )
