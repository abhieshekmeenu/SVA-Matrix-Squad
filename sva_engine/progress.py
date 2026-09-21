"""Project/task progress and history summaries for Termux-AI."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List


class TaskProgress:
    """Build user-friendly progress information from persisted tasks."""

    @staticmethod
    def percent(task: Dict[str, Any]) -> float:
        current = int(task.get("current_step") or 0)
        total = task.get("total_steps")

        if total is None:
            return 0.0

        total = int(total)

        if total <= 0:
            return 100.0 if task.get("status") == "COMPLETE" else 0.0

        value = (current / total) * 100
        return round(min(max(value, 0.0), 100.0), 1)

    @classmethod
    def summarize(cls, task: Dict[str, Any]) -> Dict[str, Any]:
        current = int(task.get("current_step") or 0)
        total = task.get("total_steps")

        if total is not None:
            total = int(total)
            remaining = max(total - current, 0)
        else:
            remaining = None

        return {
            "project_id": task.get("project_id"),
            "task_id": task.get("task_id"),
            "description": task.get("description"),
            "status": task.get("status"),
            "progress_percent": cls.percent(task),
            "current_step": current,
            "total_steps": total,
            "remaining_steps": remaining,
            "current_action": task.get("current_action"),
            "last_output": task.get("last_output"),
            "last_error": task.get("last_error"),
            "retry_count": int(task.get("retry_count") or 0),
            "pending_approval": task.get("pending_approval"),
            "updated_at": task.get("updated_at"),
        }

    @classmethod
    def project_summary(
        cls,
        project: Dict[str, Any],
        tasks: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        summaries = [cls.summarize(task) for task in tasks]

        completed = sum(
            task.get("status") == "COMPLETE"
            for task in tasks
        )
        running = sum(
            task.get("status") == "RUNNING"
            for task in tasks
        )
        paused = sum(
            task.get("status") == "PAUSED"
            for task in tasks
        )
        errors = sum(
            task.get("status") == "ERROR"
            for task in tasks
        )

        workspace = project.get("workspace")
        folder = None

        if workspace:
            workspace_path = Path(workspace)

            try:
                file_count = sum(
                    1 for item in workspace_path.rglob("*")
                    if item.is_file()
                )
            except OSError:
                file_count = 0

            folder = {
                "path": str(workspace_path),
                "exists": workspace_path.is_dir(),
                "file_count": file_count,
            }

        return {
            "project_id": project.get("project_id"),
            "name": project.get("name"),
            "description": project.get("description"),
            "status": project.get("status"),
            "folder": folder,
            "task_count": len(tasks),
            "completed_tasks": completed,
            "running_tasks": running,
            "paused_tasks": paused,
            "error_tasks": errors,
            "tasks": summaries,
            "updated_at": project.get("updated_at"),
        }
