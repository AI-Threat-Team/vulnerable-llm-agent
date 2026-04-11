#!/usr/bin/env python3
"""
Terminal 1 — User REPL
======================
Clean interface: prompt → answer. No debug output.
All trace data goes to logs/trace.jsonl (read by debug.py in Terminal 2).

Usage:
    python main.py

Commands:
    /switch <user>   Switch session
    /sessions        List sessions
    /clear           Clear history
    /mode <mode>     Set security mode (vulnerable|hardened)
    /tools           List tools
    /config          Show config
    /help            Help
    /quit            Exit
"""

import json
import os
import sys
import yaml

from dotenv import load_dotenv
load_dotenv()

WORKSPACE = os.path.dirname(os.path.abspath(__file__))
os.chdir(WORKSPACE)

from core.session import SessionManager
from core.agent import Agent
from core.prompt import PromptAssembler
from core.tracer import get_tracer

# Register all tools
import tools.shell       # noqa: F401
import tools.file_ops    # noqa: F401
import tools.memory      # noqa: F401
import tools.skills      # noqa: F401
import tools.send_message  # noqa: F401

from tools.registry import list_tools, get_schemas


# --- ANSI helpers (minimal — just for the user terminal) ---

BOLD = "\033[1m"
DIM = "\033[2m"
RED = "\033[91m"
GREEN = "\033[92m"
YELLOW = "\033[93m"
CYAN = "\033[96m"
RESET = "\033[0m"


def banner():
    print(f"""
{RED}{BOLD}┌──────────────────────────────────────────────┐
│  VULN-AGENT  ·  Red Team Training Agent      │
│  Terminal 1: User Interface                   │
└──────────────────────────────────────────────┘{RESET}
{DIM}Debug output → Terminal 2: python debug.py (or tail -f logs/trace.jsonl){RESET}
""")


def handle_cmd(cmd: str, session_mgr: SessionManager,
               current_id: str, assembler: PromptAssembler) -> str | None:
    """Process a slash command. Returns new session_id if switched, else None."""
    parts = cmd.strip().split(maxsplit=1)
    verb = parts[0].lower()
    arg = parts[1] if len(parts) > 1 else ""

    if verb == "/help":
        print(f"""
{CYAN}Commands:{RESET}
  /switch <user>   Switch session      /sessions   List sessions
  /clear           Clear history        /mode <m>   vulnerable | hardened
  /tools           List tools           /config     Show config
  /quit            Exit
""")

    elif verb == "/switch":
        if not arg:
            print(f"{RED}Usage: /switch <username>{RESET}")
        else:
            print(f"{GREEN}→ Session: {arg}{RESET}")
            return arg

    elif verb == "/sessions":
        ids = session_mgr.list_ids()
        for s in ids:
            mark = f" {CYAN}←{RESET}" if s == current_id else ""
            print(f"  {s}{mark}")
        if not ids:
            print(f"  {DIM}(none){RESET}")

    elif verb == "/clear":
        session_mgr.get(current_id).clear_history()
        print(f"{GREEN}History cleared.{RESET}")

    elif verb == "/mode":
        if arg not in ("vulnerable", "hardened"):
            print(f"{RED}Usage: /mode <vulnerable|hardened>{RESET}")
        else:
            cfg_path = os.path.join(WORKSPACE, "config.yaml")
            cfg = yaml.safe_load(open(cfg_path)) or {}
            old = cfg.get("security_mode", "vulnerable")
            cfg["security_mode"] = arg
            with open(cfg_path, "w") as f:
                yaml.dump(cfg, f, default_flow_style=False)
            assembler.reload()
            tracer = get_tracer()
            tracer.config_change("security_mode", old, arg)
            color = RED if arg == "vulnerable" else GREEN
            print(f"{color}Mode: {arg}{RESET}")

    elif verb == "/tools":
        schemas = get_schemas(assembler.enabled_tools)
        for s in schemas:
            fn = s["function"]
            params = ", ".join(fn["parameters"].get("properties", {}).keys())
            print(f"  {YELLOW}{fn['name']}{RESET}({params})")

    elif verb == "/config":
        assembler.reload()
        print(json.dumps(assembler.config, indent=2, default=str))

    elif verb == "/quit":
        print(f"{DIM}Goodbye.{RESET}")
        sys.exit(0)

    else:
        print(f"{RED}Unknown: {verb}. /help for commands.{RESET}")

    return None


def main():
    banner()

    session_mgr = SessionManager(os.path.join(WORKSPACE, "sessions"))
    assembler = PromptAssembler(os.path.join(WORKSPACE, "config.yaml"))
    tracer = get_tracer()

    # Login
    print(f"{CYAN}Username:{RESET} ", end="", flush=True)
    try:
        username = input().strip()
    except (EOFError, KeyboardInterrupt):
        print(f"\n{DIM}Goodbye.{RESET}")
        return
    if not username:
        username = "default"

    current_id = username
    session = session_mgr.get(current_id)
    tracer.set_session(current_id)

    mode = assembler.security_mode
    mode_c = RED if mode == "vulnerable" else GREEN
    print(f"\n{GREEN}Session:{RESET} {current_id}  "
          f"{DIM}Mode:{RESET} {mode_c}{mode}{RESET}  "
          f"{DIM}LLM:{RESET} {os.getenv('LLM_BASE_URL', '?')}\n")

    # REPL
    while True:
        try:
            user_input = input(f"{BOLD}[{current_id}] > {RESET}").strip()
        except (EOFError, KeyboardInterrupt):
            print(f"\n{DIM}Goodbye.{RESET}")
            break

        if not user_input:
            continue

        if user_input.startswith("/"):
            result = handle_cmd(user_input, session_mgr, current_id, assembler)
            if result is not None:
                current_id = result
                session = session_mgr.get(current_id)
                tracer.set_session(current_id)
                tracer.session_switch(username, current_id)
            continue

        # Run agent
        agent = Agent(
            session=session,
            workspace_root=WORKSPACE,
            tracer=tracer,
            config_path=os.path.join(WORKSPACE, "config.yaml"),
        )

        try:
            answer = agent.run(user_input)
            print(f"\n{GREEN}{answer}{RESET}\n")
        except Exception as e:
            print(f"\n{RED}CRASH: {type(e).__name__}: {e}{RESET}\n")
            tracer.error(f"{type(e).__name__}: {e}", "agent_crash")
            import traceback
            traceback.print_exc()


if __name__ == "__main__":
    main()
