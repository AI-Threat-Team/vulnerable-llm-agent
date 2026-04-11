"""
LLM Client — OpenAI-compatible HTTP caller
===========================================
Pure function: takes messages + tools, returns response dict.
No printing, no state beyond connection config.
"""

import json
import os
import time
import requests
from typing import Optional


class LLMClient:

    def __init__(self):
        self.base_url = os.getenv("LLM_BASE_URL", "http://localhost:8080/v1")
        self.model = os.getenv("LLM_MODEL", "gpt-3.5-turbo")
        self.api_key = os.getenv("LLM_API_KEY", "not-needed")
        self.temperature = float(os.getenv("TEMPERATURE", "0.7"))

    def chat(self, messages: list[dict],
             tools: Optional[list[dict]] = None) -> tuple[dict, float]:
        """
        Call the LLM.
        Returns (response_dict, elapsed_ms).
        response_dict has either normal API shape or {"error": "..."}.
        """
        url = f"{self.base_url}/chat/completions"
        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": self.temperature,
        }
        if tools:
            payload["tools"] = tools

        headers = {"Content-Type": "application/json"}
        if self.api_key and self.api_key != "not-needed":
            headers["Authorization"] = f"Bearer {self.api_key}"

        t0 = time.monotonic()
        try:
            resp = requests.post(url, headers=headers, json=payload, timeout=120)
            elapsed = (time.monotonic() - t0) * 1000
            resp.raise_for_status()
            return resp.json(), elapsed
        except requests.exceptions.ConnectionError:
            elapsed = (time.monotonic() - t0) * 1000
            return {"error": f"Cannot connect to LLM at {url}"}, elapsed
        except requests.exceptions.Timeout:
            elapsed = (time.monotonic() - t0) * 1000
            return {"error": "LLM request timed out (120s)"}, elapsed
        except requests.exceptions.HTTPError as e:
            elapsed = (time.monotonic() - t0) * 1000
            return {"error": f"HTTP {resp.status_code}: {resp.text}"}, elapsed
        except Exception as e:
            elapsed = (time.monotonic() - t0) * 1000
            return {"error": f"{type(e).__name__}: {e}"}, elapsed

    @staticmethod
    def extract(raw: dict) -> dict:
        """
        Parse the API response into a normalized dict:
          content:    str | None
          tool_calls: list | None
          error:      str | None
        """
        if "error" in raw:
            return {"content": None, "tool_calls": None, "error": raw["error"]}
        try:
            msg = raw["choices"][0]["message"]
            return {
                "content": msg.get("content"),
                "tool_calls": msg.get("tool_calls"),
                "error": None,
            }
        except (KeyError, IndexError) as e:
            return {"content": None, "tool_calls": None,
                    "error": f"Bad response shape: {e}"}
