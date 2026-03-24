# Dynamic Visualizer Development Guide

## Purpose
Desktop GUI (PySide6 + PyQtGraph) that loads JSON data, infers sensible defaults, and lets users switch visualization styles or apply TOML “cards” for richer layouts and overlays.

## Local Packaging
- Install editable + dev tools: `pip install -e ".[dev]"`
- Run the app with `dynamic-visualizer` or `python -m visualizer`.
- Build/test a wheel: `python -m build` then install `dist/*.whl` in a clean environment.

## Architecture Snapshot
- **Data access:** `DatasetRepository` loads JSON with length/number validation, coerces types, caches by path+mtime. JSON payloads are schema-validated when `jsonschema` is installed. Dataset discovery is recursive when a folder is chosen.
- **Interpretation:** `DefaultInterpreter` maps series datasets to `PlotSpec` and table datasets to `TableSpec`, infers line vs scatter (monotonic numeric X → line), and sorts X/Y for line plots.
- **Visualization:** `PlotRenderer` draws single or multiple specs on PyQtGraph widgets, including line/scatter/stick 2-D series plus 1-D colormap strips, event lines, and range bands; `TableRenderer` handles tabular views with configurable palette/range rules.
- **Controller/orchestration:** `SessionController` owns card loading, matching, selection, and panel planning (including overlay expansion). `MainWindow` handles only the PySide6 widgets and delegates data/card logic to the controller.
- **State persistence:** `StateManager` keeps last-used data/card paths and a recent-session history. Startup restores the current session snapshot, and File > Open Previous Session can reopen remembered snapshots. Entries with removed paths or empty data/card folders are pruned automatically.
- **Cards:** Parsed by `CardLoader`; `CardSession` resolves variables, enforces pivot for multi-variable cards, supports subcards and overlays. `chart_style` supports structured styles (`{ name = \"line\", ... }`) with style-specific argument validation (unknown args fail early); defaults cascade: per-series → subcard → global. `overlay_variable` lets overlays auto-enumerate series (e.g., multiple fragments) without exposing them as selectable variables. When the default alphabetical variable pick forms an invalid combination, selection auto-recovers to the closest discovered match. When `chart_style` is explicitly set, the dataset must be compatible (range data requires `ranges`; table data cannot declare a chart style); when omitted, panels can switch between table and plot data.
- **Axes:** Cards can control axis visibility with `show_x_axis`/`show_y_axis` (global or per subcard). With `synchronize_axis = true`, X axes are hidden by default unless explicitly enabled.

## Data Contracts
- JSON series: must match `src/visualizer/schema/data_payload.schema.json` (`data.x_axis` required; optional `data.y_axis` must match length when present); non-numeric Y is rejected; labels are optional. Eventline plots ignore `data.y_axis`.
- JSON tables: use flat `data.column_names` or grouped `data.column_headers` together with `data.row_names` and a row-major `data.content` matrix; lengths must match the flattened leaf columns. Optional `data.table_title` displays a compact title above table views. Optional `data.table_style` can define a global rule plus row/column overrides, including `reverse = true` to flip numeric gradients; column rules still target flattened leaf columns even when grouped headers are used.
- JSON ranges: use `data.ranges` as an array of `[start, end]` pairs (numeric); optional `data.range_info` entries (same length as `ranges`) are shown in an instant floating hover info box that follows the cursor while it stays inside a range; use `data.kind = "ranges"` to avoid warnings (legacy `data.kind = "range"` still loads with a warning).
- `data.kind` is optional (`series`, `table`, or `ranges`); when omitted the loader auto-detects based on the available fields.
- CSV is temporarily disabled and will return in a future update.

## Card Rules (see `docs/card_specification.md` and `docs/cards_reference.md`)
- Variables (`{{VAR}}`) are single-level components discovered from directory/file names. Wildcards (`*`) are plain globs and not exposed as variables.
- `pivot_chart` is optional; when omitted, cards default to the first discovered variable (alphabetical).
- Subcards may set `chart_height` and `chart_style`; overlays accept arrays for `filepath`/`chart_style`, optional per-series labels, and fall back to the global style when unspecified. Variable-level regex filters apply to overlays too.
- Discovery is template-driven and bounded per subcard; recursive scans are limited to variable positions, not arbitrary depth. Wildcards that remain in non-overlay paths must resolve to exactly one file.

## Near-Term Work
- Add caching/decimation strategies for very large datasets.
- Expand interpreters/renderers beyond line/scatter/stick (e.g., boolean/heat maps).
- Broaden validation and error surfacing in the GUI (e.g., schema path display, missing files per panel).
- Grow test coverage across GUI callbacks and additional card scenarios.
