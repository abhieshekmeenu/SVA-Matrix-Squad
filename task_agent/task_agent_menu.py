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


class TaskAgentMenu:
    def __init__(self):
        self.project: Optional[Path] = None
        self.deployment: Optional[DeploymentOrchestrator] = None
        self.context: Optional[ProjectContextManager] = None

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
        if self.project is None:
            return self.select_project()
        return True

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
The Find & Fix stage is the controlled repair layer.

Current deployment:
    CHECK
      ↓
    TEST
      ↓
    ERROR OBSERVATION
      ↓
    AI REPAIR
      ↓
    RETEST
      ↓
    VERIFY

The existing sva_engine testing/repair components remain the
underlying repair system and are not replaced here.
""")

        print("📂 Existing testing engine:")
        print(self.project / "sva_engine" / "testing")

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

    def ai_menu(self):
        self.clear()
        self.header("🤖 TASK AGENT AI")

        print("""
AI integration point:

USER TASK
   ↓
CONTEXT
   ↓
PROJECT UNDERSTANDING
   ↓
PLAN
   ↓
ACTION
   ↓
OBSERVATION
   ↓
ERROR ANALYSIS
   ↓
REPAIR / NEXT ACTION
   ↓
VERIFY
   ↓
MEMORY
""")

        print("The autonomous AI execution layer will connect here.")
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
