# Agent Card Authoring Guide

This guide is the single practical reference for agents creating Dynamic Visualizer
cards for real applications. A card is a TOML file that tells the visualizer which
JSON files to discover, which path segments are user-selectable variables, and how
to render each dataset.

Use this workflow:

1. Inspect the application's output folder and identify stable file patterns.
2. Map real app concepts to card variables, panels, and overlays.
3. Write a TOML card using `<CARD_DIR>`-relative paths.
4. Validate that every template resolves to existing JSON payloads and that the
   chosen styles match the data kinds.

## Inputs the Application Must Produce

Cards point to JSON data files. They do not compute, clean, or convert raw app data.
If the real application emits another format, create or update its export step so it
also writes visualizer-compatible JSON.

Supported payload shapes:

```json
{
  "data": {
    "kind": "series",
    "x_label": "Time",
    "y_label": "Intensity",
    "x_axis": [0, 1, 2],
    "y_axis": [10.0, 12.5, 9.8]
  }
}
```

```json
{
  "data": {
    "kind": "table",
    "column_names": ["precision", "recall"],
    "row_names": ["baseline", "experiment"],
    "content": [[0.81, 0.76], [0.86, 0.83]]
  }
}
```

```json
{
  "data": {
    "kind": "ranges",
    "ranges": [[1.2, 1.8], [4.0, 4.6]],
    "range_info": ["candidate A", "candidate B"]
  }
}
```

Notes:

- `kind` is optional for series and tables but recommended. Use
  `"kind": "ranges"` for range payloads.
- Series `x_axis` may contain numbers or category strings. `y_axis` is optional for
  event-line style data.
- Tables may use grouped `column_headers` instead of `column_names`; row-major
  `content` must still match the flattened leaf columns.
- Range `range_info` is optional, but when provided it must have one entry per
  range.

## Card File Basics

Cards are TOML files. Files named `__*.toml` are ignored by card discovery, so do
not use that prefix for cards that should appear in the app.

Important path rules:

- Use `<CARD_DIR>` for the directory containing the card, then navigate to data
  from there.
- Use `{{VAR}}` for a selectable variable. A variable captures exactly one path
  component or filename segment.
- Use `*` only as a non-selectable glob wildcard. It is not shown in the UI.
- Prefer named variables over broad wildcards when users need to compare or cycle
  real app entities such as dataset, run, subject, sample, class, compound, model,
  metric, or timepoint.
- A card must define either a top-level `filepath` or one or more `[subcards.*]`.

Minimal card:

```toml
[global]
pivot_chart = "{{SAMPLE}}"
chart_style = "line"

filepath = "<CARD_DIR>/../data/{{PROJECT}}/{{SAMPLE}}/signal.json"
```

## Choosing Variables for Real Applications

First inspect the application's data tree and decide which dimensions matter to a
human user.

Good variable choices:

- `{{RUN}}`, `{{BATCH}}`, `{{PROJECT}}`: top-level execution groups.
- `{{SUBJECT}}`, `{{SAMPLE}}`, `{{CLASS}}`, `{{COMPOUND}}`: primary things users
  cycle through.
- `{{MODEL}}`, `{{METHOD}}`, `{{CONDITION}}`: comparison dimensions.
- `{{METRIC}}`, `{{CHANNEL}}`, `{{FRAGMENT}}`: optional selectors or overlay-only
  dimensions.

Set `pivot_chart` to the dimension that Prev/Next should cycle. If omitted, the
first discovered variable alphabetically is used. In most real applications, set it
explicitly.

```toml
[global]
pivot_chart = "{{COMPOUND}}"

filepath = "<CARD_DIR>/../processed/{{BATCH}}/{{COMPOUND}}/summary.json"
```

Use `variable_filters` when a filename contains multiple machine-generated variants
but only some should become valid variable values:

```toml
[variable_filters]
FRAGMENT = "^[0-9.]+$"
MODEL = "^(baseline|candidate_a|candidate_b)$"
```

Filters are full-match regular expressions and are validated when the card loads.

## Picking the Card Shape

Use a simple card when one file answers the question:

```toml
[global]
pivot_chart = "{{SAMPLE}}"
chart_style = "line"

filepath = "<CARD_DIR>/../data/{{SAMPLE}}/timeseries.json"
```

Use a multi-variable card when the same visualization exists across several app
dimensions:

```toml
[global]
pivot_chart = "{{SAMPLE}}"
chart_style = "scatter"

filepath = "<CARD_DIR>/../runs/{{RUN}}/{{SAMPLE}}/{{METHOD}}/embedding.json"
```

Use a compound card when the user needs separate panels for the same current
selection:

```toml
[global]
pivot_chart = "{{SAMPLE}}"
synchronize_axis = true

[subcards.raw_signal]
chart_height = "45%"
chart_style = "line"
filepath = "<CARD_DIR>/../data/{{RUN}}/{{SAMPLE}}/raw_signal.json"

[subcards.events]
chart_height = "20%"
chart_style = { name = "eventline", color = "#253ca8", alpha = 0.7 }
filepath = "<CARD_DIR>/../data/{{RUN}}/{{SAMPLE}}/events.json"

[subcards.metrics]
chart_height = "35%"
filepath = "<CARD_DIR>/../data/{{RUN}}/{{SAMPLE}}/metrics.json"
table_style = { palette = "viridis", range = [0, 1] }
```

Use an overlay when multiple files should render in the same plot:

```toml
[global]
pivot_chart = "{{SAMPLE}}"
chart_style = [
  { name = "line", color = "#1f3f8f", line_width = 2.0 },
  { name = "scatter", marker_size = 6, alpha = 0.8 },
  { name = "ranges", palette = "cividis", alpha = 0.25 }
]
series_label = ["Signal", "Detected Peaks", "Accepted Windows"]

filepath = [
  "<CARD_DIR>/../data/{{SAMPLE}}/signal.json",
  "<CARD_DIR>/../data/{{SAMPLE}}/peaks.json",
  "<CARD_DIR>/../data/{{SAMPLE}}/accepted_ranges.json"
]
```

Use an overlay variable when an application emits an unknown number of related files
that should all render together, but should not become UI selectors:

```toml
[global]
pivot_chart = "{{SAMPLE}}"
overlay_variable = "{{FRAGMENT}}"
chart_style = ["line", { name = "scatter", marker_size = 5 }]
series_label = ["Base", "Fragments"]

filepath = [
  "<CARD_DIR>/../data/{{SAMPLE}}/base_signal.json",
  "<CARD_DIR>/../data/{{SAMPLE}}/fragment-{{FRAGMENT}}.json"
]

[variable_filters]
FRAGMENT = "^[0-9.]+$"
```

`overlay_path_filter` may further restrict auto-discovered overlay paths by regular
expression on the resolved full path:

```toml
overlay_path_filter = "_relative"
```

## Styles

`chart_style` can be a string or an object with a `name` and style-specific
arguments. Global styles are inherited by subcards and series unless overridden.

```toml
chart_style = "line"
```

```toml
chart_style = { name = "line", color = "#1e4f9a", line_width = 2.0, alpha = 0.9 }
```

Supported chart styles:

| Style | Use for | Arguments |
| --- | --- | --- |
| `line` | continuous series | `color`, `alpha`, `line_width` or `width` |
| `scatter` | point clouds, detected points | `color`, `alpha`, `marker_size` or `size` |
| `stick` | spectra or impulse-like intensities | `color`, `alpha`, `line_width` or `width` |
| `colormap` | 1-D heat strip along X | `palette`, `alpha`, `reverse` |
| `eventline` | spikes/events along X | `color`, `palette`, `alpha`, `reverse` |
| `ranges` | interval bands along X | `colors`, `palette`, `alpha`, `reverse` |

Aliases are accepted, but prefer canonical names in new cards:

- `heatmap1d`, `colormap_line` -> `colormap`
- `events`, `spikes` -> `eventline`
- `range` -> `ranges`

Chart palettes: `viridis`, `plasma`, `cividis`, `magma`, `turbo`.

Color values may be named colors, hex strings, or RGB/RGBA sequences.

Tables render as tables when no `chart_style` is specified. Do not set a chart style
on table payloads. In mixed chart/table cards, avoid a global `chart_style`; set
chart styles only on the plot subcards and use `table_style` for tables:

```toml
[global]
table_style = { palette = "magma", range = [0, 100], reverse = true }
```

Table palettes: `blue`, `viridis`, `plasma`, `cividis`, `magma`.

## Axis and Layout Controls

Compound cards can control panel heights:

```toml
[subcards.signal]
chart_height = "60%"
```

Unspecified heights split remaining space. Totals above 100% are clamped with a
warning.

Synchronize X axes when panels share the same X domain:

```toml
[global]
synchronize_axis = true
```

With synchronized axes, X axes are hidden by default unless explicitly enabled.
Control axes globally or per subcard:

```toml
[global]
show_x_axis = true
show_y_axis = true

[subcards.top]
show_x_axis = false
```

## Discovery and Validation Rules

Remember these when designing real application file layouts:

- Every `filepath` template is converted to a glob and a regex, then matched against
  existing files.
- Variables capture one segment only; they do not recurse through arbitrary depth.
- Default selections use alphabetical order and snap to the nearest valid discovered
  combination if the initial combination does not exist.
- GUI selectors only offer values compatible with the current selection.
- Each subcard must resolve to existing files for the current selection.
- Wildcards with no variables must resolve to exactly one file.
- Wildcards combined with variables must not match multiple files for the same
  variable combination.
- Per-series `chart_style` lists may be shorter than `filepath` lists; missing
  entries reuse the last style or the global fallback.
- `series_label` may be a string or list on filepath arrays. For table datasets it
  becomes the compact table title.
- Unsupported style argument keys, invalid palette names, missing pivot variables,
  and invalid regex filters fail at card load time.

## Real Application Authoring Checklist

Before writing the card:

- Identify the output root relative to the card file.
- List the app dimensions users should control.
- Decide the primary pivot for Prev/Next.
- Decide whether comparisons belong in separate panels or the same overlay.
- Confirm every referenced file is valid visualizer JSON.

While writing the card:

- Use `<CARD_DIR>` in every path.
- Use descriptive uppercase variable names.
- Use `overlay_variable` only for dimensions that should be hidden from the UI.
- Add `variable_filters` for numeric IDs, model names, fragment names, or any noisy
  generated filename segment.
- Use canonical chart style names.
- Avoid `*` unless the pattern is guaranteed to resolve to one file for each
  selection.

After writing the card:

- Load it in the app with File > Open Card File.
- Verify the sidebar selectors show the intended dimensions.
- Verify Prev/Next cycles the intended pivot.
- Verify loaded file paths match the selected real app entity.
- Check all panels, overlays, labels, table titles, hover info, and synchronized axes.
- If discovery fails, refine path templates or filters instead of broadening with
  more wildcards.

## Common Patterns

Application run comparison:

```toml
[global]
pivot_chart = "{{SAMPLE}}"
chart_style = "line"

[subcards.run_a]
chart_height = "50%"
filepath = "<CARD_DIR>/../outputs/{{RUN_A}}/{{SAMPLE}}/signal.json"

[subcards.run_b]
filepath = "<CARD_DIR>/../outputs/{{RUN_B}}/{{SAMPLE}}/signal.json"
```

Model metrics table plus prediction trace:

```toml
[global]
pivot_chart = "{{DATASET}}"
table_style = { palette = "viridis", range = [0, 1] }

[subcards.metrics]
chart_height = "35%"
filepath = "<CARD_DIR>/../eval/{{MODEL}}/{{DATASET}}/metrics.json"
series_label = "Model Metrics"

[subcards.predictions]
chart_height = "65%"
chart_style = { name = "scatter", marker_size = 4, alpha = 0.8 }
filepath = "<CARD_DIR>/../eval/{{MODEL}}/{{DATASET}}/predictions.json"
```

Signal with dynamic detected feature overlays:

```toml
[global]
pivot_chart = "{{SAMPLE}}"
overlay_variable = "{{FEATURE_ID}}"
chart_style = [
  { name = "line", color = "#1f3f8f" },
  { name = "scatter", marker_size = 5, alpha = 0.75 }
]
series_label = ["Signal", "Features"]

filepath = [
  "<CARD_DIR>/../analysis/{{SAMPLE}}/signal.json",
  "<CARD_DIR>/../analysis/{{SAMPLE}}/feature-{{FEATURE_ID}}.json"
]

[variable_filters]
FEATURE_ID = "^[0-9]+$"
```

Aligned analytical dashboard:

```toml
[global]
pivot_chart = "{{COMPOUND}}"
synchronize_axis = true

[subcards.summary]
chart_height = "30%"
filepath = "<CARD_DIR>/../processed/{{BATCH}}/{{COMPOUND}}/summary_table.json"

[subcards.signal]
chart_height = "45%"
chart_style = [
  { name = "line", line_width = 2.0 },
  { name = "ranges", palette = "cividis", alpha = 0.25 }
]
filepath = [
  "<CARD_DIR>/../processed/{{BATCH}}/{{COMPOUND}}/signal.json",
  "<CARD_DIR>/../processed/{{BATCH}}/{{COMPOUND}}/ranges.json"
]

[subcards.scores]
chart_height = "25%"
chart_style = { name = "colormap", palette = "magma", reverse = true }
filepath = "<CARD_DIR>/../processed/{{BATCH}}/{{COMPOUND}}/scores.json"
```
