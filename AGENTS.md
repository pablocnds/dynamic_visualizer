# AGENTS.md

Guidelines for working on this repository across sessions.

## Documentation and Examples
- Keep docs up to date with development changes. Update `README.md`, `docs/development_guide.md`,
  `docs/card_specification.md`, and any relevant schemas whenever behavior changes.
- Example cards should cover every implemented feature (cards, overlays, new view types, etc.).
  Add or update examples when you add features.

## Testing and Quality
- Maintain good test coverage and keep tests meaningful (avoid superficial or redundant tests).
- Prefer adding tests when behavior changes or new features are added.
- Use `PYTHONPATH=src pytest ...` when running tests locally.

## Architecture and Design
- Preserve a clean, abstract architecture (data loading, interpretation, rendering, GUI).
- If a new feature does not fit the current architecture cleanly, suggest a refactor first.
  Avoid quick fixes that add complexity or risk regressions.

## Workflow and Hygiene
- Keep changes focused and readable; refactor when it improves clarity or reduces coupling.
- Update or add schema validations alongside new data formats.
- Prefer extending existing abstractions over introducing one-off logic.

## Ignored and Local Files
- Do not edit or rely on files ignored by `.gitignore` unless explicitly requested.
- Treat files that start with "__" as personal or unofficial, and ignore them by default.

## Miscellaneous
- Be cautious about backwards compatibility; call out breaking changes early.
- Confirm UX changes with the user if they alter expected workflows.
