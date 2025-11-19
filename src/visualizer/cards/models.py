from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional


@dataclass(frozen=True)
class CardDefinition:
    path: Path
    filepath_template: str
    chart_style: Optional[str] = None
    pivot_variable: Optional[str] = None


@dataclass
class CardSession:
    definition: CardDefinition
    resolved_paths: List[Path]
    index: int = 0

    def has_paths(self) -> bool:
        return bool(self.resolved_paths)

    def current_path(self) -> Path:
        return self.resolved_paths[self.index]

    def advance(self, step: int = 1) -> Path:
        if not self.resolved_paths:
            raise ValueError("No paths to advance through")
        self.index = (self.index + step) % len(self.resolved_paths)
        return self.current_path()
