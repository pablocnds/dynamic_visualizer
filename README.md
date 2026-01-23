# Dynamic Visualizer

Interactive framework for loading processed analytical datasets (JSON) and rendering them through a PySide6/PyQtGraph desktop GUI (no web server required). Applies a convention-over-configuration approach so data is visualized immediately with sensible defaults, while still allowing the user to switch visualization styles with minimal interaction.

## Getting Started
1. `python3 -m venv .venv && source .venv/bin/activate`
2. `pip install -e ".[dev]"`
3. Launch the GUI via `dynamic-visualizer` (or `python -m visualizer`).
4. Use the File menu to open a data folder (or add individual files) to populate the sidebar. Use File > Open Card File to load card definitions for the session (last-used paths are remembered across runs).
5. Follow `docs/development_guide.md` (architecture/roadmap) and `docs/card_specification.md` (card format) as you extend the project.

## Local Packaging
- Build a wheel with `python -m build`.
- Test install in a clean environment with `pip install dist/*.whl`.

## Data Formats
- JSON inputs must satisfy `src/visualizer/schema/data_payload.schema.json` (packaged as `visualizer/schema/data_payload.schema.json`).
- Series data uses `x_axis` with an optional `y_axis`; table data uses `column_names`/`row_names` with a row-major `content` matrix; range data uses `ranges` as `[start, end]` pairs along the X axis.
- `data.kind` is optional (`series`, `table`, or `ranges`); when omitted the loader auto-detects based on the available fields (range payloads warn when `data.kind` is missing).
- CSV support is temporarily disabled and will return in a future update.

Once the GUI is running, use File > Open Data Folder to list JSON files (recursive), or File > Add Data File to add files directly. The sidebar shows either data files or cards depending on what you last loaded; you can collapse it from View > Collapse Sidebar or the toggle button in the sidebar header. The sidebar includes a “loaded files” box that lists the data file(s) used by the current view. Use View > Visualization Mode to override the automatic plot type selection. Use the “Reset View” button if you pan/zoom and want to snap the axes back to the current data bounds.

## Cards
- Card prototypes can live anywhere. Use File > Open Card File to list available cards. Supported types include the simple wildcard card, the multi-variable (single path) card that cycles via `pivot_chart`, overlays (card 5), and composite cards with multiple subcards (cards 3, 4, 6) that may each specify different visualization styles.
- Overlays can optionally specify an `overlay_variable` to auto-discover all matching series (e.g., multiple fragment files) and render them together without exposing that variable in the UI.
- Visualization modes currently include line, scatter, a 1-D colormap strip (heat line along X), a 1-D event line (spikes at X positions; Y ignored), and 1-D range bands.
- Select a card to auto-discover the matching datasets; use the Prev/Next controls to cycle through its files (non-pivot variables default to the first alphabetical value, pivot variables cycle). Variable selectors appear in the sidebar so you can manually choose dataset/class combinations (including the active pivot value); stacked plot panels display each subcard using its configured visualization type.
- Keyboard shortcuts: when a card is selected, use the left/right arrow keys to move to the previous/next visualization. Use up/down arrows to move through the current sidebar list (cards or files), even when the sidebar is collapsed.
- `5-overlay_card.toml` demonstrates overlaying multiple series in a single chart by supplying arrays in `filepath`/`chart_style` (fully supported; see `docs/card_specification.md`).
- Compound cards may optionally set `synchronize_axis = true` in `[global]` to keep X-axes linked and hide redundant axes on upper plots.
- Cards may set `show_x_axis`/`show_y_axis` globally or per subcard to control axis visibility; with `synchronize_axis = true`, X axes are hidden by default unless explicitly enabled.
- Card behavior and schema are described in `docs/card_specification.md`.

Keep this README synchronized with major development milestones.
