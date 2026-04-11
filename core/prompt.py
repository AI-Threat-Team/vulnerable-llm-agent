"""
Prompt Assembler — pure data transformation
============================================
(config, session, user_input) → list[dict]

No I/O beyond reading config/skill files from disk.
No network. No display.
"""

import yaml
from pathlib import Path
from typing import Optional

from core.session import Session


class PromptAssembler:

    def __init__(self, config_path: str = "config.yaml"):
        self.config_path = Path(config_path)
        self.config = self._load()

    def _load(self) -> dict:
        if self.config_path.exists():
            return yaml.safe_load(self.config_path.read_text()) or {}
        return {}

    def reload(self):
        """Reload config from disk (picks up skill/config changes)."""
        self.config = self._load()

    @property
    def security_mode(self) -> str:
        return self.config.get("security_mode", "vulnerable")

    @property
    def guardrails(self) -> dict:
        return self.config.get("guardrails", {})

    @property
    def enabled_tools(self) -> dict:
        return self.config.get("tools", {})

    # ------------------------------------------------------------------

    def _system_prompt(self, session: Session, workspace_root: str) -> str:
        tmpl = self.config.get("system_prompt", "You are a helpful assistant.")
        return tmpl.format(
            session_id=session.session_id,
            workspace_root=workspace_root,
        )

    def _skills_block(self, workspace_root: str) -> str:
        skills_dir = Path(workspace_root) / "skills"
        if not skills_dir.exists():
            return ""
        parts = []
        for f in sorted(skills_dir.glob("*.md")):
            parts.append(f"--- Skill: {f.stem} ---")
            parts.append(f.read_text().strip())
            parts.append("")
        return "\n".join(parts)

    def _memory_block(self, session: Session) -> str:
        files = session.list_memory_files()
        if not files:
            return ""
        parts = ["--- User Memory ---"]
        for fname in files:
            content = session.read_memory(fname)
            if content:
                parts.append(f"[{fname}]")
                parts.append(content.strip())
                parts.append("")
        return "\n".join(parts)

    def assemble(self, session: Session, user_input: str,
                 workspace_root: str) -> list[dict]:
        """Build the full messages list for the LLM API call."""
        # System message
        system_parts = [
            self._system_prompt(session, workspace_root),
        ]
        skills = self._skills_block(workspace_root)
        if skills:
            system_parts.append(skills)
        memory = self._memory_block(session)
        if memory:
            system_parts.append(memory)
        system_parts.append(f"[Security Mode: {self.security_mode}]")

        messages = [{"role": "system", "content": "\n\n".join(system_parts)}]

        # History
        messages.extend(session.load_history())

        # Current input
        messages.append({"role": "user", "content": user_input})

        return messages
