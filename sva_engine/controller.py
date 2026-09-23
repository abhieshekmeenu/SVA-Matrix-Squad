from __future__ import annotations

from pathlib import Path
import subprocess
import time


class SVAController:
    """Safe project-scoped controller for SVA Task Agent."""

    def __init__(self, store):
        self.store = store
        self.project_id = None

    def set_project(self, project_id: str) -> None:
        self.project_id = project_id

    def _workspace(self) -> Path:
        if not self.project_id:
            raise RuntimeError("No project selected")
        return self.store.workspace_dir(self.project_id)

    def execute(
        self,
        command: str,
        task_id: str | None = None,
        input_data: str | None = None,
    ):
        workspace = self._workspace()

        print(f"\\n🔄 COMMAND: {command}", flush=True)
        print(f"📂 WORKSPACE: {workspace}", flush=True)

        if input_data is not None:
            print("⌨️ INPUT PROVIDED", flush=True)
        else:
            print("⏳ Running...", flush=True)

        started = time.monotonic()

        try:
            result = subprocess.run(
                ["bash", "-lc", command],
                cwd=workspace,
                input=input_data,
                capture_output=True,
                text=True,
                timeout=120,
            )
        except subprocess.TimeoutExpired as exc:
            elapsed = int(time.monotonic() - started)
            print(f"\\n⏱️ TIMEOUT after {elapsed}s", flush=True)
            print("💡 Command may be waiting for input.", flush=True)

            stdout = exc.stdout or ""
            stderr = exc.stderr or "Command timed out after 120 seconds"

            return {
                "success": False,
                "returncode": None,
                "stdout": stdout,
                "stderr": stderr,
                "command": command,
                "timeout": True,
            }

        elapsed = int(time.monotonic() - started)
        print(f"\\n✅ COMMAND FINISHED ({elapsed}s)", flush=True)

        if result.stdout.strip():
            print("📤 OUTPUT:", flush=True)
            print(result.stdout.rstrip(), flush=True)

        if result.stderr.strip():
            print("⚠️ STDERR:", flush=True)
            print(result.stderr.rstrip(), flush=True)

        return {
            "success": result.returncode == 0,
            "returncode": result.returncode,
            "stdout": result.stdout,
            "stderr": result.stderr,
            "command": command,
        }
