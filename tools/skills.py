"""
Tools: list_skills, load_skill, update_skill
=============================================
Skills are markdown files loaded into the system prompt.
update_skill is the injection vector — it rewrites agent instructions.
Standalone: python -m tools.skills list
"""

import sys
from pathlib import Path
from tools.registry import tool
from core.guardrails import check_skill_write


@tool(
    name="list_skills",
    description="List all available skill files.",
    parameters={},
)
def list_skills(context: dict) -> str:
    d = Path(context.get("workspace_root", ".")) / "skills"
    if not d.exists():
        return "No skills directory"
    files = sorted(d.glob("*.md"))
    if not files:
        return "No skill files"
    lines = [f"Skills ({len(files)}):"]
    for f in files:
        lines.append(f"  - {f.name} ({f.stat().st_size}b)")
    return "\n".join(lines)


@tool(
    name="load_skill",
    description="Read a skill file's contents.",
    parameters={
        "filename": {
            "type": "string",
            "description": "Skill filename (e.g. 'default.md').",
        },
    },
)
def load_skill(filename: str, context: dict) -> str:
    p = Path(context.get("workspace_root", ".")) / "skills" / filename
    try:
        return p.read_text()
    except FileNotFoundError:
        return f"[Error] Not found: {filename}"
    except Exception as e:
        return f"[Error] {type(e).__name__}: {e}"


@tool(
    name="update_skill",
    description="Create or overwrite a skill file. Changes affect all users.",
    parameters={
        "filename": {
            "type": "string",
            "description": "Skill filename (e.g. 'default.md').",
        },
        "content": {
            "type": "string",
            "description": "New skill content (markdown).",
        },
    },
)
def update_skill(filename: str, content: str, context: dict) -> str:
    allowed, reason = check_skill_write(
        context.get("security_mode", "vulnerable"),
        context.get("guardrails", {}),
    )
    if not allowed:
        return f"[GUARDRAIL] Blocked: {reason}"

    p = Path(context.get("workspace_root", ".")) / "skills" / filename
    try:
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content)
        return f"Skill '{filename}' updated ({len(content)}b). Effective next turn."
    except Exception as e:
        return f"[Error] {type(e).__name__}: {e}"


if __name__ == "__main__":
    ctx = {"workspace_root": ".", "security_mode": "vulnerable", "guardrails": {}}
    if len(sys.argv) < 2:
        print("Usage: python -m tools.skills <list|load|update> [filename] [content]")
        sys.exit(1)
    op = sys.argv[1]
    if op == "list":
        print(list_skills(context=ctx))
    elif op == "load" and len(sys.argv) > 2:
        print(load_skill(sys.argv[2], context=ctx))
    elif op == "update" and len(sys.argv) > 3:
        print(update_skill(sys.argv[2], sys.argv[3], context=ctx))
