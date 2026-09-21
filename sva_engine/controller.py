from __future__ import annotations

from pathlib import Path
import subprocess


class SVAController:
    """Safe project-scoped controller for SVA Task Agent."""

    def __init__(self, store):
        self.store = store
        self.project_id = None

    def set_project(self, project_id: str) -> None:
        self.project_id = project_id

    def _workspace(self) -> Path:
        if not self.project_id:
            raise RuntimeError("No project selected")
        return self.store.workspace_dir(self.project_id)

    def execute(self, command: str, task_id: str | None = None):
        workspace = self._workspace()

        result = subprocess.run(
            ["bash", "-lc", command],
            cwd=workspace,
            capture_output=True,
            text=True,
            timeout=120,
        )

        return {
            "success": result.returncode == 0,
            "returncode": result.returncode,
            "stdout": result.stdout,
            "stderr": result.stderr,
            "command": command,
        }
