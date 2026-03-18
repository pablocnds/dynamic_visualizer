import pytest

QtCore = pytest.importorskip("PySide6.QtCore", reason="PySide6 not installed; install requirements to run table renderer tests")

from visualizer.interpretation.specs import TableSpec
from visualizer.table_style import TableColorConfig, TableColorRule
from visualizer.viz.table_renderer import TableModel


def _background_rgb(model: TableModel, row: int, column: int) -> tuple[int, int, int]:
    index = model.index(row, column)
    brush = model.data(index, QtCore.Qt.BackgroundRole)
    assert brush is not None
    color = brush.color()
    return color.red(), color.green(), color.blue()


def test_table_model_applies_custom_global_range() -> None:
    spec = TableSpec(
        dataset_id="table",
        label=None,
        column_names=["a", "b"],
        row_names=["r1", "r2"],
        content=[[0, 100], [0, 100]],
        table_style=TableColorConfig(global_rule=TableColorRule(range=(0.0, 200.0))),
    )
    model = TableModel(spec)

    # With a [0, 200] range, value 100 should render near the midpoint color.
    mid_rgb = _background_rgb(model, 0, 1)
    low_rgb = _background_rgb(model, 0, 0)

    assert mid_rgb != low_rgb
    assert mid_rgb[0] > low_rgb[0]
    assert mid_rgb[2] < low_rgb[2]


def test_table_model_row_column_rules_override_global() -> None:
    spec = TableSpec(
        dataset_id="table",
        label=None,
        column_names=["a", "b"],
        row_names=["r1", "r2"],
        content=[[50, 100], [50, 100]],
        table_style=TableColorConfig(
            global_rule=TableColorRule(palette="viridis", value_range=(0.0, 100.0)),
            row_rules=(None, TableColorRule(palette="plasma")),
            column_rules=(None, TableColorRule(range=(0.0, 200.0))),
        ),
    )
    model = TableModel(spec)

    # Column override range affects both rows in column 1.
    col1_row0 = _background_rgb(model, 0, 1)
    col0_row0 = _background_rgb(model, 0, 0)
    assert col1_row0 != col0_row0

    # Row override palette should change row 1, even with same value.
    col0_row1 = _background_rgb(model, 1, 0)
    assert col0_row1 != col0_row0
