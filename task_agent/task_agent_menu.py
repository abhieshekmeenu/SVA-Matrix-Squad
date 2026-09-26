#!/usr/bin/env python3
from __future__ import annotations

"""
SVA MATRIX — TASK AGENT MENU

This module is the user-facing controller for menu option [7].

Design:
    [7] TASK AGENT
        ├── PROJECT DEPLOYMENT
        │   ├── Project Folder
        │   ├── Check
        │   ├── Test
        │   ├── Find & Fix
        │   ├── Run
        │   ├── Verify
        │   └── Status
        ├── PROJECT CONTEXT
        │   ├── PRD
        │   ├── Architecture
        │   ├── Rules
        │   ├── Design
        │   ├── Tasks
        │   └── Memory
        ├── AI
        ├── PROJECT STATUS
        └── PROJECT MANAGEMENT

The menu is intentionally separated from the existing SVA Matrix
main menu so the Task Agent can grow without damaging options [1]-[6].
"""

import json
import os
import subprocess
from pathlib import Path
from typing import Optional

from task_agent.context.context_manager import (
    ProjectContextManager,
    CONTEXT_FILES,
)
from task_agent.deployment.orchestrator import DeploymentOrchestrator
from sva_engine.planner import AIPlanner
from sva_engine.task_store import TaskStore
from sva_engine.controller import SVAController
from sva_engine.action_executor import ActionExecutor
from sva_engine.agent import PersistentAgent


class TaskAgentMenu:
    def __init__(self, ai_client=None):
        self.ai_client = ai_client
        self.project: Optional[Path] = None
        self.deployment: Optional[DeploymentOrchestrator] = None
        self.context: Optional[ProjectContextManager] = None

        # Autonomous Task Agent runtime state.
        self.current_task: Optional[str] = None
        self.agent_state: str = "IDLE"
        self.agent_step: int = 0
        self.agent_history: list[dict] = []

    def clear(self):
        os.system("clear")

    def header(self, title: str):
        print("\n╭────────────────────────────────────────────────────────────╮")
        print(f"│ {title:<58} │")
        print("╰────────────────────────────────────────────────────────────╯")

    def select_project(self) -> bool:
        self.clear()
        self.header("📁 SELECT PROJECT")

        current = Path.cwd().resolve()
        print(f"\nCurrent directory:")
        print(f"  {current}")

        print("\nEnter project path.")
        print("Press ENTER to use current directory.")
        value = input("\nProject> ").strip()

        project = (
            current
            if not value
            else Path(value).expanduser().resolve()
        )

        if not project.exists():
            print(f"\n❌ Project not found: {project}")
            input("\nPress ENTER...")
            return False

        if not project.is_dir():
            print("\n❌ Selected path is not a directory.")
            input("\nPress ENTER...")
            return False

        self.project = project
        self.deployment = DeploymentOrchestrator(project)
        self.context = ProjectContextManager(project)

        print(f"\n✅ Project selected:")
        print(f"   {project}")

        input("\nPress ENTER...")
        return True

    def ensure_project(self) -> bool:
        if self.project is not None:
            return True

        current = Path.cwd().resolve()

        # When Task Agent is launched from an existing project,
        # use that workspace directly instead of asking for it again.
        if (
            (current / ".git").exists()
            or (current / "SVA-Matrix.py").exists()
            or (current / "pyproject.toml").exists()
            or (current / "package.json").exists()
        ):
            self.project = current
            self.deployment = DeploymentOrchestrator(current)
            self.context = ProjectContextManager(current)
            return True

        return self.select_project()

    def deployment_menu(self):
        while True:
            self.clear()
            self.header("📦 PROJECT DEPLOYMENT")

            print("""
[1] 📁 Project Folder
[2] 🔍 Check
[3] 🧪 Test
[4] 🔧 Find & Fix
[5] ▶️  Run
[6] ✅ Verify
[7] 📊 Status
[0] ← Back
""")

            choice = input("Deployment> ").strip()

            if choice == "0":
                return

            if not self.ensure_project():
                continue

            if choice == "1":
                self.show_project_folder()
            elif choice == "2":
                self.show_check()
            elif choice == "3":
                self.show_test()
            elif choice == "4":
                self.find_and_fix()
            elif choice == "5":
                self.run_project()
            elif choice == "6":
                self.verify_project()
            elif choice == "7":
                self.show_status()
            else:
                print("\n❌ Invalid choice.")
                input("\nPress ENTER...")

    def show_project_folder(self):
        self.clear()
        self.header("📁 PROJECT INFORMATION")

        status = self.deployment.status()

        print(f"""
Name          : {status.get('project')}
Path          : {status.get('path')}
Type          : {status.get('type')}
Git           : {status.get('git')}
Branch        : {status.get('branch')}
Files         : {status.get('files')}
Folders       : {status.get('folders')}
Source Files  : {status.get('source_files')}
Test Files    : {status.get('test_files')}
Dependencies  : {status.get('dependencies')}
Entry Point   : {', '.join(status.get('entry_points', [])) or 'UNKNOWN'}
Context       : {'READY' if status.get('context_ready') else 'MISSING'}
Testing       : {'FOUND' if status.get('testing_engine') else 'MISSING'}
Errors        : {status.get('errors')}
Warnings      : {status.get('warnings')}
Status        : {status.get('status')}
""")

        input("\nPress ENTER...")

    def show_check(self):
        self.clear()
        self.header("🔍 PROJECT CHECK")

        result = self.deployment.check()

        print(json.dumps(result, indent=2, ensure_ascii=False))

        input("\nPress ENTER...")

    def show_test(self):
        self.clear()
        self.header("🧪 PROJECT TEST")

        result = self.deployment.test()

        print(json.dumps(result, indent=2, ensure_ascii=False))

        input("\nPress ENTER...")

    def find_and_fix(self):
        self.clear()
        self.header("🔧 FIND & FIX")

        print("""
TEST → OBSERVE → AI ANALYZE → REPAIR → RETEST → VERIFY
""")

        testing_dir = self.project / "sva_engine" / "testing"

        if not testing_dir.is_dir():
            print("\n❌ Existing testing engine not found.")
            input("\nPress ENTER...")
            return

        try:
            from sva_engine.testing.loop import TestingLoop
            from sva_engine.ai_error_fixer import AIErrorFixer
            from sva_engine.testing.planner import TestPlanner
            from sva_engine.testing.repair import RepairProposal

            if self.ai_client is None:
                print("\n⚠️ Unified AI Gateway is not configured.")
                input("\nPress ENTER...")
                return

            # Reuse the same unified AI interface used by Task Agent.
            ai_client = self.ai_client
            fixer = AIErrorFixer(ai_client)
            loop = TestingLoop(
                self.project,
                timeout=120,
                max_retries=2,
            )

            from sva_engine.testing.detector import ProjectDetector

            detection = ProjectDetector(self.project).detect()
            print(f"🔍 Detected     : {', '.join(detection.get('languages', [])) or 'UNKNOWN'}")

            planner = TestPlanner(self.project)
            plan = planner.plan(detection)

            if not plan.get("success"):
                print("\n❌ Could not create test plan.")
                print(plan.get("reason", "Unknown error"))
                input("\nPress ENTER...")
                return

            steps = [
                step for step in plan.get("steps", [])
                if isinstance(step, dict)
            ]

            if not steps:
                print("\n⚠️ No test steps available.")
                input("\nPress ENTER...")
                return

            print(f"🤖 AI            : OpenRouter / {model}")
            print(f"🧪 Test steps    : {len(steps)}")
            print("🔁 Max retries   : 2")
            print()

            for index, step in enumerate(steps, 1):
                if step.get("conditional"):
                    condition = str(step.get("condition", ""))
                    if condition == "tests/ exists" and not (
                        self.project / "tests"
                    ).is_dir():
                        continue

                    if condition == "package.json has test script":
                        package = self.project / "package.json"
                        if not package.exists():
                            continue

                print(
                    f"\n[{index}] {step.get('id', 'unknown')}"
                )
                print(
                    "    $ "
                    + " ".join(
                        str(arg) for arg in step.get("argv", [])
                    )
                )

                def repair_proposer(
                    *,
                    step,
                    result,
                    failure,
                    attempt,
                ):

                    command = " ".join(
                        str(arg) for arg in step.get("argv", [])
                    )

                    error = (
                        str(result.get("stderr") or "")
                        + "\n"
                        + str(result.get("stdout") or "")
                    ).strip()

                    print(
                        f"\n🧠 AI analyzing failure "
                        f"(attempt {attempt})..."
                    )

                    proposal = fixer.propose_repair(
                        command,
                        error,
                        failure,
                    )

                    if not isinstance(proposal, RepairProposal):
                        raise ValueError(
                            "AI did not return a RepairProposal"
                        )

                    print("\n--- AI DIAGNOSIS ---")
                    print(proposal.diagnosis)

                    print(
                        f"Category   : "
                        f"{proposal.failure_category}"
                    )
                    print(
                        f"Fix type   : {proposal.fix_type}"
                    )
                    print(
                        f"Confidence : "
                        f"{proposal.confidence:.2f}"
                    )

                    print("\n--- PROPOSED ACTIONS ---")

                    if not proposal.actions:
                        print("(no safe file repair proposed)")
                        return proposal

                    for action in proposal.actions:
                        print(f"Action : {action.action}")
                        print(f"Path   : {action.path}")

                        if action.action == "patch_file":
                            print(
                                f"Replace: "
                                f"{action.old_text!r}"
                            )
                            print(
                                f"With   : "
                                f"{action.new_text!r}"
                            )
                        elif action.action == "write_file":
                            print("Content: <file content proposed>")

                    return proposal

                def approve_repair(proposal):
                    confirm = input(
                        "\nApply this repair? [y/N]: "
                    ).strip().lower()
                    return confirm == "y"

                result = loop.run_step(
                    step,
                    repair_proposer=repair_proposer,
                    approval_callback=approve_repair,
                )

                print("\n--- RESULT ---")
                print(
                    f"Status   : "
                    f"{result.get('status')}"
                )
                print(
                    f"Attempts : "
                    f"{result.get('attempts')}"
                )

                if result.get("success"):
                    print("✅ VERIFIED")
                else:
                    print("❌ NOT VERIFIED")

            print("\n🏁 FIND & FIX COMPLETE")

            self.testing_loop = loop
            self.ai_client = ai_client
            self.ai_error_fixer = fixer

        except Exception as exc:
            print(f"\n❌ Find & Fix failed: {exc}")

        input("\nPress ENTER...")

    def run_project(self):
        self.clear()
        self.header("▶️ RUN PROJECT")

        status = self.deployment.status()
        entries = status.get("entry_points", [])

        if not entries:
            print("\n❌ No known entry point detected.")
            print("Use Project Management to define one.")
            input("\nPress ENTER...")
            return

        print("\nDetected entry points:")
        for index, entry in enumerate(entries, 1):
            print(f"[{index}] {entry}")

        choice = input("\nSelect entry point> ").strip()

        try:
            index = int(choice) - 1
            entry = entries[index]
        except (ValueError, IndexError):
            print("\n❌ Invalid entry point.")
            input("\nPress ENTER...")
            return

        command = self.build_run_command(entry)

        print(f"\n▶ Command:")
        print(f"  {command}")

        confirm = input("\nRun this command? [y/N]: ").strip().lower()

        if confirm != "y":
            print("\n⏸️ Run cancelled.")
            input("\nPress ENTER...")
            return

        # Interactive application entry points must keep the
        # user's terminal stdin/stdout. Captured subprocess execution
        # would otherwise wait for input and block the Task Agent.
        if Path(entry).suffix.lower() == ".py":
            print("\n▶️ Starting interactive project...")
            print("ℹ️ Press the application's own Exit option to return.")
            print()

            try:
                import subprocess

                result = subprocess.run(
                    command,
                    shell=True,
                    cwd=str(self.project),
                )

                run_result = {
                    "success": result.returncode == 0,
                    "returncode": result.returncode,
                    "stdout": "",
                    "stderr": "",
                    "command": command,
                }

                print(
                    "\n✅ RUN SUCCESS"
                    if run_result["success"]
                    else "\n❌ RUN FAILED"
                )

            except Exception as exc:
                print(f"\n❌ RUN ERROR: {exc}")

        else:
            result = self.deployment.run(command)

            print("\n--- STDOUT ---")
            print(result.get("stdout") or "(empty)")

            print("\n--- STDERR ---")
            print(result.get("stderr") or "(empty)")

            print(f"\n--- RETURN CODE: {result.get('returncode')} ---")
            print(
                "\n✅ RUN SUCCESS"
                if result.get("success")
                else "\n❌ RUN FAILED"
            )

        input("\nPress ENTER...")

    def build_run_command(self, entry: str) -> str:
        suffix = Path(entry).suffix.lower()

        if suffix == ".py":
            return f"python {self.shell_quote(entry)}"

        if suffix == ".js":
            return f"node {self.shell_quote(entry)}"

        if suffix == ".ts":
            return f"npx tsx {self.shell_quote(entry)}"

        return self.shell_quote(entry)

    @staticmethod
    def shell_quote(value: str) -> str:
        return "'" + value.replace("'", "'\\''") + "'"

    def verify_project(self):
        self.clear()
        self.header("✅ PROJECT VERIFY")

        print("Running verification using the current project state...")

        result = self.deployment.verify()

        print(json.dumps(result, indent=2, ensure_ascii=False))

        input("\nPress ENTER...")

    def show_status(self):
        self.clear()
        self.header("📊 PROJECT STATUS")

        status = self.deployment.status()

        for key, value in status.items():
            print(f"{key:<18}: {value}")

        input("\nPress ENTER...")

    def context_menu(self):
        while True:
            self.clear()
            self.header("🧠 PROJECT CONTEXT")

            print("""
[1] 📄 PRD
[2] 🏗️  Architecture
[3] 📜 Rules
[4] 🎨 Design
[5] 📋 Tasks
[6] 🧠 Memory
[7] 🔄 Initialize Missing Context
[0] ← Back
""")

            choice = input("Context> ").strip()

            if choice == "0":
                return

            if not self.ensure_project():
                continue

            if choice == "7":
                self.context.ensure_project()
                print("\n✅ Missing context files initialized.")
                input("\nPress ENTER...")
                continue

            mapping = {
                "1": "prd.md",
                "2": "architecture.md",
                "3": "rules.md",
                "4": "design.md",
                "5": "tasks.md",
                "6": "memory.md",
            }

            filename = mapping.get(choice)

            if not filename:
                print("\n❌ Invalid choice.")
                input("\nPress ENTER...")
                continue

            self.show_context_file(filename)

    def show_context_file(self, filename: str):
        self.clear()
        self.header(f"📄 {filename.upper()}")

        path = self.project / filename

        if not path.exists():
            print("\n⚠️ File does not exist.")
            input("\nPress ENTER...")
            return

        print(path.read_text(encoding="utf-8", errors="replace"))

        input("\nPress ENTER...")

    def load_agent_context(self) -> dict[str, str]:
        """Load all project context files for autonomous task execution."""
        if not self.ensure_project():
            return {}

        if self.context is None:
            self.context = ProjectContextManager(self.project)

        self.context.ensure_project()
        return self.context.read_all()

    def ai_menu(self):
        self.clear()
        self.header("🤖 TASK AGENT AI")

        if self.ai_client is None:
            print("\n❌ SVA AI client is not connected.")
            input("\nPress ENTER...")
            return

        if not self.ensure_project():
            return

        context = self.load_agent_context()
        print("\n🧠 Project context loaded:", len(context), "files")

        task = input("\nTask> ").strip()
        if not task:
            print("\n❌ Task is empty.")
            input("\nPress ENTER...")
            return

        planner = AIPlanner(self.ai_client)

        print("\n🤖 Creating project-aware execution plan...")
        result = planner.plan(task, context=context)

        print("\n--- PLAN RESULT ---")
        print(json.dumps(result, indent=2, ensure_ascii=False))

        if not result.get("success"):
            print("\n❌ Planning failed.")
            input("\nPress ENTER...")
            return

        steps = result.get("steps") or []
        if not steps:
            print("\n❌ AI returned no executable steps.")
            input("\nPress ENTER...")
            return

        print(f"\n📋 Steps: {len(steps)}")

        confirm = input("\nExecute this plan? [y/N]: ").strip().lower()
        if confirm != "y":
            print("\n⏸️ Plan not executed.")
            input("\nPress ENTER...")
            return

        project_id = "sva_" + str(abs(hash(str(self.project))) % 100000000)
        task_id = "task_" + str(abs(hash(task + str(self.project))) % 100000000)

        store = TaskStore()

        store.create_project(
            project_id=project_id,
            name=self.project.name,
            description=task,
            workspace=self.project,
        )

        store.create_task(
            project_id=project_id,
            task_id=task_id,
            description=task,
            steps=steps,
        )

        controller = SVAController(store)
        controller.set_project(project_id)

        executor = ActionExecutor(controller)

        recovery_manager = None

        # Use the existing SVA AI client for safe test-failure repair.
        # Only test commands are routed through the recovery manager.
        if self.ai_client is not None:
            try:
                from sva_engine.ai_error_fixer import AIErrorFixer
                from sva_engine.testing.recovery import TestRecoveryManager

                def approve_repair(proposal):
                    print("\n🔧 AI REPAIR PROPOSAL")
                    print(
                        json.dumps(
                            proposal.to_dict(),
                            indent=2,
                            ensure_ascii=False,
                        )
                    )
                    confirm = input(
                        "\nApply this repair? [y/N]: "
                    ).strip().lower()
                    return confirm == "y"

                recovery_manager = TestRecoveryManager(
                    self.project,
                    AIErrorFixer(self.ai_client),
                    timeout=120,
                    max_retries=2,
                    approval_callback=approve_repair,
                )
            except Exception as exc:
                print(
                    f"\n⚠️ Test recovery unavailable: {exc}"
                )

        agent = PersistentAgent(
            controller,
            store=store,
            executor=executor,
            recovery_manager=recovery_manager,
        )

        self.current_task = task
        self.agent_state = "RUNNING"
        self.agent_step = 0
        self.agent_history = []

        print("\n🚀 TASK AGENT STARTED")
        print(f"📁 Project : {self.project}")
        print(f"🆔 Task    : {task_id}")
        print(f"📋 Steps   : {len(steps)}")

        execution = agent.run(project_id, task_id)

        self.agent_state = str(execution.get("status", "UNKNOWN"))
        self.agent_history.append(execution)

        # Persist autonomous results unless the user explicitly requested read-only work.
        try:
            read_only_task = any(
                phrase in task.lower()
                for phrase in (
                    "without modifying any files",
                    "do not modify any files",
                    "don't modify any files",
                    "read-only",
                    "read only",
                    "without modifying files",
                    "do not modify files",
                    "don't modify files",
                )
            )

            if read_only_task:
                print("\n🔒 Read-only task: project context files were not modified.")
            elif self.context is None:
                self.context = ProjectContextManager(self.project)

            if read_only_task:
                print("\n--- EXECUTION RESULT ---")
                print(json.dumps(execution, indent=2, ensure_ascii=False))
                input("\nPress ENTER...")
                return

            status = str(execution.get("status", "UNKNOWN"))
            result_summary = (
                execution.get("task", {}).get("last_output", "")
                if isinstance(execution.get("task"), dict)
                else ""
            )

            task_errors = []
            task_warnings = []

            task_data = execution.get("task")
            if isinstance(task_data, dict):
                last_error = task_data.get("last_error")
                if last_error:
                    task_errors.append(str(last_error))

            if status == "COMPLETE":
                self.context.record_task_result(
                    task,
                    status,
                    result=result_summary,
                    errors=task_errors or ["NONE"],
                    warnings=task_warnings or ["NONE"],
                )
                self.context.record_memory_result(
                    task,
                    status,
                    result_summary,
                )
                print("\n📝 Project context updated: tasks.md + memory.md")
            else:
                self.context.record_task_result(
                    task,
                    status,
                    result=result_summary,
                    errors=task_errors or ["NONE"],
                    warnings=task_warnings or ["NONE"],
                )
                print("\n📝 tasks.md updated with current task status.")
        except Exception as exc:
            print(f"\n⚠️ Context update unavailable: {exc}")

        print("\n--- EXECUTION RESULT ---")
        print(json.dumps(execution, indent=2, ensure_ascii=False))

        input("\nPress ENTER...")

    def project_status(self):
        if not self.ensure_project():
            return

        self.clear()
        self.header("📊 PROJECT STATUS")

        status = self.deployment.status()

        print(json.dumps(status, indent=2, ensure_ascii=False))

        input("\nPress ENTER...")

    def project_management(self):
        while True:
            self.clear()
            self.header("📁 PROJECT MANAGEMENT")

            print("""
[1] Select Project
[2] Initialize Context
[3] Show Project Path
[4] Show Context Files
[5] Show Deployment State
[0] ← Back
""")

            choice = input("Management> ").strip()

            if choice == "0":
                return

            if choice == "1":
                self.select_project()

            elif choice == "2":
                if self.ensure_project():
                    result = self.context.ensure_project()
                    print("\n✅ Context initialized.")
                    print(json.dumps(result, indent=2, ensure_ascii=False))
                    input("\nPress ENTER...")

            elif choice == "3":
                if self.ensure_project():
                    print(f"\n📁 {self.project}")
                    input("\nPress ENTER...")

            elif choice == "4":
                if self.ensure_project():
                    print("\n".join(
                        f"  {'✅' if (self.project / f).exists() else '❌'} {f}"
                        for f in CONTEXT_FILES
                    ))
                    input("\nPress ENTER...")

            elif choice == "5":
                if self.ensure_project():
                    state_file = self.project / ".sva" / "deployment_state.json"
                    if state_file.exists():
                        print(state_file.read_text(
                            encoding="utf-8",
                            errors="replace",
                        ))
                    else:
                        print("\nNo deployment state yet.")
                    input("\nPress ENTER...")

            else:
                print("\n❌ Invalid choice.")
                input("\nPress ENTER...")

    def run(self):
        while True:
            self.clear()
            self.header("🚀 SVA MATRIX — TASK AGENT")

            print("""
[1] 📦 PROJECT DEPLOYMENT
[2] 🧠 PROJECT CONTEXT
[3] 🤖 AI
[4] 📊 PROJECT STATUS
[5] 📁 PROJECT MANAGEMENT
[0] ← Back
""")

            choice = input("Task Agent> ").strip()

            if choice == "0":
                return

            if choice == "1":
                self.deployment_menu()
            elif choice == "2":
                self.context_menu()
            elif choice == "3":
                if self.ensure_project():
                    self.ai_menu()
            elif choice == "4":
                self.project_status()
            elif choice == "5":
                self.project_management()
            else:
                print("\n❌ Invalid choice.")
                input("\nPress ENTER...")


def task_agent_menu():
    TaskAgentMenu().run()


if __name__ == "__main__":
    task_agent_menu()
