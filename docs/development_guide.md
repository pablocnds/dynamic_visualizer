# Dynamic Visualizer Development Guide

## Purpose
Desktop GUI (PySide6 + PyQtGraph) that loads CSV/JSON data, infers sensible defaults, and lets users switch visualization styles or apply TOML “cards” for richer layouts and overlays.

## Architecture Snapshot
- **Data access:** `DatasetRepository` loads CSV/JSON with length/number validation, coerces types, caches by path+mtime. Dataset discovery is recursive when a folder is chosen.
- **Interpretation:** `DefaultInterpreter` maps a dataset to `PlotSpec`, infers line vs scatter (monotonic numeric X → line), and sorts X/Y for line plots.
- **Visualization:** `PlotRenderer` draws single or multiple specs on PyQtGraph widgets; caching of rendered charts is planned for large datasets.
- **GUI/orchestration:** `MainWindow` handles folder selection (no default path), file list, cards list, variable selectors, per-panel mode overrides, navigation via `pivot_chart`, and reset view.
- **Cards:** Parsed by `CardLoader`; `CardSession` resolves variables, enforces pivot for multi-variable cards, supports subcards and overlays. `chart_style` defaults cascade: per-series → subcard → global.

## Data Contracts
- CSV: at least two columns; prefers `x_axis`/`y_axis`, otherwise uses the first two; lengths must match; Y must be numeric.
- JSON: must match `schema/data_payload.schema.json` shape (`data.x_axis`/`data.y_axis` arrays with equal, non-empty lengths); non-numeric Y is rejected; labels are optional.

## Card Rules (see `docs/card_specification.md`)
- Variables (`{{VAR}}` or `*`) are single-level components discovered from directory/file names.
- If a card has more than one variable, `pivot_chart` is required; single-variable or wildcard cards may omit it.
- Subcards may set `chart_height` and `chart_style`; overlays accept arrays for `filepath`/`chart_style` and fall back to the global style when unspecified.
- Discovery is template-driven and bounded per subcard; recursive scans are limited to variable positions, not arbitrary depth.

## Near-Term Work
- Add caching/decimation strategies for very large datasets.
- Expand interpreters/renderers beyond line/scatter (e.g., boolean/heat maps).
- Broaden validation and error surfacing in the GUI (e.g., schema path display, missing files per panel).
- Grow test coverage across GUI callbacks and additional card scenarios.
