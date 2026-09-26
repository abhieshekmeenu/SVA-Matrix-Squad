from __future__ import annotations

import json
from pathlib import Path


CONFIG_FILE = Path.home() / ".sva_matrix_ai_routing.json"

VALID_MODES = {
    "single",
    "sequential",
    "load_balance",
    "smart",
}


class AIRoutingConfig:
    """Persistent routing-mode configuration."""

    def __init__(self, path: Path = CONFIG_FILE):
        self.path = Path(path)

    def get_mode(self) -> str:
        try:
            if self.path.exists():
                data = json.loads(
                    self.path.read_text(
                        encoding="utf-8",
                        errors="ignore",
                    )
                )

                mode = data.get("mode", "smart")

                if mode in VALID_MODES:
                    return mode
        except (OSError, ValueError, TypeError):
            pass

        return "smart"

    def set_mode(self, mode: str) -> bool:
        mode = mode.strip().lower()

        if mode not in VALID_MODES:
            return False

        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self.path.write_text(
                json.dumps(
                    {
                        "version": 1,
                        "mode": mode,
                    },
                    indent=2,
                ),
                encoding="utf-8",
            )
            return True
        except OSError:
            return False
