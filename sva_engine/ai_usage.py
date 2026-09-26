from __future__ import annotations

from dataclasses import dataclass
from time import time


@dataclass
class UsageState:
    key: str
    requests: int = 0
    successes: int = 0
    failures: int = 0
    total_prompt_tokens: int = 0
    total_completion_tokens: int = 0
    last_used: float = 0.0


class AIUsageTracker:
    """Track per-key AI request and token usage."""

    def __init__(self):
        self._states: dict[str, UsageState] = {}

    def sync(self, keys: list[str]) -> None:
        current = set(keys)

        for key in keys:
            if key not in self._states:
                self._states[key] = UsageState(key=key)

        for key in list(self._states):
            if key not in current:
                del self._states[key]

    def record_request(self, key: str) -> None:
        state = self._states.get(key)

        if state is None:
            state = UsageState(key=key)
            self._states[key] = state

        state.requests += 1
        state.last_used = time()

    def record_success(
        self,
        key: str,
        *,
        prompt_tokens: int = 0,
        completion_tokens: int = 0,
    ) -> None:
        state = self._states.get(key)

        if state is None:
            state = UsageState(key=key)
            self._states[key] = state

        state.successes += 1
        state.total_prompt_tokens += max(0, int(prompt_tokens))
        state.total_completion_tokens += max(0, int(completion_tokens))
        state.last_used = time()

    def record_failure(self, key: str) -> None:
        state = self._states.get(key)

        if state is None:
            state = UsageState(key=key)
            self._states[key] = state

        state.failures += 1
        state.last_used = time()

    def get(self, key: str) -> UsageState | None:
        return self._states.get(key)

    def status(self) -> list[dict[str, int | float | str]]:
        return [
            {
                "key": state.key,
                "requests": state.requests,
                "successes": state.successes,
                "failures": state.failures,
                "prompt_tokens": state.total_prompt_tokens,
                "completion_tokens": state.total_completion_tokens,
                "last_used": state.last_used,
            }
            for state in self._states.values()
        ]
