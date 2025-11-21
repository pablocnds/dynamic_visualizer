from pathlib import Path

from visualizer.cards.loader import CardLoader


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
