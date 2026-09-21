from pathlib import Path

from sva_engine.agent import PersistentAgent
from sva_engine.task_store import TaskStore


class FakeController:
    def __init__(self):
        self.project_id = None
        self.commands = []

    def set_project(self, project_id):
        self.project_id = project_id

    def execute(self, command, task_id=None):
        self.commands.append(command)
        return {
            "success": True,
            "command": command,
            "stdout": f"ok: {command}",
            "stderr": "",
            "returncode": 0,
        }


def make_agent(tmp_path):
    store = TaskStore(tmp_path / "projects")
    controller = FakeController()

    store.create_project(
        "project_1",
        name="Test Project",
        workspace=tmp_path / "workspace",
    )

    store.create_task(
        "project_1",
        "task_1",
        "test task",
        steps=["step-1", "step-2", "step-3"],
    )

    agent = PersistentAgent(controller, store=store)
    return agent, store, controller


def test_agent_runs_all_steps_and_checkpoints(tmp_path):
    agent, store, controller = make_agent(tmp_path)

    result = agent.run("project_1", "task_1")

    assert result["success"] is True
    assert result["status"] == "COMPLETE"

    task = store.load_task("project_1", "task_1")

    assert task["status"] == "COMPLETE"
    assert task["current_step"] == 3
    assert task["total_steps"] == 3
    assert len(task["results"]) == 3
    assert controller.commands == ["step-1", "step-2", "step-3"]


def test_agent_pause_is_persisted(tmp_path):
    agent, store, _ = make_agent(tmp_path)

    result = agent.pause("project_1", "task_1")

    assert result["success"] is True
    assert result["status"] == "PAUSED"

    task = store.load_task("project_1", "task_1")
    assert task["status"] == "PAUSED"


def test_agent_stop_is_persisted(tmp_path):
    agent, store, _ = make_agent(tmp_path)

    result = agent.stop("project_1", "task_1")

    assert result["success"] is True
    assert result["status"] == "STOPPED"

    task = store.load_task("project_1", "task_1")
    assert task["status"] == "STOPPED"
