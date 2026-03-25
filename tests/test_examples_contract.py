from __future__ import annotations

from pathlib import Path

import pytest

from visualizer.controller.session import SessionController
from visualizer.data.repository import DatasetRepository


_REPO_ROOT = Path(__file__).resolve().parents[1]
_EXAMPLES_CARDS_DIR = _REPO_ROOT / "examples" / "cards"
_EXAMPLES_DATA_DIR = _REPO_ROOT / "examples" / "data"
_OFFICIAL_EXAMPLE_CARDS = tuple(
    sorted(path for path in _EXAMPLES_CARDS_DIR.glob("*.toml") if not path.name.startswith("__"))
)


@pytest.mark.contract
@pytest.mark.parametrize("card_path", _OFFICIAL_EXAMPLE_CARDS, ids=lambda path: path.name)
def test_official_example_cards_build_clean_panel_plans(card_path: Path) -> None:
    controller = SessionController(DatasetRepository(), cards_dir=card_path.parent)

    controller.activate_card(card_path)
    result = controller.build_panel_plans()

    assert result.plans
    assert result.missing == []
    assert result.load_errors == []
    assert result.incompatible == []
    assert all(plan.series for plan in result.plans)
    assert all(series.dataset is not None for plan in result.plans for series in plan.series)


@pytest.mark.contract
@pytest.mark.gui
@pytest.mark.parametrize("card_path", _OFFICIAL_EXAMPLE_CARDS, ids=lambda path: path.name)
def test_official_example_cards_render_without_runtime_warnings(qt_app, card_path: Path) -> None:  # noqa: ANN001
    from visualizer.gui.main_window import MainWindow

    window = MainWindow(data_dir=_EXAMPLES_DATA_DIR.resolve(), cards_dir=_EXAMPLES_CARDS_DIR.resolve())
    try:
        window._activate_card(card_path)  # type: ignore[attr-defined]
        panel_count = len(window._panel_plots) + len(window._panel_manager.table_views())  # type: ignore[attr-defined]

        assert panel_count > 0
        assert window._warning_label.text() == ""  # type: ignore[attr-defined]
        assert window._loaded_files_list.count() > 0  # type: ignore[attr-defined]
    finally:
        window.close()
