from pathlib import Path

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
