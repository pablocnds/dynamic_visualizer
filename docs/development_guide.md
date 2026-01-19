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
- **Visualization:** `PlotRenderer` draws single or multiple specs on PyQtGraph widgets, including 1-D colormap strips and event lines; `TableRenderer` handles tabular views.
- **Controller/orchestration:** `SessionController` owns card loading, matching, selection, and panel planning (including overlay expansion). `MainWindow` handles only the PySide6 widgets and delegates data/card logic to the controller.
- **Cards:** Parsed by `CardLoader`; `CardSession` resolves variables, enforces pivot for multi-variable cards, supports subcards and overlays. `chart_style` now supports structured styles (`{ name = \"line\", ... }`) that flow through to the visualization registry; defaults cascade: per-series → subcard → global. `overlay_variable` lets overlays auto-enumerate series (e.g., multiple fragments) without exposing them as selectable variables.

## Data Contracts
- JSON series: must match `src/visualizer/schema/data_payload.schema.json` (`data.x_axis`/`data.y_axis` arrays with equal, non-empty lengths); non-numeric Y is rejected; labels are optional.
- JSON tables: use `data.column_names`/`data.row_names` with a row-major `data.content` matrix; lengths must match.
- `data.kind` is optional (`series` or `table`); when omitted the loader auto-detects based on the available fields.
- CSV is temporarily disabled and will return in a future update.

## Card Rules (see `docs/card_specification.md`)
- Variables (`{{VAR}}`) are single-level components discovered from directory/file names. Wildcards (`*`) are plain globs and not exposed as variables.
- If a card has more than one variable, `pivot_chart` is required; single-variable cards may omit it.
- Subcards may set `chart_height` and `chart_style`; overlays accept arrays for `filepath`/`chart_style`, optional per-series labels, and fall back to the global style when unspecified. Variable-level regex filters apply to overlays too.
- Discovery is template-driven and bounded per subcard; recursive scans are limited to variable positions, not arbitrary depth. Wildcards that remain in non-overlay paths must resolve to exactly one file.

## Near-Term Work
- Add caching/decimation strategies for very large datasets.
- Expand interpreters/renderers beyond line/scatter (e.g., boolean/heat maps).
- Broaden validation and error surfacing in the GUI (e.g., schema path display, missing files per panel).
- Grow test coverage across GUI callbacks and additional card scenarios.
- TODO: allow table cell color maps to be customized via card configuration (numeric/boolean/other palettes).
