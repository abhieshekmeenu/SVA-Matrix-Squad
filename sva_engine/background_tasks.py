"""Background task registry for SVA Matrix Squad."""

from __future__ import annotations

import threading
from typing import Any, Dict


class BackgroundTaskManager:
    """Run PersistentAgent tasks in background threads and track them."""

    def __init__(self):
        self._lock = threading.RLock()
        self._threads: dict[str, threading.Thread] = {}

    def start(self, agent, project_id: str, task_id: str) -> Dict[str, Any]:
        key = f"{project_id}:{task_id}"

        with self._lock:
            thread = self._threads.get(key)

            if thread is not None and thread.is_alive():
                return {
                    "success": False,
                    "reason": "Task is already running in background",
                    "project_id": project_id,
                    "task_id": task_id,
                }

            thread = threading.Thread(
                target=self._worker,
                args=(agent, project_id, task_id, key),
                daemon=True,
                name=f"sva-task-{task_id}",
            )
            self._threads[key] = thread
            thread.start()

        return {
            "success": True,
            "status": "RUNNING",
            "project_id": project_id,
            "task_id": task_id,
            "background": True,
        }

    def _worker(self, agent, project_id: str, task_id: str, key: str) -> None:
        try:
            agent.run(project_id, task_id)
        finally:
            with self._lock:
                self._threads.pop(key, None)

    def is_running(self, project_id: str, task_id: str) -> bool:
        key = f"{project_id}:{task_id}"

        with self._lock:
            thread = self._threads.get(key)
            return thread is not None and thread.is_alive()

    def active(self) -> list[Dict[str, Any]]:
        with self._lock:
            active = []

            for key, thread in self._threads.items():
                if thread.is_alive():
                    project_id, task_id = key.split(":", 1)
                    active.append(
                        {
                            "project_id": project_id,
                            "task_id": task_id,
                            "status": "RUNNING",
                        }
                    )

            return active

    def wait(self, project_id: str, task_id: str, timeout: float | None = None) -> bool:
        key = f"{project_id}:{task_id}"

        with self._lock:
            thread = self._threads.get(key)

        if thread is None:
            return True

        thread.join(timeout)
        return not thread.is_alive()
