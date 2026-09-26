"""Persistent task agent for Termux-AI."""

from __future__ import annotations

from typing import Any, Dict, Optional

from .task_store import TaskStore


class PersistentAgent:
    """Run tasks with persistent checkpoints and optional AI error recovery."""

    def __init__(
        self,
        controller,
        store: Optional[TaskStore] = None,
        recovery_manager=None,
        executor=None,
        progress_callback=None,
    ):
        self.controller = controller
        self.store = store or TaskStore()
        self.recovery_manager = recovery_manager
        self.executor = executor
        self.progress_callback = progress_callback

    def _progress(self, event: str, **data) -> None:
        callback = self.progress_callback
        if callable(callback):
            try:
                callback(event, data)
            except Exception:
                # Progress reporting must never stop task execution.
                pass

    def _result_error(self, result: Dict[str, Any]) -> str:
        return (
            result.get("reason")
            or result.get("stderr")
            or "Task step failed"
        )

    def _set_project(self, project_id: str) -> None:
        setter = getattr(self.controller, "set_project", None)
        if callable(setter):
            setter(project_id)

    def _execute(self, command, task_id=None):
        """Execute a task action through the configured executor/controller."""
        previous_result = None

        if getattr(self, "_current_project_id", None):
            task = self.store.load_task(
                self._current_project_id,
                task_id,
            ) or {}
            results = task.get("results") or []
            if results:
                previous_result = results[-1]

        if isinstance(command, dict):
            if self.executor is not None:
                return self.executor.execute(
                    command,
                    task_id=task_id,
                    previous_result=previous_result,
                )

            # Structured actions must be normalized before reaching
            # controllers, which execute command strings.
            action = command.get("action")

            if action == "run":
                command_text = command.get("command")

                if not isinstance(command_text, str) or not command_text.strip():
                    return {
                        "success": False,
                        "returncode": 1,
                        "stdout": "",
                        "stderr": "Run action requires a valid command.",
                        "action": "run",
                    }

                try:
                    return self.controller.execute(
                        command_text,
                        task_id=task_id,
                        input_data=command.get("input"),
                    )
                except TypeError:
                    return self.controller.execute(
                        command_text,
                        task_id=task_id,
                    )

            return {
                "success": False,
                "returncode": 1,
                "stdout": "",
                "stderr": f"Unsupported structured action: {action}",
                "action": action,
            }

        try:
            return self.controller.execute(
                command,
                task_id=task_id,
            )
        except TypeError:
            # Preserve compatibility with simple test/fake controllers.
            return self.controller.execute(command)

    def _persist_recovery_error(
        self,
        project_id: str,
        task_id: str,
        *,
        current_step: int,
        total_steps: int,
        action: str,
        result: Dict[str, Any],
        error: str,
    ) -> None:
        task = self.store.load_task(project_id, task_id) or {}
        retry_count = int(task.get("retry_count") or 0) + 1

        self.store.update_task(
            project_id,
            task_id,
            retry_count=retry_count,
        )

        self.store.checkpoint(
            project_id,
            task_id,
            current_step=current_step,
            total_steps=total_steps,
            current_action=action,
            status="ERROR",
            last_output=result.get("stdout"),
            last_error=error,
            result=result,
        )

    def _recover_step(
        self,
        project_id: str,
        task_id: str,
        current_step: int,
        total_steps: int,
        action: str,
        result: Dict[str, Any],
    ) -> Optional[Dict[str, Any]]:
        """Try AI recovery for one failed step.

        Returns:
            None when no recovery manager is configured.
            A result dictionary describing recovery otherwise.
        """
        if self.recovery_manager is None:
            return None

        # Let the configured recovery manager decide whether it can
        # handle this action. TestRecoveryManager, for example, can
        # restrict recovery to test commands while other recovery
        # managers may support broader task actions.
        can_recover = getattr(
            self.recovery_manager,
            "can_recover",
            None,
        )

        if callable(can_recover):
            try:
                if not can_recover(action):
                    return None
            except Exception:
                return None

        proposal = self.recovery_manager.propose(
            action,
            result,
            task_id=task_id,
        )

        if not proposal.get("success", False):
            return {
                "success": False,
                "status": "ERROR",
                "reason": proposal.get("reason")
                or "AI recovery proposal failed",
                "proposal": proposal,
            }

        if proposal.get("approval_required"):
            pending = proposal.get("safety", {}).get("approval")

            self.store.update_task(
                project_id,
                task_id,
                status="PAUSED",
                pending_approval=pending,
                current_action=action,
                last_error=(
                    "BOSS approval required for AI recovery fix"
                ),
            )

            self.store.checkpoint(
                project_id,
                task_id,
                current_step=current_step,
                total_steps=total_steps,
                current_action=action,
                status="PAUSED",
                last_error=(
                    "BOSS approval required for AI recovery fix"
                ),
            )

            return {
                "success": False,
                "status": "PAUSED",
                "reason": "BOSS approval required",
                "approval": pending,
                "proposal": proposal,
                "task": self.store.load_task(project_id, task_id),
            }

        if proposal.get("execution_allowed") is not True:
            return {
                "success": False,
                "status": "ERROR",
                "reason": (
                    proposal.get("safety", {}).get("reason")
                    or "AI recovery fix blocked by safety policy"
                ),
                "proposal": proposal,
            }

        if proposal.get("retry") is not True:
            return {
                "success": False,
                "status": "ERROR",
                "reason": "AI did not approve retry",
                "proposal": proposal,
            }

        # Execute the proposed fix through the existing safe manager.
        fix_result = self.recovery_manager.retry(
            self.controller,
            proposal,
        )

        if not fix_result.get("success", False):
            fix_error = self._result_error(fix_result)

            self._persist_recovery_error(
                project_id,
                task_id,
                current_step=current_step,
                total_steps=total_steps,
                action=action,
                result=fix_result,
                error=fix_error,
            )

            return {
                "success": False,
                "status": "ERROR",
                "reason": "AI recovery fix failed",
                "fix_result": fix_result,
                "proposal": proposal,
                "task": self.store.load_task(project_id, task_id),
            }

        # The original step is recovered only after the fix succeeds.
        completed_step = current_step + 1

        self.store.checkpoint(
            project_id,
            task_id,
            current_step=completed_step,
            total_steps=total_steps,
            current_action=None,
            status=(
                "COMPLETE"
                if completed_step >= total_steps
                else "RUNNING"
            ),
            last_output=fix_result.get("stdout"),
            last_error=None,
            result={
                "recovery": True,
                "original_action": action,
                "proposal": proposal,
                "fix_result": fix_result,
            },
        )

        return {
            "success": True,
            "status": (
                "COMPLETE"
                if completed_step >= total_steps
                else "RUNNING"
            ),
            "recovered": True,
            "fix_result": fix_result,
            "proposal": proposal,
            "current_step": completed_step,
            "task": self.store.load_task(project_id, task_id),
        }

    def run(self, project_id: str, task_id: str) -> Dict[str, Any]:
        task = self.store.load_task(project_id, task_id)

        if task is None:
            return {
                "success": False,
                "reason": "Task not found",
            }

        if task.get("status") == "COMPLETE":
            return {
                "success": True,
                "status": "COMPLETE",
                "task": task,
                "reason": "Task already complete",
            }

        self._set_project(project_id)
        self._current_project_id = project_id

        steps = task.get("steps") or []
        total_steps = len(steps)

        task = self.store.update_task(
            project_id,
            task_id,
            total_steps=total_steps,
        )

        current_step = int(task.get("current_step", 0))

        self.store.update_task(
            project_id,
            task_id,
            status="RUNNING",
        )

        while current_step < total_steps:
            task = self.store.load_task(project_id, task_id)

            if task is None:
                return {
                    "success": False,
                    "reason": "Task disappeared while running",
                }

            status = task.get("status")

            if status == "STOPPED":
                return {
                    "success": False,
                    "status": "STOPPED",
                    "task": task,
                }

            if status == "PAUSED":
                return {
                    "success": False,
                    "status": "PAUSED",
                    "task": task,
                }

            current_step = int(task.get("current_step", current_step))

            if current_step >= total_steps:
                break

            action = steps[current_step]

            self._progress(
                "step_start",
                step=current_step + 1,
                total_steps=total_steps,
                action=action,
            )

            self.store.checkpoint(
                project_id,
                task_id,
                current_step=current_step,
                total_steps=total_steps,
                current_action=action,
                status="RUNNING",
            )

            self._progress(
                "executing",
                step=current_step + 1,
                total_steps=total_steps,
                action=action,
            )

            result = self._execute(action, task_id)
            success = bool(result.get("success", False))

            self._progress(
                "step_result",
                step=current_step + 1,
                total_steps=total_steps,
                action=action,
                success=success,
                result=result,
            )

            if success:
                completed_step = current_step + 1

                live_task = self.store.load_task(
                    project_id,
                    task_id,
                )
                requested_status = (live_task or {}).get("status")

                if requested_status in {"PAUSED", "STOPPED"}:
                    self.store.checkpoint(
                        project_id,
                        task_id,
                        current_step=completed_step,
                        total_steps=total_steps,
                        current_action=None,
                        status=requested_status,
                        last_output=result.get("stdout"),
                        last_error=None,
                        result=result,
                    )

                    return {
                        "success": True,
                        "status": requested_status,
                        "task": self.store.load_task(
                            project_id,
                            task_id,
                        ),
                        "result": result,
                    }

                self.store.checkpoint(
                    project_id,
                    task_id,
                    current_step=completed_step,
                    total_steps=total_steps,
                    current_action=None,
                    status=(
                        "COMPLETE"
                        if completed_step >= total_steps
                        else "RUNNING"
                    ),
                    last_output=result.get("stdout"),
                    last_error=None,
                    result=result,
                )

                current_step = completed_step
                continue

            error = self._result_error(result)

            self.store.checkpoint(
                project_id,
                task_id,
                current_step=current_step,
                total_steps=total_steps,
                current_action=action,
                status="ERROR",
                last_output=result.get("stdout"),
                last_error=error,
                result=result,
            )

            recovery = self._recover_step(
                project_id,
                task_id,
                current_step,
                total_steps,
                action,
                result,
            )

            if recovery is None:
                return {
                    "success": False,
                    "status": "ERROR",
                    "task": self.store.load_task(
                        project_id,
                        task_id,
                    ),
                    "result": result,
                }

            if recovery.get("success"):
                current_step = int(
                    recovery.get(
                        "current_step",
                        current_step + 1,
                    )
                )
                continue

            return recovery

        task = self.store.update_task(
            project_id,
            task_id,
            status="COMPLETE",
            current_step=total_steps,
            total_steps=total_steps,
            current_action=None,
            pending_approval=None,
            last_error=None,
        )

        return {
            "success": True,
            "status": "COMPLETE",
            "task": task,
        }

    def pause(self, project_id: str, task_id: str) -> Dict[str, Any]:
        task = self.store.load_task(project_id, task_id)

        if task is None:
            return {
                "success": False,
                "reason": "Task not found",
            }

        if task.get("status") == "COMPLETE":
            return {
                "success": False,
                "reason": "Completed task cannot be paused",
                "task": task,
            }

        task = self.store.update_task(
            project_id,
            task_id,
            status="PAUSED",
        )

        return {
            "success": True,
            "status": "PAUSED",
            "task": task,
        }

    def stop(self, project_id: str, task_id: str) -> Dict[str, Any]:
        task = self.store.load_task(project_id, task_id)

        if task is None:
            return {
                "success": False,
                "reason": "Task not found",
            }

        if task.get("status") == "COMPLETE":
            return {
                "success": False,
                "reason": "Completed task cannot be stopped",
                "task": task,
            }

        task = self.store.update_task(
            project_id,
            task_id,
            status="STOPPED",
        )

        return {
            "success": True,
            "status": "STOPPED",
            "task": task,
        }

    def approve_recovery(
        self,
        project_id: str,
        task_id: str,
        *,
        decided_by: str = "BOSS",
    ) -> Dict[str, Any]:
        """Approve and persistently execute a saved recovery action exactly once."""
        task = self.store.load_task(project_id, task_id)

        if task is None:
            return {
                "success": False,
                "reason": "Task not found",
            }

        if task.get("status") == "COMPLETE":
            return {
                "success": False,
                "reason": "Completed task is locked",
                "task": task,
            }

        approval = task.get("pending_approval")

        if not isinstance(approval, dict):
            return {
                "success": False,
                "reason": "No pending recovery approval",
                "task": task,
            }

        if approval.get("status") != "PENDING":
            return {
                "success": False,
                "reason": "Recovery approval is not pending",
                "task": task,
            }

        approval_manager = getattr(self.controller, "approval", None)

        if approval_manager is None:
            return {
                "success": False,
                "reason": "Controller approval manager is unavailable",
                "task": task,
            }

        decided = approval_manager.decide(
            approval,
            True,
            decided_by=decided_by,
        )

        # Persist the decision before execution so a process crash
        # cannot silently lose the BOSS decision.
        self.store.update_task(
            project_id,
            task_id,
            pending_approval=decided,
            status="PAUSED",
        )

        action = decided.get("action")
        if not isinstance(action, str) or not action.strip():
            return {
                "success": False,
                "reason": "Approved recovery action is invalid",
                "task": self.store.load_task(project_id, task_id),
            }

        self._set_project(project_id)

        try:
            result = self.controller.execute(
                action,
                task_id=task_id,
                approval_override=True,
            )
        except TypeError:
            result = self.controller.execute(action)

        if not result.get("success", False):
            error = self._result_error(result)

            self._persist_recovery_error(
                project_id,
                task_id,
                current_step=int(task.get("current_step", 0)),
                total_steps=int(task.get("total_steps") or len(task.get("steps") or [])),
                action=action,
                result=result,
                error=error,
            )

            return {
                "success": False,
                "status": "ERROR",
                "reason": "Approved recovery fix failed",
                "approval": decided,
                "result": result,
                "task": self.store.load_task(project_id, task_id),
            }

        current_step = int(task.get("current_step", 0))
        total_steps = int(task.get("total_steps") or len(task.get("steps") or []))
        completed_step = current_step + 1

        self.store.checkpoint(
            project_id,
            task_id,
            current_step=completed_step,
            total_steps=total_steps,
            current_action=None,
            status=(
                "COMPLETE"
                if completed_step >= total_steps
                else "RUNNING"
            ),
            last_output=result.get("stdout"),
            last_error=None,
            result={
                "recovery": True,
                "approved_by": decided_by,
                "approval": decided,
                "fix_result": result,
            },
        )

        self.store.update_task(
            project_id,
            task_id,
            pending_approval=None,
        )

        if completed_step >= total_steps:
            final_task = self.store.update_task(
                project_id,
                task_id,
                status="COMPLETE",
                current_step=total_steps,
                total_steps=total_steps,
                current_action=None,
                pending_approval=None,
                last_error=None,
            )

            return {
                "success": True,
                "status": "COMPLETE",
                "approved": True,
                "recovered": True,
                "approval": decided,
                "result": result,
                "task": final_task,
            }

        # Continue from the next step using the saved checkpoint.
        continuation = self.run(project_id, task_id)

        return {
            **continuation,
            "approved": True,
            "recovered": True,
            "approval": decided,
            "recovery_result": result,
        }

    def deny_recovery(
        self,
        project_id: str,
        task_id: str,
        *,
        decided_by: str = "BOSS",
    ) -> Dict[str, Any]:
        """Persist a BOSS denial without executing the risky recovery."""
        task = self.store.load_task(project_id, task_id)

        if task is None:
            return {
                "success": False,
                "reason": "Task not found",
            }

        approval = task.get("pending_approval")

        if not isinstance(approval, dict):
            return {
                "success": False,
                "reason": "No pending recovery approval",
                "task": task,
            }

        if approval.get("status") != "PENDING":
            return {
                "success": False,
                "reason": "Recovery approval is not pending",
                "task": task,
            }

        approval_manager = getattr(self.controller, "approval", None)

        if approval_manager is None:
            return {
                "success": False,
                "reason": "Controller approval manager is unavailable",
                "task": task,
            }

        decided = approval_manager.decide(
            approval,
            False,
            decided_by=decided_by,
        )

        task = self.store.update_task(
            project_id,
            task_id,
            pending_approval=decided,
            status="ERROR",
            last_error="BOSS denied the AI recovery fix",
        )

        return {
            "success": False,
            "status": "ERROR",
            "approved": False,
            "approval": decided,
            "task": task,
        }

    def auto_resume_if_available(
        self,
        project_id: str,
        task_id: str,
        *,
        provider_available: bool = False,
    ) -> Dict[str, Any]:
        """Resume a paused task when a provider becomes available.

        Automatic recovery is intentionally limited to PAUSED tasks.
        STOPPED and COMPLETE tasks require explicit control and are never
        automatically resumed.
        """
        task = self.store.load_task(project_id, task_id)

        if task is None:
            return {
                "success": False,
                "reason": "Task not found",
            }

        status = task.get("status")

        if status == "COMPLETE":
            return {
                "success": False,
                "status": "COMPLETE",
                "reason": "Completed task is locked",
                "task": task,
            }

        if status == "STOPPED":
            return {
                "success": False,
                "status": "STOPPED",
                "reason": "Stopped task requires explicit resume",
                "task": task,
            }

        if status != "PAUSED":
            return {
                "success": False,
                "status": status,
                "reason": "Task is not paused",
                "task": task,
            }

        if not provider_available:
            return {
                "success": False,
                "status": "PAUSED",
                "reason": "No provider is currently available",
                "task": task,
            }

        # Reuse the existing checkpoint-aware resume engine.
        return self.resume(project_id, task_id)

    def resume(self, project_id: str, task_id: str) -> Dict[str, Any]:
        task = self.store.load_task(project_id, task_id)

        if task is None:
            return {
                "success": False,
                "reason": "Task not found",
            }

        if task.get("status") == "COMPLETE":
            return {
                "success": False,
                "reason": "Completed task is locked",
                "task": task,
            }

        approval = task.get("pending_approval")

        # A pending approval must never cause the original risky action
        # to be executed again.
        if isinstance(approval, dict):
            approval_status = approval.get("status")

            if approval_status == "PENDING":
                return {
                    "success": False,
                    "status": "PAUSED",
                    "reason": "BOSS approval is still pending",
                    "approval": approval,
                    "task": task,
                }

            if approval_status == "APPROVED":
                return self.approve_recovery(
                    project_id,
                    task_id,
                    decided_by=approval.get("decided_by") or "BOSS",
                )

        task = self.store.update_task(
            project_id,
            task_id,
            status="RUNNING",
        )

        return self.run(project_id, task_id)
