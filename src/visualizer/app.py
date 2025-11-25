from __future__ import annotations

import sys
from pathlib import Path

from PySide6 import QtWidgets

from visualizer.gui.main_window import MainWindow


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def main() -> None:
    app = QtWidgets.QApplication(sys.argv)
    window = MainWindow(data_dir=None, cards_dir=None)
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
