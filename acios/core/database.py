"""
ACIOS canonical local SQLite database.

Initializes schema and migrations for the local-first workspace. Other backends, if
retained for compatibility, are selected by the repository adapter and are not required
for the normal CLI/MCP workflow.
"""

import os
import sqlite3
from pathlib import Path
from typing import Optional

PROJECT_ROOT = Path(__file__).resolve().parents[2]
_configured_db_path = os.getenv("ACIOS_DB_PATH", "").strip()
if _configured_db_path:
    _candidate_db_path = Path(_configured_db_path).expanduser()
    DEFAULT_DB_PATH = (
        _candidate_db_path
        if _candidate_db_path.is_absolute()
        else PROJECT_ROOT / _candidate_db_path
    )
else:
    DEFAULT_DB_PATH = PROJECT_ROOT / "data" / "acios.db"


def get_db_connection(db_path: Optional[Path] = None) -> sqlite3.Connection:
    """Returns a SQLite connection with Row factory enabled."""
    path = db_path or DEFAULT_DB_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn


def init_db(db_path: Optional[Path] = None):
    """Initializes canonical tables and indexes if they do not exist."""
    conn = get_db_connection(db_path)
    cursor = conn.cursor()

    cursor.executescript("""
    -- 1. Organizations
    CREATE TABLE IF NOT EXISTS organizations (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT UNIQUE NOT NULL,
        country TEXT NOT NULL,
        city TEXT,
        sector TEXT,
        website TEXT,
        value_proposition TEXT,
        created_at TEXT NOT NULL
    );

    -- 2. Expansion Signals
    CREATE TABLE IF NOT EXISTS signals (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        organization_name TEXT NOT NULL,
        headline TEXT NOT NULL,
        signal_date TEXT,
        source_url TEXT,
        evidence_tier TEXT DEFAULT 'Verified Primary',
        details TEXT,
        score INTEGER DEFAULT 50,
        created_at TEXT NOT NULL,
        FOREIGN KEY (organization_name) REFERENCES organizations(name) ON UPDATE CASCADE ON DELETE CASCADE,
        UNIQUE(organization_name, headline)
    );

    -- 3. Decision-Makers & Contacts
    CREATE TABLE IF NOT EXISTS contacts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        organization_name TEXT NOT NULL,
        name TEXT NOT NULL,
        role TEXT NOT NULL,
        work_email TEXT,
        linkedin_url TEXT,
        verification_status TEXT DEFAULT 'Unverified',
        outreach_status TEXT DEFAULT 'Untouched',
        is_suppressed INTEGER DEFAULT 0,
        notes TEXT,
        updated_at TEXT NOT NULL,
        FOREIGN KEY (organization_name) REFERENCES organizations(name) ON UPDATE CASCADE ON DELETE CASCADE,
        UNIQUE(organization_name, name)
    );

    -- 4. Staged and Approved Drafts
    CREATE TABLE IF NOT EXISTS drafts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        recipient_email TEXT UNIQUE NOT NULL,
        recipient_name TEXT NOT NULL,
        organization_name TEXT NOT NULL,
        recipient_role TEXT NOT NULL,
        subject_line TEXT NOT NULL,
        body_text TEXT NOT NULL,
        word_count INTEGER NOT NULL,
        approval_hash TEXT NOT NULL,
        attachment_sha256 TEXT,
        cv_attached INTEGER NOT NULL DEFAULT 0,
        approved_snapshot_hash TEXT,
        status TEXT DEFAULT 'PENDING_APPROVAL',
        approved_by TEXT,
        approved_at TEXT,
        confirmation_note TEXT,
        idempotency_key TEXT,
        dispatched_at TEXT,
        created_at TEXT NOT NULL
    );

    -- 5. Master Suppression / Hard Bounce Registry
    CREATE TABLE IF NOT EXISTS suppression (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        email TEXT UNIQUE NOT NULL,
        reason TEXT,
        source TEXT,
        blocked_at TEXT NOT NULL
    );

    -- 6. Outreach Event Ledger
    CREATE TABLE IF NOT EXISTS outreach_events (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        recipient_email TEXT NOT NULL,
        event_type TEXT NOT NULL,
        timestamp TEXT NOT NULL,
        details TEXT
    );

    -- 7. System Settings & Profile Store
    CREATE TABLE IF NOT EXISTS settings (
        key TEXT PRIMARY KEY,
        value TEXT NOT NULL,
        updated_at TEXT NOT NULL
    );

    -- 8. Durable Background Jobs Store
    CREATE TABLE IF NOT EXISTS jobs (
        job_id TEXT PRIMARY KEY,
        job_type TEXT NOT NULL,
        status TEXT NOT NULL DEFAULT 'QUEUED',
        payload TEXT NOT NULL,
        result TEXT,
        error TEXT,
        attempts INTEGER DEFAULT 0,
        max_attempts INTEGER DEFAULT 3,
        idempotency_key TEXT UNIQUE,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL
    );

    -- 9. Idempotent Dispatch Locks
    CREATE TABLE IF NOT EXISTS dispatch_locks (
        idempotency_key TEXT PRIMARY KEY,
        draft_id INTEGER UNIQUE NOT NULL,
        recipient_email TEXT NOT NULL,
        status TEXT NOT NULL,
        dispatched_at TEXT NOT NULL
    );

    -- Indexes for fast queries
    CREATE INDEX IF NOT EXISTS idx_org_name ON organizations(name);
    CREATE INDEX IF NOT EXISTS idx_contact_email ON contacts(work_email);
    CREATE INDEX IF NOT EXISTS idx_suppression_email ON suppression(email);
    CREATE INDEX IF NOT EXISTS idx_draft_email ON drafts(recipient_email);
    CREATE INDEX IF NOT EXISTS idx_job_status ON jobs(status);
    """)

    # Safe schema migration for pre-existing local SQLite databases
    existing_draft_cols = {
        row["name"] for row in cursor.execute("PRAGMA table_info(drafts)").fetchall()
    }
    for col_name, col_type in [
        ("attachment_sha256", "TEXT"),
        ("cv_attached", "INTEGER NOT NULL DEFAULT 0"),
        ("approved_snapshot_hash", "TEXT"),
        ("approved_by", "TEXT"),
        ("approved_at", "TEXT"),
        ("confirmation_note", "TEXT"),
        ("idempotency_key", "TEXT"),
        ("dispatched_at", "TEXT"),
    ]:
        if col_name not in existing_draft_cols:
            cursor.execute(f"ALTER TABLE drafts ADD COLUMN {col_name} {col_type};")

    conn.commit()
    conn.close()
