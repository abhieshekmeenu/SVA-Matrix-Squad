"""Normal Chat command routing for projects and tasks."""

from __future__ import annotations

import re
from typing import Any, Dict, Optional

from .history import TaskHistory


class TaskCommandRouter:
    """Handle project/task commands before sending text to an AI provider."""

    def __init__(self, history: Optional[TaskHistory] = None):
        self.history = history or TaskHistory()

    def handle(self, prompt: str) -> Optional[Dict[str, Any]]:
        if not isinstance(prompt, str) or not prompt.strip():
            return None

        text = prompt.strip()
        lower = text.lower()

        if lower in {"history", "project history", "projects history"}:
            return {
                "success": True,
                "intent": "history",
                "response": self._format_history(),
            }

        match = re.match(
            r"^(?:open|check|inspect)\s+(.+?)(?:\s+folder)?$",
            text,
            re.IGNORECASE,
        )
        if match:
            project_name = match.group(1).strip()
            return self._open_or_check(project_name)

        match = re.match(
            r"^(.+?)\s+(?:open|check|inspect)(?:\s+folder)?$",
            text,
            re.IGNORECASE,
        )
        if match:
            project_name = match.group(1).strip()
            return self._open_or_check(project_name)

        # Hindi project commands.
        match = re.match(
            r"^(.+?)\s+(?:खोलो|खोलें|चेक\s+करो|चेक\s+करें|जाँच\s+करो|जांच\s+करो|निरीक्षण\s+करो|निरीक्षण\s+करें)$",
            text,
        )
        if match:
            project_name = match.group(1).strip()
            return self._open_or_check(project_name)

        match = re.match(
            r"^(?:खोलो|खोलें|चेक\s+करो|चेक\s+करें|जाँच\s+करो|जांच\s+करो|निरीक्षण\s+करो|निरीक्षण\s+करें)\s+(.+)$",
            text,
        )
        if match:
            project_name = match.group(1).strip()
            return self._open_or_check(project_name)

        return None

    def _format_history(self) -> str:
        listing = self.history.all_history()
        projects = listing.get("projects", [])

        if not projects:
            return "PROJECT HISTORY\n\nNo projects found."

        lines = ["PROJECT HISTORY", ""]
        for index, project in enumerate(projects, 1):
            lines.append(f"{index}. {project['name']}")

        return "\n".join(lines)

    def _open_or_check(self, project_name: str) -> Dict[str, Any]:
        project = self.history.find_project(project_name)

        if project is None:
            return {
                "success": False,
                "intent": "project",
                "reason": f"Project not found: {project_name}",
                "response": f"Project not found: {project_name}",
            }

        project_id = project["project_id"]
        details = self.history.check_project(project_id)

        return {
            "success": True,
            "intent": "project",
            "project": details,
            "response": self._format_project(details),
        }

    @staticmethod
    def _format_project(project: Dict[str, Any]) -> str:
        lines = [
            f"PROJECT: {project.get('name')}",
            f"Status: {project.get('status')}",
            f"Tasks: {project.get('task_count', 0)}",
            f"Completed: {project.get('completed_tasks', 0)}",
            f"Running: {project.get('running_tasks', 0)}",
            f"Paused: {project.get('paused_tasks', 0)}",
            f"Errors: {project.get('error_tasks', 0)}",
        ]

        folder = project.get("folder")
        if folder:
            lines.extend([
                f"Folder: {'✓ Found' if folder.get('exists') else '✗ Missing'}",
                f"Files: {folder.get('file_count', 0)}",
            ])

        tasks = project.get("tasks", [])
        if tasks:
            lines.append("")
            lines.append("TASKS:")
            for task in tasks:
                lines.append(
                    f"- {task.get('description') or task.get('task_id')}: "
                    f"{task.get('status')} "
                    f"({task.get('progress_percent', 0)}%)"
                )

        return "\n".join(lines)
