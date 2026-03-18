from visualizer.controller.session import SessionController
from visualizer.data.repository import DatasetRepository


def test_build_panel_plans_without_session_returns_empty_triplet() -> None:
    controller = SessionController(DatasetRepository())
    plans, missing, incompatible = controller.build_panel_plans()
    assert plans == []
    assert missing == []
    assert incompatible == []
