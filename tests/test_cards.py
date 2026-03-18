from pathlib import Path

import pytest

from visualizer.cards.loader import CardLoader
from visualizer.cards.models import (
    CardDefinition,
    CardMatch,
    ChartStyle,
    CardSession,
    OverlayDefinition,
    SubcardDefinition,
)
from visualizer.interpretation.specs import VisualizationType


def test_load_simple_card_definition() -> None:
    cards_dir = Path("examples/cards")
    loader = CardLoader(cards_dir)
    card_path = cards_dir / "1-simple_card.toml"
    definition = loader.load_definition(card_path)

    assert "complex_study" in definition.subcards[0].filepath_template
    assert definition.chart_style and definition.chart_style.name == "line"
    assert definition.variables == ("DATASET",)


def test_resolve_simple_card_matches() -> None:
    cards_dir = Path("examples/cards")
    loader = CardLoader(cards_dir)
    card_path = cards_dir / "1-simple_card.toml"
    definition = loader.load_definition(card_path)
    matches = loader.resolve_paths(definition)

    default_matches = matches.get("default")
    assert default_matches, "Expected the simple card to resolve at least one dataset"
    assert all(match.path.exists() for match in default_matches)


def test_single_variable_cards_default_to_pivot() -> None:
    cards_dir = Path("examples/cards")
    loader = CardLoader(cards_dir)
    card_path = cards_dir / "1-simple_card.toml"
    definition = loader.load_definition(card_path)

    assert definition.variables == ("DATASET",)
    assert definition.pivot_variable == "DATASET"


def test_multivariable_card_resolves_datasets_per_class() -> None:
    cards_dir = Path("examples/cards")
    loader = CardLoader(cards_dir)
    card_path = cards_dir / "2-multivariable_card.toml"
    definition = loader.load_definition(card_path)

    matches = loader.resolve_paths(definition)

    alpha_matches = [
        match for match in matches["default"] if match.variables.get("DATASET") == "dataset_alpha"
    ]
    assert [match.path.parent.name for match in alpha_matches] == ["class_A", "class_B", "class_C"]
    assert any(match.variables.get("DATASET") == "dataset_beta" for match in matches["default"])


def test_compound_card_has_subcards() -> None:
    cards_dir = Path("examples/cards")
    loader = CardLoader(cards_dir)
    card_path = cards_dir / "3-compound_comparison_card.toml"
    definition = loader.load_definition(card_path)

    assert {subcard.name for subcard in definition.subcards} == {"dataset1", "dataset2"}
    matches = loader.resolve_paths(definition)
    assert set(matches.keys()) == {"dataset1", "dataset2"}
    # Each subcard should have entries for all classes in dataset_alpha and dataset_beta
    assert any(match.variables.get("DATASET_1") == "dataset_alpha" for match in matches["dataset1"])


def test_composite_card_subcard_chart_styles() -> None:
    cards_dir = Path("examples/cards")
    loader = CardLoader(cards_dir)
    card_path = cards_dir / "4-compound_composite_card.toml"
    definition = loader.load_definition(card_path)

    styles = {
        subcard.name: (subcard.chart_style.name if subcard.chart_style else None)
        for subcard in definition.subcards
    }
    assert styles == {"time_series": None, "scatter": "scatter"}


def test_overlay_card_definitions_and_series() -> None:
    cards_dir = Path("examples/cards")
    loader = CardLoader(cards_dir)
    card_path = cards_dir / "5-overlay_card.toml"
    definition = loader.load_definition(card_path)

    assert definition.overlay_panels
    matches = loader.resolve_paths(definition)
    session = CardSession(definition=definition, matches=matches)
    overlay_def = definition.overlay_panels["overlay"]
    assert [style.name if style else None for style in overlay_def.chart_styles] == ["line", "scatter"]
    overlay_series = session._build_overlay_series(overlay_def, session.selection)
    assert len(overlay_series.series) == 2


def test_cards_with_multiple_variables_default_to_first_pivot(tmp_path: Path) -> None:
    cards_dir = tmp_path
    cards_dir.mkdir(parents=True, exist_ok=True)
    card_path = cards_dir / "missing_pivot.toml"
    card_path.write_text(
        """
filepath = "<CARD_DIR>/../data/complex_study/{{DATASET}}/{{CLASS}}/time_series.json"
"""
    )
    loader = CardLoader(cards_dir)
    definition = loader.load_definition(card_path)

    assert definition.variables == ("CLASS", "DATASET")
    assert definition.pivot_variable == "CLASS"


def test_top_level_axis_visibility_false_is_not_overridden_by_global(tmp_path: Path) -> None:
    cards_dir = tmp_path / "cards"
    cards_dir.mkdir(parents=True, exist_ok=True)
    card_path = cards_dir / "axis_visibility.toml"
    card_path.write_text(
        """
filepath = "<CARD_DIR>/../data/{{CLASS}}/signal.json"
show_x_axis = false
show_y_axis = false

[global]
show_x_axis = true
show_y_axis = true
"""
    )

    loader = CardLoader(cards_dir)
    definition = loader.load_definition(card_path)

    assert definition.show_x_axis is False
    assert definition.show_y_axis is False
    assert definition.subcards[0].show_x_axis is False
    assert definition.subcards[0].show_y_axis is False


def test_card_table_style_parses_global_and_subcard_values(tmp_path: Path) -> None:
    cards_dir = tmp_path / "cards"
    cards_dir.mkdir(parents=True, exist_ok=True)
    card_path = cards_dir / "table_style_card.toml"
    card_path.write_text(
        """
[global]
table_style = { palette = "viridis", range = [0, 100] }
pivot_chart = "{{CLASS}}"

[subcards.table_panel]
filepath = "<CARD_DIR>/../data/{{CLASS}}/table.json"
table_style = { palette = "plasma" }
"""
    )

    loader = CardLoader(cards_dir)
    definition = loader.load_definition(card_path)
    subcard = definition.subcards[0]

    assert definition.table_style is not None
    assert definition.table_style.palette == "viridis"
    assert definition.table_style.value_range == (0.0, 100.0)
    assert subcard.table_style is not None
    assert subcard.table_style.palette == "plasma"
    assert subcard.table_style.value_range is None


def test_chart_style_rejects_unknown_args(tmp_path: Path) -> None:
    cards_dir = tmp_path / "cards"
    cards_dir.mkdir(parents=True, exist_ok=True)
    card_path = cards_dir / "invalid_style_args.toml"
    card_path.write_text(
        """
filepath = "<CARD_DIR>/data.json"
chart_style = { name = "colormap", color = "#ff0000" }
"""
    )

    loader = CardLoader(cards_dir)

    with pytest.raises(ValueError, match="unsupported chart_style args"):
        loader.load_definition(card_path)


def test_chart_style_rejects_invalid_alpha_type(tmp_path: Path) -> None:
    cards_dir = tmp_path / "cards"
    cards_dir.mkdir(parents=True, exist_ok=True)
    card_path = cards_dir / "invalid_style_alpha.toml"
    card_path.write_text(
        """
filepath = "<CARD_DIR>/data.json"
chart_style = { name = "line", alpha = "opaque" }
"""
    )

    loader = CardLoader(cards_dir)

    with pytest.raises(ValueError, match="arg 'alpha' must be numeric"):
        loader.load_definition(card_path)


def test_chart_style_alias_accepts_supported_args(tmp_path: Path) -> None:
    cards_dir = tmp_path / "cards"
    cards_dir.mkdir(parents=True, exist_ok=True)
    card_path = cards_dir / "range_alias.toml"
    card_path.write_text(
        """
filepath = "<CARD_DIR>/data.json"
chart_style = { name = "range", palette = "cividis", alpha = 0.3 }
"""
    )

    loader = CardLoader(cards_dir)
    definition = loader.load_definition(card_path)

    assert definition.chart_style is not None
    assert definition.chart_style.name == "range"
    assert definition.chart_style.params["palette"] == "cividis"
    assert definition.chart_style.visualization() == VisualizationType.RANGE


def test_wildcard_only_cards_require_single_match(tmp_path: Path) -> None:
    cards_dir = tmp_path / "cards"
    data_dir = tmp_path / "data"
    cards_dir.mkdir(parents=True, exist_ok=True)
    data_dir.mkdir(parents=True, exist_ok=True)
    (data_dir / "a.json").write_text("noop")
    (data_dir / "b.json").write_text("noop")
    card_path = cards_dir / "wildcard.toml"
    card_path.write_text('filepath = "<CARD_DIR>/../data/*.json"\n')

    loader = CardLoader(cards_dir)
    definition = loader.load_definition(card_path)

    with pytest.raises(ValueError):
        loader.resolve_paths(definition)


def test_overlay_series_falls_back_to_global_style() -> None:
    definition = CardDefinition(
        path=Path("dummy"),
        subcards=(
            SubcardDefinition(
                name="overlay",
                filepath_template="dummy",
                variables=(),
                filepaths=["/tmp/a.json", "/tmp/b.json"],
                overlay_variable=None,
                chart_style=None,
                chart_height=None,
            ),
        ),
        variables=(),
        chart_style=ChartStyle("line"),
        pivot_variable=None,
        overlay_panels={
            "overlay": OverlayDefinition(
                name="overlay",
                filepaths=["/tmp/a.json", "/tmp/b.json"],
                chart_styles=[None, None],
                overlay_variable=None,
            )
        },
    )
    session = CardSession(
        definition=definition,
        matches={"overlay": [CardMatch(path=Path("/tmp/a.json"), variables={})]},
    )

    overlay_def = definition.overlay_panels["overlay"]
    series = session._build_overlay_series(overlay_def, session.selection).series

    assert [entry.chart_style.name if entry.chart_style else None for entry in series] == ["line", "line"]


def test_overlay_variable_auto_discovers_series(tmp_path: Path) -> None:
    card_dir = tmp_path / "cards"
    data_dir = card_dir / "data" / "mix"
    class_dir = data_dir / "classA"
    class_dir.mkdir(parents=True)
    (data_dir / "mix.json").write_text("noop")
    for frag in ("100.00", "200.00"):
        (class_dir / f"ms2_frag-{frag}_scatter.json").write_text("noop")

    template = "<CARD_DIR>/data/mix/{{CLASS}}/ms2_frag-{{FRAG}}_scatter.json"
    definition = CardDefinition(
        path=card_dir / "card.toml",
        subcards=(
            SubcardDefinition(
                name="overlay",
                filepath_template=template,
                variables=("CLASS",),
                filepaths=[template],
                overlay_variable="FRAG",
                chart_style=None,
                chart_height=None,
            ),
        ),
        variables=("CLASS",),
        chart_style=ChartStyle("scatter"),
        pivot_variable="CLASS",
        overlay_panels={
            "overlay": OverlayDefinition(
                name="overlay",
                filepaths=[template],
                chart_styles=[None],
                overlay_variable="FRAG",
            )
        },
    )
    matches = {
        "overlay": [
            CardMatch(
                path=class_dir / "ms2_frag-100.00_scatter.json",
                variables={"CLASS": "classA"},
            )
        ]
    }
    session = CardSession(definition=definition, matches=matches)

    series = session._build_overlay_series(definition.overlay_panels["overlay"], session.selection).series

    assert [entry.path.name for entry in series] == [
        "ms2_frag-100.00_scatter.json",
        "ms2_frag-200.00_scatter.json",
    ]


def test_overlay_variable_supports_spaced_placeholders(tmp_path: Path) -> None:
    card_dir = tmp_path / "cards"
    data_dir = card_dir / "data" / "mix"
    class_dir = data_dir / "classA"
    class_dir.mkdir(parents=True)
    for frag in ("100.00", "200.00"):
        (class_dir / f"ms2_frag-{frag}_scatter.json").write_text("noop")

    template = "<CARD_DIR>/data/mix/{{ CLASS }}/ms2_frag-{{ FRAG }}_scatter.json"
    definition = CardDefinition(
        path=card_dir / "card.toml",
        subcards=(
            SubcardDefinition(
                name="overlay",
                filepath_template=template,
                variables=("CLASS",),
                filepaths=[template],
                overlay_variable="FRAG",
                chart_style=None,
                chart_height=None,
            ),
        ),
        variables=("CLASS",),
        chart_style=ChartStyle("scatter"),
        pivot_variable="CLASS",
        overlay_panels={
            "overlay": OverlayDefinition(
                name="overlay",
                filepaths=[template],
                chart_styles=[None],
                overlay_variable="FRAG",
            )
        },
    )
    matches = {
        "overlay": [
            CardMatch(
                path=class_dir / "ms2_frag-100.00_scatter.json",
                variables={"CLASS": "classA"},
            )
        ]
    }
    session = CardSession(definition=definition, matches=matches)

    series = session._build_overlay_series(definition.overlay_panels["overlay"], session.selection).series

    assert [entry.path.name for entry in series] == [
        "ms2_frag-100.00_scatter.json",
        "ms2_frag-200.00_scatter.json",
    ]


def test_overlay_enumeration_handles_parent_paths_and_filters(tmp_path: Path) -> None:
    cards_dir = tmp_path / "cards"
    data_dir = tmp_path / "data" / "overlay_demo"
    class_dir = data_dir / "classA"
    class_dir.mkdir(parents=True)
    (class_dir / "base_signal.json").write_text("noop")
    (class_dir / "series-100.json").write_text("noop")
    (class_dir / "series-150_relative.json").write_text("noop")
    card_path = cards_dir / "overlay_card.toml"
    cards_dir.mkdir(parents=True)
    card_path.write_text(
        """
[global]
pivot_chart = "{{CLASS}}"
chart_style = ["line", "scatter"]
overlay_variable = "{{SERIES}}"

filepath = [
  "<CARD_DIR>/../data/overlay_demo/{{CLASS}}/base_signal.json",
  "<CARD_DIR>/../data/overlay_demo/{{CLASS}}/series-{{SERIES}}.json"
]

[variable_filters]
SERIES = "^[0-9.]+$"
"""
    )

    loader = CardLoader(cards_dir)
    definition = loader.load_definition(card_path)
    matches = loader.resolve_paths(definition)
    session = CardSession(definition=definition, matches=matches)
    overlay_def = definition.overlay_panels["overlay"]

    series = session._build_overlay_series(
        overlay_def,
        session.selection,
        fallback_style=definition.subcards[0].chart_style,
    ).series

    assert [entry.path.name for entry in series] == ["base_signal.json", "series-100.json"]


def test_visualization_type_accepts_colormap_aliases() -> None:
    assert VisualizationType.from_string("colormap") == VisualizationType.COLORMAP
    assert VisualizationType.from_string("colormap_line") == VisualizationType.COLORMAP
    assert VisualizationType.from_string("heatmap1d") == VisualizationType.COLORMAP
    assert VisualizationType.from_string("eventline") == VisualizationType.EVENTLINE
    assert VisualizationType.from_string("events") == VisualizationType.EVENTLINE
    assert VisualizationType.from_string("stick") == VisualizationType.STICK


def test_overlay_series_falls_back_to_subcard_style() -> None:
    definition = CardDefinition(
        path=Path("dummy"),
        subcards=(
            SubcardDefinition(
                name="overlay",
                filepath_template="dummy",
                variables=(),
                filepaths=["/tmp/a.json", "/tmp/b.json"],
                overlay_variable=None,
                chart_style=ChartStyle("scatter"),
                chart_height=None,
            ),
        ),
        variables=(),
        chart_style=ChartStyle("line"),
        pivot_variable=None,
        overlay_panels={
            "overlay": OverlayDefinition(
                name="overlay",
                filepaths=["/tmp/a.json", "/tmp/b.json"],
                chart_styles=[None, None],
                overlay_variable=None,
            )
        },
    )
    session = CardSession(
        definition=definition,
        matches={"overlay": [CardMatch(path=Path("/tmp/a.json"), variables={})]},
    )

    overlay_def = definition.overlay_panels["overlay"]
    series = session._build_overlay_series(
        overlay_def,
        session.selection,
        fallback_style=ChartStyle("scatter"),
    ).series

    assert [entry.chart_style.name if entry.chart_style else None for entry in series] == [
        "scatter",
        "scatter",
    ]


def test_wildcard_requires_single_match(tmp_path: Path) -> None:
    cards_dir = tmp_path / "cards"
    data_dir = cards_dir / "data" / "classA"
    data_dir.mkdir(parents=True)
    (data_dir / "ms1_precursor-111.json").write_text("noop")
    (data_dir / "ms1_precursor-222.json").write_text("noop")
    card_path = cards_dir / "wildcard_card.toml"
    card_path.write_text(
        """
filepath = "<CARD_DIR>/data/{{CLASS}}/ms1_precursor-*.json"
"""
    )

    loader = CardLoader(cards_dir)
    definition = loader.load_definition(card_path)

    with pytest.raises(ValueError):
        loader.resolve_paths(definition)


def test_overlay_subcard_registers_overlay_panel(tmp_path: Path) -> None:
    cards_dir = tmp_path / "cards"
    cards_dir.mkdir(parents=True)
    card_path = cards_dir / "overlay_subcard.toml"
    card_path.write_text(
        """
[subcards.overlay_panel]
filepath = [
  "<CARD_DIR>/data/{{CLASS}}/base.json",
  "<CARD_DIR>/data/{{CLASS}}/extra-{{FRAG}}.json"
]
chart_style = ["line", "scatter"]
overlay_variable = "{{FRAG}}"
"""
    )

    loader = CardLoader(cards_dir)
    definition = loader.load_definition(card_path)

    assert "overlay_panel" in definition.overlay_panels


def test_variable_filters_prune_primary_discovery(tmp_path: Path) -> None:
    cards_dir = tmp_path / "cards"
    data_dir = cards_dir / "data"
    class_a = data_dir / "classA"
    class_b = data_dir / "classB"
    class_a.mkdir(parents=True)
    class_b.mkdir(parents=True)
    (class_a / "sample.json").write_text("noop")
    (class_b / "sample.json").write_text("noop")
    card_path = cards_dir / "filtered_card.toml"
    card_path.write_text(
        """
filepath = "<CARD_DIR>/data/{{CLASS}}/sample.json"
[variable_filters]
CLASS = "^classA$"
"""
    )

    loader = CardLoader(cards_dir)
    definition = loader.load_definition(card_path)
    matches = loader.resolve_paths(definition)

    default_matches = matches["default"]
    assert len(default_matches) == 1
    assert default_matches[0].path.parent.name == "classA"


def test_card_session_handles_dataset_specific_subset_names(tmp_path: Path) -> None:
    cards_dir = tmp_path / "cards"
    cards_dir.mkdir(parents=True)
    card_path = cards_dir / "subset_card.toml"
    card_path.write_text(
        """
[global]
pivot_chart = "{{COMPOUND}}"

filepath = "<CARD_DIR>/../data/processed/{{DATASET}}/{{SUBSET}}/{{COMPOUND}}/signal.json"
"""
    )
    (tmp_path / "data" / "processed" / "R10_Standard_Mixes" / "iterative_excL_20eV" / "compound_a").mkdir(
        parents=True
    )
    (tmp_path / "data" / "processed" / "standards60" / "iterative_excL_10eV" / "compound_a").mkdir(
        parents=True
    )
    (tmp_path / "data" / "processed" / "R10_Standard_Mixes" / "iterative_excL_20eV" / "compound_a" / "signal.json").write_text(
        "noop"
    )
    (tmp_path / "data" / "processed" / "standards60" / "iterative_excL_10eV" / "compound_a" / "signal.json").write_text(
        "noop"
    )

    loader = CardLoader(cards_dir)
    definition = loader.load_definition(card_path)
    matches = loader.resolve_paths(definition)
    session = CardSession(definition=definition, matches=matches)

    assert session.current_paths()["default"].name == "signal.json"
    assert session.selection["DATASET"] in {"R10_Standard_Mixes", "standards60"}
    assert session.selection["SUBSET"] in {"iterative_excL_20eV", "iterative_excL_10eV"}


def test_session_recovers_when_default_variable_values_do_not_overlap() -> None:
    definition = CardDefinition(
        path=Path("dummy"),
        subcards=(
            SubcardDefinition(
                name="default",
                filepath_template="dummy",
                variables=("COMPOUND", "DATASET", "SUBSET"),
                filepaths=["dummy"],
                overlay_variable=None,
                chart_style=None,
                chart_height=None,
            ),
        ),
        variables=("COMPOUND", "DATASET", "SUBSET"),
        chart_style=ChartStyle("line"),
        pivot_variable="COMPOUND",
    )
    matches = {
        "default": [
            CardMatch(
                path=Path("/tmp/r10_mix.json"),
                variables={
                    "COMPOUND": "A",
                    "DATASET": "R10_Standard_Mixes",
                    "SUBSET": "iterative_excL_20eV",
                },
            ),
            CardMatch(
                path=Path("/tmp/std_mix.json"),
                variables={
                    "COMPOUND": "B",
                    "DATASET": "standards60",
                    "SUBSET": "iterative_excL_10eV",
                },
            ),
        ]
    }

    session = CardSession(definition=definition, matches=matches)

    selected_values = {key: session.selection.get(key) for key in definition.variables}
    assert selected_values in [match.variables for match in matches["default"]]
    assert session.current_paths()["default"] in {Path("/tmp/r10_mix.json"), Path("/tmp/std_mix.json")}


def test_update_selection_keeps_selected_variable_when_recovering() -> None:
    definition = CardDefinition(
        path=Path("dummy"),
        subcards=(
            SubcardDefinition(
                name="default",
                filepath_template="dummy",
                variables=("COMPOUND", "DATASET", "SUBSET"),
                filepaths=["dummy"],
                overlay_variable=None,
                chart_style=None,
                chart_height=None,
            ),
        ),
        variables=("COMPOUND", "DATASET", "SUBSET"),
        chart_style=ChartStyle("line"),
        pivot_variable="COMPOUND",
    )
    matches = {
        "default": [
            CardMatch(
                path=Path("/tmp/r10_20.json"),
                variables={
                    "COMPOUND": "A",
                    "DATASET": "R10_Standard_Mixes",
                    "SUBSET": "iterative_excL_20eV",
                },
            ),
            CardMatch(
                path=Path("/tmp/r10_30.json"),
                variables={
                    "COMPOUND": "B",
                    "DATASET": "R10_Standard_Mixes",
                    "SUBSET": "iterative_excL_30eV",
                },
            ),
            CardMatch(
                path=Path("/tmp/std_10.json"),
                variables={
                    "COMPOUND": "C",
                    "DATASET": "standards60",
                    "SUBSET": "iterative_excL_10eV",
                },
            ),
        ]
    }

    session = CardSession(definition=definition, matches=matches)
    session.update_selection("DATASET", "standards60")

    assert session.selection["DATASET"] == "standards60"
    selected_values = {key: session.selection.get(key) for key in definition.variables}
    assert selected_values in [match.variables for match in matches["default"]]
