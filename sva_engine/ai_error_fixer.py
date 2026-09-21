"""AI-powered structured error analysis and fix proposal."""

from __future__ import annotations

import json


class AIErrorFixer:
    """Ask an AI client for a safe, structured fix suggestion."""

    def __init__(self, ai_client):
        self.ai_client = ai_client

    def build_prompt(self, command, error):
        return (
            "Analyze this command failure and suggest a safe executable fix.\n"
            "Return ONLY valid JSON in exactly this format:\n"
            '{"analysis":"...","fix":"...","retry":true}\n\n'
            "Rules:\n"
            "- analysis must explain the likely cause.\n"
            "- fix must contain one concrete proposed command or action.\n"
            "- retry must be true only when retrying after the fix makes sense.\n"
            "- Never suggest destructive or dangerous actions.\n\n"
            f"Command: {command}\n"
            f"Error: {error}"
        )

    def suggest_fix(self, command, error):
        if not isinstance(command, str) or not command.strip():
            return {
                "success": False,
                "reason": "Command is required",
            }

        if not isinstance(error, str) or not error.strip():
            return {
                "success": False,
                "reason": "Error is required",
            }

        result = self.ai_client.ask(
            self.build_prompt(command.strip(), error.strip())
        )

        if not result.get("success", False):
            return {
                "success": False,
                "reason": result.get("error") or "AI fix analysis failed",
            }

        response = result.get("response", "")

        try:
            data = json.loads(response)
        except (TypeError, json.JSONDecodeError) as exc:
            return {
                "success": False,
                "reason": f"Invalid AI fixer JSON: {exc}",
                "raw_response": response,
            }

        if not isinstance(data, dict):
            return {
                "success": False,
                "reason": "AI fixer JSON must be an object",
                "raw_response": response,
            }

        analysis = data.get("analysis")
        fix = data.get("fix")
        retry = data.get("retry")

        if not isinstance(analysis, str) or not analysis.strip():
            return {
                "success": False,
                "reason": "Missing or invalid field: analysis",
                "raw_response": response,
            }

        if not isinstance(fix, str) or not fix.strip():
            return {
                "success": False,
                "reason": "Missing or invalid field: fix",
                "raw_response": response,
            }

        if not isinstance(retry, bool):
            return {
                "success": False,
                "reason": "Missing or invalid field: retry",
                "raw_response": response,
            }

        return {
            "success": True,
            "analysis": analysis.strip(),
            "fix": fix.strip(),
            "retry": retry,
            "response": response,
        }
