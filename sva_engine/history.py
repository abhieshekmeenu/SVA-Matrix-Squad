"""User-facing persistent project/task history."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from .progress import TaskProgress
from .task_store import TaskStore


class TaskHistory:
    """Expose compact history and detailed project/task inspection."""

    def __init__(self, store: Optional[TaskStore] = None):
        self.store = store or TaskStore()

    def all_history(self) -> Dict[str, List[Dict[str, Any]]]:
        """Return compact global project history.

        Only project identity is exposed here. Task details are available
        only after explicitly opening/checking a project.
        """
        projects = self.store.list_projects()

        return {
            "projects": [
                {
                    "project_id": project.get("project_id"),
                    "name": project.get("name") or project.get("project_id"),
                }
                for project in projects
            ]
        }

    def history(
        self,
        project_id: Optional[str] = None,
    ) -> Dict[str, List[Dict[str, Any]]]:
        """Return compact history.

        With no project_id, return the global project list.
        With project_id, preserve the older project-specific API.
        Neither form exposes task details.
        """
        if project_id is None:
            return self.all_history()

        project = self.store.load_project(project_id)

        if project is None:
            return {"projects": []}

        return {
            "projects": [
                {
                    "project_id": project.get("project_id", project_id),
                    "name": project.get("name") or project_id,
                }
            ]
        }

    def find_project(self, name_or_id: str) -> Optional[Dict[str, Any]]:
        """Find a project by exact ID or case-insensitive name."""
        if not isinstance(name_or_id, str) or not name_or_id.strip():
            return None

        target = name_or_id.strip()

        for project in self.store.list_projects():
            project_id = str(project.get("project_id", ""))
            name = str(project.get("name", ""))

            if target == project_id or target.lower() == name.lower():
                return project

        return None

    def task_status(
        self,
        project_id: str,
        task_id: str,
    ) -> Optional[Dict[str, Any]]:
        """Return full task details after explicit task inspection."""
        task = self.store.load_task(project_id, task_id)

        if task is None:
            return None

        return TaskProgress.summarize(task)

    def project_status(
        self,
        project_id: str,
    ) -> Optional[Dict[str, Any]]:
        """Return full project details after explicit project inspection."""
        project = self.store.load_project(project_id)

        if project is None:
            return None

        tasks = self.store.list_tasks(project_id)

        return TaskProgress.project_summary(
            project,
            tasks,
        )

    def open_project(
        self,
        project_id: str,
    ) -> Optional[Dict[str, Any]]:
        """Open a project and return its detailed current state."""
        return self.project_status(project_id)

    def check_project(
        self,
        project_id: str,
    ) -> Optional[Dict[str, Any]]:
        """Check a project and return its detailed current state."""
        return self.project_status(project_id)

# ============================================================
# USER HISTORY MANAGER
# ============================================================

import json
import re
import uuid
from datetime import datetime
from pathlib import Path


HISTORY_ROOT = Path.home() / ".sva_matrix_squad" / "history"


class HistoryManager:
    """Persistent user-facing history for chats and tasks."""

    def __init__(self, root: Optional[Path] = None):
        self.root = Path(root or HISTORY_ROOT)
        self.root.mkdir(parents=True, exist_ok=True)

    def _safe_id(self, value: str) -> str:
        return re.sub(
            r"[^a-zA-Z0-9_-]+",
            "_",
            str(value).strip(),
        ).strip("_") or uuid.uuid4().hex[:12]

    def _file(self, history_id: str) -> Path:
        return self.root / f"{self._safe_id(history_id)}.json"

    def automatic_title(self, text: str, fallback: str = "New Chat") -> str:
        """Create a short readable title from the first user input."""
        text = " ".join(str(text).split()).strip()

        if not text:
            return fallback

        words = text.split()
        title = " ".join(words[:8])

        if len(words) > 8:
            title += "..."

        return title[:80]

    def create(
        self,
        history_type: str,
        title: str = "",
        first_text: str = "",
        data: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Create a new independent history record."""

        history_id = f"{history_type}_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:8]}"

        if not title.strip():
            title = self.automatic_title(
                first_text,
                fallback="New Chat" if history_type == "chat" else "New Task",
            )

        record = {
            "history_id": history_id,
            "type": history_type,
            "title": title.strip(),
            "created_at": datetime.now().astimezone().isoformat(),
            "updated_at": datetime.now().astimezone().isoformat(),
            "data": data or {},
        }

        self.save(record)
        return record

    def save(self, record: Dict[str, Any]) -> Dict[str, Any]:
        """Save one history record."""

        record = dict(record)
        record["updated_at"] = datetime.now().astimezone().isoformat()

        path = self._file(record["history_id"])
        path.write_text(
            json.dumps(
                record,
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )

        try:
            path.chmod(0o600)
        except OSError:
            pass

        return record

    def load(self, history_id: str) -> Optional[Dict[str, Any]]:
        """Open one history record."""

        path = self._file(history_id)

        if not path.exists():
            return None

        try:
            data = json.loads(
                path.read_text(encoding="utf-8")
            )
        except (OSError, json.JSONDecodeError):
            return None

        return data if isinstance(data, dict) else None

    def list_history(
        self,
        history_type: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """List history, newest first."""

        records = []

        for path in self.root.glob("*.json"):
            try:
                data = json.loads(
                    path.read_text(encoding="utf-8")
                )
            except (OSError, json.JSONDecodeError):
                continue

            if not isinstance(data, dict):
                continue

            if (
                history_type
                and data.get("type") != history_type
            ):
                continue

            records.append(data)

        return sorted(
            records,
            key=lambda item: item.get("updated_at", ""),
            reverse=True,
        )

    def rename(
        self,
        history_id: str,
        new_title: str,
    ) -> Optional[Dict[str, Any]]:
        """Rename an existing history record."""

        record = self.load(history_id)

        if record is None:
            return None

        new_title = str(new_title).strip()

        if not new_title:
            raise ValueError("History title cannot be empty")

        record["title"] = new_title[:120]

        return self.save(record)

    def delete(self, history_id: str) -> bool:
        """Delete one history record."""

        path = self._file(history_id)

        if not path.exists():
            return False

        try:
            path.unlink()
            return True
        except OSError:
            return False

    def update_data(
        self,
        history_id: str,
        data: Dict[str, Any],
    ) -> Optional[Dict[str, Any]]:
        """Replace the stored data of an existing history."""

        record = self.load(history_id)

        if record is None:
            return None

        record["data"] = data

        return self.save(record)

    def append_message(
        self,
        history_id: str,
        role: str,
        content: str,
    ) -> Optional[Dict[str, Any]]:
        """Append a chat message to a chat history."""

        record = self.load(history_id)

        if record is None:
            return None

        messages = record.setdefault("data", {}).setdefault(
            "messages",
            [],
        )

        messages.append(
            {
                "role": role,
                "content": content,
                "timestamp": datetime.now().astimezone().isoformat(),
            }
        )

        return self.save(record)

    def touch(
        self,
        history_id: str,
    ) -> Optional[Dict[str, Any]]:
        """Update the last-used timestamp."""

        record = self.load(history_id)

        if record is None:
            return None

        return self.save(record)

