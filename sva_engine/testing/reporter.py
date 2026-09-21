from __future__ import annotations


class TestReporter:
    """Build a stable summary from universal testing results."""

    def build(
        self,
        *,
        project: str,
        detection: dict[str, object],
        results: list[dict[str, object]],
    ) -> dict[str, object]:
        passed = sum(
            1
            for item in results
            if item.get("success") is True
        )

        failed = len(results) - passed

        return {
            "project": project,
            "languages": detection.get("languages", []),
            "total": len(results),
            "passed": passed,
            "failed": failed,
            "success": failed == 0,
            "results": results,
        }

    def text(self, report: dict[str, object]) -> str:
        lines = [
            "SVA UNIVERSAL TEST REPORT",
            "=" * 28,
            f"Project: {report.get('project', '')}",
            f"Languages: {', '.join(report.get('languages', []))}",
            "",
            f"Total:  {report.get('total', 0)}",
            f"Passed: {report.get('passed', 0)}",
            f"Failed: {report.get('failed', 0)}",
            "",
        ]

        for item in report.get("results", []):
            status = "PASS" if item.get("success") else "FAIL"
            step_id = item.get("step_id", "unknown")
            lines.append(f"[{status}] {step_id}")

        lines.append("")
        lines.append(
            "Overall: PASS"
            if report.get("success")
            else "Overall: FAIL"
        )

        return "\n".join(lines)
