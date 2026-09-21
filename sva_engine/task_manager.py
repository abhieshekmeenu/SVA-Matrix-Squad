class TaskManager:
    """Manage multiple independent JARVIS tasks with dependencies."""

    def __init__(self, controller):
        self.controller = controller
        self.tasks = {}

    def create_task(self, task_id, description, commands, dependencies=None, files=None):
        self.tasks[task_id] = {
            "task_id": task_id,
            "description": description,
            "commands": list(commands),
            "dependencies": list(dependencies or []),
            "files": list(files or []),
            "status": "PENDING",
            "current_step": 0,
            "result": None,
            "error": None,
        }
        return self.tasks[task_id]

    def get_task(self, task_id):
        return self.tasks.get(task_id)

    def all_tasks(self):
        return list(self.tasks.values())

    def dependencies_ready(self, task_id):
        task = self.get_task(task_id)

        if task is None:
            return False

        for dependency_id in task["dependencies"]:
            dependency = self.get_task(dependency_id)

            if dependency is None:
                return False

            if dependency["status"] != "COMPLETE":
                return False

        return True

    def run_task(self, task_id):
        task = self.get_task(task_id)

        if task is None:
            return {
                "success": False,
                "reason": "Task not found",
            }

        if not self.dependencies_ready(task_id):
            return {
                "success": False,
                "reason": "Dependencies not complete",
                "task": task,
            }

        task["status"] = "RUNNING"
        task["error"] = None
        results = []

        for index, command in enumerate(task["commands"], start=1):
            task["current_step"] = index

            result = self.controller.execute(command)
            results.append(result)

            if not result.get("success", False):
                task["status"] = "ERROR"
                task["error"] = (
                    result.get("reason")
                    or result.get("stderr")
                )
                task["result"] = results

                return {
                    "success": False,
                    "task": task,
                }

        task["status"] = "COMPLETE"
        task["result"] = results

        return {
            "success": True,
            "task": task,
        }

    def status_summary(self):
        return {
            "total": len(self.tasks),
            "pending": sum(
                t["status"] == "PENDING"
                for t in self.tasks.values()
            ),
            "running": sum(
                t["status"] == "RUNNING"
                for t in self.tasks.values()
            ),
            "complete": sum(
                t["status"] == "COMPLETE"
                for t in self.tasks.values()
            ),
            "error": sum(
                t["status"] == "ERROR"
                for t in self.tasks.values()
            ),
        }
