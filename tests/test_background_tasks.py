import time

from sva_engine.background_tasks import BackgroundTaskManager


class FakeAgent:
    def run(self, project_id, task_id):
        time.sleep(0.15)
        return {
            "success": True,
            "status": "COMPLETE",
            "project_id": project_id,
            "task_id": task_id,
        }


def test_background_task_starts_and_finishes():
    manager = BackgroundTaskManager()
    agent = FakeAgent()

    result = manager.start(agent, "project_1", "task_1")

    assert result["success"] is True
    assert result["background"] is True

    assert manager.wait("project_1", "task_1", timeout=2) is True
    assert manager.is_running("project_1", "task_1") is False
    assert manager.active() == []


def test_duplicate_background_task_is_blocked():
    manager = BackgroundTaskManager()
    agent = FakeAgent()

    first = manager.start(agent, "project_1", "task_2")
    second = manager.start(agent, "project_1", "task_2")

    assert first["success"] is True
    assert second["success"] is False
    assert "already running" in second["reason"]

    assert manager.wait("project_1", "task_2", timeout=2) is True
