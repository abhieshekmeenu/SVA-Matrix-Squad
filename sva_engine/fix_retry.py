"""Validated AI fix proposal and retry helper."""

from __future__ import annotations

from typing import Any, Dict


class FixRetryManager:
    """Turn a validated AI fix proposal into a retry action."""

    def __init__(self, error_fixer):
        self.error_fixer = error_fixer

    def propose(self, command: str, result: Dict[str, Any]) -> Dict[str, Any]:
        if not isinstance(command, str) or not command.strip():
            return {
                "success": False,
                "reason": "Command is required",
            }

        if not isinstance(result, dict):
            return {
                "success": False,
                "reason": "Execution result must be a dictionary",
            }

        error = result.get("stderr") or result.get("reason")

        if not isinstance(error, str) or not error.strip():
            return {
                "success": False,
                "reason": "No execution error available",
            }

        proposal = self.error_fixer.suggest_fix(
            command.strip(),
            error.strip(),
        )

        if not proposal.get("success", False):
            return {
                "success": False,
                "reason": proposal.get("reason") or "Unable to create fix proposal",
                "proposal": proposal,
            }

        fix = proposal.get("fix")

        if not isinstance(fix, str) or not fix.strip():
            return {
                "success": False,
                "reason": "AI returned an empty fix",
                "proposal": proposal,
            }

        return {
            "success": True,
            "original_command": command.strip(),
            "fix": fix.strip(),
            "retry": proposal.get("retry", False),
            "analysis": proposal.get("analysis", ""),
            "proposal": proposal,
        }

    def retry(self, controller, proposal: Dict[str, Any]) -> Dict[str, Any]:
        if not proposal.get("success", False):
            return {
                "success": False,
                "reason": "Invalid fix proposal",
            }

        if proposal.get("retry") is not True:
            return {
                "success": False,
                "reason": "AI did not approve retry",
                "proposal": proposal,
            }

        fix = proposal.get("fix")

        if not isinstance(fix, str) or not fix.strip():
            return {
                "success": False,
                "reason": "No executable fix available",
            }

        return controller.execute(fix.strip())
