"""Validated bridge from AI planning to persistent Termux-AI tasks."""

from __future__ import annotations

from typing import Any, Dict, Optional

from .planner import AIPlanner
from .task_store import TaskStore


class DynamicTaskPlanner:
    """Create persistent tasks from AI-generated, validated plans."""

    def __init__(self, ai_client, store: Optional[TaskStore] = None):
        self.planner = AIPlanner(ai_client)
        self.store = store or TaskStore()

    @staticmethod
    def _clean_steps(steps: Any):
        if not isinstance(steps, list):
            return None

        clean = []

        for step in steps:
            if not isinstance(step, str):
                return None

            step = step.strip()

            if not step:
                return None

            clean.append(step)

        return clean if clean else None

    def create_task(
        self,
        project_id: str,
        task_id: str,
        description: str,
    ) -> Dict[str, Any]:

        if not project_id or not str(project_id).strip():
            return {
                "success": False,
                "reason": "project_id is required",
            }

        if not task_id or not str(task_id).strip():
            return {
                "success": False,
                "reason": "task_id is required",
            }

        if not description or not str(description).strip():
            return {
                "success": False,
                "reason": "Empty task",
            }

        plan = self.planner.plan(description)

        if not plan.get("success", False):
            return {
                "success": False,
                "reason": plan.get("reason") or "AI planning failed",
                "plan": plan,
            }

        steps = self._clean_steps(plan.get("steps"))

        if steps is None:
            return {
                "success": False,
                "reason": "Planner produced no valid executable steps",
                "plan": plan,
            }

        self.store.create_project(project_id)

        task = self.store.create_task(
            project_id,
            task_id,
            plan.get("task") or description,
            steps=steps,
        )

        return {
            "success": True,
            "project_id": project_id,
            "task_id": task_id,
            "plan": plan,
            "task": task,
        }
