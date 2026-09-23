from __future__ import annotations

from pathlib import Path
from typing import Any

from .verifier import SVAActionVerifier


class ActionExecutor:
    """Execute validated SVA task actions inside a project workspace."""

    ALLOWED_ACTIONS = {"write_file", "read_file", "run", "verify", "patch_file"}

    def __init__(self, controller):
        self.controller = controller
        self.verifier = SVAActionVerifier()

    def _safe_path(self, value: str) -> Path:
        if not isinstance(value, str) or not value.strip():
            raise ValueError("Path is required")

        path = Path(value)

        if path.is_absolute() or ".." in path.parts:
            raise ValueError("Unsafe path")

        workspace = self.controller._workspace().resolve()
        target = (workspace / path).resolve()

        if target != workspace and workspace not in target.parents:
            raise ValueError("Path escapes project workspace")

        return target

    def execute(self, action: dict[str, Any], task_id: str | None = None, previous_result=None):
        if not isinstance(action, dict):
            return {"success": False, "reason": "Action must be an object"}

        action_type = action.get("action")

        if action_type not in self.ALLOWED_ACTIONS:
            return {
                "success": False,
                "reason": f"Unsupported action: {action_type}",
            }

        try:
            if action_type == "write_file":
                path = self._safe_path(action.get("path"))
                content = action.get("content", "")

                if not isinstance(content, str):
                    return {
                        "success": False,
                        "reason": "File content must be a string",
                    }

                path.parent.mkdir(parents=True, exist_ok=True)

                # Keep a backup before replacing an existing file.
                if path.exists() and path.is_file():
                    workspace = self.controller._workspace().resolve()
                    backup_root = workspace / ".sva-backups"
                    relative = path.relative_to(workspace)
                    backup_path = backup_root / relative
                    backup_path.parent.mkdir(parents=True, exist_ok=True)
                    backup_path.write_bytes(path.read_bytes())

                path.write_text(content, encoding="utf-8")

                return {
                    "success": True,
                    "action": action_type,
                    "path": str(path),
                }

            if action_type == "patch_file":
                path = self._safe_path(action.get("path"))
                old = action.get("old")
                new = action.get("new", "")

                if not isinstance(old, str) or not old:
                    return {
                        "success": False,
                        "reason": "Patch old text is required",
                    }

                if not isinstance(new, str):
                    return {
                        "success": False,
                        "reason": "Patch new text must be a string",
                    }

                if not path.is_file():
                    return {
                        "success": False,
                        "reason": f"File not found: {action.get('path')}",
                    }

                content = path.read_text(encoding="utf-8")

                if content.count(old) != 1:
                    return {
                        "success": False,
                        "reason": "Patch target must match exactly once",
                    }

                workspace = self.controller._workspace().resolve()
                backup_path = (
                    workspace
                    / ".sva-backups"
                    / path.relative_to(workspace)
                )
                backup_path.parent.mkdir(parents=True, exist_ok=True)
                backup_path.write_bytes(path.read_bytes())

                path.write_text(
                    content.replace(old, new, 1),
                    encoding="utf-8",
                )

                return {
                    "success": True,
                    "action": action_type,
                    "path": str(path),
                }

            if action_type == "read_file":
                path = self._safe_path(action.get("path"))

                if not path.is_file():
                    return {
                        "success": False,
                        "reason": f"File not found: {action.get('path')}",
                    }

                return {
                    "success": True,
                    "action": action_type,
                    "path": str(path),
                    "content": path.read_text(encoding="utf-8"),
                }

            if action_type == "run":
                command = action.get("command")

                if not isinstance(command, str) or not command.strip():
                    return {
                        "success": False,
                        "reason": "Run command is required",
                    }

                command_input = action.get("input")

                result = self.controller.execute(
                    command,
                    task_id=task_id,
                    input_data=command_input,
                )

                if not isinstance(result, dict):
                    return {
                        "success": False,
                        "action": action_type,
                        "reason": "Controller returned an invalid result",
                    }

                result = dict(result)
                result.setdefault("action", action_type)
                result.setdefault("command", command.strip())
                result.setdefault("stdout", "")
                result.setdefault("stderr", "")
                result.setdefault("returncode", None)
                return result

            if action_type == "verify":
                expected = action.get("expect")

                if not isinstance(expected, str) or not expected.strip():
                    return {
                        "success": False,
                        "reason": "Verification expectation is required",
                    }

                result = self.verifier.verify(
                    expected,
                    previous_result,
                )
                result["action"] = action_type
                return result

        except (OSError, UnicodeError, ValueError) as exc:
            return {
                "success": False,
                "action": action_type,
                "reason": str(exc),
            }

        return {"success": False, "reason": "Action execution failed"}
