from __future__ import annotations

import glob
import tomllib
from pathlib import Path
from typing import List

from .models import CardDefinition

MAX_MATCHES = 1000


class CardLoader:
    def __init__(self, cards_dir: Path) -> None:
        self._cards_dir = cards_dir

    def list_card_files(self) -> List[Path]:
        if not self._cards_dir.exists():
            return []
        return sorted(self._cards_dir.glob("*.toml"))

    def load_definition(self, path: Path) -> CardDefinition:
        path = path.resolve()
        with path.open("rb") as handle:
            data = tomllib.load(handle)
        filepath_template = data.get("filepath")
        if filepath_template is None:
            raise ValueError("Card missing 'filepath'")

        global_section = data.get("global", {})
        chart_style = data.get("chart_style") or global_section.get("chart_style")
        pivot = data.get("pivot_chart") or global_section.get("pivot_chart")

        return CardDefinition(
            path=path,
            filepath_template=str(filepath_template),
            chart_style=str(chart_style) if chart_style else None,
            pivot_variable=_normalize_variable(pivot),
        )

    def resolve_simple_matches(self, definition: CardDefinition) -> List[Path]:
        template = definition.filepath_template
        if "{{" in template or "}}" in template:
            raise NotImplementedError("Named variables are not supported yet")
        resolved_template = template.replace("<CARD_DIR>", str(definition.path.parent))
        matches = sorted(Path(match).resolve() for match in glob.glob(resolved_template))
        if len(matches) > MAX_MATCHES:
            raise ValueError(
                f"Card resolved to {len(matches)} matches which exceeds the limit of {MAX_MATCHES}"
            )
        return matches


def _normalize_variable(value: object | None) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    if text.startswith("{{") and text.endswith("}}"):
        text = text[2:-2].strip()
    return text or None
