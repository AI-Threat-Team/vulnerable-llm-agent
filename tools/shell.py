"""
Tool: shell_exec — run a shell command
=======================================
Delegates guardrail check to core.guardrails.
Standalone: python -m tools.shell "ls -la"
"""

import subprocess
import sys
from tools.registry import tool
from core.guardrails import check_shell


@tool(
    name="shell_exec",
    description="Execute a shell command and return stdout/stderr.",
    parameters={
        "command": {
            "type": "string",
            "description": "The shell command to execute.",
        }
    },
)
def shell_exec(command: str, context: dict) -> str:
    # Guardrail
    allowed, reason = check_shell(
        command,
        context.get("security_mode", "vulnerable"),
        context.get("guardrails", {}),
    )
    if not allowed:
        return f"[GUARDRAIL] Blocked: {reason}"

    try:
        r = subprocess.run(
            command, shell=True, capture_output=True, text=True,
            timeout=30, cwd=context.get("workspace_root", "."),
        )
        out = ""
        if r.stdout:
            out += r.stdout
        if r.stderr:
            out += f"\n[stderr]\n{r.stderr}"
        if r.returncode != 0:
            out += f"\n[exit code: {r.returncode}]"
        return out.strip() or "(no output)"
    except subprocess.TimeoutExpired:
        return "[Error] Timed out (30s)"
    except Exception as e:
        return f"[Error] {type(e).__name__}: {e}"


if __name__ == "__main__":
    # Standalone usage: python -m tools.shell "ls -la"
    cmd = " ".join(sys.argv[1:]) if len(sys.argv) > 1 else "echo 'usage: python -m tools.shell <command>'"
    ctx = {"security_mode": "vulnerable", "guardrails": {}, "workspace_root": "."}
    print(shell_exec(cmd, context=ctx))
