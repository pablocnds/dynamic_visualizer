from pathlib import Path
import json

import pytest

from visualizer.data.models import RangeDataset, TableDataset
from visualizer.data.repository import DatasetRepository


def test_load_json_dataset(tmp_path: Path) -> None:
    fixture = Path(__file__).parent / "data" / "simple_series.json"
    repo = DatasetRepository()
    dataset = repo.load(fixture)

    assert dataset.identifier == "simple_series"
    assert dataset.x_label == "Index"
    assert dataset.y_label == "Value"
    assert list(dataset.x) == [0.0, 1.0, 2.0]
    assert list(dataset.y) == [0.1, 0.2, 0.3]


def test_list_datasets_filters_supported_extensions(tmp_path: Path) -> None:
    repo = DatasetRepository()
    (tmp_path / "a.json").write_text("{\"data\": {\"x_axis\":[0], \"y_axis\":[1]}}")
    (tmp_path / "b.json").write_text("{\"data\": {\"x_axis\":[0], \"y_axis\":[1]}}")
    (tmp_path / "ignore.csv").write_text("noop")

    files = repo.list_datasets(tmp_path)
    assert len(files) == 2
    assert all(file.suffix == ".json" for file in files)


def test_list_datasets_recurses(tmp_path: Path) -> None:
    repo = DatasetRepository()
    nested = tmp_path / "nested" / "inner"
    nested.mkdir(parents=True)
    (nested / "c.json").write_text("{\"data\": {\"x_axis\": [0], \"y_axis\": [1]}}")

    files = repo.list_datasets(tmp_path)

    assert (nested / "c.json") in files


def test_json_validation_rejects_mismatched_lengths(tmp_path: Path) -> None:
    bad = tmp_path / "bad.json"
    bad.write_text("{\"data\": {\"x_axis\": [0,1], \"y_axis\": [1]}}")
    repo = DatasetRepository()

    with pytest.raises(ValueError):
        repo.load(bad)


def test_json_validation_rejects_non_numeric_y(tmp_path: Path) -> None:
    bad = tmp_path / "bad_non_numeric.json"
    bad.write_text("{\"data\": {\"x_axis\": [0,1], \"y_axis\": [\"a\",\"b\"]}}")
    repo = DatasetRepository()

    with pytest.raises(ValueError):
        repo.load(bad)


def test_load_table_dataset(tmp_path: Path) -> None:
    table_path = tmp_path / "table.json"
    payload = {
        "dataset": "table_demo",
        "data": {
            "column_names": ["a", "b"],
            "row_names": [1, 2],
            "content": [[10, 20], [30, 40]],
        },
    }
    table_path.write_text(json.dumps(payload))
    repo = DatasetRepository()

    dataset = repo.load(table_path)

    assert isinstance(dataset, TableDataset)
    assert list(dataset.column_names) == ["a", "b"]
    assert list(dataset.row_names) == [1.0, 2.0]
    assert dataset.content[0][0] == 10.0


def test_load_range_dataset(tmp_path: Path) -> None:
    range_path = tmp_path / "ranges.json"
    payload = {
        "dataset": "ranges_demo",
        "data": {
            "kind": "ranges",
            "x_label": "Time",
            "ranges": [[1, 2], [5, 4]],
        },
    }
    range_path.write_text(json.dumps(payload))
    repo = DatasetRepository()

    dataset = repo.load(range_path)

    assert isinstance(dataset, RangeDataset)
    assert dataset.x_label == "Time"
    assert list(dataset.ranges) == [(1.0, 2.0), (4.0, 5.0)]


def test_range_payload_warns_when_kind_missing(tmp_path: Path) -> None:
    range_path = tmp_path / "ranges_warn.json"
    payload = {
        "dataset": "ranges_warn",
        "data": {
            "ranges": [[0, 1], [2, 3]],
        },
    }
    range_path.write_text(json.dumps(payload))
    repo = DatasetRepository()

    with pytest.warns(UserWarning):
        dataset = repo.load(range_path)

    assert isinstance(dataset, RangeDataset)


def test_range_kind_alias_warns(tmp_path: Path) -> None:
    range_path = tmp_path / "ranges_alias.json"
    payload = {
        "dataset": "ranges_alias",
        "data": {
            "kind": "range",
            "ranges": [[0, 1], [2, 3]],
        },
    }
    range_path.write_text(json.dumps(payload))
    repo = DatasetRepository()

    with pytest.warns(UserWarning):
        dataset = repo.load(range_path)

    assert isinstance(dataset, RangeDataset)


def test_table_validation_rejects_mismatched_dimensions(tmp_path: Path) -> None:
    bad_table = tmp_path / "bad_table.json"
    payload = {
        "data": {
            "column_names": ["a", "b"],
            "row_names": [1, 2],
            "content": [[10, 20]],
        },
    }
    bad_table.write_text(json.dumps(payload))
    repo = DatasetRepository()

    with pytest.raises(ValueError):
        repo.load(bad_table)
