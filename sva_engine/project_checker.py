"""SVA Matrix Squad multi-language project checker."""

from __future__ import annotations

import ast

import subprocess
import sys
from pathlib import Path


LANGUAGE_EXTENSIONS = {
    ".py": "Python",
    ".java": "Java",
    ".c": "C",
    ".h": "C/C++ Header",
    ".cc": "C++",
    ".cpp": "C++",
    ".cxx": "C++",
    ".js": "JavaScript",
    ".jsx": "JavaScript",
    ".ts": "TypeScript",
    ".tsx": "TypeScript",
    ".go": "Go",
    ".rs": "Rust",
    ".rb": "Ruby",
    ".php": "PHP",
    ".kt": "Kotlin",
    ".kts": "Kotlin",
    ".swift": "Swift",
    ".dart": "Dart",
    ".lua": "Lua",
    ".sh": "Shell",
    ".bash": "Shell",
    ".zsh": "Shell",
    ".ml": "OCaml",
    ".mli": "OCaml",
}


class ProjectChecker:
    """Discover and check source files inside a project."""

    SKIP_DIRECTORIES = {
        ".git",
        "__pycache__",
        "node_modules",
        ".venv",
        "venv",
        "dist",
        "build",
        ".pytest_cache",
    }

    def __init__(self, project_path: str | Path):
        self.project_path = Path(project_path).expanduser().resolve()

    def discover_files(self) -> list[dict[str, str]]:
        """Find supported source files inside the project."""
        if not self.project_path.is_dir():
            raise ValueError(
                f"Project directory does not exist: {self.project_path}"
            )

        files = []

        for path in self.project_path.rglob("*"):
            if not path.is_file():
                continue

            if any(
                part in self.SKIP_DIRECTORIES
                for part in path.parts
            ):
                continue

            language = LANGUAGE_EXTENSIONS.get(
                path.suffix.lower()
            )

            if language is None:
                continue

            files.append(
                {
                    "path": str(
                        path.relative_to(self.project_path)
                    ),
                    "language": language,
                }
            )

        return sorted(
            files,
            key=lambda item: (item["language"], item["path"]),
        )

    def check_python_file(self, relative_path: str) -> dict[str, object]:
        """Run a real Python syntax check on one project file."""
        path = self.project_path / relative_path

        try:
            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "py_compile",
                    str(path),
            ],
                capture_output=True,
                text=True,
                timeout=30,
            )

            return {
                "path": relative_path,
                "language": "Python",
                "success": result.returncode == 0,
                "returncode": result.returncode,
                "stdout": result.stdout.strip(),
                "stderr": result.stderr.strip(),
            }

        except subprocess.TimeoutExpired:
            return {
                "path": relative_path,
                "language": "Python",
                "success": False,
                "returncode": -1,
                "stdout": "",
                "stderr": "Python syntax check timed out.",
            }

        except Exception as error:
            return {
                "path": relative_path,
                "language": "Python",
                "success": False,
                "returncode": -1,
                "stdout": "",
                "stderr": str(error),
            }

    def run_pytest(self) -> dict[str, object]:
        """Run the project's real pytest test suite when available."""
        test_dir = self.project_path / "tests"

        if not test_dir.is_dir():
            return {
                "available": False,
                "success": False,
                "returncode": None,
                "stdout": "",
                "stderr": "",
                "message": "No tests/ directory found.",
            }

        try:
            result = subprocess.run(
                [sys.executable, "-m", "pytest", "-q"],
                cwd=str(self.project_path),
                capture_output=True,
                text=True,
                timeout=120,
            )

            return {
                "available": True,
                "success": result.returncode == 0,
                "returncode": result.returncode,
                "stdout": result.stdout.strip(),
                "stderr": result.stderr.strip(),
                "message": (
                    "Pytest passed."
                    if result.returncode == 0
                    else "Pytest reported test failures."
                ),
            }

        except subprocess.TimeoutExpired:
            return {
                "available": True,
                "success": False,
                "returncode": -1,
                "stdout": "",
                "stderr": "Pytest timed out.",
                "message": "Pytest timed out.",
            }

        except Exception as error:
            return {
                "available": False,
                "success": False,
                "returncode": -1,
                "stdout": "",
                "stderr": str(error),
                "message": "Unable to run pytest.",
            }

    def static_analyze_python_file(self, relative_path: str) -> dict[str, object]:
        """Run lightweight AST-based static analysis on one Python file."""
        path = self.project_path / relative_path
        issues: list[dict[str, object]] = []

        try:
            source = path.read_text(encoding="utf-8")
            tree = ast.parse(source, filename=str(path))
        except (OSError, UnicodeDecodeError) as error:
            return {
                "path": relative_path,
                "success": False,
                "issues": [{
                    "line": 0,
                    "code": "READ",
                    "message": str(error),
                }],
            }
        except SyntaxError as error:
            return {
                "path": relative_path,
                "success": False,
                "issues": [{
                    "line": error.lineno or 0,
                    "code": "SYNTAX",
                    "message": error.msg,
                }],
            }

        function_scopes: dict[str, set[str]] = {"<module>": set()}
        class_names: set[str] = set()

        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                parent_scope = "<module>"

                for possible_class in ast.walk(tree):
                    if isinstance(possible_class, ast.ClassDef):
                        if any(child is node for child in possible_class.body):
                            parent_scope = f"class:{possible_class.name}"
                            break

                scope = function_scopes.setdefault(parent_scope, set())

                if node.name in scope:
                    issues.append({
                        "line": node.lineno,
                        "code": "DUPLICATE_FUNCTION",
                        "message": (
                            f"Duplicate function definition in "
                            f"{parent_scope}: {node.name}"
                        ),
                    })

                scope.add(node.name)

                for default in node.args.defaults + node.args.kw_defaults:
                    if isinstance(default, (ast.List, ast.Dict, ast.Set)):
                        issues.append({
                            "line": node.lineno,
                            "code": "MUTABLE_DEFAULT",
                            "message": f"Mutable default argument in function: {node.name}",
                        })
                        break

            elif isinstance(node, ast.ClassDef):
                if node.name in class_names:
                    issues.append({
                        "line": node.lineno,
                        "code": "DUPLICATE_CLASS",
                        "message": f"Duplicate class definition: {node.name}",
                    })
                class_names.add(node.name)

            elif isinstance(node, ast.ExceptHandler):
                if node.type is None:
                    issues.append({
                        "line": node.lineno,
                        "code": "BARE_EXCEPT",
                        "message": "Bare except catches every exception.",
                    })

            elif isinstance(node, ast.Call):
                if isinstance(node.func, ast.Name) and node.func.id in {"eval", "exec"}:
                    issues.append({
                        "line": node.lineno,
                        "code": "DYNAMIC_EXEC",
                        "message": f"Use of {node.func.id}() detected.",
                    })

        return {
            "path": relative_path,
            "success": True,
            "issues": issues,
        }

    def static_analyze(self) -> dict[str, object]:
        """Run lightweight static analysis across Python project files."""
        files = self.discover_files()
        results = []

        for item in files:
            if item["language"] == "Python":
                results.append(
                    self.static_analyze_python_file(item["path"])
                )

        issue_count = sum(
            len(result["issues"])
            for result in results
        )

        failed = sum(
            1 for result in results
            if not result["success"]
        )

        return {
            "available": True,
            "success": failed == 0,
            "python_files": len(results),
            "files_with_issues": sum(
                1 for result in results
                if result["issues"]
            ),
            "issue_count": issue_count,
            "results": results,
        }

    def check(self) -> dict[str, object]:
        """Check Python files and run the project's real pytest suite."""
        files = self.discover_files()
        results = []

        for item in files:
            if item["language"] == "Python":
                results.append(
                    self.check_python_file(item["path"])
                )

        passed = sum(
            1 for result in results
            if result["success"]
        )
        failed = len(results) - passed

        return {
            "project": str(self.project_path),
            "files_discovered": len(files),
            "python_files": len(results),
            "passed": passed,
            "failed": failed,
            "results": results,
            "pytest": None,
        }

    def summary(self) -> dict[str, object]:
        """Return project discovery summary."""
        files = self.discover_files()

        languages: dict[str, int] = {}

        for item in files:
            language = item["language"]
            languages[language] = (
                languages.get(language, 0) + 1
            )

        return {
            "project": str(self.project_path),
            "files": files,
            "file_count": len(files),
            "languages": languages,
        }
