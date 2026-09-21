from __future__ import annotations

from .parser import FailureParser
from .repair import RepairProposal
from .repair_executor import RepairExecutor
from .runner import TestRunner


class TestingLoop:
    """TEST -> ANALYZE -> REPAIR -> RETEST -> VERIFY."""

    def __init__(self, project_path, *, timeout=120, max_retries=2):
        self.runner = TestRunner(project_path, timeout=timeout)
        self.parser = FailureParser()
        self.repair_executor = RepairExecutor(project_path)
        self.max_retries = max(0, int(max_retries))

    def run_step(
        self,
        step: dict[str, object],
        *,
        repair_proposer=None,
        approved=False,
    ) -> dict[str, object]:
        history = []

        for attempt in range(self.max_retries + 1):
            result = self.runner.run(
                step["argv"],
                step_id=str(step.get("id", "unknown")),
            )

            history.append({
                "attempt": attempt + 1,
                "result": result,
            })

            if result["success"]:
                return {
                    "success": True,
                    "status": "verified",
                    "attempts": attempt + 1,
                    "history": history,
                }

            failure = self.parser.parse(result)
            history[-1]["failure"] = failure

            if repair_proposer is None:
                return {
                    "success": False,
                    "status": "failed",
                    "attempts": attempt + 1,
                    "failure": failure,
                    "history": history,
                }

            proposal = repair_proposer(
                step=step,
                result=result,
                failure=failure,
                attempt=attempt + 1,
            )

            if not isinstance(proposal, RepairProposal):
                return {
                    "success": False,
                    "status": "invalid_repair_proposal",
                    "attempts": attempt + 1,
                    "failure": failure,
                    "history": history,
                }

            repair_result = self.repair_executor.apply(
                proposal,
                approved=approved,
            )

            history[-1]["repair"] = repair_result

            if not repair_result["success"]:
                return {
                    "success": False,
                    "status": repair_result["status"],
                    "attempts": attempt + 1,
                    "failure": failure,
                    "history": history,
                }

        return {
            "success": False,
            "status": "max_retries_exceeded",
            "attempts": self.max_retries + 1,
            "history": history,
        }
