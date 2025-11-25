from pathlib import Path

import pytest

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
    (tmp_path / "a.csv").write_text("x_axis,y_axis\n0,1")
    (tmp_path / "b.json").write_text("{\"data\": {\"x_axis\":[0], \"y_axis\":[1]}}")
    (tmp_path / "ignore.txt").write_text("noop")

    files = repo.list_datasets(tmp_path)
    assert len(files) == 2
    assert all(file.suffix in {".csv", ".json"} for file in files)


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
