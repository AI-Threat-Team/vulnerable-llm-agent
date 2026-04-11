"""
Session — per-user filesystem state
====================================
Each user gets a folder under sessions/:
  sessions/<id>/history.jsonl   — conversation log (one JSON object per line)
  sessions/<id>/memory/         — plain text files (agent-managed notes)
  sessions/<id>/meta.json       — timestamps, access count

This module only does filesystem I/O. No display, no network.
"""

import json
import os
import time
from pathlib import Path
from typing import Optional


class Session:
    """One user's on-disk state."""

    def __init__(self, session_id: str, base_dir: str = "sessions"):
        self.session_id = session_id
        self.base_dir = Path(base_dir)
        self.dir = self.base_dir / session_id
        self.history_file = self.dir / "history.jsonl"
        self.memory_dir = self.dir / "memory"
        self.meta_file = self.dir / "meta.json"
        self._init_dirs()

    def _init_dirs(self):
        self.dir.mkdir(parents=True, exist_ok=True)
        self.memory_dir.mkdir(exist_ok=True)
        # Update meta
        if self.meta_file.exists():
            meta = json.loads(self.meta_file.read_text())
            meta["last_active"] = time.time()
            meta["access_count"] = meta.get("access_count", 0) + 1
        else:
            meta = {
                "session_id": self.session_id,
                "created_at": time.time(),
                "last_active": time.time(),
                "access_count": 1,
            }
        self.meta_file.write_text(json.dumps(meta, indent=2))

    # --- History ---

    def load_history(self) -> list[dict]:
        if not self.history_file.exists():
            return []
        messages = []
        for line in self.history_file.read_text().strip().split("\n"):
            if line.strip():
                messages.append(json.loads(line))
        return messages

    def append_message(self, role: str, content: str, **extra):
        """Append a message. Extra kwargs (tool_calls, tool_call_id, name) included if set."""
        msg = {"role": role, "content": content}
        for k, v in extra.items():
            if v is not None:
                msg[k] = v
        with open(self.history_file, "a") as f:
            f.write(json.dumps(msg) + "\n")

    def clear_history(self):
        if self.history_file.exists():
            self.history_file.write_text("")

    # --- Memory ---

    def list_memory_files(self) -> list[str]:
        if not self.memory_dir.exists():
            return []
        return sorted(f.name for f in self.memory_dir.iterdir() if f.is_file())

    def read_memory(self, filename: str) -> Optional[str]:
        p = self.memory_dir / filename
        return p.read_text() if p.exists() else None

    def write_memory(self, filename: str, content: str):
        (self.memory_dir / filename).write_text(content)

    def search_memory(self, query: str) -> list[dict]:
        results = []
        for f in self.memory_dir.iterdir():
            if not f.is_file():
                continue
            for i, line in enumerate(f.read_text().split("\n"), 1):
                if query.lower() in line.lower():
                    results.append({"file": f.name, "line": i, "content": line.strip()})
        return results

    # --- Meta ---

    def get_meta(self) -> dict:
        return json.loads(self.meta_file.read_text()) if self.meta_file.exists() else {}


class SessionManager:
    """Manages the sessions/ directory."""

    def __init__(self, base_dir: str = "sessions"):
        self.base_dir = Path(base_dir)
        self.base_dir.mkdir(exist_ok=True)
        self._cache: dict[str, Session] = {}

    def get(self, session_id: str) -> Session:
        if session_id not in self._cache:
            self._cache[session_id] = Session(session_id, str(self.base_dir))
        return self._cache[session_id]

    def list_ids(self) -> list[str]:
        return sorted(
            d.name for d in self.base_dir.iterdir()
            if d.is_dir() and (d / "meta.json").exists()
        )
