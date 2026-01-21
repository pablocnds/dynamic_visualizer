# Card Specification

TOML cards describe where to find datasets and how to render them. Variables are single path components discovered automatically so users can cycle through data without manual file picking.

## Core Concepts
- `<CARD_DIR>`: directory containing the card; paths are resolved relative to it.
- Variables: `{{VAR}}` placeholders replace exactly one directory or filename segment and default to the first alphabetical value. Use named variables even when only one exists; a pivot is optional when there is only one variable.
- Wildcard (`*`): plain glob segment only; it is not a variable and never exposed in the UI.
- Pivot: `pivot_chart = "{{VAR}}"` identifies which variable cycles when moving prev/next.
- Styles: `chart_style` accepts `line`, `scatter`, `colormap` (1-D heatmap strip), `eventline` (1-D spike/event line), or `ranges` (1-D range bands). You can use the string shorthand (`"line"`) or an object with a `name` and optional parameters, e.g. `chart_style = { name = "line", width = 3 }` or `chart_style = { name = "ranges", palette = "cividis", alpha = 0.25 }`. Subcards and overlays may override it; missing overrides fall back to the card’s global style. One-dimensional plots can overlay with each other or with 2-D plots; in mixed overlays, 1-D data renders behind the 2-D plot with transparency. Aliases are accepted: `colormap_line`/`heatmap1d` → `colormap`, `events`/`spikes` → `eventline`, `range` → `ranges`. Table datasets ignore `chart_style` and always render as tables.
- Range style params: `palette` (colormap name), `colors` (explicit list of colors), and `alpha` (0-1 or 0-255). When both `palette` and `colors` are provided, `colors` wins.
- Synchronization: compound cards may set `synchronize_axis = true` under `[global]` to link the X axis across panels (panning/zooming one updates the others).
- Overlay discovery: `overlay_variable` marks a variable used only for overlay enumeration; it is not user-selectable and is removed from card variables/pivot logic. Variable-level filters (see below) apply to overlay variables as well; optional `overlay_path_filter` (regex on the resolved path) can further constrain entries.

## Global Section (optional)
```toml
[global]
chart_style = "line"
pivot_chart = "{{CLASS}}"  # required when >1 variable; optional for a single variable
```

## Simple Card
```toml
filepath = "<CARD_DIR>/../data/simple_study/*"
chart_style = "line"
```
Wildcard-only cards do not require `pivot_chart`, but when you need a selectable value, declare a named variable instead of relying on `*`.

## Multi-Variable Card
```toml
filepath = "<CARD_DIR>/../data/complex_study/{{DATASET}}/{{CLASS}}/time_series.json"
pivot_chart = "{{CLASS}}"  # required because two variables exist
chart_style = "line"
```

## Subcards / Composites
```toml
[global]
pivot_chart = "{{CLASS}}"
chart_style = "line"

[subcards.time_series]
chart_height = "40%"        # remaining height is split across unspecified panels
filepath = "<CARD_DIR>/../data/.../{{DATASET}}/{{CLASS}}/time_series.json"

[subcards.scatter]
chart_style = "scatter"
filepath = "<CARD_DIR>/../data/.../{{DATASET}}/{{CLASS}}/scatter.json"
```

## Overlays
```toml
[global]
chart_style = "line"        # used when per-series style is omitted

filepath = [
  "<CARD_DIR>/../data/.../{{DATASET}}/{{CLASS}}/time_series.json",
  "<CARD_DIR>/../data/.../{{DATASET}}/{{CLASS}}/ms2_frag-{{FRAG}}_scatter.json"
]
chart_style = [
  { name = "line" },
  { name = "scatter", marker_size = 6 }
]                                        # or a single value applied to all paths
overlay_variable = "{{FRAG}}"      # auto-discovers matching files and overlays them; not exposed in the UI
overlay_path_filter = "_relative"  # optional regex applied to the full path
[variable_filters]
FRAG = "^[0-9.]+$"                 # per-variable regex filters (full-match); applies to overlays too
```
When `chart_style` entries are missing/shorter than `filepath`, remaining series use the card’s global style. If `overlay_variable` is provided, that variable is filtered out from selectable variables and every match of the pattern is rendered together in the overlay.

## Variable Filters
- Define under `[variable_filters]` as `NAME = "regex"` (full-match). Applied during discovery to all captured variable values, including overlay variables.

## Discovery Rules
1. Convert each template to a glob and regex; enumerate matches up to internal limits.
2. Variables are single-level only; recursion is constrained to the positions variables occupy, not arbitrary depth.
3. Default selections use alphabetical order; cycling advances only the pivot variable.
4. If a card defines multiple user variables (excluding `overlay_variable`) without `pivot_chart`, it is rejected.
5. Each subcard must resolve to existing files; overlays load every path listed in their array and, if `overlay_variable` is present, every discovered match of that pattern.

## Validation
- Required fields: a top-level `filepath` **or** a `[subcards]` section.
- `chart_height` accepts percentages; totals above 100% are clamped with a warning.
- `chart_style` must be recognized; per-series lists may be shorter than `filepath` arrays and will be extended using the last value/global style.
- Missing or mismatched variables in `pivot_chart` cause errors.
