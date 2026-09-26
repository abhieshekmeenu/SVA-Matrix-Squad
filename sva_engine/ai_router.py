from __future__ import annotations

from dataclasses import dataclass
from time import monotonic


@dataclass
class KeyState:
    key: str
    failures: int = 0
    requests: int = 0
    successes: int = 0
    cooldown_until: float = 0.0


class AIRouter:
    """Health-aware router for the unified AI Gateway."""

    def __init__(self, cooldown_seconds: float = 5.0, mode: str = "smart"):
        self._states: dict[str, KeyState] = {}
        self._cursor = 0
        self.cooldown_seconds = cooldown_seconds
        self.mode = mode if mode in {
            "single",
            "sequential",
            "load_balance",
            "smart",
        } else "smart"

    def sync(self, keys: list[str]) -> None:
        current = set(keys)

        for key in keys:
            if key not in self._states:
                self._states[key] = KeyState(key=key)

        for key in list(self._states):
            if key not in current:
                del self._states[key]

        if self._states:
            self._cursor %= len(self._states)
        else:
            self._cursor = 0

    def available(self, key: str) -> bool:
        state = self._states.get(key)

        if state is None:
            return False

        return monotonic() >= state.cooldown_until

    def select(self, keys: list[str]) -> str | None:
        self.sync(keys)

        if not keys:
            return None

        available_keys = [
            key
            for key in keys
            if self.available(key)
        ]

        if not available_keys:
            return None

        # Prefer healthy keys with the lowest request count.
        # Cursor remains the tie-breaker for equal usage.
        ordered = (
            keys[self._cursor:] + keys[:self._cursor]
        )

        if self.mode == "single":
            preferred = keys[0]
            if preferred in available_keys:
                key = preferred
            else:
                key = available_keys[0]

        elif self.mode == "sequential":
            key = available_keys[0]

        elif self.mode == "load_balance":
            key = min(
                available_keys,
                key=lambda item: (
                    self._states[item].requests,
                    ordered.index(item),
                ),
            )

        else:
            available_keys.sort(
                key=lambda item: (
                    self._states[item].failures,
                    self._states[item].requests,
                    ordered.index(item),
                )
            )
            key = available_keys[0]
        state = self._states[key]
        state.requests += 1

        self._cursor = (keys.index(key) + 1) % len(keys)

        return key

    def record_success(self, key: str) -> None:
        state = self._states.get(key)

        if state is None:
            return

        state.successes += 1
        state.failures = 0
        state.cooldown_until = 0.0

    def record_failure(
        self,
        key: str,
        *,
        cooldown_seconds: float | None = None,
    ) -> None:
        state = self._states.get(key)

        if state is None:
            return

        state.failures += 1

        delay = (
            self.cooldown_seconds
            if cooldown_seconds is None
            else cooldown_seconds
        )

        state.cooldown_until = monotonic() + delay

    def health(self, key: str) -> str:
        state = self._states.get(key)

        if state is None:
            return "UNKNOWN"

        if not self.available(key):
            return "COOLDOWN"

        if state.failures == 0:
            return "HEALTHY"

        return "DEGRADED"

    def status(self) -> list[dict[str, int | str | float]]:
        return [
            {
                "key": state.key,
                "failures": state.failures,
                "requests": state.requests,
                "successes": state.successes,
                "health": self.health(state.key),
                "cooldown_until": state.cooldown_until,
            }
            for state in self._states.values()
        ]
