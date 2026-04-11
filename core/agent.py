"""
Agent — the ReAct loop
======================
Pure logic: takes user input, drives LLM + tools, returns answer string.
All side effects go through the Tracer (writes to log file).
No printing to stdout/stderr — that's main.py's job.
"""

import json
import os
import time

from core.llm import LLMClient
from core.prompt import PromptAssembler
from core.session import Session
from core.tracer import Tracer
from tools.registry import get_schemas, execute


class Agent:

    def __init__(self, session: Session, workspace_root: str,
                 tracer: Tracer, config_path: str = "config.yaml"):
        self.session = session
        self.workspace_root = workspace_root
        self.tracer = tracer
        self.llm = LLMClient()
        self.prompt = PromptAssembler(config_path)
        self.max_iter = int(os.getenv("MAX_ITERATIONS", "10"))

    def _context(self) -> dict:
        """Build tool execution context."""
        return {
            "session": self.session,
            "session_id": self.session.session_id,
            "workspace_root": self.workspace_root,
            "security_mode": self.prompt.security_mode,
            "guardrails": self.prompt.guardrails,
        }

    def run(self, user_input: str) -> str:
        """
        Execute one user turn. Returns the final text answer.
        All intermediate state is logged via self.tracer.
        """
        self.prompt.reload()
        self.tracer.user_input(user_input)

        # Tool schemas
        schemas = get_schemas(self.prompt.enabled_tools)

        # Assemble messages
        messages = self.prompt.assemble(
            self.session, user_input, self.workspace_root
        )

        # Persist user message
        self.session.append_message("user", user_input)

        ctx = self._context()
        tools_called: list[str] = []

        for step in range(1, self.max_iter + 1):
            self.tracer.step_start(step, self.max_iter)
            self.tracer.prompt(messages)
            self.tracer.agent_state(
                step=step,
                tools_called=tools_called,
                memory_files=self.session.list_memory_files(),
                history_length=len(self.session.load_history()),
                security_mode=self.prompt.security_mode,
            )

            # --- LLM call ---
            raw, elapsed = self.llm.chat(messages, tools=schemas)
            self.tracer.llm_response(raw, elapsed)

            parsed = LLMClient.extract(raw)

            if parsed["error"]:
                self.tracer.error(parsed["error"], "llm_response")
                err = f"[Agent Error] {parsed['error']}"
                self.session.append_message("assistant", err)
                return err

            tool_calls = parsed["tool_calls"]
            content = parsed["content"]

            # --- No tool calls → final answer ---
            if not tool_calls:
                answer = content or "(empty response)"
                self.tracer.final_answer(answer)
                self.session.append_message("assistant", answer)
                return answer

            # --- Build assistant message with tool_calls ---
            assistant_msg = {"role": "assistant", "content": content or ""}
            assistant_msg["tool_calls"] = [
                {
                    "id": tc.get("id", f"call_{step}_{i}"),
                    "type": "function",
                    "function": {
                        "name": tc["function"]["name"],
                        "arguments": (
                            tc["function"]["arguments"]
                            if isinstance(tc["function"]["arguments"], str)
                            else json.dumps(tc["function"]["arguments"])
                        ),
                    },
                }
                for i, tc in enumerate(tool_calls)
            ]
            messages.append(assistant_msg)
            self.session.append_message(
                "assistant", content or "",
                tool_calls=assistant_msg["tool_calls"],
            )

            # --- Execute each tool call ---
            for tc in tool_calls:
                call_id = tc.get("id", f"call_{step}")
                func = tc.get("function", {})
                name = func.get("name", "unknown")
                raw_args = func.get("arguments", "{}")

                if isinstance(raw_args, str):
                    try:
                        args = json.loads(raw_args)
                    except json.JSONDecodeError:
                        args = {"_raw": raw_args}
                else:
                    args = raw_args

                self.tracer.tool_call(name, args, call_id)
                tools_called.append(name)

                t0 = time.monotonic()
                result = execute(name, args, ctx)
                tool_elapsed = (time.monotonic() - t0) * 1000

                self.tracer.tool_result(name, result, call_id, tool_elapsed)

                # Log guardrail events
                if "[GUARDRAIL]" in result:
                    self.tracer.guardrail(name, "deny", result)

                tool_msg = {
                    "role": "tool",
                    "content": result,
                    "tool_call_id": call_id,
                }
                messages.append(tool_msg)
                self.session.append_message(
                    "tool", result,
                    tool_call_id=call_id, name=name,
                )

        # Max iterations
        timeout = (
            f"[Agent] Max iterations ({self.max_iter}) reached. "
            f"Tools called: {tools_called}"
        )
        self.tracer.error(timeout, "max_iterations")
        self.session.append_message("assistant", timeout)
        return timeout
