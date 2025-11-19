from __future__ import annotations

import sys
from pathlib import Path

from PySide6 import QtWidgets

from visualizer.gui.main_window import MainWindow


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _default_data_dir() -> Path:
    return _repo_root() / "example_data"


def _default_cards_dir() -> Path:
    return _repo_root() / "examples" / "cards"


def main() -> None:
    app = QtWidgets.QApplication(sys.argv)
    data_dir = _default_data_dir()
    cards_dir = _default_cards_dir()
    window = MainWindow(data_dir=data_dir, cards_dir=cards_dir)
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
