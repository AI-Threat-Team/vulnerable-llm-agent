"""
Tool Registry
=============
@tool decorator registers functions with JSON schemas.
Registry generates OpenAI-compatible tool definitions.
execute_tool dispatches by name.

Visibility: get_schemas() reads tools.allow to determine which tools
the LLM can see. But execute() runs ANY registered tool — even hidden
ones. This is a deliberate vulnerability: if the LLM learns about a
hidden tool name (via enumeration, prompt injection, etc.), it can
still call it.

Each tool function signature: (arg1, arg2, ..., context: dict) -> str
Context provides: session, session_id, workspace_root, security_mode, guardrails
"""

import json
from pathlib import Path
from typing import Callable, Optional

_TOOLS: dict[str, dict] = {}


def tool(name: str, description: str, parameters: dict):
    """Decorator to register a tool function."""
    def decorator(func: Callable) -> Callable:
        _TOOLS[name] = {
            "name": name,
            "description": description,
            "parameters": parameters,
            "func": func,
        }
        func._tool_name = name
        return func
    return decorator


def get_tool(name: str) -> Optional[dict]:
    return _TOOLS.get(name)


def list_tools() -> list[str]:
    return list(_TOOLS.keys())


def load_allow_list(workspace_root: str = ".") -> list[str] | None:
    """
    Load tools.allow file. Returns list of allowed tool names,
    or None if file doesn't exist (= all tools visible).
    """
    path = Path(workspace_root) / "tools.allow"
    if not path.exists():
        return None
    names = []
    for line in path.read_text().strip().split("\n"):
        line = line.strip()
        if line and not line.startswith("#"):
            names.append(line)
    return names


def get_schemas(enabled: Optional[dict] = None,
                allow_list: list[str] | None = None) -> list[dict]:
    """
    Generate OpenAI function-calling tool definitions.

    Args:
        enabled:    Dict of {tool_name: bool} from config.yaml tools section.
        allow_list: List of tool names from tools.allow. If provided, only
                    these tools are included in schemas (LLM visibility).
                    If None, all enabled tools are included.
    """
    schemas = []
    for name, info in _TOOLS.items():
        # Check config.yaml toggles
        if enabled is not None and not enabled.get(name, True):
            continue
        # Check tools.allow visibility
        if allow_list is not None and name not in allow_list:
            continue
        schemas.append({
            "type": "function",
            "function": {
                "name": name,
                "description": info["description"],
                "parameters": {
                    "type": "object",
                    "properties": info["parameters"],
                    "required": list(info["parameters"].keys()),
                },
            },
        })
    return schemas


def execute(name: str, arguments: dict, context: dict) -> str:
    """
    Run a tool by name. Returns string result.
    NOTE: Executes ANY registered tool, even if not in tools.allow.
    This is deliberate — the allow list only controls LLM visibility.
    """
    info = _TOOLS.get(name)
    if not info:
        return f"Error: unknown tool '{name}'. Available: {list(_TOOLS.keys())}"
    try:
        return str(info["func"](**arguments, context=context))
    except TypeError as e:
        return f"Error calling '{name}': {e}"
    except Exception as e:
        return f"Error in '{name}': {type(e).__name__}: {e}"
