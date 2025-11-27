import os

import pytest

PySide6 = pytest.importorskip("PySide6", reason="PySide6 not installed; install requirements to run renderer tests")
pg = pytest.importorskip("pyqtgraph", reason="pyqtgraph not installed; install requirements to run renderer tests")

from PySide6 import QtWidgets  # type: ignore

from visualizer.interpretation.specs import PlotSpec, VisualizationType
from visualizer.viz.renderer import PlotRenderer


@pytest.fixture(scope="module")
def app() -> QtWidgets.QApplication:
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    existing = QtWidgets.QApplication.instance()
    if existing:
        return existing
    return QtWidgets.QApplication([])


def test_colormap_render_does_not_raise(app: QtWidgets.QApplication) -> None:
    renderer = PlotRenderer()
    widget = pg.PlotWidget()
    spec = PlotSpec(
        dataset_id="d1",
        label=None,
        x=[0, 1, 2],
        y=[1, 2, 3],
        x_label="x",
        y_label="y",
        visualization=VisualizationType.COLORMAP,
    )
    renderer.render(widget, spec)


def test_eventline_render_does_not_raise(app: QtWidgets.QApplication) -> None:
    renderer = PlotRenderer()
    widget = pg.PlotWidget()
    spec = PlotSpec(
        dataset_id="d2",
        label=None,
        x=[0, 2, 4],
        y=[1, 5, 10],
        x_label="time",
        y_label="intensity",
        visualization=VisualizationType.EVENTLINE,
    )
    renderer.render(widget, spec)


def test_overlay_rejects_mixed_dimensions(app: QtWidgets.QApplication) -> None:
    renderer = PlotRenderer()
    widget = pg.PlotWidget()
    specs = [
        PlotSpec(
            dataset_id="d1",
            label=None,
            x=[0, 1, 2],
            y=[1, 2, 3],
            x_label="x",
            y_label="y",
            visualization=VisualizationType.LINE,
        ),
        PlotSpec(
            dataset_id="d2",
            label=None,
            x=[0, 1, 2],
            y=[1, 2, 3],
            x_label="x",
            y_label="y",
            visualization=VisualizationType.COLORMAP,
        ),
    ]
    with pytest.raises(ValueError):
        renderer.render_multiple(widget, specs)


def test_overlay_allows_one_dimensional_mix(app: QtWidgets.QApplication) -> None:
    renderer = PlotRenderer()
    widget = pg.PlotWidget()
    specs = [
        PlotSpec(
            dataset_id="d1",
            label=None,
            x=[0, 1, 2],
            y=[1, 2, 3],
            x_label="x",
            y_label="y",
            visualization=VisualizationType.COLORMAP,
        ),
        PlotSpec(
            dataset_id="d2",
            label=None,
            x=[0, 1, 2],
            y=[0.5, 0.6, 0.7],
            x_label="x",
            y_label="y",
            visualization=VisualizationType.EVENTLINE,
        ),
    ]
    renderer.render_multiple(widget, specs)
