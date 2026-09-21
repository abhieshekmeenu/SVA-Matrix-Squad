from __future__ import annotations

import subprocess
import time
from pathlib import Path
from typing import Sequence


class TestRunner:
    """Controlled runner for planned project checks."""

    def __init__(self, project_path: str | Path, timeout: int = 120):
        self.project_path = Path(project_path).expanduser().resolve()
        self.timeout = max(1, int(timeout))

    def run(self, argv: Sequence[str], *, step_id: str = "unknown") -> dict[str, object]:
        if not argv:
            raise ValueError("Command argv cannot be empty")

        if not self.project_path.is_dir():
            raise ValueError(
                f"Project directory does not exist: {self.project_path}"
            )

        command = [str(item) for item in argv]
        started = time.monotonic()

        try:
            result = subprocess.run(
                command,
                cwd=self.project_path,
                capture_output=True,
                text=True,
                timeout=self.timeout,
            )

            duration_ms = int((time.monotonic() - started) * 1000)

            return {
                "success": result.returncode == 0,
                "step_id": step_id,
                "argv": command,
                "returncode": result.returncode,
                "stdout": result.stdout,
                "stderr": result.stderr,
                "duration_ms": duration_ms,
                "timed_out": False,
            }

        except subprocess.TimeoutExpired as exc:
            duration_ms = int((time.monotonic() - started) * 1000)

            stdout = exc.stdout or ""
            stderr = exc.stderr or ""

            if isinstance(stdout, bytes):
                stdout = stdout.decode(errors="replace")

            if isinstance(stderr, bytes):
                stderr = stderr.decode(errors="replace")

            return {
                "success": False,
                "step_id": step_id,
                "argv": command,
                "returncode": None,
                "stdout": stdout,
                "stderr": stderr,
                "duration_ms": duration_ms,
                "timed_out": True,
                "error": f"Command timed out after {self.timeout}s",
            }

        except OSError as exc:
            duration_ms = int((time.monotonic() - started) * 1000)

            return {
                "success": False,
                "step_id": step_id,
                "argv": command,
                "returncode": None,
                "stdout": "",
                "stderr": str(exc),
                "duration_ms": duration_ms,
                "timed_out": False,
                "error": str(exc),
            }
