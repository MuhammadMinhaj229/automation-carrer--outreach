"""
Master Suppression & Bounce Protection Engine.
Guarantees zero outreach to known bounced, opted-out, or invalid inboxes.
"""

import json
from pathlib import Path
from typing import Set


class SuppressionEngine:
    def __init__(self, suppression_files: list = None):
        self._blocked_emails: Set[str] = set()
        
        # Default known paths in project environment
        default_paths = [
            Path(__file__).resolve().parent.parent.parent / "data" / "suppression" / "master_suppression.json",
            Path(r"C:\Users\User\.gemini\antigravity\brain\eb93f88a-ad00-4e03-89b8-0c0b43ed482d\jobs automation\master_suppression_list.json"),
            Path(r"C:\Users\User\.gemini\antigravity\brain\eb93f88a-ad00-4e03-89b8-0c0b43ed482d\scratch\gmail_history_audit.json")
        ]
        
        paths_to_load = suppression_files or default_paths
        for p in paths_to_load:
            path_obj = Path(p)
            if path_obj.exists():
                self._load_file(path_obj)

    def _load_file(self, path: Path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            
            # Extract from master_suppression_list.json format
            if isinstance(data, dict):
                if "suppressed_emails" in data:
                    for email in data["suppressed_emails"]:
                        self._blocked_emails.add(str(email).strip().lower())
                # Extract from gmail_history_audit.json format
                if "bounced_addresses" in data:
                    for email in data["bounced_addresses"]:
                        self._blocked_emails.add(str(email).strip().lower())
            elif isinstance(data, list):
                for email in data:
                    self._blocked_emails.add(str(email).strip().lower())
        except Exception as e:
            print(f"[SuppressionEngine Warning] Could not load {path}: {e}")

    @property
    def total_blocked(self) -> int:
        return len(self._blocked_emails)

    def block(self, email: str):
        """Manually blocks an email address."""
        if email:
            self._blocked_emails.add(str(email).strip().lower())

    def is_suppressed(self, email: str) -> bool:
        """Returns True if the email is on the suppression or bounce list."""
        if not email:
            return True
        return email.strip().lower() in self._blocked_emails

    def add_suppression(self, email: str):
        """Dynamically add an address to the in-memory suppression set."""
        if email:
            self._blocked_emails.add(email.strip().lower())
