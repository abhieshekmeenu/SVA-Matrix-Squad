#!/usr/bin/env python3
from __future__ import annotations
import json
import os
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any

CONTEXT_FILES = {
    "prd.md": "# Product Requirements Document\n\n## Project\nUNKNOWN\n\n## Goal\nUNKNOWN\n\n## Requirements\n- TODO\n",
    "architecture.md": "# Architecture\n\n## Project Type\nUNKNOWN\n\n## Structure\nUNKNOWN\n\n## Components\n- TODO\n\n## Entry Point\nUNKNOWN\n",
    "rules.md": "# Project Rules\n\n## Allowed\n- Read project files\n- Analyze project structure\n- Run project tests\n- Run safe project commands\n- Modify files required by the approved task\n\n## Forbidden\n- Delete unrelated project data\n- Modify protected files without explicit permission\n- Invent missing requirements\n- Report success without verification\n\n## Protected Files\n- TODO\n\n## Testing Requirement\nAll changes must be tested and verified before completion.\n",
    "design.md": "# Design\n\n## UI / UX\nUNKNOWN\n\n## User Flow\nUNKNOWN\n\n## Technical Design\nUNKNOWN\n",
    "tasks.md": "# Tasks\n\n## Current Task\nNONE\n\n## Status\nNEW\n\n## Progress\n- [ ] Project context initialized\n- [ ] Project checked\n- [ ] Tests completed\n- [ ] Required fixes completed\n- [ ] Run completed\n- [ ] Verification completed\n\n## Errors\nNONE\n\n## Warnings\nNONE\n",
    "memory.md": "# Project Memory\n\n## Project History\n\n## Decisions\n\n## Previous Tasks\n\n## Errors and Fixes\n\n## Important Context\n",
}

class ProjectContextManager:
    def __init__(self, project_path: str | Path):
        self.project = Path(project_path).expanduser().resolve()
        self.context_dir = self.project
        self.state_dir = self.project / ".sva"
        self.state_file = self.state_dir / "context_state.json"

    def ensure_project(self) -> Dict[str, Any]:
        self.project.mkdir(parents=True, exist_ok=True)
        created = []
        existing = []
        for filename, template in CONTEXT_FILES.items():
            path = self.context_dir / filename
            if path.exists():
                existing.append(filename)
            else:
                path.write_text(template, encoding="utf-8")
                created.append(filename)
        self.state_dir.mkdir(parents=True, exist_ok=True)
        previous = {}
        if self.state_file.exists():
            try:
                loaded = json.loads(self.state_file.read_text(encoding="utf-8"))
                if isinstance(loaded, dict):
                    previous = loaded
            except (OSError, json.JSONDecodeError):
                previous = {}

        state = {
            **previous,
            "project": str(self.project),
            "initialized_at": previous.get("initialized_at", datetime.now().isoformat()),
            "context_files": list(CONTEXT_FILES),
            "created": created,
            "existing": existing,
            "updated_at": datetime.now().isoformat(),
        }
        self.state_file.write_text(json.dumps(state, indent=2), encoding="utf-8")
        return state

    def read_all(self) -> Dict[str, str]:
        data = {}
        for filename in CONTEXT_FILES:
            path = self.context_dir / filename
            if path.exists():
                data[filename] = path.read_text(encoding="utf-8", errors="replace")
        return data

    def write(self, filename: str, content: str) -> Path:
        if filename not in CONTEXT_FILES:
            raise ValueError(f"Invalid context file: {filename}")
        path = self.context_dir / filename
        path.write_text(content, encoding="utf-8")
        return path

    def update_tasks(self, task: str, status: str, progress: List[str] | None = None, errors: List[str] | None = None, warnings: List[str] | None = None) -> Path:
        content = [
            "# Tasks",
            "",
            "## Current Task",
            task or "NONE",
            "",
            "## Status",
            status,
            "",
            "## Progress",
        ]
        for item in progress or []:
            content.append(f"- {item}")
        content += [
            "",
            "## Errors",
            *(errors or ["NONE"]),
            "",
            "## Warnings",
            *(warnings or ["NONE"]),
            "",
        ]
        return self.write("tasks.md", "\n".join(content))

    def record_task_result(
        self,
        task: str,
        status: str,
        *,
        result: str = "",
        errors: List[str] | None = None,
        warnings: List[str] | None = None,
    ) -> Path:
        """Record the latest autonomous task result without inventing project facts."""
        progress = [
            "[x] Project context initialized",
            "[x] Project checked",
            "[x] Tests completed" if status == "COMPLETE" else "[ ] Tests completed",
            "[x] Required fixes completed" if status == "COMPLETE" else "[ ] Required fixes completed",
            "[x] Run completed" if status == "COMPLETE" else "[ ] Run completed",
            "[x] Verification completed" if status == "COMPLETE" else "[ ] Verification completed",
        ]

        return self.update_tasks(
            task,
            status,
            progress=progress,
            errors=errors or ["NONE"],
            warnings=warnings or ["NONE"],
        )

    def record_memory_result(
        self,
        task: str,
        status: str,
        result: str = "",
    ) -> Path:
        """Append a factual autonomous-task result to project memory."""
        content = (
            f"Task: {task}\n"
            f"Status: {status}\n"
            f"Result: {result or 'No result summary available.'}"
        )
        return self.append_memory("Autonomous Task Result", content)

    def append_memory(self, title: str, content: str) -> Path:
        path = self.context_dir / "memory.md"
        old = path.read_text(encoding="utf-8", errors="replace") if path.exists() else CONTEXT_FILES["memory.md"]
        entry = f"\n\n## {title}\n\n{content}\n"
        path.write_text(old.rstrip() + entry, encoding="utf-8")
        return path

    def summary(self) -> Dict[str, Any]:
        files = self.read_all()
        return {
            "project": str(self.project),
            "context_files": {
                name: {
                    "exists": (self.project / name).exists(),
                    "size": len(content),
                }
                for name, content in files.items()
            },
            "state_file": str(self.state_file),
        }

def initialize_project_context(project_path: str | Path) -> ProjectContextManager:
    manager = ProjectContextManager(project_path)
    manager.ensure_project()
    return manager

if __name__ == "__main__":
    import sys
    project = sys.argv[1] if len(sys.argv) > 1 else "."
    manager = initialize_project_context(project)
    print(json.dumps(manager.summary(), indent=2))
