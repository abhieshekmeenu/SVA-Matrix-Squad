#!/usr/bin/env python3
from __future__ import annotations

import json
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Any, Dict

from task_agent.context.context_manager import ProjectContextManager, CONTEXT_FILES
from task_agent.deployment.project_deployment import ProjectDeployment


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

    def save_state(self, state: Dict[str, Any]) -> None:
        self.state_dir.mkdir(parents=True, exist_ok=True)
        state["updated_at"] = datetime.now().isoformat()
        temp = self.state_file.with_suffix(".tmp")
        temp.write_text(
            json.dumps(state, indent=2, ensure_ascii=False),
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
        result = self.deployment.test()
        self.save_state({
            "project": str(self.project),
            "status": "TESTED",
            "phase": "TEST",
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
            "result": result_data,
        })
        return result_data

    def verify(self, test_result: Dict[str, Any] | None = None, run_result: Dict[str, Any] | None = None) -> Dict[str, Any]:
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

        verified = checks["project_exists"] and checks["context_available"]

        if test_result is not None:
            verified = verified and checks["tests_passed"]

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
