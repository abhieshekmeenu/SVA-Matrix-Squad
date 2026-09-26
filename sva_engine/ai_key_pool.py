from __future__ import annotations

import json
from pathlib import Path


API_KEYS_FILE = Path.home() / ".sva_matrix_squad_api_keys.json"


class AIKeyPool:
    """Manage multiple SVA Matrix AI API keys safely."""

    def __init__(self, path: Path = API_KEYS_FILE, max_keys: int | None = None):
        self.path = Path(path)
        self.max_keys = max_keys

    def load(self) -> list[str]:
        keys: list[str] = []

        try:
            if not self.path.exists():
                return keys

            data = json.loads(
                self.path.read_text(
                    encoding="utf-8",
                    errors="ignore",
                )
            )

            stored_keys = data.get("keys", [])

            if not isinstance(stored_keys, list):
                return keys

            for item in stored_keys:
                if isinstance(item, dict):
                    key = str(item.get("key", "")).strip()
                elif isinstance(item, str):
                    key = item.strip()
                else:
                    continue

                if key and key not in keys:
                    keys.append(key)

        except (OSError, ValueError, TypeError):
            return []

        return keys if self.max_keys is None else keys[: self.max_keys]

    def save(self, keys: list[str]) -> bool:
        unique: list[str] = []

        for key in keys:
            key = str(key).strip()
            if key and key not in unique:
                unique.append(key)

        if self.max_keys is not None and len(unique) > self.max_keys:
            unique = unique[: self.max_keys]

        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self.path.write_text(
                json.dumps(
                    {
                        "version": 1,
                        "keys": [{"key": key} for key in unique],
                    },
                    indent=2,
                ),
                encoding="utf-8",
            )
            return True
        except OSError:
            return False

    def add(self, key: str) -> bool:
        key = key.strip()

        if not key:
            return False

        keys = self.load()

        if key in keys:
            return True

        if self.max_keys is not None and len(keys) >= self.max_keys:
            return False

        keys.append(key)
        return self.save(keys)

    def remove(self, key: str) -> bool:
        key = key.strip()
        keys = self.load()

        if key not in keys:
            return False

        keys.remove(key)
        return self.save(keys)

    @staticmethod
    def mask(key: str) -> str:
        key = key.strip()

        if len(key) <= 8:
            return "*" * len(key)

        return f"{key[:4]}...{key[-4:]}"

    def masked(self) -> list[str]:
        return [self.mask(key) for key in self.load()]

    def count(self) -> int:
        return len(self.load())
