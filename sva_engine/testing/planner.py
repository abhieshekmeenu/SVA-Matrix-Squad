from __future__ import annotations

from pathlib import Path


class TestPlanner:
    """Create a non-executing test plan from project detection."""

    def __init__(self, project_path: str | Path):
        self.project_path = Path(project_path).expanduser().resolve()

    def plan(self, detection: dict[str, object]) -> dict[str, object]:
        languages = detection.get("languages", [])

        if not isinstance(languages, list):
            return {
                "success": False,
                "reason": "Invalid project detection result",
                "steps": [],
            }

        steps: list[dict[str, object]] = []

        for language in languages:
            if language == "Python":
                steps.extend([
                    {
                        "id": "python_compile",
                        "type": "syntax",
                        "language": "Python",
                        "argv": ["python", "-m", "compileall", "-q", "."],
                    },
                    {
                        "id": "python_pytest",
                        "type": "test",
                        "language": "Python",
                        "argv": ["python", "-m", "pytest", "-q"],
                        "conditional": True,
                        "condition": "tests/ exists",
                    },
                ])

            elif language in {"JavaScript", "TypeScript"}:
                steps.extend([
                    {
                        "id": "node_test",
                        "type": "test",
                        "language": language,
                        "argv": ["npm", "test"],
                        "conditional": True,
                        "condition": "package.json has test script",
                    },
                    {
                        "id": "node_build",
                        "type": "build",
                        "language": language,
                        "argv": ["npm", "run", "build"],
                        "conditional": True,
                        "condition": "package.json has build script",
                    },
                ])

            elif language == "Go":
                steps.append({
                    "id": "go_test",
                    "type": "test",
                    "language": "Go",
                    "argv": ["go", "test", "./..."],
                })

            elif language == "Rust":
                steps.append({
                    "id": "rust_test",
                    "type": "test",
                    "language": "Rust",
                    "argv": ["cargo", "test"],
                })

            elif language == "Java":
                steps.append({
                    "id": "java_build",
                    "type": "build",
                    "language": "Java",
                    "argv": ["mvn", "test"],
                    "conditional": True,
                    "condition": "pom.xml exists",
                })

            elif language == "Ruby":
                steps.append({
                    "id": "ruby_test",
                    "type": "test",
                    "language": "Ruby",
                    "argv": ["bundle", "exec", "rake", "test"],
                    "conditional": True,
                })

            elif language == "PHP":
                steps.append({
                    "id": "php_test",
                    "type": "test",
                    "language": "PHP",
                    "argv": ["composer", "test"],
                    "conditional": True,
                })

        return {
            "success": True,
            "project": str(self.project_path),
            "steps": steps,
            "step_count": len(steps),
        }
