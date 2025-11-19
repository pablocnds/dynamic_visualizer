# Dynamic Visualizer Development Guide

## Purpose and Status
- **Objective:** Build a reusable pipeline that loads processed analytical data from heterogenous sources (CSV, JSON) and renders interactive plots via a native desktop GUI (PySide6 + PyQtGraph).
- **Scope:** Start with single-series line visualizations, but architecture must generalize to additional interpreters, chart types, and visualization layouts.
- **Living Document:** Update the README and this guide whenever architecture, dependencies, or workflows change.

## High-Level Requirements
1. Load generic two-axis datasets from CSV or JSON files under `example_data/` (later arbitrary roots) and render in < 1 second when cached.
2. GUI user can choose which file(s) to visualize without restarting the application. Future revisions will allow selecting configuration cards/profiles.
3. Application must run as a local desktop app without requiring a server or file uploads—file selectors operate directly on local paths. **Status:** satisfied by PySide6/PyQtGraph plan; revisit if packaging introduces constraints.
4. Interpretation layer defaults to a simple axis-mapping logic now but must evolve to support declarative cards (TOML) describing sources and rendering specifics (see `docs/card_specification.md`). **Status:** spec drafted; implementation starts after the base GUI stabilizes.
5. Support multiple visualization types in the long run (line plots, scatter overlays, boolean grids). Only line plots are implemented in phase 1. **Status:** boolean map and composite plot requirements are TBD.
6. Provide caching so previously rendered plots switch instantly; acceptable implementations include in-memory memoization plus optional persistent caches. Avoid large memory footprints by setting cache size limits for cases of long sessions with multiple plots.
7. To guarantee speed and responsiveness, with large datasets consider downsampling strategies during rendering and/or caching to keep data handling efficient (e.g., PyQtGraph's built-in decimation).
8. Maintain high test coverage across loaders, interpreters, visual encoders, GUI callbacks, and cache behaviors.
9. Keep README concise but up to date with capabilities, setup steps, and roadmap (ensure every milestone updates it).
10. Apply a “convention over configuration” philosophy: automatically choose the most sensible visualization for loaded data, while allowing minimal-click overrides (e.g., toggle between line/scatter when appropriate). **Status:** heuristics to be refined alongside interpreter development.

## Proposed Architecture (Modular, Layered)
1. **Data Access Layer**
   - `CSVDataSource` and `JSONDataSource` implementations parse files into standardized `DataFrame`/`DataSeries` objects.
   - File loaders hash absolute path + modification timestamp to drive caching.
   - Abstraction: `DatasetRepository` exposes `load(dataset_id) -> CanonicalDataset`.
   - **Revision note:** dataset discovery mechanics (e.g., recursive folder scanning, metadata registries) remain TBD until GUI requirements settle.

2. **Interpretation Layer**
   - Converts canonical datasets into a `PlotSpec` containing metadata (axes labels, series definitions, visualization type hints).
   - Initial interpreter assumes two arrays representing X and Y values and infers a default visualization (line vs scatter) based on heuristics such as data density or monotonic axes.
   - Later, plug `CardInterpreter` that reads TOML config for mapping columns to semantics or alternate visualization modes while still offering sensible defaults.
   - **Open question:** mapping strategy for custom multi-series overlays—needs design once multi-file requirements clarified.

3. **Visualization Layer**
   - Strategy classes translate `PlotSpec` to PyQtGraph items (e.g., `LinePlotRenderer`, `BooleanGridRenderer`).
   - Maintains a cache keyed by serialized `PlotSpec` for sub-second redraws.
   - Responsible for applying shared styling themes so GUI stays consistent.

4. **GUI / Orchestration Layer**
   - PySide6 application with panels for file selection (user explicitly chooses which dataset to load), summary statistics, quick visualization toggles (line/scatter/etc.), a “Reset View” button to re-fit axes, and future controls for interpretation cards.
   - The central view embeds PyQtGraph widgets produced by the visualization layer.
   - Event chain: user action → repository loads data → interpreter → renderer → cached figure → widget redraw.
   - **Pending decisions:** navigation for multi-plot dashboards and how to present boolean maps; revisit during phase 2.

5. **Configuration & Cards**
   - Short term: default behavior if no card is supplied; treat each CSV/JSON file as a single dataset containing one X/Y pair.
   - Future: `*.toml` cards describing interpreters, dataset glob patterns, and visualization overrides. Variables (`{{VAR}}` or `*`) are auto-populated by scanning directory/file names (single-level components only), defaulting to the alphabetical first result. Cards declare a single `pivot_chart` variable controlling cycling; wildcard behaves like an anonymous variable. Subcards inherit global options but may override style or layout (e.g., `chart_height`). Validation (schema, clamping sums >100%, missing files) is tracked in `docs/card_specification.md`. **Status:** documentation established; runtime implementation pending.

## Data Formats
- **CSV:** Expect two columns describing the values to plot on each axis (default assumption: `x_axis` and `y_axis`). Additional columns should be retained for future interpreters but ignored by default until mappings are provided.
- **JSON:** Accept objects shaped like
  ```json
  {
    "any_custom_field1": "optional metadata",
    "data": {
      "x_label": "optional axis label",
      "y_label": "optional axis label",
      "x_axis": [ ... numeric/string ... ],
      "y_axis": [ ... numeric ... ]
    }
  }
  ```
  Schema stored at `schema/data_payload.schema.json` (see next section). Labels optional; lengths of `x_axis` and `y_axis` must match.

## JSON Schema
- The schema enforces the presence of a `data` object with arrays for axes.
- Additional top-level/custom fields are permitted to carry metadata used by future interpreters.
- Keep schema version-controlled; bump `$schema` or `$id` if we add complex validations.

## Performance & Caching Strategy
- Use in-memory caches (e.g., `functools.lru_cache` or `diskcache.Cache`) for parsed datasets and rendered figures.
- When the GUI requests a dataset, check modification time to invalidate stale caches.
- **Benchmark goal:** switching between already-rendered plots should take < 1s on commodity hardware. Collect baseline metrics after first UI prototype. **Status:** measurement plan pending.

## Testing Strategy
- **Loaders:** fixture CSV/JSON files validating schema adherence, error handling, caching invalidation.
- **Interpreter:** property-based tests (Hypothesis) validating axis-length constraints or other interpreter-specific invariants.
- **Visualization:** design PyQtGraph snapshot/assertion helpers that validate presence of expected data series.
- **GUI:** unit-test Qt signals/slots or use Qt testing frameworks once the UI takes shape (tooling TBD).
- Keep tests isolated from `example_data/` by copying fixtures into `tests/data/`.

## Tooling & Setup
1. Python 3.12+ (recommended to create `.venv` via `python3 -m venv .venv`).
2. Install dependencies with `pip install -r requirements.txt` inside the virtual environment.
3. Run formatters/linters as they are adopted (none yet; decision pending).
4. Launch the PySide6 application via `PYTHONPATH=src python -m visualizer.app` (until packaging/installer tooling is introduced). Later provide standalone packaging instructions (e.g., PyInstaller). **Status:** packaging approach TBD.

## Roadmap & Tasks
1. Implement CSV/JSON loaders and caching primitives. *(In progress soon)*
2. Build line chart interpreter and PyQtGraph renderer.
3. Create PySide6 GUI for file selection and visualization display.
4. Introduce TOML card parser, starting with the simple wildcard card, then layering multivariable/composite features per `docs/card_specification.md`; expand to boolean map support afterwards.
5. Layer automated performance regression tests and documentation updates.

> ⚠️ **Areas flagged for later revision:** card specification, dataset discovery UX, boolean map visualization strategy, benchmark methodology, and CLI tooling. Revisit these sections after the initial single-plot experience is functional.
