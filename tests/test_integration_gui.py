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


def test_one_dim_overlay_has_multiple_colorbars(app: QtWidgets.QApplication) -> None:  # noqa: ARG001
    window = _create_window()
    card_path = window._cards_dir / "10-overlay_1d_card.toml"  # type: ignore[attr-defined]
    window._activate_card(card_path)
    plot = window._panel_plots[0] if window._panel_plots else None  # type: ignore[attr-defined]
    assert plot is not None
    scene = plot.getPlotItem().scene()
    colorbars = [item for item in scene.items() if isinstance(item, pg.ColorBarItem)]
    assert len(colorbars) >= 2


def test_colorbars_do_not_stack_across_card_switches(app: QtWidgets.QApplication) -> None:  # noqa: ARG001
    window = _create_window()
    window._activate_card(window._cards_dir / "8-colormap_card.toml")  # type: ignore[attr-defined]
    plot = window._panel_plots[0] if window._panel_plots else None  # type: ignore[attr-defined]
    assert plot is not None
    scene = plot.getPlotItem().scene()
    initial_colorbars = [item for item in scene.items() if isinstance(item, pg.ColorBarItem)]
    assert len(initial_colorbars) >= 1

    window._activate_card(window._cards_dir / "9-eventline_card.toml")  # type: ignore[attr-defined]
    plot2 = window._panel_plots[0] if window._panel_plots else None  # type: ignore[attr-defined]
    assert plot2 is not None
    scene2 = plot2.getPlotItem().scene()
    colorbars_after = [item for item in scene2.items() if isinstance(item, pg.ColorBarItem)]
    assert len(colorbars_after) <= 2


def test_colorbars_do_not_stack_within_same_card_rerender(app: QtWidgets.QApplication) -> None:  # noqa: ARG001
    window = _create_window()
    window._activate_card(window._cards_dir / "10-overlay_1d_card.toml")  # type: ignore[attr-defined]
    plot = window._panel_plots[0] if window._panel_plots else None  # type: ignore[attr-defined]
    assert plot is not None
    scene = plot.getPlotItem().scene()
    first_colorbars = [item for item in scene.items() if isinstance(item, pg.ColorBarItem)]
    assert len(first_colorbars) >= 2

    # Force rerender (simulates view change)
    window._render_current_card_selection()
    scene2 = plot.getPlotItem().scene()
    second_colorbars = [item for item in scene2.items() if isinstance(item, pg.ColorBarItem)]
    assert len(second_colorbars) >= 2
    assert len(second_colorbars) == len(first_colorbars)
