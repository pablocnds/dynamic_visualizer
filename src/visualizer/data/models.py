from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Sequence


@dataclass(frozen=True)
class Dataset:
    """Canonical representation of numeric data to be visualized."""

    identifier: str
    source_path: Path
    x: Sequence[float | str]
    y: Sequence[float]
    x_label: str | None = None
    y_label: str | None = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def cache_key(self) -> tuple[Any, ...]:
        """Stable key for caching downstream plot specs."""

        return (
            self.identifier,
            tuple(self.x),
            tuple(self.y),
            self.x_label,
            self.y_label,
        )
