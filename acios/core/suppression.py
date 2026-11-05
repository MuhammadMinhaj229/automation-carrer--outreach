"""Local suppression guard with optional durable SQLite storage.

SQLite storage is opt-in; all records remain on the operator's machine.
This module does not authorize or perform outbound messaging.
"""

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Set


def _normalize(email: str) -> str:
    if not isinstance(email, str):
        return ""
    value = email.strip().lower()
    # Reject whitespace/control characters and clearly malformed addresses.
    if (
        not value or value.count("@") != 1 or
        any(char.isspace() or ord(char) < 32 for char in value)
    ):
        return ""
    local, domain = value.split("@")
    return value if local and "." in domain and not domain.startswith(".") else ""


class SuppressionEngine:
    """Checks static lists and, when configured, a cross-process SQLite registry."""

    def __init__(self, suppression_files: list = None, sqlite_path: Path = None):
        self._blocked_emails: Set[str] = set()
        self.sqlite_path = Path(sqlite_path) if sqlite_path is not None else None

        default_paths = [
            Path(__file__).resolve().parent.parent.parent / "data" / "suppression" / "master_suppression.json",
        ]
        paths_to_load = default_paths if suppression_files is None else suppression_files
        for path in paths_to_load:
            path_obj = Path(path)
            if path_obj.exists():
                self._load_file(path_obj)
        if self.sqlite_path is not None:
            self.sqlite_path.parent.mkdir(parents=True, exist_ok=True)
            with self._connect() as conn:
                conn.execute(
                    "CREATE TABLE IF NOT EXISTS suppressed_recipients ("
                    "email TEXT PRIMARY KEY, reason TEXT NOT NULL, created_at TEXT NOT NULL)"
                )

    def _connect(self):
        conn = sqlite3.connect(str(self.sqlite_path), timeout=10)
        conn.execute("PRAGMA busy_timeout=10000")
        return conn

    def _load_file(self, path: Path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, dict):
                entries = list(data.get("suppressed_emails", [])) + list(
                    data.get("bounced_addresses", [])
                )
            elif isinstance(data, list):
                entries = data
            else:
                entries = []
            for email in entries:
                clean = _normalize(email)
                if clean:
                    self._blocked_emails.add(clean)
        except (OSError, ValueError, TypeError) as exc:
            # Never silently claim a corrupted static suppression list was loaded.
            raise RuntimeError(f"Could not load suppression file: {path}") from exc

    @property
    def total_blocked(self) -> int:
        if self.sqlite_path is None:
            return len(self._blocked_emails)
        with self._connect() as conn:
            rows = conn.execute("SELECT email FROM suppressed_recipients").fetchall()
        return len(self._blocked_emails | {row[0] for row in rows})

    def block(self, email: str, reason: str = "manual"):
        """Persist before updating the in-memory cache; repeated blocks are idempotent."""
        clean = _normalize(email)
        if not clean:
            raise ValueError("A valid recipient email is required for suppression")
        if self.sqlite_path is not None:
            with self._connect() as conn:
                conn.execute(
                    "INSERT OR IGNORE INTO suppressed_recipients(email, reason, created_at) "
                    "VALUES (?, ?, ?)",
                    (clean, str(reason)[:200], datetime.now(timezone.utc).isoformat()),
                )
        self._blocked_emails.add(clean)

    def is_suppressed(self, email: str) -> bool:
        """Fail closed for invalid addresses and unreadable configured storage."""
        clean = _normalize(email)
        if not clean:
            return True
        if clean in self._blocked_emails:
            return True
        if self.sqlite_path is None:
            return False
        try:
            with self._connect() as conn:
                row = conn.execute(
                    "SELECT 1 FROM suppressed_recipients WHERE email = ?", (clean,)
                ).fetchone()
            return row is not None
        except sqlite3.Error:
            return True

    def add_suppression(self, email: str):
        """Legacy compatibility alias."""
        self.block(email)
