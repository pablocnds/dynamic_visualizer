# Cards Quick Reference

Practical guide for creating and customizing TOML cards.

## 1. Minimal Template
```toml
[global]
pivot_chart = "{{CLASS}}"     # optional
chart_style = "line"          # optional

filepath = "<CARD_DIR>/../data/study/{{CLASS}}/signal.json"
```

## 2. Core Building Blocks
- `filepath`: path template (string) or series list (array).
- `{{VAR}}`: captured variable, shown in UI selectors.
- `*`: wildcard glob, not a selectable variable.
- `[global]`: card defaults shared by subcards/series.
- `[subcards.<name>]`: multi-panel card sections.
- `chart_style`: string or object:
  - string: `chart_style = "scatter"`
  - object: `chart_style = { name = "scatter", marker_size = 7 }`
- `series_label`: optional label(s) for array/filepath overlays.
  - For table data, this is used as the compact table title.

## 3. Style Arguments
Style args are validated when loading cards. Unknown keys raise an error.

```toml
chart_style = { name = "line", color = "#1e4f9a", line_width = 2.0, alpha = 0.9 }
```

Supported args by style:

| Style | Args |
|---|---|
| `line` | `color`, `alpha`, `line_width`/`width` |
| `scatter` | `color`, `alpha`, `marker_size`/`size` |
| `stick` | `color`, `alpha`, `line_width`/`width` |
| `colormap` | `palette`, `alpha` |
| `eventline` | `color`, `palette`, `alpha` |
| `ranges` | `colors`, `palette`, `alpha` (`colors` takes precedence) |

Aliases:
- `heatmap1d`, `colormap_line` -> `colormap`
- `events`, `spikes` -> `eventline`
- `range` -> `ranges`

## 4. Common Templates

### Simple wildcard card
```toml
filepath = "<CARD_DIR>/../data/simple_study/*"
chart_style = "line"
```

### Multi-variable card
```toml
[global]
pivot_chart = "{{CLASS}}"
chart_style = "line"

filepath = "<CARD_DIR>/../data/complex_study/{{DATASET}}/{{CLASS}}/time_series.json"
```

### Compound card (multiple panels)
```toml
[global]
pivot_chart = "{{CLASS}}"
synchronize_axis = true
show_x_axis = true

[subcards.signal]
chart_height = "45%"
filepath = "<CARD_DIR>/../data/.../{{DATASET}}/{{CLASS}}/time_series.json"
chart_style = { name = "line", line_width = 2.0 }

[subcards.events]
chart_height = "25%"
filepath = "<CARD_DIR>/../data/.../{{DATASET}}/{{CLASS}}/events.json"
chart_style = { name = "eventline", color = "#253ca8", alpha = 0.7 }

[subcards.table]
chart_height = "30%"
filepath = "<CARD_DIR>/../data/.../{{DATASET}}/{{CLASS}}/table.json"
table_style = { palette = "plasma", range = [0, 100] }
```

### Overlay from explicit filepath list
```toml
[global]
chart_style = "line"

filepath = [
  "<CARD_DIR>/../data/.../{{DATASET}}/{{CLASS}}/signal.json",
  "<CARD_DIR>/../data/.../{{DATASET}}/{{CLASS}}/spikes.json",
  "<CARD_DIR>/../data/.../{{DATASET}}/{{CLASS}}/ranges.json"
]
chart_style = [
  { name = "line", color = "#1f3f8f" },
  { name = "eventline", alpha = 0.75 },
  { name = "ranges", palette = "cividis", alpha = 0.25 }
]
series_label = ["Signal", "Events", "Windows"]
```

### Overlay auto-discovery with hidden overlay variable
```toml
[global]
pivot_chart = "{{CLASS}}"
chart_style = "scatter"

filepath = [
  "<CARD_DIR>/../data/.../{{CLASS}}/base.json",
  "<CARD_DIR>/../data/.../{{CLASS}}/frag-{{FRAG}}.json"
]
chart_style = ["line", { name = "scatter", marker_size = 6 }]
overlay_variable = "{{FRAG}}"      # not shown in the UI
overlay_path_filter = "_relative"  # optional regex on resolved path

[variable_filters]
FRAG = "^[0-9.]+$"
```

## 5. Table Customization

Card-level table style fallback:
```toml
[global]
table_style = { palette = "magma", range = [0, 120] }
```

Per-subcard override:
```toml
[subcards.metrics]
filepath = "<CARD_DIR>/../data/.../metrics.json"
table_style = { palette = "plasma" }
```

Card-level table title via label:
```toml
filepath = ["<CARD_DIR>/../data/.../table.json"]
series_label = "Model Metrics"
```

JSON can also provide `data.table_title`, and row/column-specific `data.table_style`.

## 6. Behavior Notes
- If `pivot_chart` is omitted, the first discovered variable (alphabetical) becomes pivot.
- If default alphabetical selections do not form a valid combination, selection snaps to the nearest valid match.
- In overlays, missing `chart_style` entries reuse the last style/global fallback.
- Tables reject incompatible `chart_style`; range datasets require `ranges`.

## 7. Troubleshooting
- `unsupported chart_style args ...`: typo or unsupported arg for that style.
- `chart_style object must include 'name'`: object form requires `name`.
- `Pivot variable ... is not present`: `pivot_chart` variable does not exist in `filepath`.
- `wildcard matched multiple files`: pattern is ambiguous; refine it or add variables.
