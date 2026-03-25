from __future__ import annotations

import os
from pathlib import Path

import pytest


os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


@pytest.fixture(scope="session")
def repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


@pytest.fixture(scope="session")
def examples_dir(repo_root: Path) -> Path:
    return repo_root / "examples"


@pytest.fixture(scope="session")
def examples_cards_dir(examples_dir: Path) -> Path:
    return examples_dir / "cards"


@pytest.fixture(scope="session")
def examples_data_dir(examples_dir: Path) -> Path:
    return examples_dir / "data"


@pytest.fixture(scope="session")
def qt_app():
    QtWidgets = pytest.importorskip(
        "PySide6.QtWidgets",
        reason="PySide6 not installed; install requirements to run GUI tests",
    )
    existing = QtWidgets.QApplication.instance()
    if existing:
        return existing
    return QtWidgets.QApplication([])
