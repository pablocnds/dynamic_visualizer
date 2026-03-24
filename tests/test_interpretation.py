from pathlib import Path

from visualizer.data.models import Dataset, RangeDataset, TableColumnGroup, TableDataset
from visualizer.interpretation.specs import DefaultInterpreter, TableSpec, VisualizationType
from visualizer.table_style import TableColorConfig, TableColorRule


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


def test_stick_plot_keeps_original_order() -> None:
    dataset = Dataset(
        identifier="unsorted",
        source_path=Path("dummy"),
        x=[3, 1, 2],
        y=[30.0, 10.0, 20.0],
    )
    interpreter = DefaultInterpreter()

    spec = interpreter.build_plot_spec(dataset, override=VisualizationType.STICK)

    assert list(spec.x) == [3, 1, 2]
    assert list(spec.y) == [30.0, 10.0, 20.0]


def test_table_spec_builds_from_dataset() -> None:
    dataset = TableDataset(
        identifier="table",
        source_path=Path("dummy"),
        column_names=["a", "b"],
        row_names=[1, 2],
        content=[[10, 20], [30, 40]],
        table_title="Compact Table Title",
    )
    interpreter = DefaultInterpreter()

    spec = interpreter.build_spec(dataset)

    assert isinstance(spec, TableSpec)
    assert list(spec.column_names) == ["a", "b"]
    assert list(spec.row_names) == [1, 2]
    assert spec.label == "Compact Table Title"


def test_table_spec_preserves_grouped_column_metadata() -> None:
    dataset = TableDataset(
        identifier="table",
        source_path=Path("dummy"),
        column_names=["precision", "AUC", "winner", "precision", "recall"],
        row_names=[1],
        content=[[0.91, 0.95, "Model 1", 0.89, 0.87]],
        column_groups=[
            TableColumnGroup(label="Model 1", subcolumns=["precision", "AUC"]),
            TableColumnGroup(label="winner"),
            TableColumnGroup(label="Model 2", subcolumns=["precision", "recall"]),
        ],
    )
    interpreter = DefaultInterpreter()

    spec = interpreter.build_spec(dataset)

    assert isinstance(spec, TableSpec)
    assert spec.column_groups is not None
    assert len(spec.column_groups) == 3
    assert spec.column_groups[0].label == "Model 1"
    assert list(spec.column_groups[0].subcolumns) == ["precision", "AUC"]
    assert spec.column_groups[1].label == "winner"
    assert list(spec.column_groups[1].subcolumns) == []


def test_range_spec_builds_from_dataset() -> None:
    dataset = RangeDataset(
        identifier="ranges",
        source_path=Path("dummy"),
        ranges=[(1.0, 2.0), (3.0, 4.0)],
        range_info=["A", None],
        x_label="Time",
    )
    interpreter = DefaultInterpreter()

    spec = interpreter.build_spec(dataset)

    assert spec.visualization == VisualizationType.RANGE
    assert spec.ranges == [(1.0, 2.0), (3.0, 4.0)]
    assert spec.interactions is not None
    assert [interaction.hover_text for interaction in spec.interactions] == ["A", None]


def test_table_spec_merges_global_style_override_as_fallback() -> None:
    dataset = TableDataset(
        identifier="table",
        source_path=Path("dummy"),
        column_names=["a", "b"],
        row_names=[1, 2],
        content=[[10, 20], [30, 40]],
        table_style=TableColorConfig(
            global_rule=None,
            row_rules=(None, TableColorRule(palette="plasma")),
            column_rules=(TableColorRule(value_range=(0.0, 50.0)), None),
        ),
    )
    interpreter = DefaultInterpreter()

    spec = interpreter.build_table_spec(
        dataset,
        table_style_global_override=TableColorRule(palette="viridis", value_range=(0.0, 100.0)),
    )

    assert spec.table_style is not None
    assert spec.table_style.global_rule is not None
    assert spec.table_style.global_rule.palette == "viridis"
    assert spec.table_style.global_rule.value_range == (0.0, 100.0)
    assert spec.table_style.global_rule.reverse is None
    assert spec.table_style.row_rules[1] is not None
    assert spec.table_style.row_rules[1].palette == "plasma"
    assert spec.table_style.column_rules[0] is not None
    assert spec.table_style.column_rules[0].value_range == (0.0, 50.0)


def test_table_spec_keeps_dataset_global_style_over_card_override() -> None:
    dataset = TableDataset(
        identifier="table",
        source_path=Path("dummy"),
        column_names=["a"],
        row_names=[1],
        content=[[10]],
        table_style=TableColorConfig(global_rule=TableColorRule(palette="cividis")),
    )
    interpreter = DefaultInterpreter()

    spec = interpreter.build_table_spec(
        dataset,
        table_style_global_override=TableColorRule(palette="viridis", value_range=(0.0, 100.0)),
    )

    assert spec.table_style is not None
    assert spec.table_style.global_rule is not None
    assert spec.table_style.global_rule.palette == "cividis"
    assert spec.table_style.global_rule.value_range is None


def test_table_spec_merges_reverse_global_style_override_as_fallback() -> None:
    dataset = TableDataset(
        identifier="table",
        source_path=Path("dummy"),
        column_names=["a"],
        row_names=[1],
        content=[[10]],
        table_style=TableColorConfig(global_rule=None),
    )
    interpreter = DefaultInterpreter()

    spec = interpreter.build_table_spec(
        dataset,
        table_style_global_override=TableColorRule(palette="viridis", reverse=True),
    )

    assert spec.table_style is not None
    assert spec.table_style.global_rule is not None
    assert spec.table_style.global_rule.palette == "viridis"
    assert spec.table_style.global_rule.reverse is True
