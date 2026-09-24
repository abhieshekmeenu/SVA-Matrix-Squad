import json


ALLOWED_ACTIONS = {
    "write_file",
    "patch_file",
    "read_file",
    "run",
    "verify",
}


class AIPlanner:
    """Convert a natural-language task into structured executable actions."""

    def __init__(self, ai_client):
        self.ai_client = ai_client

    def build_prompt(self, task):
        return (
            "You are the SVA Matrix Squad task planner.\n"
            "Convert the user's task into a safe, ordered execution plan.\n\n"
            "Return ONLY valid JSON. No Markdown. No explanation.\n\n"
            "Format:\n"
            "{"
            '"task":"short task name",'
            '"steps":['
            '{"action":"write_file","path":"main.py","content":"..."},'
            '{"action":"run","command":"python main.py"},'
            '{"action":"verify","expect":"describe expected result"}'
            "]"
            "}\n\n"
            "Allowed actions ONLY:\n"
            "- write_file: create or replace a file inside the project workspace\n"
            "- patch_file: replace one exact block inside an existing file\n"
            "- read_file: read a file inside the project workspace\n"
            "- run: run a benign local project command inside the project workspace\n"
            "- verify: check whether the previous result satisfies the expected result\n\n"
            "Rules:\n"
            "1. Never use absolute file paths.\n"
            "2. File paths must stay inside the project workspace.\n"
            "3. Do not use destructive system commands.\n"
            "4. Do not install packages or modify the Android/Termux system.\n"
            "5. Keep commands focused on the current project.\n"
            "6. For coding tasks, write the required files before running them.\n"
            "7. A project may contain many files and nested folders; create the structure needed by the task.\n"
            "8. Choose a concise safe project_name based on the user requirement.\n"
            "9. If the user gives an existing project path, treat that path as the workspace to inspect and repair.\n"
            "10. Inspect existing files before proposing fixes when the task is an existing-project repair.\n"
            "11. For an existing-file bug fix, prefer patch_file after reading the file instead of rewriting the whole file.\n"
            "12. patch_file requires path, old, and new fields, and old must identify one exact block.\n"
            "13. Include a verify step after an important run.\n\n"
            f"User task:\n{task}"
        )

    @staticmethod
    def _parse_json_response(response):
        """Parse JSON from a model response without weakening validation."""
        if not isinstance(response, str):
            return None

        candidate = response.strip()

        if not candidate:
            return None

        # Normal JSON response.
        try:
            return json.loads(candidate)
        except json.JSONDecodeError:
            pass

        # Remove Markdown JSON fences if the model added them.
        if candidate.startswith("```") and candidate.endswith("```"):
            lines = candidate.splitlines()
            if len(lines) >= 3:
                candidate = "\n".join(lines[1:-1]).strip()
                try:
                    return json.loads(candidate)
                except json.JSONDecodeError:
                    pass

        # Extract the outermost JSON object when the model added text
        # before or after the JSON.
        start = candidate.find("{")
        end = candidate.rfind("}")

        if start != -1 and end > start:
            candidate = candidate[start:end + 1]

            try:
                return json.loads(candidate)
            except json.JSONDecodeError:
                pass

            # Recover one common extra-closing-brace error.
            if candidate.endswith("}}"):
                try:
                    return json.loads(candidate[:-1])
                except json.JSONDecodeError:
                    pass

            # Recover the existing malformed steps-array pattern.
            marker = ']}},{"action":"run"'
            repaired = candidate.replace(
                marker,
                '}},{"action":"run"',
                1,
            )

            if repaired != candidate:
                try:
                    return json.loads(repaired)
                except json.JSONDecodeError:
                    pass

        return None

    def plan(self, task):
        if not task or not task.strip():
            return {
                "success": False,
                "reason": "Empty task",
                "task": task,
                "steps": [],
            }

        result = self.ai_client.ask(self.build_prompt(task))

        if not result.get("success", False):
            return {
                "success": False,
                "reason": (
                    result.get("error")
                    or result.get("reason")
                    or "AI planning failed"
                ),
                "task": task,
                "steps": [],
            }

        response = result.get("response", "")
        data = self._parse_json_response(response)

        # If the model produced malformed JSON, ask it once more for a
        # strict JSON-only response instead of immediately failing the task.
        if data is None:
            retry_prompt = (
                "Your previous planner response was invalid JSON.\n"
                "Return ONLY one valid JSON object.\n"
                "Do not use Markdown fences.\n"
                "Do not add explanations.\n"
                "Preserve the requested task and create safe executable steps.\n\n"
                f"User task:\n{task}"
            )

            retry_result = self.ai_client.ask(retry_prompt)

            if retry_result.get("success", False):
                retry_response = retry_result.get("response", "")
                data = self._parse_json_response(retry_response)

                if data is not None:
                    response = retry_response

        if data is None:
            return {
                "success": False,
                "reason": "Planner returned invalid JSON after automatic retry",
                "task": task,
                "steps": [],
                "raw_response": response,
            }

        if not isinstance(data, dict):
            return {
                "success": False,
                "reason": "Planner response must be a JSON object",
                "task": task,
                "steps": [],
                "raw_response": response,
            }

        steps = data.get("steps")

        if not isinstance(steps, list) or not steps:
            return {
                "success": False,
                "reason": "Planner JSON contains no steps",
                "task": task,
                "steps": [],
                "raw_response": response,
            }

        clean_steps = []

        for index, step in enumerate(steps, start=1):
            if not isinstance(step, dict):
                return {
                    "success": False,
                    "reason": f"Step {index} is not an object",
                    "task": task,
                    "steps": [],
                    "raw_response": response,
                }

            action = step.get("action")

            if action not in ALLOWED_ACTIONS:
                return {
                    "success": False,
                    "reason": (
                        f"Step {index} has unsupported action: "
                        f"{action!r}"
                    ),
                    "task": task,
                    "steps": [],
                    "raw_response": response,
                }

            clean_step = {
                "action": action,
            }

            if action in {"write_file", "read_file", "patch_file"}:
                path = step.get("path")

                if not isinstance(path, str) or not path.strip():
                    return {
                        "success": False,
                        "reason": f"Step {index} requires a file path",
                        "task": task,
                        "steps": [],
                        "raw_response": response,
                    }

                if path.startswith("/") or ".." in path.split("/"):
                    return {
                        "success": False,
                        "reason": f"Step {index} contains an unsafe path",
                        "task": task,
                        "steps": [],
                        "raw_response": response,
                    }

                clean_step["path"] = path

            if action == "patch_file":
                old_text = step.get("old")
                new_text = step.get("new", "")

                if not isinstance(old_text, str) or not old_text:
                    return {
                        "success": False,
                        "reason": f"Step {index} requires patch old text",
                        "task": task,
                        "steps": [],
                        "raw_response": response,
                    }

                if not isinstance(new_text, str):
                    return {
                        "success": False,
                        "reason": f"Step {index} requires patch new text",
                        "task": task,
                        "steps": [],
                        "raw_response": response,
                    }

                clean_step["old"] = old_text
                clean_step["new"] = new_text

            if action == "write_file":
                content = step.get("content")

                if not isinstance(content, str):
                    return {
                        "success": False,
                        "reason": f"Step {index} requires file content",
                        "task": task,
                        "steps": [],
                        "raw_response": response,
                    }

                clean_step["content"] = content

            if action == "run":
                command = step.get("command")

                if not isinstance(command, str) or not command.strip():
                    return {
                        "success": False,
                        "reason": f"Step {index} requires a command",
                        "task": task,
                        "steps": [],
                        "raw_response": response,
                    }

                clean_step["command"] = command

                command_input = step.get("input")
                if command_input is not None:
                    if not isinstance(command_input, str):
                        return {
                            "success": False,
                            "reason": f"Step {index} requires string input",
                            "task": task,
                            "steps": [],
                            "raw_response": response,
                        }
                    clean_step["input"] = command_input

            if action == "verify":
                expect = step.get("expect", "")

                if not isinstance(expect, str):
                    expect = str(expect)

                clean_step["expect"] = expect

            clean_steps.append(clean_step)

        project_name = data.get("project_name")

        if not isinstance(project_name, str) or not project_name.strip():
            project_name = "sva-task"

        project_name = project_name.strip()

        if (
            project_name in {".", ".."}
            or project_name.startswith(".")
            or "/" in project_name
            or "\\" in project_name
            or ".." in project_name
        ):
            return {
                "success": False,
                "reason": "Planner returned an unsafe project_name",
                "task": task,
                "steps": [],
                "raw_response": response,
            }

        return {
            "success": True,
            "project_name": project_name,
            "task": data.get("task", task),
            "steps": clean_steps,
        }
