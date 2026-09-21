import json
from pathlib import Path

import requests


API_KEYS_FILE = Path.home() / ".sva_matrix_squad_api_keys.json"
ACTIVE_KEY_FILE = Path.home() / ".sva_matrix_squad_active_key"


class SVAAIClient:
    """OpenRouter client with automatic configured-key failover."""

    def __init__(self, api_key, api_url, model):
        self.api_key = api_key
        self.api_url = api_url
        self.model = model

    def _get_api_keys(self):
        keys = []

        try:
            if API_KEYS_FILE.exists():
                data = json.loads(API_KEYS_FILE.read_text())
                stored_keys = data.get("keys", [])

                if isinstance(stored_keys, list):
                    for item in stored_keys:
                        if isinstance(item, dict):
                            key = item.get("key", "").strip()
                            if key and key not in keys:
                                keys.append(key)
        except Exception:
            pass

        if self.api_key and self.api_key not in keys:
            keys.insert(0, self.api_key)

        return keys

    def ask(self, prompt):
        keys = self._get_api_keys()

        if not keys:
            return {
                "success": False,
                "error": "No API keys configured.",
            }

        last_error = "All configured API keys failed."

        # Start with the last known working configured key.
        start_index = 0
        try:
            saved_key = ACTIVE_KEY_FILE.read_text(
                encoding="utf-8"
            ).strip()
            if saved_key in keys:
                start_index = keys.index(saved_key)
        except (OSError, UnicodeError):
            pass

        ordered_keys = keys[start_index:] + keys[:start_index]

        for key_index, key in enumerate(ordered_keys, start=1):
            # Keep normal requests quiet.
            # The caller will report only an actual key failover.

            headers = {
                "Authorization": f"Bearer {key}",
                "Content-Type": "application/json",
                "HTTP-Referer": "https://github.com/Hackerscolonyofficial/SVA-Matrix",
                "X-Title": "SVA Matrix Squad",
            }

            payload = {
                "model": self.model,
                "messages": [
                    {
                        "role": "user",
                        "content": prompt,
                    }
                ],
                "max_tokens": 2000,
            }

            try:
                response = requests.post(
                    self.api_url,
                    headers=headers,
                    json=payload,
                    timeout=30,
                )

                print(
                    f"🤖 AI response: HTTP {response.status_code}"
                )

                try:
                    data = response.json()
                except ValueError:
                    data = {}

                if response.status_code == 200:
                    print("🤖 AI JSON keys:", list(data.keys()))

                    choices = data.get("choices", [])
                    print("🤖 AI choices count:", len(choices))

                    if choices:
                        print(
                            "🤖 AI choice keys:",
                            list(choices[0].keys())
                            if isinstance(choices[0], dict)
                            else type(choices[0]).__name__
                        )

                        message = choices[0].get("message", {})
                        if isinstance(message, dict):
                            print(
                                "🤖 AI message keys:",
                                list(message.keys())
                            )

                    answer = (
                        data.get("choices", [{}])[0]
                        .get("message", {})
                        .get("content")
                    )

                    if answer:
                        try:
                            ACTIVE_KEY_FILE.write_text(
                                key,
                                encoding="utf-8",
                            )
                        except OSError:
                            pass

                        return {
                            "success": True,
                            "response": answer,
                        }

                    last_error = "AI returned an empty response."
                    continue

                error_data = data.get("error", response.text)

                if response.status_code == 429:
                    last_error = (
                        f"OpenRouter HTTP 429: {error_data}"
                    )
                    continue

                last_error = (
                    f"OpenRouter HTTP {response.status_code}: "
                    f"{error_data}"
                )

                return {
                    "success": False,
                    "error": last_error,
                }

            except requests.RequestException as exc:
                last_error = f"AI request failed: {exc}"
                continue

        return {
            "success": False,
            "error": last_error,
        }
