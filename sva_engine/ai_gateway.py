from __future__ import annotations

from typing import Any, Optional

from .ai_client import SVAAIClient
from .ai_key_pool import AIKeyPool
from .ai_router import AIRouter
from .ai_usage import AIUsageTracker
from .ai_routing_config import AIRoutingConfig


class AIGateway:
    """Unified AI interface with shared key pool and smart routing."""

    def __init__(
        self,
        api_key: str,
        api_url: str,
        model: str,
        *,
        client: Optional[SVAAIClient] = None,
        key_pool: Optional[AIKeyPool] = None,
        router: Optional[AIRouter] = None,
        usage: Optional[AIUsageTracker] = None,
        routing_config: Optional[AIRoutingConfig] = None,
        client_factory=None,
    ):
        self.api_url = api_url
        self.model = model
        self.key_pool = key_pool or AIKeyPool()
        self.router = router or AIRouter()
        self.usage = usage or AIUsageTracker()
        self.routing_config = routing_config or AIRoutingConfig()
        self.router.mode = self.routing_config.get_mode()
        self.client = client or SVAAIClient(
            api_key=api_key,
            api_url=api_url,
            model=model,
        )
        self.client_factory = client_factory or SVAAIClient

        self.api_key = api_key

    def _keys(self) -> list[str]:
        keys = self.key_pool.load()

        if self.api_key and self.api_key not in keys:
            keys.insert(0, self.api_key)

        return keys

    def ask(self, prompt: str) -> dict[str, Any]:
        """Send one AI request using the smart key router."""

        keys = self._keys()

        if not keys:
            return self.client.ask(prompt)

        self.router.mode = self.routing_config.get_mode()
        self.router.sync(keys)
        self.usage.sync(keys)

        key = self.router.select(keys)

        if key is None:
            return {
                "success": False,
                "error": "No available AI API key.",
            }

        attempted: set[str] = set()
        last_result: dict[str, Any] = {
            "success": False,
            "error": "All available AI API keys failed.",
        }

        while key is not None and key not in attempted:
            attempted.add(key)
            self.usage.record_request(key)

            client = self.client_factory(
                api_key=key,
                api_url=self.api_url,
                model=self.model,
            )

            result = client.ask(prompt)

            if result.get("success"):
                self.router.record_success(key)
                usage_data = result.get("usage", {})
                if isinstance(usage_data, dict):
                    self.usage.record_success(
                        key,
                        prompt_tokens=usage_data.get("prompt_tokens", 0),
                        completion_tokens=usage_data.get("completion_tokens", 0),
                    )
                else:
                    self.usage.record_success(key)
                return result

            self.router.record_failure(key)
            self.usage.record_failure(key)
            last_result = result

            key = self.router.select(keys)

        return last_result

    def set_routing_mode(self, mode: str) -> bool:
        """Persist and apply a routing mode."""
        if not self.routing_config.set_mode(mode):
            return False

        self.router.mode = self.routing_config.get_mode()
        return True

    def get_routing_mode(self) -> str:
        """Return the active routing mode."""
        return self.routing_config.get_mode()

    def status(self) -> list[dict[str, int | str | float]]:
        """Return router state without exposing full API keys."""

        result = []

        for item in self.router.status():
            key = str(item["key"])
            result.append(
                {
                    **item,
                    "key": AIKeyPool.mask(key),
                }
            )

        return result
