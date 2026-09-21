"""Automatic provider-recovery coordinator for Termux-AI."""

from __future__ import annotations

from typing import Any, Dict, Optional

from .agent import PersistentAgent
from .provider_registry import ProviderRegistry
from .task_store import TaskStore


class RecoveryCoordinator:
    """Resume PAUSED tasks when at least one AI provider is available."""

    def __init__(
        self,
        controller,
        store: Optional[TaskStore] = None,
        registry: Optional[ProviderRegistry] = None,
        agent: Optional[PersistentAgent] = None,
    ):
        self.controller = controller
        self.store = store or TaskStore()
        self.registry = registry or ProviderRegistry()
        self.agent = agent or PersistentAgent(
            controller,
            store=self.store,
        )

    def available_providers(self) -> list[str]:
        """Return currently available provider names."""
        return list(self.registry.available_names())

    def paused_tasks(self) -> list[dict[str, Any]]:
        """Return every PAUSED task across all persisted projects."""
        paused = []

        for project in self.store.list_projects():
            project_id = project.get("project_id")

            if not project_id:
                continue

            for task in self.store.list_tasks(project_id):
                if task.get("status") == "PAUSED":
                    paused.append(task)

        return paused

    def resume_available_tasks(self) -> Dict[str, Any]:
        """Resume all PAUSED tasks when a provider is available."""
        providers = self.available_providers()
        provider_available = bool(providers)

        if not provider_available:
            return {
                "success": False,
                "provider_available": False,
                "providers": [],
                "paused_count": len(self.paused_tasks()),
                "resumed_count": 0,
                "results": [],
            }

        results = []

        for task in self.paused_tasks():
            project_id = task.get("project_id")
            task_id = task.get("task_id")

            if not project_id or not task_id:
                continue

            result = self.agent.auto_resume_if_available(
                project_id,
                task_id,
                provider_available=True,
            )

            results.append(result)

        resumed_count = sum(
            1
            for result in results
            if result.get("success")
        )

        return {
            "success": True,
            "provider_available": True,
            "providers": providers,
            "paused_count": len(results),
            "resumed_count": resumed_count,
            "results": results,
        }
