"""SVA Matrix Squad code analysis and real test engine."""

from __future__ import annotations

import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any


class CodeDebugger:
    """Analyze code and collect real local test/syntax results."""

    def __init__(self, ai_client=None):
        self.ai_client = ai_client

    def check_python(self, code: str) -> dict[str, Any]:
        """Run a real Python syntax/compile check."""
        if not isinstance(code, str) or not code.strip():
            return {
                "success": False,
                "error": "No Python code provided.",
            }

        temp_path = None

        try:
            with tempfile.NamedTemporaryFile(
                mode="w",
                suffix=".py",
                encoding="utf-8",
                delete=False,
            ) as handle:
                handle.write(code)
                temp_path = Path(handle.name)

            result = subprocess.run(
                [sys.executable, "-m", "py_compile", str(temp_path)],
                capture_output=True,
                text=True,
                timeout=30,
            )

            return {
                "success": result.returncode == 0,
                "returncode": result.returncode,
                "stdout": result.stdout.strip(),
                "stderr": result.stderr.strip(),
                "command": (
                    f"{sys.executable} -m py_compile "
                    f"{temp_path.name}"
                ),
            }

        except subprocess.TimeoutExpired:
            return {
                "success": False,
                "returncode": -1,
                "stdout": "",
                "stderr": "Python compile check timed out.",
            }

        except Exception as error:
            return {
                "success": False,
                "returncode": -1,
                "stdout": "",
                "stderr": str(error),
            }

        finally:
            if temp_path is not None:
                try:
                    temp_path.unlink(missing_ok=True)
                except OSError:
                    pass

    def build_prompt(
        self,
        question: str,
        code: str,
        test_result: dict[str, Any],
    ) -> str:
        return (
            "You are the SVA Matrix Squad Code Debugger.\n"
            "Analyze the user's code using the REAL test result below.\n"
            "Do not invent errors or test output.\n\n"
            "Return EXACTLY these sections:\n"
            "BUG / PROBLEM\n"
            "WHY\n"
            "EXACT FIX\n"
            "FIXED CODE\n"
            "HOW TO TEST\n\n"
            "In FIXED CODE, provide the COMPLETE corrected Python code "
            "inside one Python code block. Do not omit unchanged lines.\n"
            "If the code has no bug, FIXED CODE must contain the original "
            "code unchanged.\n\n"
            f"User question:\n{question}\n\n"
            f"Code supplied by the user:\n{code}\n\n"
            "IMPORTANT: The temporary filename used by the test runner "
            "is not the user's project filename. Do not claim that it is.\n"
            f"REAL TEST RESULT:\n{test_result}\n"
        )

    def debug(
        self,
        question: str,
        code: str,
    ) -> dict[str, Any]:
        """Collect a real result and optionally ask the configured AI."""
        test_result = self.check_python(code)

        response = {
            "success": test_result.get("success", False),
            "test_result": test_result,
        }

        if self.ai_client is None:
            response["analysis"] = ""
            return response

        prompt = self.build_prompt(
            question,
            code,
            test_result,
        )

        try:
            ai_result = self.ai_client.ask(prompt)
        except Exception as error:
            response["ai_error"] = str(error)
            response["analysis"] = ""
            return response

        if isinstance(ai_result, dict):
            if ai_result.get("success"):
                response["analysis"] = ai_result.get("response", "")
            else:
                response["analysis"] = ""
                response["ai_error"] = ai_result.get(
                    "error",
                    "AI request failed.",
                )
        else:
            response["analysis"] = str(ai_result or "")

        return response
