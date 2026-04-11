#!/usr/bin/env python3
"""
Terminal 2 — Debug Viewer
=========================
Tails logs/trace.jsonl and renders rich formatted trace output.
This is a standalone reader — it only reads the log file.

Usage:
    python debug.py                    # tail mode (follow new events)
    python debug.py --replay           # replay entire log from start
    python debug.py --replay --raw     # replay as raw JSON lines
    python debug.py --filter tool_call # only show matching event types
    python debug.py --session alice    # only show events for session

Or skip this entirely and just:
    tail -f logs/trace.jsonl | python -m json.tool
"""

import argparse
import json
import os
import sys
import time
from pathlib import Path

from dotenv import load_dotenv
load_dotenv()

LOG_PATH = Path(os.getenv("TRACE_LOG", "logs/trace.jsonl"))


# ── ANSI ──────────────────────────────────────────────────────────────

RESET   = "\033[0m"
BOLD    = "\033[1m"
DIM     = "\033[2m"
RED     = "\033[91m"
GREEN   = "\033[92m"
YELLOW  = "\033[93m"
BLUE    = "\033[94m"
MAGENTA = "\033[95m"
CYAN    = "\033[96m"
WHITE   = "\033[97m"

WIDTH = 78


def sep(label: str, color: str = CYAN) -> str:
    pad = WIDTH - len(label) - 4
    return f"{color}{BOLD}{'═' * 2} {label} {'═' * max(pad, 2)}{RESET}"


def dim_line(text: str) -> str:
    return f"  {DIM}│{RESET} {text}"


def json_block(obj, max_lines: int = 60) -> str:
    text = json.dumps(obj, indent=2, ensure_ascii=False, default=str)
    lines = text.split("\n")
    if len(lines) > max_lines:
        h = max_lines // 2
        lines = lines[:h] + [f"  ... ({len(lines) - max_lines} lines omitted) ..."] + lines[-h:]
    return "\n".join(dim_line(l) for l in lines)


def text_block(text: str, max_lines: int = 40) -> str:
    lines = str(text).split("\n")
    if len(lines) > max_lines:
        h = max_lines // 2
        lines = lines[:h] + [f"... ({len(lines) - max_lines} lines omitted) ..."] + lines[-h:]
    return "\n".join(dim_line(l) for l in lines)


# ── Event Renderers ───────────────────────────────────────────────────

def render_step_start(ev: dict):
    step = ev.get("step", "?")
    mx = ev.get("max_steps", "?")
    print(f"\n{sep(f'STEP {step}/{mx}')}")


def render_prompt(ev: dict):
    msgs = ev.get("messages", [])
    total = ev.get("total_chars", 0)
    print(f"\n{BLUE}{BOLD}┌─ FULL PROMPT{RESET} {DIM}({len(msgs)} messages, ~{total} chars){RESET}")

    for msg in msgs:
        role = msg.get("role", "?")
        rc = {"system": MAGENTA, "user": GREEN, "assistant": BLUE, "tool": YELLOW}.get(role, WHITE)

        header = f"{rc}{BOLD}[{role}]{RESET}"
        if msg.get("tool_call_id"):
            header += f" {DIM}(call_id: {msg['tool_call_id']}){RESET}"
        if msg.get("name"):
            header += f" {DIM}(name: {msg['name']}){RESET}"
        print(f"\n{dim_line(header)}")

        content = msg.get("content", "")
        if content:
            # Truncate very long system prompts in display
            lines = str(content).split("\n")
            if len(lines) > 30:
                display = "\n".join(lines[:15] + [f"... ({len(lines) - 30} lines) ..."] + lines[-15:])
            else:
                display = content
            print(text_block(display))

        if msg.get("tool_calls"):
            print(dim_line(f"{YELLOW}tool_calls:{RESET}"))
            print(json_block(msg["tool_calls"], max_lines=20))


def render_llm_response(ev: dict):
    elapsed = ev.get("elapsed_ms", 0)
    raw = ev.get("raw", {})
    print(f"\n{GREEN}{BOLD}┌─ LLM RESPONSE{RESET} {DIM}({elapsed:.0f}ms){RESET}")

    # Show just the message part if available, full raw otherwise
    try:
        msg = raw["choices"][0]["message"]
        if msg.get("content"):
            print(dim_line(f"{GREEN}content:{RESET}"))
            print(text_block(msg["content"]))
        if msg.get("tool_calls"):
            print(dim_line(f"{YELLOW}tool_calls:{RESET}"))
            print(json_block(msg["tool_calls"]))
        if not msg.get("content") and not msg.get("tool_calls"):
            print(json_block(raw))
    except (KeyError, IndexError):
        print(json_block(raw))


def render_tool_call(ev: dict):
    name = ev.get("tool", "?")
    cid = ev.get("call_id", "?")
    args = ev.get("arguments", {})
    print(f"\n{YELLOW}{BOLD}┌─ TOOL CALL: {name}{RESET} {DIM}(id: {cid}){RESET}")
    print(dim_line(f"{BOLD}arguments:{RESET}"))
    print(json_block(args))


def render_tool_result(ev: dict):
    name = ev.get("tool", "?")
    cid = ev.get("call_id", "?")
    elapsed = ev.get("elapsed_ms", 0)
    result = ev.get("result", "")
    print(f"\n{MAGENTA}{BOLD}┌─ TOOL RESULT: {name}{RESET} {DIM}(id: {cid}, {elapsed:.0f}ms){RESET}")
    print(text_block(result))


def render_guardrail(ev: dict):
    name = ev.get("tool", "?")
    action = ev.get("action", "?")
    reason = ev.get("reason", "")
    color = RED if action == "deny" else GREEN
    print(f"\n{color}{BOLD}┌─ GUARDRAIL [{action.upper()}]: {name}{RESET}")
    print(dim_line(f"{color}{reason}{RESET}"))


def render_agent_state(ev: dict):
    print(f"\n{CYAN}{BOLD}┌─ AGENT STATE{RESET}")
    state = {k: v for k, v in ev.items() if k not in ("ts", "event", "session")}
    print(json_block(state))


def render_final_answer(ev: dict):
    answer = ev.get("answer", "")
    print(f"\n{sep('FINAL ANSWER', GREEN)}")
    print(f"{GREEN}{answer}{RESET}")


def render_error(ev: dict):
    err = ev.get("error", "")
    ctx = ev.get("context", "")
    label = f"ERROR ({ctx})" if ctx else "ERROR"
    print(f"\n{RED}{BOLD}┌─ {label}{RESET}")
    print(dim_line(f"{RED}{err}{RESET}"))


def render_user_input(ev: dict):
    text = ev.get("text", "")
    session = ev.get("session", "?")
    print(f"\n{sep(f'USER INPUT [{session}]', GREEN)}")
    print(f"{GREEN}{BOLD}  > {text}{RESET}")


def render_session_switch(ev: dict):
    print(f"\n{CYAN}→ Session switch: {ev.get('from', '?')} → {ev.get('to', '?')}{RESET}")


def render_config_change(ev: dict):
    print(f"\n{YELLOW}⚙ Config: {ev.get('key', '?')}: {ev.get('old', '?')} → {ev.get('new', '?')}{RESET}")


def render_llm_request(ev: dict):
    summary = ev.get("payload_summary", {})
    print(f"\n{DIM}┌─ LLM REQUEST{RESET}")
    print(json_block(summary))


# Event type → renderer
RENDERERS = {
    "step_start":     render_step_start,
    "prompt":         render_prompt,
    "llm_request":    render_llm_request,
    "llm_response":   render_llm_response,
    "tool_call":      render_tool_call,
    "tool_result":    render_tool_result,
    "guardrail":      render_guardrail,
    "agent_state":    render_agent_state,
    "final_answer":   render_final_answer,
    "error":          render_error,
    "user_input":     render_user_input,
    "session_switch": render_session_switch,
    "config_change":  render_config_change,
}


def render_event(ev: dict, raw_mode: bool = False):
    if raw_mode:
        print(json.dumps(ev, indent=2, ensure_ascii=False, default=str))
        return

    event_type = ev.get("event", "unknown")
    renderer = RENDERERS.get(event_type)
    if renderer:
        renderer(ev)
    else:
        print(f"\n{DIM}[{event_type}] {json.dumps(ev, default=str)}{RESET}")


# ── Tail loop ─────────────────────────────────────────────────────────

def tail_file(path: Path, from_start: bool = False,
              raw: bool = False,
              event_filter: str | None = None,
              session_filter: str | None = None):
    """Follow a JSONL file, rendering each line."""

    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.touch()

    with open(path, "r") as f:
        if not from_start:
            f.seek(0, 2)  # Jump to end

        while True:
            line = f.readline()
            if not line:
                try:
                    time.sleep(0.1)
                except KeyboardInterrupt:
                    print(f"\n{DIM}Debug viewer stopped.{RESET}")
                    break
                continue

            line = line.strip()
            if not line:
                continue

            try:
                ev = json.loads(line)
            except json.JSONDecodeError:
                print(f"{RED}[bad json] {line}{RESET}")
                continue

            # Filters
            if event_filter and ev.get("event") != event_filter:
                continue
            if session_filter and ev.get("session") != session_filter:
                continue

            render_event(ev, raw_mode=raw)


def main():
    parser = argparse.ArgumentParser(
        description="Vuln-Agent Debug Viewer (Terminal 2)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python debug.py                       # follow new events
  python debug.py --replay              # replay from start
  python debug.py --filter tool_call    # only tool calls
  python debug.py --session alice       # only alice's events
  python debug.py --raw                 # raw JSON output
  tail -f logs/trace.jsonl              # skip this script entirely
""",
    )
    parser.add_argument("--replay", action="store_true",
                        help="Replay from start of log file")
    parser.add_argument("--raw", action="store_true",
                        help="Output raw JSON instead of formatted")
    parser.add_argument("--filter", type=str, default=None,
                        help="Only show events of this type")
    parser.add_argument("--session", type=str, default=None,
                        help="Only show events for this session")
    parser.add_argument("--log", type=str, default=None,
                        help=f"Log file path (default: {LOG_PATH})")
    args = parser.parse_args()

    log = Path(args.log) if args.log else LOG_PATH

    print(f"""
{RED}{BOLD}┌──────────────────────────────────────────────┐
│  VULN-AGENT  ·  Debug Viewer                 │
│  Terminal 2: Full Trace Output               │
└──────────────────────────────────────────────┘{RESET}
{DIM}Reading: {log}{RESET}
{DIM}Mode: {'replay' if args.replay else 'follow (tail -f)'}{RESET}
{DIM}Filter: {args.filter or 'all events'}{RESET}
{DIM}Session: {args.session or 'all sessions'}{RESET}
{DIM}Press Ctrl+C to stop.{RESET}
""")

    tail_file(
        log,
        from_start=args.replay,
        raw=args.raw,
        event_filter=args.filter,
        session_filter=args.session,
    )


if __name__ == "__main__":
    main()
