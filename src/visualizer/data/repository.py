from __future__ import annotations

import json
import warnings
from dataclasses import dataclass
from importlib import resources
from importlib.resources.abc import Traversable
from pathlib import Path
from typing import Dict, List, Sequence
try:
    import jsonschema
except ImportError:  # pragma: no cover - optional dependency for schema validation
    jsonschema = None

from .models import DataKind, DataPayload, Dataset, RangeDataset, TableDataset

SUPPORTED_EXTENSIONS = (".json",)


@dataclass
class CachedEntry:
    modified_ns: int
    dataset: DataPayload


class DatasetRepository:
    """Loads datasets from disk with lightweight caching by file mtime."""

    def __init__(self, schema_path: Path | None = None) -> None:
        self._cache: Dict[Path, CachedEntry] = {}
        self._schema_path: Path | Traversable = (
            schema_path if schema_path else self._default_schema_path()
        )
        self._json_validator = self._load_json_validator()
        self._schema_validation_enabled = self._json_validator is not None

    @property
    def schema_validation_enabled(self) -> bool:
        return self._schema_validation_enabled

    def _load_json_validator(self):
        if jsonschema is None:
            return None
        try:
            schema = json.loads(self._schema_path.read_text())
            return jsonschema.Draft202012Validator(schema)
        except Exception:
            return None

    def list_datasets(self, root: Path) -> List[Path]:
        files: List[Path] = []
        for extension in SUPPORTED_EXTENSIONS:
            files.extend(root.rglob(f"*{extension}"))
        return sorted(files)

    def load(self, path: Path) -> DataPayload:
        path = path.expanduser().resolve()
        stat = path.stat()
        cached = self._cache.get(path)
        if cached and cached.modified_ns == stat.st_mtime_ns:
            return cached.dataset

        if path.suffix.lower() != ".json":
            raise ValueError(f"Unsupported file extension: {path.suffix}")
        dataset = self._load_json(path)

        self._cache[path] = CachedEntry(modified_ns=stat.st_mtime_ns, dataset=dataset)
        return dataset

    def _load_json(self, path: Path) -> DataPayload:
        payload = json.loads(path.read_text())
        self._validate_json_schema(payload, path)
        if not isinstance(payload, dict):
            raise ValueError(f"JSON payload must be an object: {path}")
        data_section = payload.get("data")
        if not isinstance(data_section, dict):
            raise ValueError(f"JSON payload missing 'data' object: {path}")

        kind = self._infer_kind(data_section, path)
        if kind == DataKind.TABLE:
            return self._load_table_payload(payload, data_section, path)
        if kind == DataKind.RANGE:
            return self._load_range_payload(payload, data_section, path)
        return self._load_series_payload(payload, data_section, path)

    def _validate_json_schema(self, payload: dict, path: Path) -> None:
        if not self._json_validator or jsonschema is None:
            return
        try:
            self._json_validator.validate(payload)
        except jsonschema.ValidationError as exc:
            raise ValueError(f"JSON schema validation failed for {path}: {exc.message}") from exc

    @staticmethod
    def _default_schema_path() -> Traversable:
        return resources.files("visualizer.schema").joinpath("data_payload.schema.json")

    def _infer_kind(self, data_section: dict, path: Path) -> DataKind:
        kind_value = data_section.get("kind")
        if kind_value is not None:
            normalized = str(kind_value).strip().lower()
            if normalized in {"series", "plot", "xy"}:
                return DataKind.SERIES
            if normalized in {"table", "matrix"}:
                return DataKind.TABLE
            if normalized == "range":
                warnings.warn(
                    f"Data payload in {path} uses data.kind = 'range'; "
                    "use data.kind = 'ranges' instead.",
                    UserWarning,
                )
                return DataKind.RANGE
            if normalized == "ranges":
                return DataKind.RANGE
            raise ValueError(f"Unsupported data kind '{kind_value}' in {path}")
        if "ranges" in data_section:
            warnings.warn(
                f"Data payload in {path} uses 'ranges' without an explicit data.kind; "
                "set data.kind = 'ranges' to make the intent clear.",
                UserWarning,
            )
            return DataKind.RANGE
        if any(key in data_section for key in ("column_names", "row_names", "content")):
            return DataKind.TABLE
        return DataKind.SERIES

    def _load_series_payload(self, payload: dict, data_section: dict, path: Path) -> Dataset:
        self._validate_series_payload(data_section, path)
        x_series = list(data_section.get("x_axis") or [])
        if "y_axis" not in data_section or data_section.get("y_axis") is None:
            y_series = [1.0] * len(x_series)
        else:
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

    def _load_table_payload(self, payload: dict, data_section: dict, path: Path) -> TableDataset:
        self._validate_table_payload(data_section, path)
        column_names = self._coerce_sequence(list(data_section.get("column_names") or []))
        row_names = self._coerce_sequence(list(data_section.get("row_names") or []))
        raw_content = data_section.get("content") or []
        content = [self._coerce_sequence(list(row)) for row in raw_content]

        return TableDataset(
            identifier=str(payload.get("dataset") or path.stem),
            source_path=path,
            column_names=column_names,
            row_names=row_names,
            content=content,
            metadata={k: v for k, v in payload.items() if k != "data"},
        )

    def _load_range_payload(self, payload: dict, data_section: dict, path: Path) -> RangeDataset:
        self._validate_range_payload(data_section, path)
        raw_ranges = data_section.get("ranges") or []
        ranges = self._coerce_ranges(raw_ranges, path)
        return RangeDataset(
            identifier=str(payload.get("dataset") or path.stem),
            source_path=path,
            ranges=ranges,
            x_label=data_section.get("x_label"),
            y_label=data_section.get("y_label"),
            metadata={k: v for k, v in payload.items() if k != "data"},
        )

    def _validate_series_payload(self, data_section: dict, path: Path) -> None:
        if "x_axis" not in data_section:
            raise ValueError(f"JSON payload missing 'x_axis': {path}")
        if not isinstance(data_section["x_axis"], Sequence) or isinstance(
            data_section["x_axis"], (str, bytes)
        ):
            raise ValueError(f"'x_axis' must be an array: {path}")
        if len(data_section["x_axis"]) == 0:
            raise ValueError(f"'x_axis' cannot be empty: {path}")
        if "y_axis" in data_section and data_section["y_axis"] is not None:
            if not isinstance(data_section["y_axis"], Sequence) or isinstance(
                data_section["y_axis"], (str, bytes)
            ):
                raise ValueError(f"'y_axis' must be an array of numbers: {path}")
            if len(data_section["y_axis"]) == 0:
                raise ValueError(f"'y_axis' cannot be empty when provided: {path}")

    def _validate_table_payload(self, data_section: dict, path: Path) -> None:
        if "column_names" not in data_section or "row_names" not in data_section or "content" not in data_section:
            raise ValueError(f"JSON table payload missing 'column_names'/'row_names'/'content': {path}")
        if not isinstance(data_section["column_names"], Sequence) or isinstance(
            data_section["column_names"], (str, bytes)
        ):
            raise ValueError(f"'column_names' must be an array: {path}")
        if not isinstance(data_section["row_names"], Sequence) or isinstance(
            data_section["row_names"], (str, bytes)
        ):
            raise ValueError(f"'row_names' must be an array: {path}")
        if not isinstance(data_section["content"], Sequence) or isinstance(
            data_section["content"], (str, bytes)
        ):
            raise ValueError(f"'content' must be an array of rows: {path}")
        if len(data_section["column_names"]) == 0 or len(data_section["row_names"]) == 0:
            raise ValueError(f"'column_names'/'row_names' cannot be empty: {path}")
        if len(data_section["content"]) == 0:
            raise ValueError(f"'content' cannot be empty: {path}")
        expected_cols = len(data_section["column_names"])
        expected_rows = len(data_section["row_names"])
        if len(data_section["content"]) != expected_rows:
            raise ValueError(f"Row count mismatch between 'row_names' and 'content' in {path}")
        for idx, row in enumerate(data_section["content"]):
            if not isinstance(row, Sequence) or isinstance(row, (str, bytes)):
                raise ValueError(f"Row {idx} in 'content' must be an array: {path}")
            if len(row) != expected_cols:
                raise ValueError(
                    f"Column count mismatch in row {idx} (expected {expected_cols}) in {path}"
                )

    def _validate_range_payload(self, data_section: dict, path: Path) -> None:
        if "ranges" not in data_section:
            raise ValueError(f"JSON range payload missing 'ranges': {path}")
        if not isinstance(data_section["ranges"], Sequence) or isinstance(
            data_section["ranges"], (str, bytes)
        ):
            raise ValueError(f"'ranges' must be an array of [start, end] pairs: {path}")
        if len(data_section["ranges"]) == 0:
            raise ValueError(f"'ranges' cannot be empty: {path}")

    @staticmethod
    def _coerce_sequence(values: Sequence) -> List[float | str | bool]:
        coerced: List[float | str | bool] = []
        for value in values:
            if isinstance(value, bool):
                coerced.append(value)
            elif isinstance(value, (int, float)):
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

    def _coerce_ranges(self, values: Sequence, path: Path) -> List[tuple[float, float]]:
        ranges: List[tuple[float, float]] = []
        for idx, pair in enumerate(values):
            if not isinstance(pair, Sequence) or isinstance(pair, (str, bytes)):
                raise ValueError(f"Range entry {idx} must be an array: {path}")
            if len(pair) != 2:
                raise ValueError(f"Range entry {idx} must have exactly two values: {path}")
            try:
                start = float(pair[0])
                end = float(pair[1])
            except (TypeError, ValueError) as exc:
                raise ValueError(f"Range entry {idx} must be numeric: {path}") from exc
            if start <= end:
                ranges.append((start, end))
            else:
                ranges.append((end, start))
        return ranges

    @staticmethod
    def _validate_axis_lengths(
        x_values: Sequence[float | str | bool], y_values: Sequence[float], path: Path
    ) -> None:
        if len(x_values) != len(y_values):
            raise ValueError(f"Length mismatch between x_axis and y_axis in {path}")
        if not x_values or not y_values:
            raise ValueError(f"Empty axis data in {path}")
