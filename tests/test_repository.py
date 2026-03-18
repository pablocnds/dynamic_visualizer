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


def test_series_accepts_missing_y_axis(tmp_path: Path) -> None:
    series_path = tmp_path / "events.json"
    series_path.write_text("{\"data\": {\"x_axis\": [1, 2, 3]}}")
    repo = DatasetRepository()

    dataset = repo.load(series_path)

    assert list(dataset.x) == [1.0, 2.0, 3.0]
    assert list(dataset.y) == [1.0, 1.0, 1.0]


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


def test_range_info_loads_and_preserves_multiline_entries(tmp_path: Path) -> None:
    range_path = tmp_path / "ranges_info.json"
    payload = {
        "dataset": "ranges_info",
        "data": {
            "kind": "ranges",
            "ranges": [[0, 1], [2, 3]],
            "range_info": [
                ["Window A", "score=0.8", "count=4"],
                "Window B\nscore=0.5",
            ],
        },
    }
    range_path.write_text(json.dumps(payload))
    repo = DatasetRepository()

    dataset = repo.load(range_path)

    assert isinstance(dataset, RangeDataset)
    assert list(dataset.range_info) == [
        "Window A\nscore=0.8\ncount=4",
        "Window B\nscore=0.5",
    ]


def test_range_info_must_match_ranges_length(tmp_path: Path) -> None:
    range_path = tmp_path / "ranges_bad_info.json"
    payload = {
        "dataset": "ranges_bad_info",
        "data": {
            "kind": "ranges",
            "ranges": [[0, 1], [2, 3]],
            "range_info": ["only_one_entry"],
        },
    }
    range_path.write_text(json.dumps(payload))
    repo = DatasetRepository()

    with pytest.raises(ValueError, match="'range_info' must contain exactly 2 entries"):
        repo.load(range_path)


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


def test_table_style_configuration_loads_with_row_column_overrides(tmp_path: Path) -> None:
    table_path = tmp_path / "styled_table.json"
    payload = {
        "dataset": "styled_table",
        "data": {
            "table_title": "Styled Metrics",
            "column_names": ["a", "b"],
            "row_names": ["r1", "r2"],
            "content": [[10, 20], [30, 40]],
            "table_style": {
                "global": {"palette": "viridis", "range": [0, 100], "reverse": True},
                "rows": [None, {"palette": "plasma", "range": [5, 45]}],
                "columns": [{"range": [0, 50]}, {"palette": "cividis", "reverse": False}],
            },
        },
    }
    table_path.write_text(json.dumps(payload))
    repo = DatasetRepository()

    dataset = repo.load(table_path)

    assert isinstance(dataset, TableDataset)
    assert dataset.table_title == "Styled Metrics"
    assert dataset.table_style is not None
    assert dataset.table_style.global_rule is not None
    assert dataset.table_style.global_rule.palette == "viridis"
    assert dataset.table_style.global_rule.value_range == (0.0, 100.0)
    assert dataset.table_style.global_rule.reverse is True
    assert len(dataset.table_style.row_rules) == 2
    assert dataset.table_style.row_rules[1] is not None
    assert dataset.table_style.row_rules[1].palette == "plasma"
    assert len(dataset.table_style.column_rules) == 2
    assert dataset.table_style.column_rules[0] is not None
    assert dataset.table_style.column_rules[0].value_range == (0.0, 50.0)
    assert dataset.table_style.column_rules[1] is not None
    assert dataset.table_style.column_rules[1].reverse is False


def test_table_style_rejects_row_column_length_mismatches(tmp_path: Path) -> None:
    table_path = tmp_path / "bad_style_table.json"
    payload = {
        "dataset": "bad_style_table",
        "data": {
            "column_names": ["a", "b"],
            "row_names": ["r1", "r2"],
            "content": [[10, 20], [30, 40]],
            "table_style": {
                "rows": [{"palette": "viridis"}],
                "columns": [{"palette": "plasma"}],
            },
        },
    }
    table_path.write_text(json.dumps(payload))
    repo = DatasetRepository()

    with pytest.raises(ValueError, match="data.table_style.rows must contain exactly 2 entries"):
        repo.load(table_path)


def test_table_style_rejects_invalid_reverse_type(tmp_path: Path) -> None:
    table_path = tmp_path / "bad_reverse_style.json"
    payload = {
        "dataset": "bad_reverse_style",
        "data": {
            "column_names": ["a"],
            "row_names": ["r1"],
            "content": [[10]],
            "table_style": {
                "global": {"palette": "viridis", "reverse": "yes"},
            },
        },
    }
    table_path.write_text(json.dumps(payload))
    repo = DatasetRepository()

    with pytest.raises(ValueError, match="data.table_style.global.reverse must be a boolean"):
        repo.load(table_path)
