from __future__ import annotations

import shlex
from typing import Any

from .loop import TestingLoop
from .repair import RepairProposal, proposal_from_dict


class TestRecoveryManager:
    """Bridge PersistentAgent recovery with the existing test repair engine."""

    def __init__(
        self,
        project_path,
        ai_fixer,
        *,
        timeout=120,
        max_retries=2,
        approval_callback=None,
    ):
        self.ai_fixer = ai_fixer
        self.loop = TestingLoop(
            project_path,
            timeout=timeout,
            max_retries=max_retries,
        )
        self.approval_callback = approval_callback
        self._pending: dict[str, Any] = {}

    @staticmethod
    def _command(action: Any) -> str:
        if isinstance(action, dict):
            command = action.get("command")
            if isinstance(command, str) and command.strip():
                return command.strip()

            argv = action.get("argv")
            if isinstance(argv, list) and argv:
                return shlex.join(str(item) for item in argv)

        if isinstance(action, str) and action.strip():
            return action.strip()

        return ""

    @classmethod
    def can_recover(cls, action: Any) -> bool:
        """Return True only for test-related commands."""
        command = cls._command(action)
        if not command:
            return False

        lowered = command.lower()
        return any(
            token in lowered
            for token in ("pytest", "unittest", "test")
        )

    @staticmethod
    def _argv(command: str) -> list[str]:
        argv = shlex.split(command)

        # Planner-generated pytest commands may contain shell redirection.
        # TestRunner uses subprocess argv, so remove standalone redirects.
        return [
            item for item in argv
            if item not in {"2>&1", "1>&2"}
        ]

    def propose(
        self,
        action,
        result,
        *,
        task_id=None,
    ) -> dict[str, object]:
        command = self._command(action)

        if not command:
            return {
                "success": False,
                "reason": "Test recovery requires a test command",
            }

        error = "\n".join(
            part
            for part in (
                str(result.get("stderr") or ""),
                str(result.get("stdout") or ""),
                str(result.get("error") or ""),
            )
            if part
        ).strip()

        if not error:
            error = "Test command failed without diagnostic output."

        failure = self.loop.parser.parse(result)

        try:
            proposal = self.ai_fixer.propose_repair(
                command,
                error,
                failure,
            )
        except Exception as exc:
            return {
                "success": False,
                "reason": f"AI repair analysis failed: {exc}",
            }

        if not isinstance(proposal, RepairProposal):
            return {
                "success": False,
                "reason": "AI did not return a valid repair proposal",
            }

        if not proposal.actions:
            return {
                "success": False,
                "reason": "AI could not determine a safe file repair",
                "proposal": proposal.to_dict(),
            }

        approved = False

        if self.approval_callback is not None:
            try:
                approved = bool(self.approval_callback(proposal))
            except Exception as exc:
                return {
                    "success": False,
                    "reason": f"Repair approval failed: {exc}",
                }

        if proposal.requires_approval and not approved:
            return {
                "success": False,
                "status": "PAUSED",
                "reason": "BOSS approval required",
                "approval_required": True,
                "execution_allowed": False,
                "retry": False,
                "safety": {
                    "approval": proposal.to_dict(),
                },
                "proposal": proposal.to_dict(),
            }

        self._pending[str(task_id or "unknown")] = {
            "proposal": proposal,
            "command": command,
            "argv": self._argv(command),
        }

        return {
            "success": True,
            "approval_required": False,
            "execution_allowed": True,
            "retry": True,
            "task_id": str(task_id or "unknown"),
            "safety": {
                "approved": True,
            },
            # TaskStore persists recovery results as JSON, so never expose
            # the live RepairProposal object outside this manager.
            "proposal": proposal.to_dict(),
        }

    def retry(self, controller, proposal) -> dict[str, object]:
        # PersistentAgent passes the complete recovery result. The actual
        # RepairProposal is nested under the "proposal" field.
        recovery_result = proposal

        task_key = None

        if isinstance(proposal, dict):
            task_key = str(proposal.get("task_id") or "")

            nested = proposal.get("proposal")
            if nested is not None:
                proposal = nested

        if isinstance(proposal, dict):
            try:
                proposal = proposal_from_dict(proposal)
            except Exception as exc:
                return {
                    "success": False,
                    "status": "failed",
                    "reason": f"Invalid recovery proposal: {exc}",
                }

        if task_key and task_key in self._pending:
            pending = self._pending.pop(task_key)
        else:
            pending = None
            for key, candidate in self._pending.items():
                if candidate.get("proposal") is proposal:
                    task_key = key
                    pending = self._pending.pop(key)
                    break

        if pending is None and len(self._pending) == 1:
            task_key, pending = next(iter(self._pending.items()))
            self._pending.pop(task_key)

        if pending is None:
            return {
                "success": False,
                "status": "failed",
                "reason": "Recovery proposal is not pending",
            }

        repair = pending["proposal"]

        repair_result = self.loop.repair_executor.apply(
            repair,
            approved=True,
        )

        if not repair_result.get("success"):
            return {
                "success": False,
                "status": repair_result.get("status", "failed"),
                "reason": repair_result.get(
                    "reason",
                    "Repair could not be applied",
                ),
                "repair": repair_result,
            }

        retest = self.loop.runner.run(
            pending["argv"],
            step_id=f"recovery:{task_key}",
        )

        return {
            "success": bool(retest.get("success")),
            "status": (
                "verified"
                if retest.get("success")
                else "retest_failed"
            ),
            "repair": repair_result,
            "retest": retest,
            "stdout": retest.get("stdout", ""),
            "stderr": retest.get("stderr", ""),
            "returncode": retest.get("returncode"),
        }
