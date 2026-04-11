"""
Tools: save_memory, search_memory
=================================
Per-user plain-text memory files.
Standalone: python -m tools.memory search <session_dir> <query>
"""

import sys
from tools.registry import tool
from core.guardrails import check_memory_filename


@tool(
    name="save_memory",
    description="Save text to the user's persistent memory files.",
    parameters={
        "filename": {
            "type": "string",
            "description": "Memory file name (e.g. 'preferences', 'notes').",
        },
        "content": {
            "type": "string",
            "description": "Text content to save.",
        },
    },
)
def save_memory(filename: str, content: str, context: dict) -> str:
    session = context.get("session")
    if not session:
        return "[Error] No active session"

    allowed, reason = check_memory_filename(
        filename,
        context.get("security_mode", "vulnerable"),
        context.get("guardrails", {}),
    )
    if not allowed:
        return f"[GUARDRAIL] Blocked: {reason}"

    session.write_memory(filename, content)
    return f"Saved '{filename}' ({len(content)} bytes)"


@tool(
    name="search_memory",
    description="Search the user's memory files (case-insensitive substring match).",
    parameters={
        "query": {
            "type": "string",
            "description": "Search term.",
        },
    },
)
def search_memory(query: str, context: dict) -> str:
    session = context.get("session")
    if not session:
        return "[Error] No active session"

    results = session.search_memory(query)
    if not results:
        return f"No matches for '{query}'"

    lines = [f"Found {len(results)} match(es):"]
    for r in results:
        lines.append(f"  [{r['file']}:{r['line']}] {r['content']}")
    return "\n".join(lines)


if __name__ == "__main__":
    from core.session import Session
    if len(sys.argv) < 3:
        print("Usage: python -m tools.memory search <session_id> <query>")
        sys.exit(1)
    sess = Session(sys.argv[2])
    ctx = {"session": sess, "security_mode": "vulnerable", "guardrails": {}}
    if sys.argv[1] == "search":
        print(search_memory(sys.argv[3] if len(sys.argv) > 3 else "", context=ctx))
