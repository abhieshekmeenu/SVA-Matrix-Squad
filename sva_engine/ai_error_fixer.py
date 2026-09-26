"""AI-powered structured error analysis and safe repair proposals."""

from __future__ import annotations

import json

from .testing.repair import RepairProposal, proposal_from_dict


class AIErrorFixer:
    """Ask the existing SVA AI client for structured repair proposals."""

    def __init__(self, ai_client, *, repair_retries=1):
        self.ai_client = ai_client
        if not isinstance(repair_retries, int) or repair_retries < 0:
            raise ValueError("repair_retries must be a non-negative integer")
        self.repair_retries = repair_retries

    @staticmethod
    def _parse_json(response: str) -> dict[str, object]:
        text = response.strip()

        if text.startswith("```"):
            lines = text.splitlines()
            lines = [
                line for line in lines
                if line.strip().lower() not in {"```json", "```"}
            ]
            text = "\n".join(lines).strip()

        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            start = text.find("{")
            end = text.rfind("}")

            if start < 0 or end <= start:
                raise

            data = json.loads(text[start:end + 1])

        if not isinstance(data, dict):
            raise ValueError("AI response must be a JSON object")

        return data

    def build_repair_prompt(self, command, error, failure=None):
        failure_text = json.dumps(
            failure or {},
            ensure_ascii=False,
        )

        return (
            "Analyze the failed project test and propose a SAFE file repair.\n"
            "Return ONLY valid JSON. No Markdown.\n\n"
            "Required JSON format:\n"
            "{\n"
            '  "failure_category": "syntax|test|dependency|runtime|unknown",\n'
            '  "diagnosis": "likely cause",\n'
            '  "fix_type": "patch_file|write_file",\n'
            '  "confidence": 0.0,\n'
            '  "requires_approval": true,\n'
            '  "actions": [\n'
            "    {\n"
            '      "action": "patch_file",\n'
            '      "path": "relative/path.py",\n'
            '      "old_text": "exact existing text",\n'
            '      "new_text": "replacement text"\n'
            "    }\n"
            "  ]\n"
            "}\n\n"
            "Rules:\n"
            "- Only repair files inside the project workspace.\n"
            "- Use relative file paths only.\n"
            "- Never use absolute paths.\n"
            "- Never use '..' paths.\n"
            "- Prefer patch_file when an exact existing code section is known.\n"
            "- Use write_file only when creating a genuinely missing file.\n"
            "- old_text must match exactly one existing occurrence.\n"
            "- Do not delete the project, repository, or unrelated files.\n"
            "- Do not modify secrets, API keys, credentials, or private data.\n"
            "- Do not suggest destructive commands.\n"
            "- Keep the repair minimal.\n"
            "- Set requires_approval=true for the repair proposal.\n"
            "- If a safe file repair cannot be determined, return actions as [].\n\n"
            f"Failed command: {command}\n"
            f"Failure observation: {failure_text}\n"
            f"Error output:\n{error}\n"
        )

    def propose_repair(
        self,
        command,
        error,
        failure=None,
    ) -> RepairProposal:
        if not isinstance(command, str) or not command.strip():
            raise ValueError("Command is required")

        if not isinstance(error, str) or not error.strip():
            raise ValueError("Error is required")

        base_prompt = self.build_repair_prompt(
            command.strip(),
            error.strip(),
            failure,
        )

        prompt = base_prompt
        last_error = None

        for attempt in range(self.repair_retries + 1):
            result = self.ai_client.ask(prompt)

            if not result.get("success", False):
                last_error = (
                    result.get("error")
                    or "AI repair analysis failed"
                )
            else:
                response = str(result.get("response") or "")

                try:
                    data = self._parse_json(response)
                    return proposal_from_dict(data)
                except (TypeError, ValueError, json.JSONDecodeError) as exc:
                    last_error = exc

                    if attempt < self.repair_retries:
                        prompt = (
                            "Your previous response did not satisfy the "
                            "required repair JSON contract.\n"
                            "Return ONLY one valid JSON object. No explanation, "
                            "no Markdown, and no text before or after the JSON.\n\n"
                            "Use the exact schema and safety rules from the "
                            "original repair request.\n\n"
                            f"Original repair request:\n{base_prompt}\n\n"
                            f"Previous invalid response:\n{response}\n\n"
                            f"Parser error: {exc}"
                        )

        raise RuntimeError(
            "AI repair analysis failed after "
            f"{self.repair_retries + 1} attempt(s): {last_error}"
        )

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
        """Backward-compatible command-fix interface."""

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
            data = self._parse_json(str(response))
        except (TypeError, ValueError, json.JSONDecodeError) as exc:
            return {
                "success": False,
                "reason": f"Invalid AI fixer JSON: {exc}",
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
