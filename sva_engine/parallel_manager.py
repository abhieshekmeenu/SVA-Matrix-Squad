from concurrent.futures import ThreadPoolExecutor


class ParallelTaskManager:
    """Run independent JARVIS tasks concurrently with file-conflict protection."""

    def __init__(self, task_manager, max_workers=3):
        self.task_manager = task_manager
        self.max_workers = max_workers
        self.file_owners = {}

    def claim_files(self, task_id, files):
        conflicts = []

        for file_path in files:
            owner = self.file_owners.get(file_path)

            if owner is not None and owner != task_id:
                conflicts.append({
                    "file": file_path,
                    "owner": owner,
                })

        if conflicts:
            return {
                "success": False,
                "conflicts": conflicts,
            }

        for file_path in files:
            self.file_owners[file_path] = task_id

        return {
            "success": True,
            "conflicts": [],
        }

    def release_files(self, task_id):
        self.file_owners = {
            path: owner
            for path, owner in self.file_owners.items()
            if owner != task_id
        }

    def run_tasks(self, task_ids):
        accepted = {}
        results = {}

        for task_id in task_ids:
            task = self.task_manager.get_task(task_id)

            if task is None:
                results[task_id] = {
                    "success": False,
                    "reason": "Task not found",
                }
                continue

            files = task.get("files", [])

            claim = self.claim_files(task_id, files)

            if not claim["success"]:
                results[task_id] = {
                    "success": False,
                    "reason": "File conflict",
                    "conflicts": claim["conflicts"],
                    "task": task,
                }
                continue

            accepted[task_id] = files

        if accepted:
            with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
                futures = {
                    task_id: executor.submit(
                        self.task_manager.run_task,
                        task_id
                    )
                    for task_id in accepted
                }

                for task_id, future in futures.items():
                    results[task_id] = future.result()

        for task_id in accepted:
            self.release_files(task_id)

        return results
