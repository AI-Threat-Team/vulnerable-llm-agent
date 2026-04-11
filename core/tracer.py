"""
Tracer — structured event log
==============================
Writes JSON-lines events to a log file. Each event has:
  - timestamp (ISO 8601)
  - event type
  - session_id
  - payload (event-specific data)

The debug terminal reads this file with `tail -f` or `python debug.py`.
The user terminal never sees trace output.

This module does ONE thing: append JSON lines to a file.
"""

import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


class Tracer:
    """Append-only structured event logger."""

    def __init__(self, log_path: str | None = None):
        self.log_path = Path(
            log_path or os.getenv("TRACE_LOG", "logs/trace.jsonl")
        )
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        self._session_id = "unknown"

    def set_session(self, session_id: str):
        self._session_id = session_id

    def _emit(self, event_type: str, data: dict[str, Any]):
        """Write a single JSON-line event to the log file."""
        event = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "event": event_type,
            "session": self._session_id,
            **data,
        }
        line = json.dumps(event, ensure_ascii=False, default=str)
        with open(self.log_path, "a") as f:
            f.write(line + "\n")

    # ------------------------------------------------------------------
    # Event emitters — one method per event type
    # ------------------------------------------------------------------

    def step_start(self, step: int, max_steps: int):
        self._emit("step_start", {"step": step, "max_steps": max_steps})

    def prompt(self, messages: list[dict]):
        """Log the full prompt sent to the LLM."""
        self._emit("prompt", {
            "message_count": len(messages),
            "messages": messages,
            "total_chars": sum(len(str(m.get("content", ""))) for m in messages),
        })

    def llm_request(self, payload: dict):
        """Log the outgoing LLM API request (without messages, to avoid duplication)."""
        summary = {
            k: v for k, v in payload.items()
            if k not in ("messages",)
        }
        self._emit("llm_request", {"payload_summary": summary})

    def llm_response(self, raw_response: dict, elapsed_ms: float):
        """Log the raw LLM response."""
        self._emit("llm_response", {
            "raw": raw_response,
            "elapsed_ms": round(elapsed_ms, 1),
        })

    def tool_call(self, tool_name: str, arguments: dict, call_id: str):
        self._emit("tool_call", {
            "tool": tool_name,
            "arguments": arguments,
            "call_id": call_id,
        })

    def tool_result(self, tool_name: str, result: str, call_id: str,
                    elapsed_ms: float):
        self._emit("tool_result", {
            "tool": tool_name,
            "result": result,
            "call_id": call_id,
            "elapsed_ms": round(elapsed_ms, 1),
        })

    def guardrail(self, tool_name: str, action: str, reason: str):
        """Log a guardrail decision (allow or deny)."""
        self._emit("guardrail", {
            "tool": tool_name,
            "action": action,
            "reason": reason,
        })

    def agent_state(self, step: int, tools_called: list[str],
                    memory_files: list[str], history_length: int,
                    security_mode: str):
        self._emit("agent_state", {
            "step": step,
            "security_mode": security_mode,
            "tools_called": tools_called,
            "memory_files": memory_files,
            "history_length": history_length,
        })

    def final_answer(self, answer: str):
        self._emit("final_answer", {"answer": answer})

    def error(self, error: str, context: str = ""):
        self._emit("error", {"error": error, "context": context})

    def user_input(self, text: str):
        self._emit("user_input", {"text": text})

    def session_switch(self, old_id: str, new_id: str):
        self._emit("session_switch", {"from": old_id, "to": new_id})

    def config_change(self, key: str, old_value: Any, new_value: Any):
        self._emit("config_change", {
            "key": key, "old": old_value, "new": new_value,
        })


# Module-level singleton — importable anywhere
_tracer: Tracer | None = None


def get_tracer(log_path: str | None = None) -> Tracer:
    """Get or create the global tracer instance."""
    global _tracer
    if _tracer is None:
        _tracer = Tracer(log_path)
    return _tracer
