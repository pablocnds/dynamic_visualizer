import json
import os
from contextlib import contextmanager
from typing import Iterator
from pathlib import Path

import pytest

QtWidgets = pytest.importorskip("PySide6.QtWidgets", reason="PySide6 not installed; install requirements to run GUI tests")
QtCore = pytest.importorskip("PySide6.QtCore", reason="PySide6 not installed; install requirements to run GUI tests")
pg = pytest.importorskip("pyqtgraph", reason="pyqtgraph not installed; install requirements to run GUI tests")

from visualizer.gui.main_window import MainWindow


@pytest.fixture(scope="module")
def app() -> QtWidgets.QApplication:
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    existing = QtWidgets.QApplication.instance()
    if existing:
        return existing
    return QtWidgets.QApplication([])


@contextmanager
def capture_qt_messages() -> Iterator[list[str]]:
    messages: list[str] = []

    def handler(msg_type: QtCore.QtMsgType, context: QtCore.QMessageLogContext, message: str) -> None:  # noqa: ARG001
        messages.append(message)

    old_handler = QtCore.qInstallMessageHandler(handler)
    try:
        yield messages
    finally:
        QtCore.qInstallMessageHandler(old_handler)


def _create_window() -> MainWindow:
    data_dir = Path("examples/data").resolve()
    cards_dir = Path("examples/cards").resolve()
    window = MainWindow(data_dir=data_dir, cards_dir=cards_dir)
    # Ensure state restore does not override paths
    window._set_card_loader(cards_dir)  # type: ignore[attr-defined]
    return window


def _write_series(path: Path, x_values: list[float], y_values: list[float]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {"dataset": path.stem, "data": {"x_axis": x_values, "y_axis": y_values}}
    path.write_text(json.dumps(payload))


def _create_missing_panel_window(tmp_path: Path) -> tuple[MainWindow, Path]:
    data_dir = tmp_path / "data"
    cards_dir = tmp_path / "cards"
    cards_dir.mkdir(parents=True, exist_ok=True)
    _write_series(data_dir / "a" / "primary.json", [0.0, 1.0, 2.0], [1.0, 1.5, 2.0])
    _write_series(data_dir / "a" / "secondary.json", [0.0, 1.0, 2.0], [0.2, 0.4, 0.6])
    _write_series(data_dir / "b" / "secondary.json", [0.0, 1.0, 2.0], [0.1, 0.3, 0.5])
    _write_series(data_dir / "c" / "primary.json", [0.0, 1.0, 2.0], [1.1, 1.4, 1.9])

    card_path = cards_dir / "missing_panels.toml"
    card_path.write_text(
        "\n".join(
            [
                "[global]",
                'pivot_chart = "sample"',
                "",
                "[subcards.primary]",
                'filepath = "<CARD_DIR>/../data/{{sample}}/primary.json"',
                'chart_style = "line"',
                "",
                "[subcards.secondary]",
                'filepath = "<CARD_DIR>/../data/{{sample}}/secondary.json"',
                'chart_style = "colormap"',
                "",
            ]
        )
    )

    window = MainWindow(data_dir=data_dir, cards_dir=cards_dir)
    window._set_card_loader(cards_dir)  # type: ignore[attr-defined]
    return window, card_path


def test_colormap_card_renders_items(app: QtWidgets.QApplication) -> None:  # noqa: ARG001
    window = _create_window()
    card_path = window._cards_dir / "8-colormap_card.toml"  # type: ignore[attr-defined]
    with capture_qt_messages() as messages:
        window._activate_card(card_path)
    plot = window._panel_plots[0] if window._panel_plots else None  # type: ignore[attr-defined]
    assert plot is not None
    items = plot.getPlotItem().items
    assert any(isinstance(item, pg.ImageItem) for item in items)
    assert not [m for m in messages if "invalid row" in m or "Scale" in m]


def test_eventline_card_renders_items(app: QtWidgets.QApplication) -> None:  # noqa: ARG001
    window = _create_window()
    card_path = window._cards_dir / "9-eventline_card.toml"  # type: ignore[attr-defined]
    with capture_qt_messages() as messages:
        window._activate_card(card_path)
    plot = window._panel_plots[0] if window._panel_plots else None  # type: ignore[attr-defined]
    assert plot is not None
    items = plot.getPlotItem().items
    assert any(isinstance(item, pg.BarGraphItem) for item in items)
    assert not [m for m in messages if "invalid row" in m or "Scale" in m]


def test_stick_card_renders_items(app: QtWidgets.QApplication) -> None:  # noqa: ARG001
    window = _create_window()
    card_path = window._cards_dir / "13-stick_card.toml"  # type: ignore[attr-defined]
    with capture_qt_messages() as messages:
        window._activate_card(card_path)
    plot = window._panel_plots[0] if window._panel_plots else None  # type: ignore[attr-defined]
    assert plot is not None
    items = plot.getPlotItem().items
    assert any(isinstance(item, pg.PlotDataItem) for item in items)
    assert not [m for m in messages if "invalid row" in m or "Scale" in m]


def test_one_dim_overlay_has_no_colorbars(app: QtWidgets.QApplication) -> None:  # noqa: ARG001
    window = _create_window()
    card_path = window._cards_dir / "10-overlay_1d_card.toml"  # type: ignore[attr-defined]
    window._activate_card(card_path)
    plot = window._panel_plots[0] if window._panel_plots else None  # type: ignore[attr-defined]
    assert plot is not None
    scene = plot.getPlotItem().scene()
    colorbars = [item for item in scene.items() if isinstance(item, pg.ColorBarItem)]
    assert len(colorbars) == 0


def test_colorbars_absent_for_1d_cards(app: QtWidgets.QApplication) -> None:  # noqa: ARG001
    window = _create_window()
    window._activate_card(window._cards_dir / "8-colormap_card.toml")  # type: ignore[attr-defined]
    plot = window._panel_plots[0] if window._panel_plots else None  # type: ignore[attr-defined]
    assert plot is not None
    scene = plot.getPlotItem().scene()
    colorbars = [item for item in scene.items() if isinstance(item, pg.ColorBarItem)]
    assert len(colorbars) == 0

    window._activate_card(window._cards_dir / "9-eventline_card.toml")  # type: ignore[attr-defined]
    plot2 = window._panel_plots[0] if window._panel_plots else None  # type: ignore[attr-defined]
    assert plot2 is not None
    scene2 = plot2.getPlotItem().scene()
    colorbars_after = [item for item in scene2.items() if isinstance(item, pg.ColorBarItem)]
    assert len(colorbars_after) == 0


def test_range_overlay_renders_items(app: QtWidgets.QApplication) -> None:  # noqa: ARG001
    window = _create_window()
    card_path = window._cards_dir / "12-range_overlay_card.toml"  # type: ignore[attr-defined]
    window._activate_card(card_path)
    plot = window._panel_plots[0] if window._panel_plots else None  # type: ignore[attr-defined]
    assert plot is not None
    items = plot.getPlotItem().items
    regions = [item for item in items if isinstance(item, pg.LinearRegionItem)]
    assert regions
    assert any(region.toolTip() for region in regions)


def test_colorbars_absent_after_rerender(app: QtWidgets.QApplication) -> None:  # noqa: ARG001
    window = _create_window()
    window._activate_card(window._cards_dir / "10-overlay_1d_card.toml")  # type: ignore[attr-defined]
    plot = window._panel_plots[0] if window._panel_plots else None  # type: ignore[attr-defined]
    assert plot is not None
    scene = plot.getPlotItem().scene()
    first_colorbars = [item for item in scene.items() if isinstance(item, pg.ColorBarItem)]
    assert len(first_colorbars) == 0

    window._render_current_card_selection()
    scene2 = plot.getPlotItem().scene()
    second_colorbars = [item for item in scene2.items() if isinstance(item, pg.ColorBarItem)]
    assert len(second_colorbars) == 0


def test_synchronized_axes_respect_axis_visibility(app: QtWidgets.QApplication) -> None:  # noqa: ARG001
    window = _create_window()
    window._activate_card(window._cards_dir / "11-sync_demo_card.toml")  # type: ignore[attr-defined]
    plots = window._panel_plots  # type: ignore[attr-defined]
    assert len(plots) >= 2
    top_axis = plots[0].getPlotItem().getAxis("bottom")
    bottom_axis = plots[-1].getPlotItem().getAxis("bottom")
    assert top_axis.isVisible() is True
    assert bottom_axis.isVisible() is False


def test_missing_panels_clear_previous_items(
    app: QtWidgets.QApplication, tmp_path: Path  # noqa: ARG001
) -> None:
    window, card_path = _create_missing_panel_window(tmp_path)
    window._activate_card(card_path)

    primary = window._panel_manager.plot_by_name("primary")  # type: ignore[attr-defined]
    secondary = window._panel_manager.plot_by_name("secondary")  # type: ignore[attr-defined]
    assert primary is not None
    assert secondary is not None
    assert any(isinstance(item, pg.PlotDataItem) for item in primary.getPlotItem().items)
    assert any(isinstance(item, pg.ImageItem) for item in secondary.getPlotItem().items)

    window._controller.update_selection("sample", "b")  # type: ignore[attr-defined]
    window._render_current_card_selection()
    assert not any(isinstance(item, pg.PlotDataItem) for item in primary.getPlotItem().items)
    assert any(isinstance(item, pg.ImageItem) for item in secondary.getPlotItem().items)

    window._controller.update_selection("sample", "c")  # type: ignore[attr-defined]
    window._render_current_card_selection()
    assert any(isinstance(item, pg.PlotDataItem) for item in primary.getPlotItem().items)
    assert not any(isinstance(item, pg.ImageItem) for item in secondary.getPlotItem().items)


def test_restore_state_uses_card_dir_when_card_file_is_missing(
    app: QtWidgets.QApplication, tmp_path: Path, monkeypatch: pytest.MonkeyPatch  # noqa: ARG001
) -> None:
    cards_dir = tmp_path / "cards"
    cards_dir.mkdir(parents=True)
    (cards_dir / "demo.toml").write_text('filepath = "<CARD_DIR>/../data/*.json"\n')
    missing_card = cards_dir / "does_not_exist.toml"

    saved_state = {
        "card_file": str(missing_card),
        "card_dir": str(cards_dir),
    }

    monkeypatch.setattr("visualizer.gui.main_window.StateManager.load", lambda _self: saved_state)
    monkeypatch.setattr("visualizer.gui.main_window.StateManager.save", lambda _self, _state: None)

    window = MainWindow(data_dir=None, cards_dir=None)

    assert window._cards_dir == cards_dir  # type: ignore[attr-defined]
    assert window._card_list.count() == 1  # type: ignore[attr-defined]
    assert window._sidebar_mode == "card"  # type: ignore[attr-defined]
