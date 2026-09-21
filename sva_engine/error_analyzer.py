import json


class ErrorAnalyzer:
    """Analyze command failures and return a structured fix suggestion."""

    def __init__(self, ai_client=None):
        self.ai_client = ai_client

    def build_prompt(self, command, error):
        return (
            "Analyze this command failure.\n"
            "Return ONLY valid JSON:\n"
            '{"error":"...","cause":"...","fix":"..."}\n\n'
            f"Command:\n{command}\n\n"
            f"Error:\n{error}"
        )

    def analyze(self, command, result=None):
        if not command or not command.strip():
            return {"success": False, "reason": "Empty command"}

        if result is None:
            return {"success": False, "reason": "Empty result"}

        if isinstance(result, dict):
            error = result.get("stderr") or result.get("reason") or "Unknown error"
        else:
            error = str(result)

        if not str(error).strip():
            return {"success": False, "reason": "Empty error"}

        if self.ai_client is None:
            return {
                "success": True,
                "error": str(error),
                "cause": "AI client not configured",
                "fix": "Review the command error and provide a safe correction",
            }

        result = self.ai_client.ask(
            self.build_prompt(command, str(error))
        )

        if not result.get("success", False):
            return {
                "success": False,
                "reason": result.get("error") or "AI error analysis failed",
            }

        try:
            data = json.loads(result.get("response", ""))
        except (TypeError, json.JSONDecodeError) as exc:
            return {
                "success": False,
                "reason": f"Invalid analyzer JSON: {exc}",
            }

        for key in ("error", "cause", "fix"):
            if not isinstance(data.get(key), str) or not data[key].strip():
                return {
                    "success": False,
                    "reason": f"Missing or invalid field: {key}",
                }

        return {
            "success": True,
            "error": data["error"],
            "cause": data["cause"],
            "fix": data["fix"],
        }

AIErrorAnalyzer = ErrorAnalyzer
