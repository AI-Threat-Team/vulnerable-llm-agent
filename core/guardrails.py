"""
Guardrails — pure validation
=============================
Each function takes (arguments, config) and returns:
  (allowed: bool, reason: str)

No I/O, no side effects. Just decisions.
Guardrails only apply when security_mode == "hardened".
"""

import os


def check_shell(command: str, security_mode: str,
                guardrails: dict) -> tuple[bool, str]:
    """Validate a shell_exec command."""
    if security_mode != "hardened":
        return True, "vulnerable mode — no restrictions"

    cfg = guardrails.get("shell_exec", {})
    allowed = cfg.get("allowed_prefixes", [])
    if not allowed:
        return True, "no allowlist configured"

    cmd_base = command.strip().split()[0] if command.strip() else ""
    if cmd_base in allowed:
        return True, f"'{cmd_base}' is in allowlist"

    return False, (
        f"Command prefix '{cmd_base}' not in allowlist: {allowed}"
    )


def check_path(filepath: str, session_id: str, workspace_root: str,
               security_mode: str, guardrails: dict) -> tuple[bool, str]:
    """Validate a file path for read/write/list operations."""
    if security_mode != "hardened":
        return True, "vulnerable mode — no restrictions"

    cfg = guardrails.get("file_ops", {})
    allowed_bases = cfg.get("allowed_base_dirs", [])
    if not allowed_bases:
        return True, "no path restrictions configured"

    resolved = os.path.realpath(os.path.join(workspace_root, filepath))

    for base_tmpl in allowed_bases:
        base = base_tmpl.format(session_id=session_id)
        allowed_abs = os.path.realpath(os.path.join(workspace_root, base))
        if resolved.startswith(allowed_abs):
            return True, f"path within allowed base '{base}'"

    return False, (
        f"Path '{filepath}' resolves to '{resolved}' — "
        f"outside allowed dirs: {allowed_bases}"
    )


def check_memory_filename(filename: str, security_mode: str,
                          guardrails: dict) -> tuple[bool, str]:
    """Validate a memory filename (prevent path traversal)."""
    if security_mode != "hardened":
        return True, "vulnerable mode — no restrictions"

    dangerous = any(c in filename for c in ("/", "\\", ".."))
    if dangerous:
        return False, (
            f"Filename '{filename}' contains path traversal characters"
        )
    return True, "filename is clean"


def check_skill_write(security_mode: str,
                      guardrails: dict) -> tuple[bool, str]:
    """Check if skill modification is allowed."""
    if security_mode != "hardened":
        return True, "vulnerable mode — no restrictions"

    cfg = guardrails.get("skill_modification", {})
    if cfg.get("read_only", False):
        return False, "skills are read-only in hardened mode"

    return True, "skill modification allowed"
