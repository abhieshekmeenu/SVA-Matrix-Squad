from pathlib import Path

from sva_engine.project_checker import ProjectChecker


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_project_discovery():
    checker = ProjectChecker(PROJECT_ROOT)

    files = checker.discover_files()

    assert files
    assert any(item["language"] == "Python" for item in files)


def test_python_files_compile():
    checker = ProjectChecker(PROJECT_ROOT)

    report = checker.check()

    assert report["python_files"] > 0
    assert report["failed"] == 0


def test_project_summary():
    checker = ProjectChecker(PROJECT_ROOT)

    summary = checker.summary()

    assert summary["file_count"] > 0
    assert "Python" in summary["languages"]
