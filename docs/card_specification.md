# Card Specification

This document defines the configuration format for visualization cards. It is a living reference and must be revised whenever the format evolves.

## Goals
- Describe datasets without coding so the GUI can discover files, infer variables, and render plots with minimal user action.
- Enforce "convention over configuration" by auto-populating variables (no manual selection) and providing sensible defaults for chart styles/layouts.
- Support progressive complexity: single-series cards, multi-variable switching, multi-panel comparisons, composite dashboards.

> **Implementation status:** current build supports simple wildcard cards, single-file cards with automatically discovered variables (e.g., Dataset + Class) plus pivot-based cycling, and multi-pane cards with subcards (e.g., comparison/composite cards). Future sections describe additional capabilities (boolean maps, advanced layouts) that are not yet implemented.

## Common Concepts
- **Card file root (`<CARD_DIR>`)**: placeholder for the directory where the card resides. Paths are resolved relative to it.
- **Data root**: Cards are expected to reference files under a controlled `data/` hierarchy. Discovery only walks directories referenced by a card to avoid deep scans.
- **Variables (`{{VAR}}`)**: placeholders that resolve automatically by inspecting directory names or file stems. They always map to a single directory or filename component (no multi-level expansion) and default to the alphabetical first match. Cycling through views changes only the variable identified by `pivot_chart`.
- **Wildcard (`*`)**: shorthand for a single anonymous variable when no other variables exist (same semantics as `{{VAR}}`).
- **Pivot**: `pivot_chart = {{VAR_NAME}}` identifies which variable changes when the user advances to the next visualization.
- **Chart style**: default visualization type (`line`, `scatter`, `boolean_map`, etc.). Subcards inherit this unless overridden.

## Autodiscovery Rules
1. Parse the `filepath` template and list the directory levels that contain variables.
2. For each variable appearance, enumerate directories/files that match the surrounding pattern, caching the results per card.
3. Default selection is the alphabetically first result. Cycling follows alphabetical order.
4. Wildcards behave like unnamed variables following the same enumeration rules.
5. Discovery guards: stop recursion at the expected depth (only inspect directories where the template specifies a variable), and fail with a warning if enumeration exceeds internal limits (e.g., >1000 entries or >2 seconds per level).

## Filepath Field
```
filepath = "<CARD_DIR>/data/simple_study/*"
filepath = "<CARD_DIR>/data/complex/{{DATASET}}/{{CLASS}}/time_series.json"
```
- Required for each card or subcard.
- Must evaluate to at least one existing file (JSON/CSV) for the card to load.
- If multiple matches exist, the card cycles through them according to `pivot_chart`.

## Global Section (optional)
```
[global]
chart_style = "line"
pivot_chart = "{{CLASS}}"
```
- `chart_style`: default visualization applied to the card (string). Subcards inherit unless they define their own.
- `pivot_chart`: identifies the variable used for cycling. Required when at least one variable exists. Only one variable should be designated. Always wrap the placeholder in quotes so the file remains valid TOML.
- Additional future settings (e.g., themes) will be documented here.

## Subcards
Subcards define multiple panes within a single card.
```
[subcards.dataset1]
filepath = "<CARD_DIR>/data/..."
chart_height = "50%"
chart_style = "scatter"  # optional override
```
- Inherit `chart_style`, `pivot_chart`, and other global defaults unless overridden.
- `chart_height`: optional percentage (string with `%`). Missing values are assigned from remaining height equally. If the sum exceeds 100%, the loader clamps and surfaces a validation error in the GUI.
- `chart_style`: optional visualization override for that panel (e.g., time series = line, scatter = scatter). When omitted, the subcard inherits `global.chart_style`.
- Missing files per subcard: if a filepath resolves to zero matches, that panel is skipped while others render.

## Validation
- Cards must validate against a TOML schema (to be finalized). Validation covers required keys, allowed chart styles, numeric formats, and layout constraints.
- Loader should surface actionable errors (missing files, invalid variables, conflicting heights) without crashing the app.

## Rendering Behavior
- When a card is active, the GUI replaces variables according to the current selection, loads each resolved file, and displays the plots based on `chart_style` (with per-panel overrides).
- Subcards render top-to-bottom respecting `chart_height` percentages.
- Missing data for composite cards: render available panels and note missing data in the status area.

## Future Considerations
- Formal JSON schema (converted from TOML) for tooling/tests.
- Support for additional visualization types (heatmaps, boolean grids) and per-series styling metadata.
- Caching of resolved variable combinations to accelerate switching across large data directories.
