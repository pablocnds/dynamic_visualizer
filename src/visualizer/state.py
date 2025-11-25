from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Dict

from platformdirs import user_config_dir


class StateManager:
    """Small helper to persist last-used paths in a user config directory."""

    def __init__(self, app_name: str = "dynamic_visualizer") -> None:
        config_root = Path(user_config_dir(app_name))
        self._config_file = config_root / "state.json"
        self._config_file.parent.mkdir(parents=True, exist_ok=True)

    def load(self) -> Dict[str, Any]:
        if not self._config_file.exists():
            return {}
        try:
            return json.loads(self._config_file.read_text())
        except Exception:
            return {}

    def save(self, state: Dict[str, Any]) -> None:
        try:
            tmp_path = self._config_file.with_suffix(".tmp")
            tmp_path.write_text(json.dumps(state, indent=2))
            os.replace(tmp_path, self._config_file)
        except Exception:
            # Fail silently; persistence should never break the app.
            return
