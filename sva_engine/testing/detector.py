from __future__ import annotations

from pathlib import Path


class ProjectDetector:
    """Detect project ecosystems without executing project code."""

    MARKERS = {
        "Python": {
            "pyproject.toml",
            "requirements.txt",
            "setup.py",
            "setup.cfg",
        },
        "JavaScript": {
            "package.json",
        },
        "TypeScript": {
            "tsconfig.json",
        },
        "Go": {
            "go.mod",
        },
        "Rust": {
            "Cargo.toml",
        },
        "Java": {
            "pom.xml",
            "build.gradle",
            "build.gradle.kts",
        },
        "C#": {
            "*.csproj",
            "*.sln",
        },
        "Ruby": {
            "Gemfile",
        },
        "PHP": {
            "composer.json",
        },
        "Dart": {
            "pubspec.yaml",
        },
        "Kotlin": {
            "build.gradle.kts",
        },
        "Swift": {
            "Package.swift",
        },
    }

    def __init__(self, project_path: str | Path):
        self.project_path = Path(project_path).expanduser().resolve()

    def detect(self) -> dict[str, object]:
        if not self.project_path.is_dir():
            raise ValueError(
                f"Project directory does not exist: {self.project_path}"
            )

        found: dict[str, list[str]] = {}

        for language, markers in self.MARKERS.items():
            matches = []

            for marker in markers:
                if "*" in marker:
                    matches.extend(
                        str(path.relative_to(self.project_path))
                        for path in self.project_path.glob(marker)
                        if path.is_file()
                    )
                else:
                    path = self.project_path / marker
                    if path.is_file():
                        matches.append(marker)

            if matches:
                found[language] = sorted(set(matches))

        languages = sorted(found)

        return {
            "project": str(self.project_path),
            "languages": languages,
            "markers": found,
            "multi_language": len(languages) > 1,
        }
