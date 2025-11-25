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

    def __init__(self, schema_path: Path | None = None) -> None:
        self._cache: Dict[Path, CachedEntry] = {}
        self._schema_path = schema_path or Path(__file__).resolve().parents[2] / "schema" / "data_payload.schema.json"

    def list_datasets(self, root: Path) -> List[Path]:
        files: List[Path] = []
        for extension in SUPPORTED_EXTENSIONS:
            files.extend(root.rglob(f"*{extension}"))
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
        self._validate_axis_lengths(x_series, y_series, path)

        try:
            x_values = self._coerce_sequence(x_series)
            y_values = self._coerce_numeric_sequence(y_series)
        except ValueError as exc:
            raise ValueError(f"CSV file has non-numeric Y values: {path}") from exc

        return Dataset(
            identifier=path.stem,
            source_path=path,
            x=x_values,
            y=y_values,
            x_label=str(x_column),
            y_label=str(y_column),
            metadata={"columns": list(data_frame.columns)},
        )

    def _load_json(self, path: Path) -> Dataset:
        payload = json.loads(path.read_text())
        self._validate_json_payload(payload, path)
        data_section = payload.get("data") or {}
        x_series = list(data_section.get("x_axis") or [])
        y_series = list(data_section.get("y_axis") or [])
        self._validate_axis_lengths(x_series, y_series, path)

        try:
            x_values = self._coerce_sequence(x_series)
            y_values = self._coerce_numeric_sequence(y_series)
        except ValueError as exc:
            raise ValueError(f"JSON file has invalid numeric values: {path}") from exc

        return Dataset(
            identifier=str(payload.get("dataset") or path.stem),
            source_path=path,
            x=x_values,
            y=y_values,
            x_label=data_section.get("x_label"),
            y_label=data_section.get("y_label"),
            metadata={k: v for k, v in payload.items() if k != "data"},
        )

    def _validate_json_payload(self, payload: dict, path: Path) -> None:
        if not isinstance(payload, dict):
            raise ValueError(f"JSON payload must be an object: {path}")
        data_section = payload.get("data")
        if not isinstance(data_section, dict):
            raise ValueError(f"JSON payload missing 'data' object: {path}")
        if "x_axis" not in data_section or "y_axis" not in data_section:
            raise ValueError(f"JSON payload missing 'x_axis'/'y_axis': {path}")
        if not isinstance(data_section["x_axis"], Sequence) or isinstance(
            data_section["x_axis"], (str, bytes)
        ):
            raise ValueError(f"'x_axis' must be an array: {path}")
        if not isinstance(data_section["y_axis"], Sequence) or isinstance(
            data_section["y_axis"], (str, bytes)
        ):
            raise ValueError(f"'y_axis' must be an array of numbers: {path}")
        if len(data_section["x_axis"]) == 0 or len(data_section["y_axis"]) == 0:
            raise ValueError(f"'x_axis'/'y_axis' cannot be empty: {path}")

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

    def _coerce_numeric_sequence(self, values: Sequence) -> List[float]:
        numeric: List[float] = []
        for value in values:
            try:
                numeric.append(float(value))
            except (TypeError, ValueError) as exc:
                raise ValueError("Non-numeric value encountered") from exc
        return numeric

    @staticmethod
    def _validate_axis_lengths(
        x_values: Sequence[float | str], y_values: Sequence[float], path: Path
    ) -> None:
        if len(x_values) != len(y_values):
            raise ValueError(f"Length mismatch between x_axis and y_axis in {path}")
        if not x_values or not y_values:
            raise ValueError(f"Empty axis data in {path}")
