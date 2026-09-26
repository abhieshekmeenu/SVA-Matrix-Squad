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

class RecoveryController(FakeController):
    def __init__(self):
        super().__init__()
        self.attempts = {}

    def execute(self, command, task_id=None):
        self.attempts[command] = self.attempts.get(command, 0) + 1

        if command == "failing-step" and self.attempts[command] == 1:
            self.commands.append(command)
            return {
                "success": False,
                "command": command,
                "stdout": "",
                "stderr": "intentional failure",
                "returncode": 1,
            }

        self.commands.append(command)
        return {
            "success": True,
            "command": command,
            "stdout": f"ok: {command}",
            "stderr": "",
            "returncode": 0,
        }


class FakeRecoveryManager:
    def __init__(self):
        self.proposals = 0
        self.retries = 0

    def propose(self, action, result, task_id=None):
        self.proposals += 1
        return {
            "success": True,
            "approval_required": False,
            "execution_allowed": True,
            "retry": True,
            "safety": {},
            "proposal": {
                "action": action,
                "task_id": task_id,
            },
        }

    def retry(self, controller, proposal):
        self.retries += 1
        return {
            "success": True,
            "stdout": "repair applied",
            "stderr": "",
            "returncode": 0,
        }


def test_agent_recovery_retries_failed_step(tmp_path):
    store = TaskStore(tmp_path / "projects")
    controller = RecoveryController()

    store.create_project(
        "project_1",
        name="Recovery Project",
        workspace=tmp_path / "workspace",
    )

    store.create_task(
        "project_1",
        "task_1",
        "recovery test",
        steps=["before-step", "failing-step", "after-step"],
    )

    recovery = FakeRecoveryManager()

    agent = PersistentAgent(
        controller,
        store=store,
        recovery_manager=recovery,
    )

    result = agent.run("project_1", "task_1")

    assert result["success"] is True
    assert result["status"] == "COMPLETE"
    assert recovery.proposals == 1
    assert recovery.retries == 1

    task = store.load_task("project_1", "task_1")

    assert task["status"] == "COMPLETE"
    assert task["current_step"] == 3
    assert task["total_steps"] == 3
    assert controller.commands == [
        "before-step",
        "failing-step",
        "after-step",
    ]



def test_agent_test_recovery_repairs_and_retests(tmp_path):
    from sva_engine.ai_error_fixer import AIErrorFixer
    from sva_engine.testing.recovery import TestRecoveryManager

    project = tmp_path / "workspace"
    project.mkdir()

    test_file = project / "test_sample.py"
    test_file.write_text(
        "def test_sample():\n"
        "    assert 1 == 2\n",
        encoding="utf-8",
    )

    class FakeAI:
        def ask(self, prompt):
            return {
                "success": True,
                "response": (
                    "{"
                    '"failure_category":"test",'
                    '"diagnosis":"Intentional failing assertion",'
                    '"fix_type":"patch_file",'
                    '"confidence":0.95,'
                    '"requires_approval":true,'
                    '"actions":[{'
                    '"action":"patch_file",'
                    '"path":"test_sample.py",'
                    '"old_text":"assert 1 == 2",'
                    '"new_text":"assert 1 == 1"'
                    "}]"
                    "}"
                ),
            }

    fixer = AIErrorFixer(FakeAI())

    approvals = []

    def approve(proposal):
        approvals.append(proposal)
        return True

    recovery = TestRecoveryManager(
        project,
        fixer,
        approval_callback=approve,
    )

    first = recovery.loop.runner.run(
        ["python", "-m", "pytest", "-q"],
        step_id="test",
    )

    assert first["success"] is False

    proposal_result = recovery.propose(
        {
            "action": "run",
            "command": "python -m pytest -q",
        },
        first,
        task_id="task_1",
    )

    assert proposal_result["success"] is True
    assert proposal_result["retry"] is True
    assert len(approvals) == 1

    retry_result = recovery.retry(
        None,
        proposal_result["proposal"],
    )

    assert retry_result["success"] is True
    assert retry_result["status"] == "verified"


def test_persistent_agent_uses_test_recovery_end_to_end(tmp_path):
    from sva_engine.ai_error_fixer import AIErrorFixer
    from sva_engine.testing.recovery import TestRecoveryManager

    project = tmp_path / "workspace"
    project.mkdir()

    test_file = project / "test_sample.py"
    test_file.write_text(
        "def test_sample():\n"
        "    assert 1 == 2\n",
        encoding="utf-8",
    )

    class FakeAI:
        def ask(self, prompt):
            return {
                "success": True,
                "response": (
                    "{"
                    '"failure_category":"test",'
                    '"diagnosis":"Intentional failing assertion",'
                    '"fix_type":"patch_file",'
                    '"confidence":0.95,'
                    '"requires_approval":true,'
                    '"actions":[{'
                    '"action":"patch_file",'
                    '"path":"test_sample.py",'
                    '"old_text":"assert 1 == 2",'
                    '"new_text":"assert 1 == 1"'
                    "}]"
                    "}"
                ),
            }

    class ProjectController:
        def __init__(self, project_path):
            self.project_path = project_path
            self.project_id = None

        def set_project(self, project_id):
            self.project_id = project_id

        def execute(self, command, task_id=None, input_data=None):
            import subprocess

            result = subprocess.run(
                ["bash", "-lc", command],
                cwd=self.project_path,
                input=input_data,
                capture_output=True,
                text=True,
                timeout=120,
            )

            return {
                "success": result.returncode == 0,
                "command": command,
                "returncode": result.returncode,
                "stdout": result.stdout,
                "stderr": result.stderr,
            }

    store = TaskStore(tmp_path / "projects")

    store.create_project(
        "project_1",
        name="Recovery Project",
        workspace=project,
    )

    store.create_task(
        "project_1",
        "task_1",
        "run project tests and repair failures",
        steps=[
            {
                "action": "run",
                "command": "python -m pytest -q",
            }
        ],
    )

    controller = ProjectController(project)
    controller.set_project("project_1")

    fixer = AIErrorFixer(FakeAI())

    approvals = []

    def approve(proposal):
        approvals.append(proposal)
        return True

    recovery = TestRecoveryManager(
        project,
        fixer,
        timeout=120,
        max_retries=2,
        approval_callback=approve,
    )

    agent = PersistentAgent(
        controller,
        store=store,
        recovery_manager=recovery,
    )

    result = agent.run("project_1", "task_1")

    assert result["success"] is True
    assert result["status"] == "COMPLETE"
    assert len(approvals) == 1

    fixed = test_file.read_text(encoding="utf-8")
    assert "assert 1 == 1" in fixed

    task = store.load_task("project_1", "task_1")
    assert task["status"] == "COMPLETE"
