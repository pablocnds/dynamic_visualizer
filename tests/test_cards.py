from pathlib import Path

from visualizer.cards.loader import CardLoader


def test_load_simple_card_definition() -> None:
    cards_dir = Path("examples/cards")
    loader = CardLoader(cards_dir)
    card_path = cards_dir / "1-simple_card.toml"
    definition = loader.load_definition(card_path)

    assert definition.filepath_template.endswith("data/simple_study/*")
    assert definition.chart_style == "line"


def test_resolve_simple_card_matches() -> None:
    cards_dir = Path("examples/cards")
    loader = CardLoader(cards_dir)
    card_path = cards_dir / "1-simple_card.toml"
    definition = loader.load_definition(card_path)
    matches = loader.resolve_simple_matches(definition)

    assert matches, "Expected the simple card to resolve at least one dataset"
    assert all(path.exists() for path in matches)
