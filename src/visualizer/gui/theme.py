from __future__ import annotations

from typing import Dict


DEFAULT_PALETTE: Dict[str, str] = {
    "bg": "#e9e9e9",
    "sidebar_bg": "#efefef",
    "surface": "#ffffff",
    "surface_alt": "#f3f3f3",
    "text": "#1b1b1b",
    "muted_text": "#3f3f3f",
    "border": "#c6c6c6",
    "accent": "#2b5f87",
    "accent_soft": "#e6eef5",
    "warning": "#9c6d00",
    "button_bg": "#ffffff",
}


def build_stylesheet(palette: Dict[str, str] | None = None) -> str:
    colors = DEFAULT_PALETTE.copy()
    if palette:
        colors.update(palette)
    return f"""
QMainWindow {{
  background: {colors["bg"]};
  color: {colors["text"]};
}}

QMenuBar {{
  background: {colors["bg"]};
  color: {colors["text"]};
  border-bottom: 1px solid {colors["border"]};
}}

QMenuBar::item {{
  padding: 6px 10px;
  background: transparent;
}}

QMenuBar::item:selected {{
  background: {colors["accent_soft"]};
}}

QMenu {{
  background: {colors["surface"]};
  color: {colors["text"]};
  border: 1px solid {colors["border"]};
}}

QMenu::item {{
  padding: 6px 12px;
}}

QMenu::item:selected {{
  background: {colors["accent_soft"]};
}}

#sidebar {{
  background: {colors["sidebar_bg"]};
  border-right: 1px solid {colors["border"]};
}}

#sidebarPathLabel {{
  color: {colors["muted_text"]};
}}

#sidebarModeLabel {{
  color: {colors["muted_text"]};
  font-size: 12px;
}}

#sidebarToggleButton {{
  border: 1px solid transparent;
  border-radius: 8px;
  padding: 2px;
  color: {colors["muted_text"]};
}}

#sidebarToggleButton:hover {{
  background: {colors["accent_soft"]};
  color: {colors["text"]};
}}

#loadedFilesToggle {{
  border: 1px solid transparent;
  border-radius: 6px;
  padding: 2px;
  color: {colors["text"]};
}}

#loadedFilesToggle:hover {{
  background: {colors["accent_soft"]};
}}

#sidebar QListWidget QScrollBar:vertical {{
  background: {colors["surface_alt"]};
  width: 10px;
  margin: 0;
}}

#sidebar QListWidget QScrollBar::handle:vertical {{
  background: {colors["border"]};
  border-radius: 5px;
  min-height: 20px;
}}

#sidebar QListWidget QScrollBar::handle:vertical:hover {{
  background: {colors["muted_text"]};
}}

#sidebar QListWidget QScrollBar::add-line:vertical,
#sidebar QListWidget QScrollBar::sub-line:vertical {{
  background: none;
  height: 0;
}}

#sidebar QListWidget QScrollBar::add-page:vertical,
#sidebar QListWidget QScrollBar::sub-page:vertical {{
  background: {colors["surface_alt"]};
}}

#sidebar QListWidget QScrollBar:horizontal {{
  background: {colors["surface_alt"]};
  height: 10px;
  margin: 0;
}}

#sidebar QListWidget QScrollBar::handle:horizontal {{
  background: {colors["border"]};
  border-radius: 5px;
  min-width: 20px;
}}

#sidebar QListWidget QScrollBar::handle:horizontal:hover {{
  background: {colors["muted_text"]};
}}

#sidebar QListWidget QScrollBar::add-line:horizontal,
#sidebar QListWidget QScrollBar::sub-line:horizontal {{
  background: none;
  width: 0;
}}

#sidebar QListWidget QScrollBar::add-page:horizontal,
#sidebar QListWidget QScrollBar::sub-page:horizontal {{
  background: {colors["surface_alt"]};
}}

QListWidget {{
  background: {colors["surface"]};
  border: 1px solid {colors["border"]};
  border-radius: 6px;
  padding: 2px;
}}

QListWidget::item {{
  padding: 6px 8px;
  border-radius: 4px;
}}

QListWidget::item:selected {{
  background: {colors["accent_soft"]};
}}

QGroupBox {{
  border: 1px solid {colors["border"]};
  border-radius: 6px;
  margin-top: 10px;
}}

QGroupBox::title {{
  subcontrol-origin: margin;
  subcontrol-position: top left;
  padding: 0 4px;
  color: {colors["muted_text"]};
}}

QPushButton {{
  background: {colors["button_bg"]};
  border: 1px solid {colors["border"]};
  border-radius: 6px;
  padding: 6px 10px;
}}

QPushButton:hover {{
  border-color: {colors["accent"]};
}}

QPushButton:pressed {{
  background: {colors["accent_soft"]};
}}

QToolButton {{
  background: transparent;
}}

QComboBox {{
  background: {colors["surface"]};
  border: 1px solid {colors["border"]};
  border-radius: 6px;
  padding: 4px 8px;
}}

QComboBox::drop-down {{
  border-left: 1px solid {colors["border"]};
  width: 18px;
}}

QTableView {{
  background: {colors["surface"]};
  border: 1px solid {colors["border"]};
  gridline-color: {colors["border"]};
}}

#statusLabel {{
  background: {colors["surface"]};
  border: 1px solid {colors["border"]};
  border-radius: 6px;
  padding: 6px;
  color: {colors["text"]};
}}

#warningLabel {{
  color: {colors["warning"]};
}}

#sidebar QListWidget {{
  color: {colors["text"]};
}}

#sidebar QListWidget::item {{
  color: {colors["text"]};
}}

#sidebar QListWidget::item:selected {{
  color: {colors["text"]};
}}

#sidebar QGroupBox {{
  color: {colors["text"]};
}}

#sidebar QGroupBox::title {{
  color: {colors["text"]};
}}

#sidebar QPushButton {{
  color: {colors["text"]};
}}

#sidebar QComboBox {{
  color: {colors["text"]};
}}

#sidebar QComboBox QAbstractItemView {{
  background: {colors["surface"]};
  color: {colors["text"]};
  border: 1px solid {colors["border"]};
  selection-background-color: {colors["accent_soft"]};
  selection-color: {colors["text"]};
}}

#cardVariablesGroup QLabel {{
  color: {colors["text"]};
}}

#loadedFilesLabel {{
  color: {colors["text"]};
}}
""".strip()
