# Card Specification

TOML cards describe where to find datasets and how to render them. Variables are single path components discovered automatically so users can cycle through data without manual file picking.

## Core Concepts
- `<CARD_DIR>`: directory containing the card; paths are resolved relative to it.
- Variables: `{{VAR}}` or `*` (wildcard). They replace exactly one directory or filename segment and default to the first alphabetical value.
- Pivot: `pivot_chart = "{{VAR}}"` identifies which variable cycles when moving prev/next.
- Styles: `chart_style` accepts `line` or `scatter` today. Subcards and overlays may override it; missing overrides fall back to the card’s global style.
- Overlay discovery: `overlay_variable` marks a variable used only for overlay enumeration; it is not user-selectable and is removed from card variables/pivot logic.

## Global Section (optional)
```toml
[global]
chart_style = "line"
pivot_chart = "{{CLASS}}"  # required when >1 variable; optional for a single variable/wildcard
```

## Simple Card
```toml
filepath = "<CARD_DIR>/../data/simple_study/*"
chart_style = "line"
```
Wildcard cards do not require `pivot_chart`.

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
chart_style = ["line", "scatter"]  # or a single value applied to all paths
overlay_variable = "{{FRAG}}"      # auto-discovers matching files and overlays them; not exposed in the UI
```
When `chart_style` entries are missing/shorter than `filepath`, remaining series use the card’s global style. If `overlay_variable` is provided, that variable is filtered out from selectable variables and every match of the pattern is rendered together in the overlay.

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
