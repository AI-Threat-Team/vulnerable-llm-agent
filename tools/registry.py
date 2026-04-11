"""
Tool Registry
=============
@tool decorator registers functions with JSON schemas.
Registry generates OpenAI-compatible tool definitions.
execute_tool dispatches by name.

Each tool function signature: (arg1, arg2, ..., context: dict) -> str
Context provides: session, session_id, workspace_root, security_mode, guardrails
"""

import json
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


def get_schemas(enabled: Optional[dict] = None) -> list[dict]:
    """Generate OpenAI function-calling tool definitions."""
    schemas = []
    for name, info in _TOOLS.items():
        if enabled is not None and not enabled.get(name, True):
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
    """Run a tool by name. Returns string result."""
    info = _TOOLS.get(name)
    if not info:
        return f"Error: unknown tool '{name}'. Available: {list(_TOOLS.keys())}"
    try:
        return str(info["func"](**arguments, context=context))
    except TypeError as e:
        return f"Error calling '{name}': {e}"
    except Exception as e:
        return f"Error in '{name}': {type(e).__name__}: {e}"
