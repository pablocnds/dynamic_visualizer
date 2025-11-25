# Dynamic Visualizer

Interactive framework for loading processed analytical datasets (CSV or JSON) and rendering them through a PySide6/PyQtGraph desktop GUI (no web server required). Applies a convention-over-configuration approach so data is visualized immediately with sensible defaults, while still allowing the user to switch visualization styles with minimal interaction.

## Getting Started
1. `python3 -m venv .venv && source .venv/bin/activate`
2. `pip install -r requirements.txt`
3. Launch the prototype GUI via `PYTHONPATH=src python -m visualizer.app`.
4. Choose a data folder in the GUI (or add individual files) to populate the sidebar.
5. Follow `docs/development_guide.md` (architecture/roadmap) and `docs/card_specification.md` (card format) as you extend the project.

## Data Formats
- CSV inputs should include at least two columns describing X- and Y-axis values (default expectation is `x_axis`/`y_axis`, configurable via interpreters noted in the development guide).
- JSON inputs must satisfy `schema/data_payload.schema.json` (top-level metadata plus a `data` object with axis arrays).

Once the GUI is running, pick a data folder to list CSV/JSON files (recursive), or add files directly. Use the “Reset View” button if you pan/zoom and want to snap the axes back to the current data bounds.

## Cards
- Card prototypes live under `examples/cards`. The app automatically lists them and currently supports the simple wildcard card, the multi-variable (single path) card that cycles via `pivot_chart`, overlays (card 5), and composite cards with multiple subcards (cards 3, 4, 6) that may each specify different visualization styles.
- Select a card to auto-discover the matching datasets; use the Prev/Next controls to cycle through its files (non-pivot variables default to the first alphabetical value, pivot variables cycle). Variable selectors appear in the sidebar so you can manually choose dataset/class combinations (including the active pivot value), and stacked plot panels display each subcard using its configured visualization type—with per-panel mode selectors for on-the-fly overrides.
- Keyboard shortcuts: when a card is selected, use the left/right arrow keys to move to the previous/next visualization.
- `5-overlay_card.toml` demonstrates overlaying multiple series in a single chart by supplying arrays in `filepath`/`chart_style` (fully supported; see `docs/card_specification.md`).
- Card behavior and schema are described in `docs/card_specification.md`.

Keep this README synchronized with major development milestones.
