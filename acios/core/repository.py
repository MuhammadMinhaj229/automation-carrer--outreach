"""
ACIOS Career Intelligence Repository.
Provides clean, typed domain access to organizations, contacts, signals, drafts,
and safety suppression checks backed by the canonical SQLite store.
"""

from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any, List, Optional
import sqlite3

from acios.core.database import get_db_connection, init_db, DEFAULT_DB_PATH
from acios.models.organization import Organization, ExpansionSignal, SectorCategory
from acios.models.contact import Contact, VerificationStatus, OutreachStatus
from acios.models.email_draft import EmailDraft


class CareerRepository:
    def __init__(self, db_path: Optional[Path] = None):
        self.db_path = db_path or DEFAULT_DB_PATH
        init_db(self.db_path)

    def _conn(self) -> sqlite3.Connection:
        return get_db_connection(self.db_path)

    # ==========================================
    # Organizations
    # ==========================================

    def upsert_organization(self, org: Organization) -> int:
        """Inserts or updates an organization record."""
        now_iso = datetime.now(timezone.utc).isoformat()
        with self._conn() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO organizations (name, country, city, sector, website, value_proposition, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(name) DO UPDATE SET
                    country = excluded.country,
                    city = COALESCE(excluded.city, organizations.city),
                    sector = excluded.sector,
                    website = COALESCE(excluded.website, organizations.website),
                    value_proposition = COALESCE(excluded.value_proposition, organizations.value_proposition)
            """, (org.name, org.country, org.city, org.sector.value, str(org.website) if org.website else None, org.value_proposition, now_iso))
            
            # Also record any expansion signals
            for sig in org.signals:
                cursor.execute("""
                    INSERT INTO signals (organization_name, headline, signal_date, source_url, evidence_tier, details, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(organization_name, headline) DO UPDATE SET
                        signal_date = excluded.signal_date,
                        source_url = excluded.source_url,
                        evidence_tier = excluded.evidence_tier,
                        details = excluded.details
                """, (org.name, sig.headline, sig.signal_date, sig.source_url, sig.evidence_tier, sig.details, now_iso))
                
            conn.commit()
            return cursor.lastrowid

    def get_organization(self, name: str) -> Optional[dict]:
        with self._conn() as conn:
            row = conn.execute("SELECT * FROM organizations WHERE name = ?", (name,)).fetchone()
            if not row:
                return None
            org_data = dict(row)
            # fetch signals
            sig_rows = conn.execute("SELECT * FROM signals WHERE organization_name = ?", (name,)).fetchall()
            org_data["signals"] = [dict(s) for s in sig_rows]
            return org_data

    def list_organizations(self, country: Optional[str] = None) -> List[dict]:
        with self._conn() as conn:
            if country:
                rows = conn.execute("SELECT * FROM organizations WHERE country = ? ORDER BY name ASC", (country,)).fetchall()
            else:
                rows = conn.execute("SELECT * FROM organizations ORDER BY country, name ASC").fetchall()
            return [dict(r) for r in rows]

    # ==========================================
    # Decision-Makers & Contacts
    # ==========================================

    def upsert_contact(self, contact: Contact) -> int:
        now_iso = datetime.now(timezone.utc).isoformat()
        with self._conn() as conn:
            cursor = conn.cursor()
            cursor.execute("INSERT OR IGNORE INTO organizations (name, country, created_at) VALUES (?, 'GCC', ?)", (contact.organization_name, now_iso))
            cursor.execute("""
                INSERT INTO contacts (
                    organization_name, name, role, work_email, linkedin_url,
                    verification_status, outreach_status, is_suppressed, notes, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(organization_name, name) DO UPDATE SET
                    role = excluded.role,
                    work_email = excluded.work_email,
                    linkedin_url = excluded.linkedin_url,
                    verification_status = excluded.verification_status,
                    outreach_status = excluded.outreach_status,
                    is_suppressed = excluded.is_suppressed,
                    notes = excluded.notes,
                    updated_at = excluded.updated_at
            """, (
                contact.organization_name,
                contact.name,
                contact.role,
                contact.work_email,
                contact.linkedin_url,
                contact.verification_status.value,
                contact.outreach_status.value,
                1 if contact.is_suppressed else 0,
                contact.notes,
                now_iso
            ))
            conn.commit()
            return cursor.lastrowid

    def list_contacts(self, org_name: Optional[str] = None) -> List[dict]:
        with self._conn() as conn:
            if org_name:
                rows = conn.execute("SELECT * FROM contacts WHERE organization_name = ? ORDER BY name ASC", (org_name,)).fetchall()
            else:
                rows = conn.execute("SELECT * FROM contacts ORDER BY organization_name, name ASC").fetchall()
            return [dict(r) for r in rows]

    def update_contact_status(self, email: str, status: str) -> bool:
        """Updates outreach status for a contact by work email address."""
        clean_email = email.strip().lower()
        now_iso = datetime.now(timezone.utc).isoformat()
        with self._conn() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE contacts
                SET outreach_status = ?, updated_at = ?
                WHERE LOWER(work_email) = ?
            """, (status, now_iso, clean_email))
            conn.commit()
            return cursor.rowcount > 0

    # ==========================================
    # Drafts
    # ==========================================

    def upsert_draft(self, draft: EmailDraft, status: str = "STAGED") -> int:
        now_iso = datetime.now(timezone.utc).isoformat()
        with self._conn() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO drafts (
                    recipient_email, recipient_name, organization_name, recipient_role,
                    subject_line, body_text, word_count, approval_hash, status, created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(recipient_email) DO UPDATE SET
                    subject_line = excluded.subject_line,
                    body_text = excluded.body_text,
                    word_count = excluded.word_count,
                    approval_hash = excluded.approval_hash,
                    status = excluded.status
            """, (
                draft.recipient_email,
                draft.recipient_name,
                draft.organization_name,
                draft.recipient_role,
                draft.subject_line,
                draft.body_text,
                draft.word_count,
                draft.approval_hash,
                status,
                now_iso
            ))
            conn.commit()
            return cursor.lastrowid

    def list_drafts(self) -> List[dict]:
        with self._conn() as conn:
            rows = conn.execute("SELECT * FROM drafts ORDER BY id ASC").fetchall()
            return [dict(r) for r in rows]

    # ==========================================
    # Suppression
    # ==========================================

    def add_suppression(self, email: str, reason: str = "Hard Bounce", source: str = "Audit") -> bool:
        clean_email = email.strip().lower()
        now_iso = datetime.now(timezone.utc).isoformat()
        try:
            with self._conn() as conn:
                conn.execute("""
                    INSERT OR IGNORE INTO suppression (email, reason, source, blocked_at)
                    VALUES (?, ?, ?, ?)
                """, (clean_email, reason, source, now_iso))
                conn.commit()
                return True
        except Exception:
            return False

    def is_suppressed(self, email: Optional[str]) -> bool:
        if not email:
            return True
        clean_email = email.strip().lower()
        with self._conn() as conn:
            row = conn.execute("SELECT 1 FROM suppression WHERE email = ?", (clean_email,)).fetchone()
            return row is not None

    def get_suppression_count(self) -> int:
        with self._conn() as conn:
            row = conn.execute("SELECT COUNT(*) AS total FROM suppression").fetchone()
            return row["total"] if row else 0

    # ==========================================
    # Outreach Ledger & Signals
    # ==========================================

    def record_outreach_event(self, recipient_email: str, action_type: str, status: str = "DELIVERED", details: str = "", status_message: Optional[str] = None):
        now_iso = datetime.now(timezone.utc).isoformat()
        msg = status_message if status_message is not None else details
        with self._conn() as conn:
            conn.execute("""
                INSERT INTO outreach_events (recipient_email, event_type, timestamp, details)
                VALUES (?, ?, ?, ?)
            """, (recipient_email, action_type, now_iso, f"[{status}] {msg}" if status else msg))
            conn.commit()

    def list_outreach_events(self, limit: int = 50) -> List[dict]:
        with self._conn() as conn:
            rows = conn.execute("SELECT * FROM outreach_events ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
            result = []
            for r in rows:
                d = dict(r)
                det = d.get("details", "")
                stat = "DELIVERED" if "DELIVERED" in det or "SUCCESS" in det else ("LOCAL_STAGED" if "LOCAL" in det else "STAGED")
                result.append({
                    "id": d["id"],
                    "recipient_email": d["recipient_email"],
                    "action_type": d["event_type"],
                    "status": stat,
                    "status_message": det,
                    "timestamp": d["timestamp"]
                })
            return result

    def list_signals(self, country: Optional[str] = None, limit: int = 100) -> List[dict]:
        with self._conn() as conn:
            if country:
                rows = conn.execute("""
                    SELECT s.*, o.country FROM signals s
                    JOIN organizations o ON s.organization_name = o.name
                    WHERE o.country = ?
                    ORDER BY s.id DESC LIMIT ?
                """, (country, limit)).fetchall()
            else:
                rows = conn.execute("SELECT * FROM signals ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
            return [dict(r) for r in rows]

    # ==========================================
    # System Settings & Profile Store
    # ==========================================

    def set_setting(self, key: str, value: str):
        now_iso = datetime.now(timezone.utc).isoformat()
        with self._conn() as conn:
            conn.execute("""
                INSERT INTO settings (key, value, updated_at)
                VALUES (?, ?, ?)
                ON CONFLICT(key) DO UPDATE SET
                    value = excluded.value,
                    updated_at = excluded.updated_at
            """, (key, value, now_iso))
            conn.commit()

    def get_setting(self, key: str) -> Optional[str]:
        with self._conn() as conn:
            row = conn.execute("SELECT value FROM settings WHERE key = ?", (key,)).fetchone()
            return row["value"] if row else None

    def save_candidate_profile(self, profile_data: dict):
        import json
        self.set_setting("candidate_profile", json.dumps(profile_data))

    def get_candidate_profile(self) -> Optional[dict]:
        import json
        val = self.get_setting("candidate_profile")
        if val:
            try:
                return json.loads(val)
            except Exception:
                pass
        return None

    # ==========================================
    # System Metrics & Reconciliation
    # ==========================================

    def get_system_stats(self) -> Dict[str, Any]:
        with self._conn() as conn:
            orgs_count = conn.execute("SELECT COUNT(*) AS c FROM organizations").fetchone()["c"]
            contacts_count = conn.execute("SELECT COUNT(*) AS c FROM contacts").fetchone()["c"]
            drafts_count = conn.execute("SELECT COUNT(*) AS c FROM drafts").fetchone()["c"]
            supp_count = conn.execute("SELECT COUNT(*) AS c FROM suppression").fetchone()["c"]
            signals_count = conn.execute("SELECT COUNT(*) AS c FROM signals").fetchone()["c"]
            
            return {
                "total_organizations": orgs_count,
                "total_contacts": contacts_count,
                "total_signals": signals_count,
                "total_staged_drafts": drafts_count,
                "total_suppressed_emails": supp_count
            }
