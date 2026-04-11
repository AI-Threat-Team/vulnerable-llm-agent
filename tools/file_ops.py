"""
Tools: read_file, write_file, list_dir
======================================
Filesystem operations with guardrail delegation.
Standalone: python -m tools.file_ops read <path>
            python -m tools.file_ops list <path>
"""

import os
import sys
from tools.registry import tool
from core.guardrails import check_path


def _guard(filepath: str, context: dict) -> str | None:
    """Returns error string if blocked, None if allowed."""
    allowed, reason = check_path(
        filepath,
        context.get("session_id", ""),
        context.get("workspace_root", "."),
        context.get("security_mode", "vulnerable"),
        context.get("guardrails", {}),
    )
    if not allowed:
        return f"[GUARDRAIL] Blocked: {reason}"
    return None


@tool(
    name="read_file",
    description="Read a file's contents.",
    parameters={
        "path": {
            "type": "string",
            "description": "File path relative to workspace root.",
        }
    },
)
def read_file(path: str, context: dict) -> str:
    err = _guard(path, context)
    if err:
        return err
    full = os.path.join(context.get("workspace_root", "."), path)
    try:
        with open(full) as f:
            return f.read()
    except FileNotFoundError:
        return f"[Error] Not found: {path}"
    except Exception as e:
        return f"[Error] {type(e).__name__}: {e}"


@tool(
    name="write_file",
    description="Write content to a file (creates or overwrites).",
    parameters={
        "path": {
            "type": "string",
            "description": "File path relative to workspace root.",
        },
        "content": {
            "type": "string",
            "description": "Content to write.",
        },
    },
)
def write_file(path: str, content: str, context: dict) -> str:
    err = _guard(path, context)
    if err:
        return err
    full = os.path.join(context.get("workspace_root", "."), path)
    try:
        os.makedirs(os.path.dirname(full), exist_ok=True)
        with open(full, "w") as f:
            f.write(content)
        return f"Wrote {len(content)} bytes to {path}"
    except Exception as e:
        return f"[Error] {type(e).__name__}: {e}"


@tool(
    name="list_dir",
    description="List files and directories at a path.",
    parameters={
        "path": {
            "type": "string",
            "description": "Directory path relative to workspace root. '.' for root.",
        }
    },
)
def list_dir(path: str, context: dict) -> str:
    err = _guard(path, context)
    if err:
        return err
    full = os.path.join(context.get("workspace_root", "."), path)
    try:
        entries = []
        for name in sorted(os.listdir(full)):
            fp = os.path.join(full, name)
            if os.path.isdir(fp):
                entries.append(f"  [dir]  {name}/")
            else:
                entries.append(f"  [file] {name} ({os.path.getsize(fp)}b)")
        return "\n".join(entries) or "(empty)"
    except FileNotFoundError:
        return f"[Error] Not found: {path}"
    except Exception as e:
        return f"[Error] {type(e).__name__}: {e}"


if __name__ == "__main__":
    ctx = {"security_mode": "vulnerable", "guardrails": {}, "workspace_root": "."}
    if len(sys.argv) < 3:
        print("Usage: python -m tools.file_ops <read|list|write> <path> [content]")
        sys.exit(1)
    op, path = sys.argv[1], sys.argv[2]
    if op == "read":
        print(read_file(path, context=ctx))
    elif op == "list":
        print(list_dir(path, context=ctx))
    elif op == "write":
        content = sys.argv[3] if len(sys.argv) > 3 else ""
        print(write_file(path, content, context=ctx))
