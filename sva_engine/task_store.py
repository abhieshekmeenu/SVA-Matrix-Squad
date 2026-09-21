"""Persistent project/task storage for Termux-AI."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional


PROJECTS_ROOT = Path(__file__).resolve().parents[2] / "projects"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class TaskStore:
    """Persist projects and tasks independently on disk."""

    def __init__(self, root: Optional[Path] = None):
        self.root = Path(root or PROJECTS_ROOT)
        self.root.mkdir(parents=True, exist_ok=True)

    def project_dir(self, project_id: str) -> Path:
        if not project_id or not str(project_id).strip():
            raise ValueError("project_id is required")
        return self.root / str(project_id).strip()

    def task_dir(self, project_id: str) -> Path:
        path = self.project_dir(project_id) / "tasks"
        path.mkdir(parents=True, exist_ok=True)
        return path

    def project_file(self, project_id: str) -> Path:
        return self.project_dir(project_id) / "project.json"

    def workspace_dir(self, project_id: str) -> Path:
        """Return the project's configured workspace."""
        project = self.load_project(project_id)

        if project:
            configured = project.get("workspace")
            if isinstance(configured, str) and configured.strip():
                path = Path(configured).expanduser().resolve()
                path.mkdir(parents=True, exist_ok=True)
                return path

        path = self.project_dir(project_id) / "workspace"
        path.mkdir(parents=True, exist_ok=True)
        return path

    def task_file(self, project_id: str, task_id: str) -> Path:
        if not task_id or not str(task_id).strip():
            raise ValueError("task_id is required")
        return self.task_dir(project_id) / f"{str(task_id).strip()}.json"

    def _save_json(self, path: Path, data: Dict[str, Any]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)

        temp = path.with_suffix(path.suffix + ".tmp")
        temp.write_text(
            json.dumps(data, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        temp.replace(path)

    def create_project(
        self,
        project_id: str,
        name: Optional[str] = None,
        description: str = "",
        workspace: Optional[Path] = None,
    ) -> Dict[str, Any]:
        path = self.project_file(project_id)

        if path.exists():
            existing = self.load_project(project_id)
            if existing is not None:
                self.workspace_dir(project_id)
            return existing

        if workspace is None:
            workspace_path = self.workspace_dir(project_id)
        else:
            workspace_path = Path(workspace).expanduser().resolve()
            workspace_path.mkdir(parents=True, exist_ok=True)

        project = {
            "project_id": str(project_id),
            "name": name or str(project_id),
            "description": description,
            "status": "ACTIVE",
            "workspace": str(workspace_path),
            "created_at": _now(),
            "updated_at": _now(),
        }

        self._save_json(path, project)
        return project

    def load_project(self, project_id: str) -> Optional[Dict[str, Any]]:
        path = self.project_file(project_id)

        if not path.exists():
            return None

        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return None

        return data if isinstance(data, dict) else None

    def create_task(
        self,
        project_id: str,
        task_id: str,
        description: str,
        steps: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        path = self.task_file(project_id, task_id)

        if path.exists():
            existing = self.load_task(project_id, task_id)
            if existing is not None:
                return existing

        clean_steps = list(steps or [])

        task = {
            "task_id": str(task_id),
            "project_id": str(project_id),
            "description": description,
            "status": "PENDING",
            "current_step": 0,
            "total_steps": len(clean_steps) if clean_steps else None,
            "current_action": None,
            "steps": clean_steps,
            "results": [],
            "last_output": None,
            "last_error": None,
            "retry_count": 0,
            "checkpoint": None,
            "pending_approval": None,
            "created_at": _now(),
            "updated_at": _now(),
        }

        self._save_json(path, task)
        return task

    def load_task(
        self,
        project_id: str,
        task_id: str,
    ) -> Optional[Dict[str, Any]]:
        path = self.task_file(project_id, task_id)

        if not path.exists():
            return None

        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return None

        return data if isinstance(data, dict) else None

    def save_task(self, task: Dict[str, Any]) -> Dict[str, Any]:
        if not isinstance(task, dict):
            raise TypeError("task must be a dictionary")

        project_id = task.get("project_id")
        task_id = task.get("task_id")

        if not project_id or not task_id:
            raise ValueError("task must contain project_id and task_id")

        task = dict(task)
        task["updated_at"] = _now()

        self._save_json(
            self.task_file(project_id, task_id),
            task,
        )
        return task

    def update_task(self, project_id: str, task_id: str, **values) -> Optional[Dict[str, Any]]:
        task = self.load_task(project_id, task_id)

        if task is None:
            return None

        task.update(values)
        task["updated_at"] = _now()

        return self.save_task(task)

    def checkpoint(
        self,
        project_id: str,
        task_id: str,
        *,
        current_step: int,
        total_steps: Optional[int] = None,
        current_action: Optional[str] = None,
        status: Optional[str] = None,
        last_output: Optional[str] = None,
        last_error: Optional[str] = None,
        result: Optional[Dict[str, Any]] = None,
    ) -> Optional[Dict[str, Any]]:
        task = self.load_task(project_id, task_id)

        if task is None:
            return None

        task["current_step"] = int(current_step)

        if total_steps is not None:
            task["total_steps"] = int(total_steps)

        task["current_action"] = current_action

        if status is not None:
            task["status"] = status

        if last_output is not None:
            task["last_output"] = last_output

        if last_error is not None:
            task["last_error"] = last_error

        task["checkpoint"] = {
            "current_step": task["current_step"],
            "total_steps": task["total_steps"],
            "current_action": task["current_action"],
            "saved_at": _now(),
        }

        if result is not None:
            task["results"].append(result)

        return self.save_task(task)

    def list_projects(self) -> List[Dict[str, Any]]:
        """Return all persisted projects without creating project directories."""
        if not self.root.exists():
            return []

        projects = []

        for directory in self.root.iterdir():
            if not directory.is_dir():
                continue

            project_file = directory / "project.json"
            if not project_file.is_file():
                continue

            try:
                data = json.loads(project_file.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue

            if isinstance(data, dict):
                projects.append(data)

        return sorted(
            projects,
            key=lambda project: project.get("updated_at", ""),
            reverse=True,
        )

    def list_tasks(self, project_id: str) -> List[Dict[str, Any]]:
        directory = self.task_dir(project_id)
        tasks = []

        for path in directory.glob("*.json"):
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue

            if isinstance(data, dict):
                tasks.append(data)

        return sorted(
            tasks,
            key=lambda task: task.get("updated_at", ""),
            reverse=True,
        )

    def list_active_tasks(self, project_id: str) -> List[Dict[str, Any]]:
        """Return tasks that are still active or recoverable."""
        active_statuses = {
            "PENDING",
            "RUNNING",
            "PAUSED",
            "ERROR",
        }
        return [
            task
            for task in self.list_tasks(project_id)
            if task.get("status") in active_statuses
        ]

    def list_completed_tasks(self, project_id: str) -> List[Dict[str, Any]]:
        """Return completed tasks. Completed tasks remain locked."""
        return [
            task
            for task in self.list_tasks(project_id)
            if task.get("status") == "COMPLETE"
        ]

    def list_stopped_tasks(self, project_id: str) -> List[Dict[str, Any]]:
        """Return stopped tasks that may be resumed."""
        return [
            task
            for task in self.list_tasks(project_id)
            if task.get("status") == "STOPPED"
        ]

    def get_task_history(self, project_id: str) -> Dict[str, List[Dict[str, Any]]]:
        """Return task history grouped by lifecycle state."""
        tasks = self.list_tasks(project_id)

        return {
            "active": [
                task for task in tasks
                if task.get("status") in {
                    "PENDING",
                    "RUNNING",
                    "PAUSED",
                    "ERROR",
                }
            ],
            "stopped": [
                task for task in tasks
                if task.get("status") == "STOPPED"
            ],
            "completed": [
                task for task in tasks
                if task.get("status") == "COMPLETE"
            ],
        }

    def reopen_task(
        self,
        project_id: str,
        task_id: str,
    ) -> Optional[Dict[str, Any]]:
        """Reopen a recoverable task without creating a new history record."""
        task = self.load_task(project_id, task_id)

        if task is None:
            return None

        if task.get("status") == "COMPLETE":
            raise ValueError("Completed task is locked and cannot be reopened")

        if task.get("status") not in {
            "PAUSED",
            "STOPPED",
            "ERROR",
            "PENDING",
        }:
            raise ValueError(
                f"Task cannot be reopened from status: {task.get('status')}"
            )

        return self.update_task(
            project_id,
            task_id,
            status="PENDING",
        )
