"""
Prompt Assembler — pure data transformation
============================================
(config, session, user_input, language) → list[dict]

Language support:
  - System prompt loaded from lang/{lang}.yaml
  - Skills loaded from skills/{lang}/*.md
  - Config.yaml remains language-neutral (guardrails, toggles)

No network. No display.
"""

import yaml
from pathlib import Path
from typing import Optional

from core.session import Session


class PromptAssembler:

    def __init__(self, config_path: str = "config.yaml", language: str = "en"):
        self.config_path = Path(config_path)
        self.workspace_root = self.config_path.parent
        self.language = language
        self.config = self._load_config()
        self.lang = self._load_lang()

    def _load_config(self) -> dict:
        if self.config_path.exists():
            return yaml.safe_load(self.config_path.read_text()) or {}
        return {}

    def _load_lang(self) -> dict:
        lang_path = self.workspace_root / "lang" / f"{self.language}.yaml"
        if lang_path.exists():
            return yaml.safe_load(lang_path.read_text()) or {}
        # Fallback to en
        fallback = self.workspace_root / "lang" / "en.yaml"
        if fallback.exists():
            return yaml.safe_load(fallback.read_text()) or {}
        return {}

    def reload(self):
        """Reload config and lang from disk."""
        self.config = self._load_config()
        self.lang = self._load_lang()

    @property
    def security_mode(self) -> str:
        return self.config.get("security_mode", "vulnerable")

    @property
    def guardrails(self) -> dict:
        return self.config.get("guardrails", {})

    @property
    def enabled_tools(self) -> dict:
        return self.config.get("tools", {})

    @property
    def repl_strings(self) -> dict:
        return self.lang.get("repl", {})

    # ------------------------------------------------------------------

    def _system_prompt(self, session: Session, workspace_root: str) -> str:
        # System prompt comes from lang file, not config.yaml
        tmpl = self.lang.get("system_prompt")
        if not tmpl:
            tmpl = self.config.get("system_prompt",
                                   "You are a helpful assistant.")
        return tmpl.format(
            session_id=session.session_id,
            workspace_root=workspace_root,
        )

    def _skills_block(self, workspace_root: str, session_id: str) -> str:
        """Load skills from skills/{language}/ directory, with {session_id} substitution."""
        skills_dir = Path(workspace_root) / "skills" / self.language
        if not skills_dir.exists():
            # Fallback to skills/en/
            skills_dir = Path(workspace_root) / "skills" / "en"
        if not skills_dir.exists():
            # Legacy fallback to skills/ (flat)
            skills_dir = Path(workspace_root) / "skills"
        if not skills_dir.exists():
            return ""

        parts = []
        for f in sorted(skills_dir.glob("*.md")):
            parts.append(f"--- Skill: {f.stem} ---")
            content = f.read_text().strip()
            # Substitute {session_id} in skill content
            try:
                content = content.format(session_id=session_id)
            except (KeyError, IndexError):
                pass  # If skill has other braces, don't crash
            parts.append(content)
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
        system_parts = [
            self._system_prompt(session, workspace_root),
        ]
        skills = self._skills_block(workspace_root, session.session_id)
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
