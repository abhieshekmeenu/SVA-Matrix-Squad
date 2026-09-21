from __future__ import annotations

from pathlib import Path
import shutil
import time

from .repair import RepairProposal


class RepairExecutor:
    """Apply validated repair proposals inside a project workspace."""

    ALLOWED_ACTIONS = {"write_file", "patch_file"}

    def __init__(self, project_path: str | Path):
        self.project_path = Path(project_path).expanduser().resolve()
        self.backup_dir = self.project_path / ".sva-backups"

    def _safe_path(self, value: str) -> Path:
        if not isinstance(value, str) or not value.strip():
            raise ValueError("Repair path is required")

        path = Path(value)

        if path.is_absolute() or ".." in path.parts:
            raise ValueError("Unsafe repair path")

        target = (self.project_path / path).resolve()

        if target != self.project_path and self.project_path not in target.parents:
            raise ValueError("Repair path escapes project workspace")

        return target

    def _backup(self, target: Path) -> str | None:
        if not target.exists():
            return None

        self.backup_dir.mkdir(mode=0o700, exist_ok=True)

        timestamp = time.strftime("%Y%m%d-%H%M%S")
        relative = target.relative_to(self.project_path)

        backup = (
            self.backup_dir
            / f"{timestamp}-{relative.name}.bak"
        )

        shutil.copy2(target, backup)
        return str(backup.relative_to(self.project_path))

    def apply(
        self,
        proposal: RepairProposal,
        *,
        approved: bool = False,
    ) -> dict[str, object]:
        if not isinstance(proposal, RepairProposal):
            raise TypeError("proposal must be a RepairProposal")

        validation = proposal.validate()

        if not validation["valid"]:
            return {
                "success": False,
                "status": "invalid",
                "errors": validation["errors"],
                "actions": [],
            }

        if proposal.requires_approval and not approved:
            return {
                "success": False,
                "status": "approval_required",
                "reason": "Repair proposal requires approval",
                "actions": [],
            }

        applied = []

        for action in proposal.actions:
            if action.action not in self.ALLOWED_ACTIONS:
                return {
                    "success": False,
                    "status": "blocked",
                    "reason": f"Unsupported repair action: {action.action}",
                    "actions": applied,
                }

            if not action.path:
                return {
                    "success": False,
                    "status": "invalid",
                    "reason": "Repair action path is required",
                    "actions": applied,
                }

            target = self._safe_path(action.path)

            if action.action == "patch_file":
                if not target.is_file():
                    return {
                        "success": False,
                        "status": "failed",
                        "reason": f"File does not exist: {action.path}",
                        "actions": applied,
                    }

                if action.old_text is None or action.new_text is None:
                    return {
                        "success": False,
                        "status": "invalid",
                        "reason": "patch_file requires old_text and new_text",
                        "actions": applied,
                    }

                original = target.read_text(encoding="utf-8")

                matches = original.count(action.old_text)

                if matches != 1:
                    return {
                        "success": False,
                        "status": "failed",
                        "reason": (
                            f"Expected exactly one patch match, "
                            f"found {matches}: {action.path}"
                        ),
                        "actions": applied,
                    }

                backup = self._backup(target)

                target.write_text(
                    original.replace(
                        action.old_text,
                        action.new_text,
                        1,
                    ),
                    encoding="utf-8",
                )

                applied.append({
                    "action": "patch_file",
                    "path": action.path,
                    "backup": backup,
                })

            elif action.action == "write_file":
                if action.content is None:
                    return {
                        "success": False,
                        "status": "invalid",
                        "reason": "write_file requires content",
                        "actions": applied,
                    }

                target.parent.mkdir(parents=True, exist_ok=True)

                backup = self._backup(target)

                target.write_text(
                    action.content,
                    encoding="utf-8",
                )

                applied.append({
                    "action": "write_file",
                    "path": action.path,
                    "backup": backup,
                })

        return {
            "success": True,
            "status": "applied",
            "actions": applied,
        }
