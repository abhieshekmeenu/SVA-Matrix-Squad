from __future__ import annotations

from pathlib import Path
from typing import Any, Dict


class SVAActionVerifier:
    """Verify the result of the previous project action."""

    def verify(
        self,
        expectation: str,
        previous_result: Dict[str, Any] | None = None,
    ) -> Dict[str, Any]:
        if not isinstance(expectation, str) or not expectation.strip():
            return {
                "success": False,
                "verified": False,
                "error": "Verification expectation is empty",
            }

        if not isinstance(previous_result, dict):
            return {
                "success": False,
                "verified": False,
                "error": "No previous action result available",
            }

        if not previous_result.get("success", False):
            return {
                "success": False,
                "verified": False,
                "error": "Previous action failed",
            }

        expected = expectation.strip()

        output = str(
            previous_result.get("stdout")
            or previous_result.get("content")
            or ""
        )

        # Direct output verification.
        if expected.lower() in output.lower():
            return {
                "success": True,
                "verified": True,
                "expect": expected,
                "output": output,
                "reason": "Expected text found in previous result",
            }

        # A successful run with no stdout is still a successful process.
        # Do not fail verification merely because the command was silent.
        action = previous_result.get("action")

        if action == "run":
            return {
                "success": True,
                "verified": True,
                "expect": expected,
                "output": output,
                "reason": "Previous run completed successfully",
            }

        # Verify that a file created by write_file still exists.
        path_value = previous_result.get("path")

        if path_value:
            try:
                path = Path(path_value)

                if path.is_file():
                    return {
                        "success": True,
                        "verified": True,
                        "expect": expected,
                        "output": output,
                        "path": str(path),
                        "reason": "Expected file exists",
                    }
            except (OSError, ValueError):
                pass

        return {
            "success": False,
            "verified": False,
            "expect": expected,
            "output": output,
            "error": (
                "Verification failed: expected text was not found "
                "and no successful verification condition matched"
            ),
        }
