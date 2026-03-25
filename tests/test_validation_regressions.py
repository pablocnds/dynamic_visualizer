from __future__ import annotations

import json
from pathlib import Path

import pytest

from visualizer.cards.loader import CardLoader
from visualizer.data.repository import DatasetRepository


def test_list_card_files_ignores_unofficial_double_underscore_cards(tmp_path: Path) -> None:
    cards_dir = tmp_path / "cards"
    cards_dir.mkdir(parents=True)
    (cards_dir / "official.toml").write_text('filepath = "<CARD_DIR>/data.json"\n')
    (cards_dir / "__draft.toml").write_text('filepath = "<CARD_DIR>/scratch.json"\n')

    loader = CardLoader(cards_dir)

    assert [path.name for path in loader.list_card_files()] == ["official.toml"]


def test_variable_filter_regex_must_be_valid_at_load_time(tmp_path: Path) -> None:
    cards_dir = tmp_path / "cards"
    cards_dir.mkdir(parents=True)
    card_path = cards_dir / "bad_filter.toml"
    card_path.write_text(
        """
filepath = "<CARD_DIR>/../data/{{GROUP}}/signal.json"

[variable_filters]
GROUP = "["
"""
    )

    loader = CardLoader(cards_dir)

    with pytest.raises(ValueError, match="variable_filters\\.GROUP.*valid regex"):
        loader.load_definition(card_path)


def test_overlay_path_filter_regex_must_be_valid_at_load_time(tmp_path: Path) -> None:
    cards_dir = tmp_path / "cards"
    cards_dir.mkdir(parents=True)
    card_path = cards_dir / "bad_overlay_filter.toml"
    card_path.write_text(
        """
filepath = [
  "<CARD_DIR>/../data/{{CLASS}}/base.json",
  "<CARD_DIR>/../data/{{CLASS}}/fragment-{{FRAG}}.json"
]
overlay_variable = "{{FRAG}}"
overlay_path_filter = "["
"""
    )

    loader = CardLoader(cards_dir)

    with pytest.raises(ValueError, match="overlay_path_filter.*valid regex"):
        loader.load_definition(card_path)


@pytest.mark.parametrize(
    ("payload", "expected_message"),
    [
        (
            {"data": {"column_names": ["a"], "content": [[1]]}},
            "missing 'row_names'",
        ),
        (
            {"data": {"column_names": ["a"], "row_names": ["r1"]}},
            "missing 'content'",
        ),
    ],
)
def test_table_payload_missing_required_keys_still_raise_clear_errors_without_schema_validation(
    tmp_path: Path,
    payload: dict,
    expected_message: str,
) -> None:
    table_path = tmp_path / "bad_table.json"
    table_path.write_text(json.dumps(payload))
    repo = DatasetRepository()
    repo._json_validator = None
    repo._schema_validation_enabled = False

    with pytest.raises(ValueError, match=expected_message):
        repo.load(table_path)
