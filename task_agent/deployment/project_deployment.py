#!/usr/bin/env python3
from __future__ import annotations
import json
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

ROOT = Path(__file__).resolve().parents[2]

class ProjectDeployment:
    def __init__(self, project_path: str | Path):
        self.project = Path(project_path).expanduser().resolve()
        self.context_files = [
            "prd.md",
            "architecture.md",
            "rules.md",
            "design.md",
            "tasks.md",
            "memory.md",
        ]

    def _run(self, command: str, timeout: int = 60) -> Dict[str, Any]:
        try:
            result = subprocess.run(
                command,
                shell=True,
                cwd=str(self.project),
                text=True,
                capture_output=True,
                timeout=timeout,
            )
            return {
                "command": command,
                "returncode": result.returncode,
                "success": result.returncode == 0,
                "stdout": result.stdout.strip(),
                "stderr": result.stderr.strip(),
            }
        except subprocess.TimeoutExpired:
            return {
                "command": command,
                "returncode": 124,
                "success": False,
                "stdout": "",
                "stderr": "COMMAND TIMEOUT",
            }
        except Exception as exc:
            return {
                "command": command,
                "returncode": 1,
                "success": False,
                "stdout": "",
                "stderr": repr(exc),
            }

    def scan(self) -> Dict[str, Any]:
        files = []
        folders = []
        source_files = []
        test_files = []
        dependencies = []
        configs = []

        if not self.project.exists():
            return {
                "success": False,
                "error": f"Project not found: {self.project}",
            }

        ignored = {
            ".git",
            ".venv",
            "venv",
            "__pycache__",
            "node_modules",
            ".pytest_cache",
        }

        for path in self.project.rglob("*"):
            if any(part in ignored for part in path.parts):
                continue
            if path.is_file():
                files.append(str(path.relative_to(self.project)))
                suffix = path.suffix.lower()
                name = path.name.lower()

                if suffix in {
                    ".py", ".js", ".ts", ".tsx", ".jsx",
                    ".java", ".c", ".cpp", ".h", ".hpp",
                    ".go", ".rs", ".rb", ".php", ".kt",
                }:
                    source_files.append(str(path.relative_to(self.project)))

                if (
                    "test" in name
                    or name.startswith("test_")
                    or "tests" in path.parts
                ):
                    test_files.append(str(path.relative_to(self.project)))

                if name in {
                    "requirements.txt",
                    "pyproject.toml",
                    "package.json",
                    "package-lock.json",
                    "pnpm-lock.yaml",
                    "yarn.lock",
                    "cargo.toml",
                    "go.mod",
                    "pom.xml",
                    "build.gradle",
                }:
                    dependencies.append(str(path.relative_to(self.project)))

                if (
                    name.endswith(".env")
                    or "config" in name
                    or name in {
                        "settings.json",
                        "settings.yaml",
                        "settings.yml",
                        "config.json",
                        "config.yaml",
                        "config.yml",
                    }
                ):
                    configs.append(str(path.relative_to(self.project)))
            elif path.is_dir():
                folders.append(str(path.relative_to(self.project)))

        entry_points = []
        for candidate in [
            "main.py",
            "app.py",
            "run.py",
            "server.py",
            "SVA-Matrix.py",
            "index.js",
            "index.ts",
            "main.js",
            "main.ts",
            "manage.py",
        ]:
            if (self.project / candidate).exists():
                entry_points.append(candidate)

        git = self._run("git rev-parse --is-inside-work-tree")
        branch = self._run("git branch --show-current")
        git_status = self._run("git status --short")

        project_type = "Unknown"
        if any(x.endswith(".py") for x in source_files):
            project_type = "Python Project"
        elif any(x.endswith((".js", ".ts", ".jsx", ".tsx")) for x in source_files):
            project_type = "Node/JavaScript Project"
        elif any(x.endswith(".java") for x in source_files):
            project_type = "Java Project"
        elif any(x.endswith((".c", ".cpp")) for x in source_files):
            project_type = "C/C++ Project"

        return {
            "success": True,
            "name": self.project.name,
            "path": str(self.project),
            "type": project_type,
            "git": git["stdout"] == "true",
            "branch": branch["stdout"] or "UNKNOWN",
            "files": len(files),
            "folders": len(folders),
            "source_files": len(source_files),
            "test_files": len(test_files),
            "dependencies": dependencies,
            "entry_points": entry_points,
            "configuration": configs,
            "git_status": git_status["stdout"],
            "all_files": files,
        }

    def read_context(self) -> Dict[str, str]:
        context = {}
        for filename in self.context_files:
            path = self.project / filename
            if path.exists():
                context[filename] = path.read_text(
                    encoding="utf-8",
                    errors="replace",
                )
        return context

    def check(self) -> Dict[str, Any]:
        scan = self.scan()
        if not scan.get("success"):
            return scan

        errors: List[str] = []
        warnings: List[str] = []

        if not scan["entry_points"]:
            warnings.append("No known entry point detected.")

        if not scan["test_files"]:
            warnings.append("No test files detected.")

        if scan["git"] and scan["git_status"]:
            warnings.append("Git working tree has changes.")

        if not self.project.exists():
            errors.append("Project directory does not exist.")

        return {
            "success": not errors,
            "errors": errors,
            "warnings": warnings,
            "scan": scan,
        }

    def test(self) -> Dict[str, Any]:
        commands = []

        if (self.project / "pytest.ini").exists() or (self.project / "pyproject.toml").exists():
            if any(self.project.rglob("test_*.py")):
                commands.append("python -m pytest -q")

        if (self.project / "package.json").exists():
            commands.append("npm test -- --runInBand")

        if not commands:
            if any(self.project.glob("*.py")):
                commands.append("python -m compileall -q .")

        if not commands:
            return {
                "success": True,
                "status": "NO_AUTOMATIC_TEST_FOUND",
                "results": [],
            }

        results = []
        for command in commands:
            result = self._run(command, timeout=180)
            results.append(result)
            if not result["success"]:
                return {
                    "success": False,
                    "status": "TEST_FAILED",
                    "results": results,
                }

        return {
            "success": True,
            "status": "TEST_PASSED",
            "results": results,
        }

    def status(self) -> Dict[str, Any]:
        check = self.check()
        scan = check.get("scan", {})
        return {
            "project": scan.get("name", self.project.name),
            "path": str(self.project),
            "type": scan.get("type", "Unknown"),
            "git": "Connected" if scan.get("git") else "Not detected",
            "branch": scan.get("branch", "UNKNOWN"),
            "files": scan.get("files", 0),
            "folders": scan.get("folders", 0),
            "source_files": scan.get("source_files", 0),
            "test_files": scan.get("test_files", 0),
            "dependencies": len(scan.get("dependencies", [])),
            "entry_points": scan.get("entry_points", []),
            "errors": len(check.get("errors", [])),
            "warnings": len(check.get("warnings", [])),
            "status": (
                "READY"
                if not check.get("errors")
                and not check.get("warnings")
                else "REVIEW REQUIRED"
                if not check.get("errors")
                else "BLOCKED"
            ),
            "timestamp": datetime.now().isoformat(),
        }

    def deploy_scan(self) -> Dict[str, Any]:
        return {
            "success": True,
            "project": self.status(),
            "context": self.read_context(),
            "check": self.check(),
        }

def main() -> None:
    import sys

    project = Path(sys.argv[1]).expanduser() if len(sys.argv) > 1 else Path.cwd()
    agent = ProjectDeployment(project)

    print("\n🚀 SVA TASK AGENT — PROJECT DEPLOYMENT")
    print("=" * 60)
    print(f"📁 Project : {agent.project}")
    print("🔍 Scanning project...")
    result = agent.deploy_scan()
    print(json.dumps(result, indent=2, ensure_ascii=False))

if __name__ == "__main__":
    main()
