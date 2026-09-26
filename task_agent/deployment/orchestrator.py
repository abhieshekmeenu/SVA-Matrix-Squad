#!/usr/bin/env python3
from __future__ import annotations

import json
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Any, Dict

from task_agent.context.context_manager import ProjectContextManager, CONTEXT_FILES
from task_agent.deployment.project_deployment import ProjectDeployment
from sva_engine.project_checker import ProjectChecker
from sva_engine.testing.planner import TestPlanner
from sva_engine.testing.loop import TestingLoop
from sva_engine.planner import AIPlanner
from sva_engine.action_executor import ActionExecutor


class DeploymentOrchestrator:
    """
    Unified SVA Task Agent deployment controller.

    Flow:
        PROJECT
          ↓
        CONTEXT
          ↓
        CHECK
          ↓
        TEST
          ↓
        FIND & FIX
          ↓
        RUN
          ↓
        VERIFY
          ↓
        STATUS

    Existing SVA testing/repair modules remain independent and can be
    connected by higher-level Task Agent logic without replacing them.
    """

    def __init__(self, project_path: str | Path):
        self.project = Path(project_path).expanduser().resolve()
        self.context = ProjectContextManager(self.project)
        self.deployment = ProjectDeployment(self.project)
        self.state_dir = self.project / ".sva"
        self.state_file = self.state_dir / "deployment_state.json"

    def load_state(self) -> Dict[str, Any]:
        if not self.state_file.exists():
            return {}

        try:
            data = json.loads(
                self.state_file.read_text(
                    encoding="utf-8",
                    errors="ignore",
                )
            )
            return data if isinstance(data, dict) else {}
        except (OSError, json.JSONDecodeError):
            return {}

    def save_state(self, state: Dict[str, Any]) -> None:
        self.state_dir.mkdir(parents=True, exist_ok=True)

        existing: Dict[str, Any] = {}

        if self.state_file.exists():
            try:
                loaded = json.loads(
                    self.state_file.read_text(
                        encoding="utf-8",
                        errors="ignore",
                    )
                )
                if isinstance(loaded, dict):
                    existing = loaded
            except (OSError, json.JSONDecodeError):
                existing = {}

        existing.update(state)
        existing["updated_at"] = datetime.now().isoformat()

        temp = self.state_file.with_suffix(".tmp")
        temp.write_text(
            json.dumps(existing, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        temp.replace(self.state_file)

    def initialize(self) -> Dict[str, Any]:
        context_state = self.context.ensure_project()
        state = {
            "project": str(self.project),
            "status": "INITIALIZED",
            "phase": "CONTEXT",
            "context": context_state,
            "history": [],
        }
        self.save_state(state)
        return state

    def check(self) -> Dict[str, Any]:
        self.save_state({
            "project": str(self.project),
            "status": "CHECKING",
            "phase": "CHECK",
        })
        result = self.deployment.check()
        self.save_state({
            "project": str(self.project),
            "status": "CHECKED",
            "phase": "CHECK",
            "result": result,
        })
        return result

    def test(self) -> Dict[str, Any]:
        self.save_state({
            "project": str(self.project),
            "status": "TESTING",
            "phase": "TEST",
        })

        tests_dir = self.project / "tests"
        pytest_config = any(
            (self.project / name).exists()
            for name in (
                "pytest.ini",
                "pyproject.toml",
                "setup.cfg",
                "tox.ini",
            )
        )

        if tests_dir.is_dir() or pytest_config:
            result = self.run("python -m pytest -q")
        else:
            result = self.deployment.test()

        if result.get("success"):
            result["status"] = "TEST_PASSED"
        else:
            result["status"] = "TEST_FAILED"

        self.save_state({
            "project": str(self.project),
            "status": "TESTED",
            "phase": "TEST",
            "test": result,
            "result": result,
        })
        return result

    def run(self, command: str) -> Dict[str, Any]:
        if not command or not command.strip():
            return {
                "success": False,
                "error": "No run command supplied.",
            }

        self.save_state({
            "project": str(self.project),
            "status": "RUNNING",
            "phase": "RUN",
            "command": command,
        })

        try:
            result = subprocess.run(
                command,
                shell=True,
                cwd=str(self.project),
                text=True,
                capture_output=True,
                timeout=120,
            )
            result_data = {
                "success": result.returncode == 0,
                "returncode": result.returncode,
                "stdout": result.stdout,
                "stderr": result.stderr,
                "command": command,
            }
        except subprocess.TimeoutExpired:
            result_data = {
                "success": False,
                "returncode": 124,
                "stdout": "",
                "stderr": "RUN COMMAND TIMEOUT",
                "command": command,
            }
        except Exception as exc:
            result_data = {
                "success": False,
                "returncode": 1,
                "stdout": "",
                "stderr": repr(exc),
                "command": command,
            }

        self.save_state({
            "project": str(self.project),
            "status": "RUN_COMPLETE" if result_data["success"] else "RUN_FAILED",
            "phase": "RUN",
            "run": result_data,
            "result": result_data,
        })
        return result_data

    def verify(self, test_result: Dict[str, Any] | None = None, run_result: Dict[str, Any] | None = None) -> Dict[str, Any]:
        state = self.load_state()
        saved_test = state.get("test")
        saved_run = state.get("run")

        if test_result is None and isinstance(saved_test, dict):
            test_result = saved_test

        if run_result is None and isinstance(saved_run, dict):
            run_result = saved_run

        checks = {
            "project_exists": self.project.exists(),
            "context_available": all(
                (self.project / filename).exists()
                for filename in CONTEXT_FILES
            ),
            "tests_passed": (
                test_result.get("success", False)
                if test_result is not None
                else False
            ),
            "run_passed": (
                run_result.get("success", False)
                if run_result is not None
                else None
            ),
        }

        verified = (
            checks["project_exists"]
            and checks["context_available"]
            and checks["tests_passed"]
        )

        if run_result is not None:
            verified = verified and checks["run_passed"]

        result = {
            "success": verified,
            "verified": verified,
            "checks": checks,
            "timestamp": datetime.now().isoformat(),
        }

        self.save_state({
            "project": str(self.project),
            "status": "VERIFIED" if verified else "VERIFICATION_FAILED",
            "phase": "VERIFY",
            "result": result,
        })
        return result

    def autonomous_plan(self, ai_client=None, task: str | None = None) -> Dict[str, Any]:
        """Build a safe autonomous execution plan without executing actions."""
        if ai_client is None:
            return {
                "success": False,
                "phase": "PLAN",
                "error": "AI client is required.",
            }

        scan = ProjectDeployment(self.project).scan()
        context = self.context.read_all()

        detection = ProjectChecker(self.project).check()
        languages = sorted({
            result.get("language")
            for result in detection.get("results", [])
            if isinstance(result, dict) and result.get("language")
        })

        detection = {
            **detection,
            "languages": languages,
        }

        test_plan = TestPlanner(self.project).plan(detection)

        requested_task = (
            task.strip()
            if isinstance(task, str) and task.strip()
            else "Inspect the current project and prepare a safe execution plan."
        )

        planning_context = (
            f"PROJECT SCAN:\\n{scan}\\n\\n"
            f"PROJECT CONTEXT:\\n{context}\\n\\n"
            f"TEST PLAN:\\n{test_plan}\\n\\n"
            "Rules:\\n"
            "- Inspect before modifying.\\n"
            "- Do not delete unrelated data.\\n"
            "- Do not install packages or modify the system.\\n"
            "- Use only safe project actions.\\n"
            "- Prefer patch_file for targeted changes.\\n"
            "- Include verification after important work.\\n"
            "- Return only the structured action plan."
        )

        planner = AIPlanner(ai_client)
        plan = planner.plan(
            requested_task,
            context=planning_context,
        )

        result = {
            "success": bool(plan),
            "phase": "PLAN",
            "scan": scan,
            "context": context,
            "detection": detection,
            "test_plan": test_plan,
            "plan": plan,
        }

        self.save_state({
            "project": str(self.project),
            "status": "PLANNED" if result["success"] else "PLAN_FAILED",
            "phase": "PLAN",
            "result": result,
        })

        return result

    def status(self) -> Dict[str, Any]:
        status = self.deployment.status()
        status["state_file"] = str(self.state_file)
        status["context_ready"] = all(
            (self.project / filename).exists()
            for filename in CONTEXT_FILES
        )
        status["testing_engine"] = (
            (self.project / "sva_engine" / "testing").is_dir()
        )
        status["task_agent"] = True
        return status

    def autonomous_execute(
        self,
        task: str,
        ai_client=None,
        task_id: str | None = None,
    ) -> Dict[str, Any]:
        """Plan and safely execute an autonomous project task."""

        if not isinstance(task, str) or not task.strip():
            return {
                "success": False,
                "phase": "PLAN",
                "error": "Task is required.",
                "steps": [],
            }

        if ai_client is None:
            return {
                "success": False,
                "phase": "PLAN",
                "error": "AI client is required.",
                "steps": [],
            }

        from sva_engine.action_executor import ActionExecutor
        from sva_engine.controller import SVAController
        from sva_engine.planner import AIPlanner
        from sva_engine.task_store import TaskStore

        plan_result = self.autonomous_plan(ai_client=ai_client, task=task)

        if not plan_result.get("success"):
            return {
                **plan_result,
                "phase": "PLAN",
                "executed_steps": [],
            }

        plan = plan_result.get("plan")

        if not isinstance(plan, dict):
            return {
                **plan_result,
                "success": False,
                "phase": "PLAN",
                "error": "Planner returned an invalid plan.",
                "executed_steps": [],
            }

        steps = plan.get("steps")

        if not isinstance(steps, list) or not steps:
            return {
                **plan_result,
                "success": False,
                "phase": "PLAN",
                "error": "Planner returned no executable steps.",
                "executed_steps": [],
            }

        store = TaskStore()
        project_id = f"sva-autonomous-{self.project.name.lower()}"

        existing_project = store.load_project(project_id)

        if existing_project is None:
            store.create_project(
                project_id=project_id,
                name=self.project.name,
                description="Autonomous SVA Task Agent project",
                workspace=self.project,
            )

        controller = SVAController(store)
        controller.set_project(project_id)
        executor = ActionExecutor(controller)

        if task_id is None:
            task_id = "autonomous-task"

        executed_steps = []

        for index, action in enumerate(steps, start=1):
            if not isinstance(action, dict):
                result = {
                    "success": False,
                    "reason": f"Step {index} is not an action object.",
                }
            else:
                result = executor.execute(
                    action,
                    task_id=task_id,
                    previous_result=(
                        executed_steps[-1]["result"]
                        if executed_steps
                        else None
                    ),
                )

            executed_steps.append({
                "index": index,
                "action": action,
                "result": result,
            })

            if not result.get("success", False):
                action_command = ""
                if isinstance(action, dict):
                    action_command = str(
                        action.get("command") or ""
                    ).strip()

                recoverable_test = (
                    isinstance(action, dict)
                    and action.get("action") == "run"
                    and any(
                        token in action_command.lower()
                        for token in ("pytest", "unittest", "test")
                    )
                )

                if recoverable_test:
                    break

                final = {
                    **plan_result,
                    "success": False,
                    "phase": "WORK",
                    "task": task,
                    "task_id": task_id,
                    "project_id": project_id,
                    "executed_steps": executed_steps,
                    "failed_step": index,
                    "error": result.get("reason", "Action failed"),
                }

                self.save_state({
                    "project": str(self.project),
                    "status": "WORK_FAILED",
                    "phase": "WORK",
                    "result": final,
                })

                return final

        # TEST -> VERIFY
        detection = ProjectChecker(self.project).check()

        languages = sorted({
            result.get("language")
            for result in detection.get("results", [])
            if isinstance(result, dict) and result.get("language")
        })

        detection = {
            **detection,
            "languages": languages,
        }

        test_plan = TestPlanner(self.project).plan(detection)
        testing_loop = TestingLoop(self.project)

        recovery_manager = None

        if ai_client is not None:
            try:
                from sva_engine.ai_error_fixer import AIErrorFixer
                from sva_engine.testing.recovery import TestRecoveryManager

                recovery_manager = TestRecoveryManager(
                    self.project,
                    AIErrorFixer(ai_client, repair_retries=1),
                    timeout=120,
                    max_retries=2,
                )
            except Exception as exc:
                self.save_state({
                    "project": str(self.project),
                    "status": "RECOVERY_UNAVAILABLE",
                    "phase": "TEST",
                    "error": str(exc),
                })

        test_results = []

        for test_step in test_plan.get("steps", []):
            test_result = testing_loop.run_step(test_step)

            if (
                not test_result.get("success", False)
                and recovery_manager is not None
            ):
                recovery_action = {
                    "action": "run",
                    "argv": test_step.get("argv", []),
                }

                recovery_result = recovery_manager.propose(
                    recovery_action,
                    test_result,
                    task_id=task_id,
                )

                if recovery_result.get("success", False):
                    retry_result = recovery_manager.retry(
                        None,
                        recovery_result,
                    )

                    if retry_result.get("success", False):
                        test_result = {
                            **retry_result,
                            "recovered": True,
                        }
                    else:
                        test_result = {
                            **test_result,
                            "recovery": recovery_result,
                            "retry": retry_result,
                        }
                else:
                    test_result = {
                        **test_result,
                        "recovery": recovery_result,
                    }

            test_results.append({
                "step": test_step,
                "result": test_result,
            })

            if not test_result.get("success", False):
                final = {
                    **plan_result,
                    "success": False,
                    "phase": "TEST",
                    "task": task,
                    "task_id": task_id,
                    "project_id": project_id,
                    "executed_steps": executed_steps,
                    "test_results": test_results,
                    "failed_test": test_step.get("id"),
                    "error": test_result.get(
                        "status",
                        "Test failed",
                    ),
                }

                self.save_state({
                    "project": str(self.project),
                    "status": "TEST_FAILED",
                    "phase": "TEST",
                    "result": final,
                })

                return final

        final = {
            **plan_result,
            "success": True,
            "phase": "VERIFY",
            "task": task,
            "task_id": task_id,
            "project_id": project_id,
            "executed_steps": executed_steps,
            "test_results": test_results,
        }

        self.save_state({
            "project": str(self.project),
            "status": "VERIFIED",
            "phase": "VERIFY",
            "result": final,
        })

        return final

    def full_check(self) -> Dict[str, Any]:
        initialized = self.initialize()
        check_result = self.check()
        test_result = self.test()

        verification = self.verify(
            test_result=test_result,
            run_result=None,
        )

        final_status = self.status()

        result = {
            "success": verification["success"],
            "initialized": initialized,
            "check": check_result,
            "test": test_result,
            "verification": verification,
            "status": final_status,
        }

        self.save_state({
            "project": str(self.project),
            "status": "READY" if result["success"] else "REVIEW_REQUIRED",
            "phase": "STATUS",
            "result": result,
        })

        return result


def main() -> None:
    import sys

    project = (
        Path(sys.argv[1]).expanduser()
        if len(sys.argv) > 1
        else Path.cwd()
    )

    agent = DeploymentOrchestrator(project)

    print("\n╭──────────────────────────────────────────────────────────╮")
    print("│ 🚀 SVA MATRIX — UNIFIED TASK AGENT DEPLOYMENT            │")
    print("├──────────────────────────────────────────────────────────┤")
    print(f"│ 📁 Project : {agent.project}")
    print("│ 🧠 Context → Check → Test → Verify → Status")
    print("╰──────────────────────────────────────────────────────────╯")

    result = agent.full_check()

    status = result.get("status", {})
    check = result.get("check", {})
    test = result.get("test", {})
    verification = result.get("verification", {})

    print("\n📊 PROJECT STATUS")
    print(f"Name          : {status.get('project')}")
    print(f"Type          : {status.get('type')}")
    print(f"Git           : {status.get('git')}")
    print(f"Branch        : {status.get('branch')}")
    print(f"Files         : {status.get('files')}")
    print(f"Source Files  : {status.get('source_files')}")
    print(f"Test Files    : {status.get('test_files')}")
    print(f"Context       : {'READY' if status.get('context_ready') else 'MISSING'}")
    print(f"Testing Engine: {'FOUND' if status.get('testing_engine') else 'MISSING'}")
    print(f"Check         : {'PASS' if check.get('success') else 'FAIL'}")
    print(f"Test          : {test.get('status', 'UNKNOWN')}")
    print(f"Verify        : {'PASS' if verification.get('verified') else 'FAIL'}")
    print(f"Final         : {'READY' if result.get('success') else 'REVIEW REQUIRED'}")


if __name__ == "__main__":
    main()
