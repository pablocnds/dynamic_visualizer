from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Sequence

import pandas as pd

from .models import Dataset

SUPPORTED_EXTENSIONS = (".csv", ".json")


@dataclass
class CachedEntry:
    modified_ns: int
    dataset: Dataset


class DatasetRepository:
    """Loads datasets from disk with lightweight caching by file mtime."""

    def __init__(self) -> None:
        self._cache: Dict[Path, CachedEntry] = {}

    def list_datasets(self, root: Path) -> List[Path]:
        files: List[Path] = []
        for extension in SUPPORTED_EXTENSIONS:
            files.extend(root.glob(f"*{extension}"))
        return sorted(files)

    def load(self, path: Path) -> Dataset:
        path = path.expanduser().resolve()
        stat = path.stat()
        cached = self._cache.get(path)
        if cached and cached.modified_ns == stat.st_mtime_ns:
            return cached.dataset

        if path.suffix.lower() == ".csv":
            dataset = self._load_csv(path)
        elif path.suffix.lower() == ".json":
            dataset = self._load_json(path)
        else:
            raise ValueError(f"Unsupported file extension: {path.suffix}")

        self._cache[path] = CachedEntry(modified_ns=stat.st_mtime_ns, dataset=dataset)
        return dataset

    def _load_csv(self, path: Path) -> Dataset:
        data_frame = pd.read_csv(path)
        if data_frame.empty or len(data_frame.columns) < 2:
            raise ValueError(f"CSV file must contain at least two columns: {path}")

        x_column, y_column = self._detect_axis_columns(list(data_frame.columns))
        x_series = data_frame[x_column].tolist()
        y_series = data_frame[y_column].tolist()

        return Dataset(
            identifier=path.stem,
            source_path=path,
            x=self._coerce_sequence(x_series),
            y=self._coerce_numeric_sequence(y_series),
            x_label=str(x_column),
            y_label=str(y_column),
            metadata={"columns": list(data_frame.columns)},
        )

    def _load_json(self, path: Path) -> Dataset:
        payload = json.loads(path.read_text())
        data_section = payload.get("data") or {}
        x_series = data_section.get("x_axis")
        y_series = data_section.get("y_axis")
        if not isinstance(x_series, Sequence) or not isinstance(y_series, Sequence):
            raise ValueError(f"JSON payload missing axis arrays: {path}")

        return Dataset(
            identifier=str(payload.get("dataset") or path.stem),
            source_path=path,
            x=self._coerce_sequence(list(x_series)),
            y=self._coerce_numeric_sequence(list(y_series)),
            x_label=data_section.get("x_label"),
            y_label=data_section.get("y_label"),
            metadata={k: v for k, v in payload.items() if k != "data"},
        )

    @staticmethod
    def _detect_axis_columns(columns: Sequence[str]) -> tuple[str, str]:
        lowered = [c.lower() for c in columns]
        if "x_axis" in lowered and "y_axis" in lowered:
            x_idx = lowered.index("x_axis")
            y_idx = lowered.index("y_axis")
            return columns[x_idx], columns[y_idx]
        # default to first two columns
        return columns[0], columns[1]

    @staticmethod
    def _coerce_sequence(values: Sequence) -> List[float | str]:
        coerced: List[float | str] = []
        for value in values:
            if isinstance(value, (int, float)):
                coerced.append(float(value))
            else:
                try:
                    coerced.append(float(value))
                except (TypeError, ValueError):
                    coerced.append(str(value))
        return coerced

    @staticmethod
    def _coerce_numeric_sequence(values: Sequence) -> List[float]:
        numeric: List[float] = []
        for value in values:
            if isinstance(value, (int, float)):
                numeric.append(float(value))
            else:
                numeric.append(float(str(value)))
        return numeric
