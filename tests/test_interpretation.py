from pathlib import Path

from visualizer.data.models import Dataset
from visualizer.interpretation.specs import DefaultInterpreter, VisualizationType


def _dataset(values: list[float]) -> Dataset:
    return Dataset(
        identifier="test",
        source_path=Path("dummy"),
        x=values,
        y=[value * 10 for value in values],
    )


def test_line_plot_spec_sorts_by_x() -> None:
    dataset = Dataset(
        identifier="unsorted",
        source_path=Path("dummy"),
        x=[3, 1, 2],
        y=[30.0, 10.0, 20.0],
    )
    interpreter = DefaultInterpreter()

    spec = interpreter.build_plot_spec(dataset, override=VisualizationType.LINE)

    assert list(spec.x) == [1.0, 2.0, 3.0]
    assert list(spec.y) == [10.0, 20.0, 30.0]


def test_scatter_plot_keeps_original_order() -> None:
    dataset = Dataset(
        identifier="unsorted",
        source_path=Path("dummy"),
        x=[3, 1, 2],
        y=[30.0, 10.0, 20.0],
    )
    interpreter = DefaultInterpreter()

    spec = interpreter.build_plot_spec(dataset, override=VisualizationType.SCATTER)

    assert list(spec.x) == [3, 1, 2]
    assert list(spec.y) == [30.0, 10.0, 20.0]
