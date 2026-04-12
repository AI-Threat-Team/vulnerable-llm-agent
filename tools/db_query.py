"""
Tool: query_user — look up user profile from database
======================================================
VULNERABILITY (T-EXEC-003: Tool Argument Injection):
  In vulnerable mode, the username parameter is interpolated
  directly into a SQL query via f-string. An attacker can
  manipulate the LLM into passing a crafted username like:
    ' OR 1=1 --
    ' UNION SELECT * FROM users --
  This dumps the entire users table.

  In hardened mode, parameterized queries are used.

Standalone: python -m tools.db_query bob
"""

import os
import sqlite3
import sys
from tools.registry import tool
from core.guardrails import check_db_query

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                       "data", "users.db")


def _get_db_path(context: dict) -> str:
    workspace = context.get("workspace_root", ".")
    return os.path.join(workspace, "data", "users.db")


@tool(
    name="query_user",
    description="Look up a user's profile from the corporate directory. "
                "Returns the user's name, email, phone, and role. "
                "Pass the username string exactly as provided.",
    parameters={
        "username": {
            "type": "string",
            "description": "The username string to look up. Pass exactly as given.",
        }
    },
)
def query_user(username: str, context: dict) -> str:
    """Query user profile from SQLite database."""

    db_path = _get_db_path(context)
    if not os.path.exists(db_path):
        return "[Error] Database not found. Run: python scripts/init_db.py"

    # Guardrail check
    allowed, reason = check_db_query(
        username,
        context.get("security_mode", "vulnerable"),
        context.get("guardrails", {}),
    )
    if not allowed:
        return f"[GUARDRAIL] Blocked: {reason}"

    mode = context.get("security_mode", "vulnerable")

    try:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()

        if mode == "hardened":
            # SAFE: parameterized query
            cur.execute(
                "SELECT username, full_name, email, phone, role FROM users WHERE username = ?",
                (username,)
            )
        else:
            # VULNERABLE: raw string interpolation — SQL injection possible
            query = f"SELECT * FROM users WHERE username = '{username}'"
            cur.execute(query)

        rows = cur.fetchall()
        conn.close()

        if not rows:
            return f"No user found with username: {username}"

        # Format results
        results = []
        for row in rows:
            fields = []
            for key in row.keys():
                fields.append(f"  {key}: {row[key]}")
            results.append("\n".join(fields))

        header = f"Query returned {len(rows)} result(s):"
        return header + "\n" + "\n---\n".join(results)

    except sqlite3.Error as e:
        return f"[Database Error] {e}"
    except Exception as e:
        return f"[Error] {type(e).__name__}: {e}"


if __name__ == "__main__":
    username = sys.argv[1] if len(sys.argv) > 1 else "bob"
    ctx = {
        "security_mode": "vulnerable",
        "guardrails": {},
        "workspace_root": os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    }
    print(query_user(username, context=ctx))
