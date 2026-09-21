from __future__ import annotations


class FailureParser:
    """Classify structured test-runner failures."""

    def parse(self, result: dict[str, object]) -> dict[str, object]:
        if not isinstance(result, dict):
            raise ValueError("Result must be a dictionary")

        if result.get("success") is True:
            return {
                "failed": False,
                "category": None,
                "severity": "none",
                "summary": "Test step passed",
                "evidence": "",
            }

        stderr = str(result.get("stderr") or "")
        stdout = str(result.get("stdout") or "")
        error = str(result.get("error") or "")
        returncode = result.get("returncode")
        timed_out = bool(result.get("timed_out"))

        evidence = "\n".join(
            part for part in (error, stderr, stdout) if part
        ).strip()

        if timed_out:
            category = "timeout"
            severity = "high"
            summary = "Test command exceeded the configured timeout"

        elif returncode is None and (
            "No such file or directory" in evidence
            or "not found" in evidence.lower()
        ):
            category = "command_unavailable"
            severity = "high"
            summary = "Required test command or executable is unavailable"

        elif "SyntaxError" in evidence:
            category = "syntax_error"
            severity = "high"
            summary = "Python syntax error detected"

        elif "ImportError" in evidence or "ModuleNotFoundError" in evidence:
            category = "dependency_error"
            severity = "high"
            summary = "Python import or dependency error detected"

        elif "FAILED" in evidence or "ERROR" in evidence:
            category = "test_failure"
            severity = "medium"
            summary = "Test framework reported a failure or error"

        elif returncode not in (None, 0):
            category = "command_failure"
            severity = "medium"
            summary = f"Test command exited with code {returncode}"

        else:
            category = "unknown"
            severity = "medium"
            summary = "Test step failed for an unknown reason"

        return {
            "failed": True,
            "category": category,
            "severity": severity,
            "summary": summary,
            "evidence": evidence[-5000:],
            "returncode": returncode,
            "timed_out": timed_out,
        }
