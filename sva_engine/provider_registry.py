"""Provider registry for Termux-AI.

Providers are registered by name and expose a common ``ask()`` method.
This keeps the router independent from individual AI vendors.
"""

from __future__ import annotations

from typing import Any, Dict, Iterable, Optional


class ProviderRegistry:
    """Register, inspect and resolve AI providers dynamically."""

    def __init__(self, providers: Optional[Dict[str, Any]] = None):
        self._providers: Dict[str, Any] = {}

        if providers:
            for name, client in providers.items():
                self.register(name, client)

    def register(self, name: str, client: Any) -> None:
        if not isinstance(name, str) or not name.strip():
            raise ValueError("Provider name is required")

        if client is None or not callable(getattr(client, "ask", None)):
            raise ValueError(
                f"Provider '{name}' must expose an ask() method"
            )

        self._providers[name.strip().lower()] = client

    def unregister(self, name: str) -> bool:
        return self._providers.pop(name.strip().lower(), None) is not None

    def get(self, name: str) -> Any:
        return self._providers.get(name.strip().lower())

    def has(self, name: str) -> bool:
        return name.strip().lower() in self._providers

    def names(self) -> list[str]:
        return list(self._providers.keys())

    def available(self, name: str) -> bool:
        client = self.get(name)

        if client is None:
            return False

        checker = getattr(client, "available", None)

        if checker is None:
            return True

        try:
            return bool(checker())
        except Exception:
            return False

    def available_names(self) -> list[str]:
        return [
            name
            for name in self.names()
            if self.available(name)
        ]

    def first_available(
        self,
        preferred: Optional[str] = None,
        fallback_order: Optional[Iterable[str]] = None,
    ) -> Optional[str]:
        candidates = []

        if preferred:
            candidates.append(preferred.strip().lower())

        if fallback_order:
            candidates.extend(
                str(name).strip().lower()
                for name in fallback_order
            )

        seen = set()

        for name in candidates:
            if name in seen:
                continue

            seen.add(name)

            if self.available(name):
                return name

        return None
