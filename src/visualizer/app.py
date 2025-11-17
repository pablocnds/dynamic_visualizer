from __future__ import annotations

import sys
from pathlib import Path

from PySide6 import QtWidgets

from visualizer.gui.main_window import MainWindow


def _default_data_dir() -> Path:
    return Path(__file__).resolve().parents[2] / "example_data"


def main() -> None:
    app = QtWidgets.QApplication(sys.argv)
    data_dir = _default_data_dir()
    window = MainWindow(data_dir=data_dir)
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
