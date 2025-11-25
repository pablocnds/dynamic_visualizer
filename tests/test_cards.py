from pathlib import Path

import pytest

from visualizer.cards.loader import CardLoader
from visualizer.cards.models import (
    CardDefinition,
    CardMatch,
    CardSession,
    OverlayDefinition,
    SubcardDefinition,
)


def test_load_simple_card_definition() -> None:
    cards_dir = Path("examples/cards")
    loader = CardLoader(cards_dir)
    card_path = cards_dir / "1-simple_card.toml"
    definition = loader.load_definition(card_path)

    assert definition.subcards[0].filepath_template.endswith("../data/simple_study/*")
    assert definition.chart_style == "line"
    assert definition.variables == ()


def test_resolve_simple_card_matches() -> None:
    cards_dir = Path("examples/cards")
    loader = CardLoader(cards_dir)
    card_path = cards_dir / "1-simple_card.toml"
    definition = loader.load_definition(card_path)
    matches = loader.resolve_paths(definition)

    default_matches = matches.get("default")
    assert default_matches, "Expected the simple card to resolve at least one dataset"
    assert all(match.path.exists() for match in default_matches)


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

    styles = {subcard.name: subcard.chart_style for subcard in definition.subcards}
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
    overlay_series = session._build_overlay_series(overlay_def, session.selection)
    assert len(overlay_series.series) == 2


def test_cards_with_multiple_variables_require_pivot(tmp_path: Path) -> None:
    cards_dir = tmp_path
    cards_dir.mkdir(parents=True, exist_ok=True)
    card_path = cards_dir / "missing_pivot.toml"
    card_path.write_text(
        """
filepath = "<CARD_DIR>/../data/complex_study/{{DATASET}}/{{CLASS}}/time_series.json"
"""
    )
    loader = CardLoader(cards_dir)

    with pytest.raises(ValueError):
        loader.load_definition(card_path)


def test_overlay_series_falls_back_to_global_style() -> None:
    definition = CardDefinition(
        path=Path("dummy"),
        subcards=(
            SubcardDefinition(
                name="overlay",
                filepath_template="dummy",
                variables=(),
                filepaths=["/tmp/a.json", "/tmp/b.json"],
                chart_style=None,
                chart_height=None,
            ),
        ),
        variables=(),
        chart_style="line",
        pivot_variable=None,
        overlay_panels={
            "overlay": OverlayDefinition(
                name="overlay",
                filepaths=["/tmp/a.json", "/tmp/b.json"],
                chart_styles=[None, None],
            )
        },
    )
    session = CardSession(
        definition=definition,
        matches={"overlay": [CardMatch(path=Path("/tmp/a.json"), variables={})]},
    )

    overlay_def = definition.overlay_panels["overlay"]
    series = session._build_overlay_series(overlay_def, session.selection).series

    assert [entry.chart_style for entry in series] == ["line", "line"]
