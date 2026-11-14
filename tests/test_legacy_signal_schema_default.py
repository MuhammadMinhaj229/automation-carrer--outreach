"""Offline regression coverage for the legacy signals schema default."""

import sqlite3

from acios.core.database import init_db


def test_new_legacy_signal_without_tier_is_unverified(tmp_path):
    db_path = tmp_path / "signals.db"
    init_db(db_path)
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            "INSERT INTO organizations (name, country, created_at) VALUES (?, ?, ?)",
            ("Synthetic Example", "ZZ", "2026-01-01T00:00:00Z"),
        )
        conn.execute(
            "INSERT INTO signals (organization_name, headline, created_at) "
            "VALUES (?, ?, ?)",
            ("Synthetic Example", "Synthetic lead", "2026-01-01T00:00:00Z"),
        )
        tier = conn.execute("SELECT evidence_tier FROM signals").fetchone()[0]
        assert tier == "UNVERIFIED_NEEDS_PRIMARY_SOURCE"


def test_legacy_signal_schema_does_not_reclassify_existing_records(tmp_path):
    db_path = tmp_path / "legacy.db"
    with sqlite3.connect(db_path) as conn:
        conn.executescript(
            """
            CREATE TABLE organizations (
                id INTEGER PRIMARY KEY, name TEXT UNIQUE NOT NULL,
                country TEXT NOT NULL, created_at TEXT NOT NULL
            );
            CREATE TABLE signals (
                id INTEGER PRIMARY KEY, organization_name TEXT NOT NULL,
                headline TEXT NOT NULL, evidence_tier TEXT DEFAULT 'Verified Primary',
                created_at TEXT NOT NULL
            );
            INSERT INTO organizations (name, country, created_at)
            VALUES ('Synthetic Example', 'ZZ', '2026-01-01');
            INSERT INTO signals (organization_name, headline, created_at)
            VALUES ('Synthetic Example', 'Legacy row', '2026-01-01');
            """
        )
    init_db(db_path)
    with sqlite3.connect(db_path) as conn:
        assert conn.execute(
            "SELECT evidence_tier FROM signals WHERE headline = 'Legacy row'"
        ).fetchone()[0] == "Verified Primary"
