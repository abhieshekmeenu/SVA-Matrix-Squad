"""Safety-aware AI fix retry workflow."""

from __future__ import annotations

from typing import Any, Dict, Optional


class SafeFixRetryManager:
    """Route AI-generated fixes through the safety/approval boundary."""

    def __init__(self, fix_retry_manager, safety_guard):
        self.fix_retry_manager = fix_retry_manager
        self.safety_guard = safety_guard

    def propose(
        self,
        command: str,
        result: Dict[str, Any],
        *,
        task_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        proposal = self.fix_retry_manager.propose(command, result)

        if not proposal.get("success", False):
            return proposal

        fix = proposal.get("fix")

        guard = self.safety_guard.inspect(
            fix,
            task_id=task_id,
            reason=proposal.get("analysis")
            or "AI proposed a fix after command failure",
        )

        return {
            **proposal,
            "risk": guard.get("risk"),
            "execution_allowed": guard.get("execute", False),
            "approval_required": guard.get("approval_required", False)
            or guard.get("risk") == "APPROVAL_REQUIRED",
            "safety": guard,
        }

    def retry(
        self,
        controller,
        proposal: Dict[str, Any],
    ) -> Dict[str, Any]:
        if not proposal.get("success", False):
            return {
                "success": False,
                "reason": "Invalid fix proposal",
            }

        if proposal.get("execution_allowed") is not True:
            return {
                "success": False,
                "reason": (
                    "BOSS approval required before executing AI fix"
                    if proposal.get("approval_required")
                    else "AI fix blocked by safety policy"
                ),
                "approval": (
                    proposal.get("safety", {}).get("approval")
                ),
                "risk": proposal.get("risk"),
            }

        return self.fix_retry_manager.retry(
            controller,
            proposal,
        )
