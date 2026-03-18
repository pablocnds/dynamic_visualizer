from __future__ import annotations

import json
from pathlib import Path

from visualizer.controller.session import SessionController
from visualizer.data.repository import DatasetRepository


def _write_series(path: Path, x_values: list[float], y_values: list[float]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {"dataset": path.stem, "data": {"x_axis": x_values, "y_axis": y_values}}
    path.write_text(json.dumps(payload))


def _write_table(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "dataset": path.stem,
        "data": {
            "column_names": ["a", "b"],
            "row_names": ["r1", "r2"],
            "content": [[1, 2], [3, 4]],
        },
    }
    path.write_text(json.dumps(payload))


def test_build_panel_plans_without_session_returns_empty_triplet() -> None:
    controller = SessionController(DatasetRepository())
    plans, missing, incompatible = controller.build_panel_plans()
    assert plans == []
    assert missing == []
    assert incompatible == []


def test_build_panel_plans_expands_overlay_series(tmp_path: Path) -> None:
    cards_dir = tmp_path / "cards"
    card_path = cards_dir / "overlay.toml"
    class_dir = cards_dir / "data" / "classA"
    _write_series(class_dir / "base.json", [0.0, 1.0], [1.0, 2.0])
    _write_series(class_dir / "frag-100.json", [0.0, 1.0], [3.0, 4.0])
    _write_series(class_dir / "frag-200.json", [0.0, 1.0], [5.0, 6.0])
    cards_dir.mkdir(parents=True, exist_ok=True)
    card_path.write_text(
        """
filepath = [
  "<CARD_DIR>/data/{{CLASS}}/base.json",
  "<CARD_DIR>/data/{{CLASS}}/frag-{{FRAG}}.json"
]
chart_style = ["line", "scatter"]
overlay_variable = "{{FRAG}}"

[global]
chart_style = "line"
"""
    )

    controller = SessionController(DatasetRepository(), cards_dir=cards_dir)
    controller.activate_card(card_path)
    plans, missing, incompatible = controller.build_panel_plans()

    assert missing == []
    assert incompatible == []
    assert len(plans) == 1
    plan = plans[0]
    assert [series.path.name for series in plan.series] == [
        "base.json",
        "frag-100.json",
        "frag-200.json",
    ]
    assert [series.chart_style.name if series.chart_style else None for series in plan.series] == [
        "line",
        "scatter",
        "scatter",
    ]
    assert all(series.dataset is not None for series in plan.series)


def test_build_panel_plans_reports_incompatible_table_chart_style(tmp_path: Path) -> None:
    cards_dir = tmp_path / "cards"
    card_path = cards_dir / "table_line.toml"
    _write_table(cards_dir / "data" / "table.json")
    cards_dir.mkdir(parents=True, exist_ok=True)
    card_path.write_text(
        """
filepath = "<CARD_DIR>/data/table.json"
chart_style = "line"
"""
    )

    controller = SessionController(DatasetRepository(), cards_dir=cards_dir)
    controller.activate_card(card_path)
    plans, missing, incompatible = controller.build_panel_plans()

    assert missing == []
    assert len(plans) == 1
    assert len(plans[0].series) == 1
    assert plans[0].series[0].dataset is None
    assert len(incompatible) == 1
    assert "table data cannot use chart_style 'line'" in incompatible[0]


def test_build_panel_plans_reports_missing_subcard_for_active_selection(tmp_path: Path) -> None:
    cards_dir = tmp_path / "cards"
    card_path = cards_dir / "partial_subcards.toml"
    _write_series(cards_dir / "data" / "classA" / "primary.json", [0.0, 1.0], [1.0, 2.0])
    _write_series(cards_dir / "data" / "classB" / "primary.json", [0.0, 1.0], [2.0, 3.0])
    _write_series(cards_dir / "data" / "classB" / "secondary.json", [0.0, 1.0], [4.0, 5.0])
    cards_dir.mkdir(parents=True, exist_ok=True)
    card_path.write_text(
        """
[global]
pivot_chart = "{{CLASS}}"

[subcards.primary]
filepath = "<CARD_DIR>/data/{{CLASS}}/primary.json"

[subcards.secondary]
filepath = "<CARD_DIR>/data/{{CLASS}}/secondary.json"
"""
    )

    controller = SessionController(DatasetRepository(), cards_dir=cards_dir)
    session = controller.activate_card(card_path)
    session.update_selection("CLASS", "classA")
    plans, missing, incompatible = controller.build_panel_plans()

    assert len(plans) == 2
    assert missing == ["secondary"]
    assert incompatible == []
    primary_plan = next(plan for plan in plans if plan.subcard.name == "primary")
    secondary_plan = next(plan for plan in plans if plan.subcard.name == "secondary")
    assert len(primary_plan.series) == 1
    assert primary_plan.series[0].dataset is not None
    assert secondary_plan.series == []
