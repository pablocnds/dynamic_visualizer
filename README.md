# Dynamic Visualizer

Interactive framework for loading processed analytical datasets (CSV or JSON) and rendering them through a PySide6/PyQtGraph desktop GUI (no web server required). Applies a convention-over-configuration approach so data is visualized immediately with sensible defaults, while still allowing the user to switch visualization styles with minimal interaction.

## Getting Started
1. `python3 -m venv .venv && source .venv/bin/activate`
2. `pip install -r requirements.txt`
3. Launch the prototype GUI via `PYTHONPATH=src python -m visualizer.app`.
4. Follow `docs/development_guide.md` for architecture notes, roadmap, and packaging decisions.

## Data Formats
- CSV inputs should include at least two columns describing X- and Y-axis values (default expectation is `x_axis`/`y_axis`, configurable via interpreters noted in the development guide).
- JSON inputs must satisfy `schema/data_payload.schema.json` (top-level metadata plus a `data` object with axis arrays).

Keep this README synchronized with major development milestones.
