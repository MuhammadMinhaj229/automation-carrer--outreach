"""
ACIOS Career Intelligence Repository.
Provides clean, typed domain access to organizations, contacts, signals, drafts,
approvals, idempotent dispatch locks, durable jobs, and safety suppression checks.
Supports MongoDB Atlas in production (via MONGODB_URI) and SQLite for local development.
"""

from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any, List, Optional
import json
import os
import hashlib
import sqlite3
import uuid

from acios.core.database import get_db_connection, init_db, DEFAULT_DB_PATH
from acios.models.organization import Organization, ExpansionSignal, SectorCategory
from acios.models.contact import Contact, VerificationStatus, OutreachStatus
from acios.models.email_draft import EmailDraft


class CareerRepository:
    def __init__(
        self,
        db_path: Optional[Path] = None,
        mongo_uri: Optional[str] = None,
        mongo_client: Any = None,
        mongo_db_name: Optional[str] = None,
    ):
        # SQLite is the local-first default. Legacy MongoDB credentials alone do
        # not silently switch storage or send private career data to a remote service.
        storage_backend = os.getenv("ACIOS_STORAGE_BACKEND", "sqlite").strip().lower()
        use_mongo = mongo_client is not None or mongo_uri is not None or storage_backend == "mongodb"
        if storage_backend not in {"sqlite", "mongodb"}:
            raise ValueError("ACIOS_STORAGE_BACKEND must be 'sqlite' or 'mongodb'.")

        effective_mongo_uri = mongo_uri or (
            os.getenv("MONGODB_URI", "").strip()
            if db_path is None and storage_backend == "mongodb"
            else ""
        )
        self._mongo = None
        if use_mongo:
            if mongo_client is None and not effective_mongo_uri:
                raise RuntimeError(
                    "MongoDB was explicitly selected but MONGODB_URI is not configured."
                )
            from acios.core.mongo_repository import MongoCareerBackend

            db_name = mongo_db_name or os.getenv("MONGODB_DB_NAME", "acios_local_compat")
            self._mongo = MongoCareerBackend(
                mongo_uri=effective_mongo_uri or None,
                db_name=db_name,
                mongo_client=mongo_client,
            )
            self.db_path = db_path or DEFAULT_DB_PATH
        else:
            # A persistent host must never silently fall back to an ephemeral SQLite
            # database. SQLite is an explicit local-development option only.
            runtime_environment = os.getenv("ACIOS_ENV", "").strip().lower()
            managed_production_host = any(
                os.getenv(name)
                for name in (
                    "RAILWAY_ENVIRONMENT",
                    "RENDER",
                    "K_SERVICE",
                    "WEBSITE_INSTANCE_ID",
                    "FLY_APP_NAME",
                )
            )
            if (
                db_path is None
                and (
                    runtime_environment == "production"
                    or managed_production_host
                )
            ):
                raise RuntimeError(
                    "MONGODB_URI is required when ACIOS_ENV=production. "
                    "Configure MongoDB Atlas in the backend and worker secret stores."
                )
            self.db_path = db_path or DEFAULT_DB_PATH
            init_db(self.db_path)

    @property
    def storage_engine(self) -> str:
        return "mongodb" if self._mongo is not None else "sqlite"

    def _conn(self) -> sqlite3.Connection:
        return get_db_connection(self.db_path)

    # ==========================================
    # Organizations & Dossier
    # ==========================================

    def upsert_organization(self, org: Organization) -> int:
        """Inserts or updates an organization record."""
        if self._mongo is not None:
            return self._mongo.upsert_organization(org)

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
        if self._mongo is not None:
            return self._mongo.get_organization(name)

        with self._conn() as conn:
            row = conn.execute("SELECT * FROM organizations WHERE name = ?", (name,)).fetchone()
            if not row:
                return None
            org_data = dict(row)
            sig_rows = conn.execute("SELECT * FROM signals WHERE organization_name = ?", (name,)).fetchall()
            org_data["signals"] = [dict(s) for s in sig_rows]
            return org_data

    def get_company_dossier(self, organization_name: str) -> Optional[dict]:
        """Retrieves complete sourced dossier for an organization (org, signals, contacts, drafts)."""
        org = self.get_organization(organization_name)
        contacts = self.list_contacts(org_name=organization_name)
        drafts = [
            d for d in self.list_drafts() if d.get("organization_name") == organization_name
        ]
        if not org and not contacts and not drafts:
            return None
        return {
            "organization_name": organization_name,
            "organization": org,
            "signals": (org or {}).get("signals", []),
            "contacts": contacts,
            "drafts": drafts,
        }

    def list_organizations(self, country: Optional[str] = None) -> List[dict]:
        if self._mongo is not None:
            return self._mongo.list_organizations(country=country)

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
        if self._mongo is not None:
            return self._mongo.upsert_contact(contact)

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
        if self._mongo is not None:
            return self._mongo.list_contacts(org_name=org_name)

        with self._conn() as conn:
            if org_name:
                rows = conn.execute("SELECT * FROM contacts WHERE organization_name = ? ORDER BY name ASC", (org_name,)).fetchall()
            else:
                rows = conn.execute("SELECT * FROM contacts ORDER BY organization_name, name ASC").fetchall()
            return [dict(r) for r in rows]

    def update_contact_status(self, email: str, status: str) -> bool:
        """Updates outreach status for a contact by work email address."""
        if self._mongo is not None:
            return self._mongo.update_contact_status(email, status)

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
    # Drafts & Explicit Approval Flow
    # ==========================================

    def upsert_draft(self, draft: EmailDraft, status: str = "STAGED") -> int:
        """Persist a draft and bind its integrity hash to the currently attached resume.

        A changed message or resume resets the record to the requested pending state;
        approval metadata is deliberately cleared on every replacement.
        """
        existing_draft = self.get_draft_by_email(draft.recipient_email)
        if existing_draft and existing_draft.get("status") in {
            "DISPATCHED", "REPLIED", "BOUNCED", "OPTED_OUT", "CLOSED",
            "SUPPRESSED", "REQUIRES_RECONCILIATION",
        }:
            raise ValueError(
                "This recipient has a terminal or unresolved outreach state; "
                "create a new reviewed case instead of overwriting the existing record."
            )
        configured_resume_dir = os.getenv("ACIOS_RESUME_DIR", "").strip()
        resume_path = (
            Path(configured_resume_dir).expanduser().resolve() / "master_resume.pdf"
            if configured_resume_dir
            else Path(__file__).resolve().parent.parent.parent / "data" / "resume" / "master_resume.pdf"
        )
        attachment_sha256 = draft.attachment_sha256
        cv_attached = bool(draft.cv_attached and attachment_sha256)
        if resume_path.is_file():
            try:
                attachment_sha256 = hashlib.sha256(resume_path.read_bytes()).hexdigest()
                cv_attached = True
            except OSError:
                attachment_sha256 = None
                cv_attached = False
        persisted_draft = draft.model_copy(update={
            "attachment_sha256": attachment_sha256,
            "cv_attached": cv_attached,
        })
        if self._mongo is not None:
            return self._mongo.upsert_draft(persisted_draft, status=status)

        now_iso = datetime.now(timezone.utc).isoformat()
        with self._conn() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO drafts (
                    recipient_email, recipient_name, organization_name, recipient_role,
                    subject_line, body_text, word_count, approval_hash, attachment_sha256,
                    cv_attached, approved_snapshot_hash, status, created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, NULL, ?, ?)
                ON CONFLICT(recipient_email) DO UPDATE SET
                    recipient_name = excluded.recipient_name,
                    organization_name = excluded.organization_name,
                    recipient_role = excluded.recipient_role,
                    subject_line = excluded.subject_line,
                    body_text = excluded.body_text,
                    word_count = excluded.word_count,
                    approval_hash = excluded.approval_hash,
                    attachment_sha256 = excluded.attachment_sha256,
                    cv_attached = excluded.cv_attached,
                    approved_snapshot_hash = NULL,
                    approved_by = NULL,
                    approved_at = NULL,
                    confirmation_note = NULL,
                    idempotency_key = NULL,
                    dispatched_at = NULL,
                    status = excluded.status
            """, (
                persisted_draft.recipient_email.strip().lower(),
                persisted_draft.recipient_name,
                persisted_draft.organization_name,
                persisted_draft.recipient_role,
                persisted_draft.subject_line,
                persisted_draft.body_text,
                persisted_draft.word_count,
                persisted_draft.approval_hash,
                persisted_draft.attachment_sha256,
                int(persisted_draft.cv_attached),
                status,
                now_iso
            ))
            conn.commit()
            row = conn.execute(
                "SELECT id FROM drafts WHERE LOWER(recipient_email) = ?",
                (persisted_draft.recipient_email.strip().lower(),)
            ).fetchone()
            return int(row["id"]) if row else cursor.lastrowid

    def list_drafts(self) -> List[dict]:
        if self._mongo is not None:
            return self._mongo.list_drafts()

        with self._conn() as conn:
            rows = conn.execute("SELECT * FROM drafts ORDER BY id ASC").fetchall()
            return [dict(r) for r in rows]

    def get_draft_by_id(self, draft_id: int) -> Optional[dict]:
        if self._mongo is not None:
            return self._mongo.get_draft_by_id(draft_id)

        with self._conn() as conn:
            row = conn.execute("SELECT * FROM drafts WHERE id = ?", (int(draft_id),)).fetchone()
            return dict(row) if row else None

    def get_draft_by_email(self, recipient_email: str) -> Optional[dict]:
        if self._mongo is not None:
            return self._mongo.get_draft_by_email(recipient_email)

        with self._conn() as conn:
            row = conn.execute(
                "SELECT * FROM drafts WHERE LOWER(recipient_email) = ?",
                (recipient_email.strip().lower(),),
            ).fetchone()
            return dict(row) if row else None

    def list_pending_approvals(self) -> List[dict]:
        if self._mongo is not None:
            return self._mongo.list_pending_approvals()

        with self._conn() as conn:
            rows = conn.execute(
                "SELECT * FROM drafts WHERE status IN ('STAGED', 'PENDING_APPROVAL') ORDER BY id ASC"
            ).fetchall()
            return [dict(r) for r in rows]

    def approve_draft(
        self, draft_id: int, approved_by: str = "operator", confirmation_note: str = ""
    ) -> Optional[dict]:
        if self._mongo is not None:
            return self._mongo.approve_draft(
                draft_id=draft_id,
                approved_by=approved_by,
                confirmation_note=confirmation_note,
            )

        now_iso = datetime.now(timezone.utc).isoformat()
        existing = self.get_draft_by_id(draft_id)
        if not existing:
            return None
        if self.is_suppressed(existing.get("recipient_email")):
            raise ValueError("Suppressed recipients cannot be approved for outreach.")
        if existing.get("status") in {
            "DISPATCHED", "REPLIED", "BOUNCED", "OPTED_OUT", "CLOSED", "SUPPRESSED",
        }:
            raise ValueError(
                f"Draft {draft_id} has a terminal outreach status and cannot be approved."
            )
        if existing.get("status") == "REQUIRES_RECONCILIATION":
            raise ValueError(f"Draft {draft_id} requires send-outcome reconciliation.")

        approval_model = EmailDraft(
            recipient_email=existing["recipient_email"],
            recipient_name=existing["recipient_name"],
            organization_name=existing["organization_name"],
            recipient_role=existing["recipient_role"],
            subject_line=existing["subject_line"],
            body_text=existing["body_text"],
            cv_attached=bool(existing.get("cv_attached", False)),
            attachment_sha256=existing.get("attachment_sha256"),
        )
        snapshot_hash = approval_model.approval_hash
        with self._conn() as conn:
            conn.execute(
                """
                UPDATE drafts
                SET status = 'APPROVED',
                    approval_hash = ?,
                    approved_snapshot_hash = ?,
                    approved_by = ?,
                    approved_at = ?,
                    confirmation_note = ?
                WHERE id = ?
                """,
                (snapshot_hash, snapshot_hash, approved_by, now_iso, confirmation_note, int(draft_id)),
            )
            conn.commit()

        self.record_outreach_event(
            recipient_email=existing["recipient_email"],
            action_type="APPROVED",
            status="APPROVED",
            details=f"Draft #{draft_id} approved by {approved_by}. {confirmation_note}".strip(),
        )
        return self.get_draft_by_id(draft_id)

    def claim_dispatch_lock(
        self, draft_id: int, recipient_email: str, idempotency_key: str
    ) -> Dict[str, Any]:
        """Atomically claims a send lock so no draft or idempotency key is ever dispatched twice."""
        if self._mongo is not None:
            return self._mongo.claim_dispatch_lock(
                draft_id=draft_id,
                recipient_email=recipient_email,
                idempotency_key=idempotency_key,
            )

        now_iso = datetime.now(timezone.utc).isoformat()
        with self._conn() as conn:
            existing = conn.execute(
                "SELECT * FROM dispatch_locks WHERE idempotency_key = ? OR draft_id = ?",
                (idempotency_key, int(draft_id)),
            ).fetchone()
            if existing:
                return {
                    "acquired": False,
                    "duplicate_prevented": True,
                    "existing_lock": dict(existing),
                }
            try:
                conn.execute(
                    """
                    INSERT INTO dispatch_locks (idempotency_key, draft_id, recipient_email, status, dispatched_at)
                    VALUES (?, ?, ?, 'LOCKED', ?)
                    """,
                    (idempotency_key, int(draft_id), recipient_email.strip().lower(), now_iso),
                )
                conn.commit()
                return {
                    "acquired": True,
                    "duplicate_prevented": False,
                    "existing_lock": {
                        "idempotency_key": idempotency_key,
                        "draft_id": int(draft_id),
                        "recipient_email": recipient_email.strip().lower(),
                        "status": "LOCKED",
                        "dispatched_at": now_iso,
                    },
                }
            except sqlite3.IntegrityError:
                existing_after = conn.execute(
                    "SELECT * FROM dispatch_locks WHERE idempotency_key = ? OR draft_id = ?",
                    (idempotency_key, int(draft_id)),
                ).fetchone()
                return {
                    "acquired": False,
                    "duplicate_prevented": True,
                    "existing_lock": dict(existing_after) if existing_after else None,
                }

    def mark_dispatch_requires_reconciliation(self, draft_id: int, details: str) -> None:
        """Retain the send lock and require manual reconciliation after an ambiguous SMTP result."""
        if self._mongo is not None:
            self._mongo.mark_dispatch_requires_reconciliation(draft_id, details)
            return

        with self._conn() as conn:
            row = conn.execute(
                "SELECT recipient_email FROM dispatch_locks WHERE draft_id = ?",
                (int(draft_id),),
            ).fetchone()
            conn.execute(
                "UPDATE dispatch_locks SET status = 'REQUIRES_RECONCILIATION' WHERE draft_id = ?",
                (int(draft_id),),
            )
            conn.commit()
        if row:
            self.record_outreach_event(
                recipient_email=row["recipient_email"],
                action_type="SEND_OUTCOME_UNKNOWN",
                status="REQUIRES_RECONCILIATION",
                details=(details or "SMTP outcome could not be confirmed.")[:1000],
            )

    def mark_draft_dispatched(self, draft_id: int, idempotency_key: str) -> Optional[dict]:
        if self._mongo is not None:
            return self._mongo.mark_draft_dispatched(draft_id, idempotency_key)

        now_iso = datetime.now(timezone.utc).isoformat()
        with self._conn() as conn:
            conn.execute(
                """
                UPDATE drafts
                SET status = 'DISPATCHED',
                    idempotency_key = ?,
                    dispatched_at = ?
                WHERE id = ?
                """,
                (idempotency_key, now_iso, int(draft_id)),
            )
            conn.execute(
                """
                UPDATE dispatch_locks
                SET status = 'DISPATCHED',
                    dispatched_at = ?
                WHERE draft_id = ?
                """,
                (now_iso, int(draft_id)),
            )
            conn.commit()
        return self.get_draft_by_id(draft_id)

    # ==========================================
    # Suppression
    # ==========================================

    def add_suppression(self, email: str, reason: str = "Hard Bounce", source: str = "Audit") -> bool:
        if self._mongo is not None:
            return self._mongo.add_suppression(email, reason=reason, source=source)

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
        if self._mongo is not None:
            return self._mongo.is_suppressed(email)

        if not email:
            return True
        clean_email = email.strip().lower()
        with self._conn() as conn:
            row = conn.execute("SELECT 1 FROM suppression WHERE email = ?", (clean_email,)).fetchone()
            return row is not None

    def get_suppression_count(self) -> int:
        if self._mongo is not None:
            return self._mongo.get_suppression_count()

        with self._conn() as conn:
            row = conn.execute("SELECT COUNT(*) AS total FROM suppression").fetchone()
            return row["total"] if row else 0

    # ==========================================
    # Outreach Ledger & Signals
    # ==========================================

    def record_outreach_event(self, recipient_email: str, action_type: str, status: str = "DELIVERED", details: str = "", status_message: Optional[str] = None):
        if self._mongo is not None:
            self._mongo.record_outreach_event(
                recipient_email=recipient_email,
                action_type=action_type,
                status=status,
                details=details,
                status_message=status_message,
            )
            return

        now_iso = datetime.now(timezone.utc).isoformat()
        msg = status_message if status_message is not None else details
        with self._conn() as conn:
            conn.execute("""
                INSERT INTO outreach_events (recipient_email, event_type, timestamp, details)
                VALUES (?, ?, ?, ?)
            """, (recipient_email, action_type, now_iso, f"[{status}] {msg}" if status else msg))
            conn.commit()

    def list_outreach_events(self, limit: int = 50) -> List[dict]:
        if self._mongo is not None:
            return self._mongo.list_outreach_events(limit=limit)

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
        if self._mongo is not None:
            return self._mongo.list_signals(country=country, limit=limit)

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

    def search_growth_signals(
        self, query: str = "", country: Optional[str] = None, limit: int = 25
    ) -> List[dict]:
        if self._mongo is not None:
            return self._mongo.search_growth_signals(query=query, country=country, limit=limit)

        all_signals = self.list_signals(country=country, limit=250)
        q = query.strip().lower()
        if not q:
            return all_signals[:limit]
        filtered = [
            s
            for s in all_signals
            if q in (s.get("organization_name") or "").lower()
            or q in (s.get("headline") or "").lower()
            or q in (s.get("details") or "").lower()
        ]
        return filtered[:limit]

    # ==========================================
    # Local source provenance, discovery events, and time-aware claims
    # ==========================================

    def record_source_document(self, source: Dict[str, Any]) -> int:
        """Persist a fetched/public source and its content hash without calling it verified."""
        if self._mongo is not None:
            raise RuntimeError("The provenance ledger is available in the local SQLite backend only.")

        from urllib.parse import urlsplit, urlunsplit

        raw_url = str(source.get("url") or source.get("final_url") or "").strip()
        parts = urlsplit(raw_url)
        if parts.scheme not in {"http", "https"} or not parts.hostname:
            raise ValueError("A source document needs a valid HTTP(S) URL.")
        if parts.username or parts.password:
            raise ValueError("Source URLs containing embedded credentials are not accepted.")
        safe_url = urlunsplit((parts.scheme.lower(), parts.netloc.lower(), parts.path, parts.query, ""))
        title = str(source.get("title") or "").strip()[:1000]
        excerpt = str(source.get("excerpt") or "").strip()[:5000]
        content_text = str(source.get("content_text") or source.get("content_markdown") or "")
        # Bound local source storage; source documents are an evidence cache, not a raw-web archive.
        content_text = content_text[:100_000]
        content_hash = str(source.get("content_hash") or "").strip()
        if not content_hash:
            material = content_text or excerpt or title
            content_hash = hashlib.sha256(material.encode("utf-8")).hexdigest()
        source_type = str(source.get("source_type") or "UNKNOWN").strip().upper()
        retrieved_at = str(source.get("retrieved_at") or datetime.now(timezone.utc).isoformat())
        metadata = source.get("metadata") or {}
        now_iso = datetime.now(timezone.utc).isoformat()

        with self._conn() as conn:
            conn.execute(
                """
                INSERT INTO source_documents (
                    url, canonical_url, publisher, title, source_type, retrieved_at,
                    published_at, content_hash, excerpt, content_text, extraction_provider,
                    verification_status, metadata_json
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(url, content_hash) DO UPDATE SET
                    canonical_url = COALESCE(excluded.canonical_url, source_documents.canonical_url),
                    publisher = COALESCE(excluded.publisher, source_documents.publisher),
                    title = CASE WHEN excluded.title != '' THEN excluded.title ELSE source_documents.title END,
                    excerpt = CASE WHEN excluded.excerpt != '' THEN excluded.excerpt ELSE source_documents.excerpt END,
                    content_text = CASE WHEN excluded.content_text != '' THEN excluded.content_text ELSE source_documents.content_text END,
                    metadata_json = excluded.metadata_json
                """,
                (
                    safe_url,
                    source.get("canonical_url"),
                    source.get("publisher"),
                    title,
                    source_type,
                    retrieved_at,
                    source.get("published_at"),
                    content_hash,
                    excerpt,
                    content_text,
                    source.get("extraction_provider") or source.get("provider"),
                    source.get("verification_status") or "CAPTURED_NEEDS_REVIEW",
                    json.dumps(metadata, ensure_ascii=False, default=str),
                ),
            )
            row = conn.execute(
                "SELECT id FROM source_documents WHERE url = ? AND content_hash = ?",
                (safe_url, content_hash),
            ).fetchone()
            if row is None:
                raise RuntimeError("The source document could not be persisted.")
            return int(row["id"])

    def record_discovery_event(self, record: Dict[str, Any]) -> Dict[str, Any]:
        """Persist an RSS/search result as an unverified discovery lead."""
        if self._mongo is not None:
            raise RuntimeError("The local discovery provenance ledger requires SQLite.")

        source_url = str(record.get("source_url") or "").strip()
        headline = str(record.get("headline") or "").strip()
        if not source_url or not headline:
            raise ValueError("Discovery records require a real source URL and headline.")

        fingerprint = str(record.get("discovery_record_sha256") or "").strip()
        if not fingerprint:
            fingerprint = hashlib.sha256(
                f"{source_url}\n{headline}\n{record.get('evidence_excerpt') or ''}".encode("utf-8")
            ).hexdigest()
        source_id = self.record_source_document({
            "url": source_url,
            "publisher": record.get("source_outlet"),
            "title": headline,
            "source_type": record.get("source_type") or "NEWS_AGGREGATOR_RESULT",
            "retrieved_at": record.get("retrieved_at"),
            "published_at": record.get("published_at"),
            "content_hash": fingerprint,
            "excerpt": record.get("evidence_excerpt"),
            "content_text": record.get("evidence_excerpt"),
            "extraction_provider": "growth_signal_scanner",
            "verification_status": "DISCOVERED_NEEDS_PRIMARY_VERIFICATION",
            "metadata": {
                "entity_resolution_status": record.get("entity_resolution_status"),
                "published_date_raw": record.get("published_date_raw"),
                "event_date_status": record.get("event_date_status"),
            },
        })
        now_iso = datetime.now(timezone.utc).isoformat()
        with self._conn() as conn:
            conn.execute(
                """
                INSERT INTO organization_events (
                    organization_name, event_type, headline, event_date, publication_date,
                    source_id, verification_status, relevance_score, score_type,
                    event_fingerprint, record_json, created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(event_fingerprint) DO UPDATE SET
                    organization_name = excluded.organization_name,
                    event_type = excluded.event_type,
                    headline = excluded.headline,
                    publication_date = excluded.publication_date,
                    source_id = excluded.source_id,
                    verification_status = 'DISCOVERED_NEEDS_PRIMARY_VERIFICATION',
                    relevance_score = excluded.relevance_score,
                    score_type = excluded.score_type,
                    record_json = excluded.record_json,
                    updated_at = excluded.updated_at
                """,
                (
                    record.get("organization_name"),
                    record.get("trigger_category") or record.get("trigger_type") or "UNCLASSIFIED",
                    headline,
                    record.get("event_date"),
                    record.get("published_date"),
                    source_id,
                    "DISCOVERED_NEEDS_PRIMARY_VERIFICATION",
                    record.get("score"),
                    record.get("score_type") or "HEURISTIC_NOT_PROBABILITY",
                    fingerprint,
                    json.dumps(record, ensure_ascii=False, default=str),
                    now_iso,
                    now_iso,
                ),
            )
            row = conn.execute(
                "SELECT id, source_id, verification_status FROM organization_events WHERE event_fingerprint = ?",
                (fingerprint,),
            ).fetchone()
            return dict(row) if row else {"source_id": source_id, "verification_status": "DISCOVERED_NEEDS_PRIMARY_VERIFICATION"}

    def list_discovery_events(
        self, query: str = "", country: Optional[str] = None, limit: int = 100
    ) -> List[dict]:
        """List discovery leads with source URL, excerpt, hashes, and explicit review status."""
        if self._mongo is not None:
            raise RuntimeError("The local discovery provenance ledger requires SQLite.")
        params: List[Any] = []
        where: List[str] = []
        if query.strip():
            where.append("(LOWER(e.headline) LIKE ? OR LOWER(COALESCE(e.organization_name, '')) LIKE ?)")
            needle = f"%{query.strip().lower()}%"
            params.extend([needle, needle])
        if country:
            where.append("LOWER(COALESCE(json_extract(e.record_json, '$.country'), '')) = ?")
            params.append(country.strip().lower())
        clause = ("WHERE " + " AND ".join(where)) if where else ""
        params.append(max(1, min(int(limit), 1000)))
        with self._conn() as conn:
            rows = conn.execute(
                f"""
                SELECT e.*, s.url AS source_url, s.publisher, s.source_type,
                       s.retrieved_at, s.published_at AS source_published_at,
                       s.content_hash, s.excerpt
                FROM organization_events e
                JOIN source_documents s ON s.id = e.source_id
                {clause}
                ORDER BY e.id DESC LIMIT ?
                """,
                tuple(params),
            ).fetchall()
            return [dict(row) for row in rows]

    def add_claim(
        self,
        entity_type: str,
        entity_key: str,
        predicate: str,
        claim_value: str,
        source_id: int,
        excerpt: str,
        valid_from: Optional[str] = None,
        valid_to: Optional[str] = None,
    ) -> int:
        """Add a claim with a direct source reference; new claims begin unconfirmed."""
        if self._mongo is not None:
            raise RuntimeError("The claim provenance ledger requires SQLite.")
        if not all(str(v or "").strip() for v in (entity_type, entity_key, predicate, claim_value, excerpt)):
            raise ValueError("Entity, predicate, claim value, and source excerpt are required.")
        now_iso = datetime.now(timezone.utc).isoformat()
        with self._conn() as conn:
            source = conn.execute(
                "SELECT id FROM source_documents WHERE id = ?", (int(source_id),)
            ).fetchone()
            if not source:
                raise ValueError(f"Source document #{source_id} does not exist.")
            conn.execute(
                """
                INSERT INTO claims (
                    entity_type, entity_key, predicate, claim_value, valid_from, valid_to,
                    source_id, excerpt, verification_status, created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'UNCONFIRMED', ?)
                ON CONFLICT(entity_type, entity_key, predicate, claim_value, source_id) DO UPDATE SET
                    valid_from = excluded.valid_from,
                    valid_to = excluded.valid_to,
                    excerpt = excluded.excerpt
                """,
                (
                    entity_type.strip().lower(), entity_key.strip(), predicate.strip(),
                    claim_value.strip(), valid_from, valid_to, int(source_id), excerpt.strip()[:5000], now_iso,
                ),
            )
            row = conn.execute(
                """
                SELECT id FROM claims
                WHERE entity_type = ? AND entity_key = ? AND predicate = ?
                  AND claim_value = ? AND source_id = ?
                """,
                (entity_type.strip().lower(), entity_key.strip(), predicate.strip(), claim_value.strip(), int(source_id)),
            ).fetchone()
            return int(row["id"])

    def review_claim(
        self,
        claim_id: int,
        verification_status: str,
        reviewed_by: str,
        review_note: str,
        confidence: Optional[float] = None,
    ) -> dict:
        """Record an explicit human review, requiring source suitability for strong labels."""
        if self._mongo is not None:
            raise RuntimeError("The claim provenance ledger requires SQLite.")
        allowed = {"VERIFIED_PRIMARY", "CORROBORATED", "UNCONFIRMED", "CONFLICTED", "STALE", "REJECTED"}
        status = str(verification_status or "").strip().upper()
        if status not in allowed:
            raise ValueError(f"Unsupported claim review status: {status}")
        if not reviewed_by.strip() or not review_note.strip():
            raise ValueError("A reviewer identity and review note are required.")
        if confidence is not None and not 0.0 <= float(confidence) <= 1.0:
            raise ValueError("Confidence must be between 0 and 1.")
        now_iso = datetime.now(timezone.utc).isoformat()
        with self._conn() as conn:
            row = conn.execute(
                """
                SELECT c.*, s.source_type
                FROM claims c JOIN source_documents s ON s.id = c.source_id
                WHERE c.id = ?
                """,
                (int(claim_id),),
            ).fetchone()
            if not row:
                raise ValueError(f"Claim #{claim_id} does not exist.")
            if status == "VERIFIED_PRIMARY" and row["source_type"] not in {
                "OFFICIAL_PRIMARY", "REGULATORY_PRIMARY", "OFFICIAL_PROFILE", "OFFICIAL_COMPANY_PAGE"
            }:
                raise ValueError(
                    "VERIFIED_PRIMARY requires a source explicitly classified as an official primary source."
                )
            if status == "CORROBORATED":
                peer = conn.execute(
                    """
                    SELECT COUNT(DISTINCT s.publisher) AS publishers
                    FROM claims c JOIN source_documents s ON s.id = c.source_id
                    WHERE c.entity_type = ? AND c.entity_key = ? AND c.predicate = ?
                      AND c.claim_value = ? AND c.verification_status IN ('CORROBORATED', 'VERIFIED_PRIMARY')
                      AND s.publisher IS NOT NULL AND TRIM(s.publisher) != ''
                    """,
                    (row["entity_type"], row["entity_key"], row["predicate"], row["claim_value"]),
                ).fetchone()
                if int(peer["publishers"] or 0) < 2:
                    raise ValueError(
                        "CORROBORATED requires independent source records from at least two named publishers."
                    )
            conn.execute(
                """
                UPDATE claims
                SET verification_status = ?, confidence = ?, reviewed_by = ?,
                    reviewed_at = ?, review_note = ?
                WHERE id = ?
                """,
                (status, confidence, reviewed_by.strip(), now_iso, review_note.strip()[:4000], int(claim_id)),
            )
            conn.commit()
            result = conn.execute(
                """
                SELECT c.*, s.url AS source_url, s.publisher, s.source_type,
                       s.content_hash, s.retrieved_at
                FROM claims c JOIN source_documents s ON s.id = c.source_id
                WHERE c.id = ?
                """,
                (int(claim_id),),
            ).fetchone()
            return dict(result) if result else {"id": int(claim_id), "verification_status": status}

    def list_claims(self, query: str = "", limit: int = 100) -> List[dict]:
        """Return time-aware claims with source and reviewer provenance."""
        if self._mongo is not None:
            raise RuntimeError("The claim provenance ledger requires SQLite.")
        params: List[Any] = []
        clause = ""
        if query.strip():
            needle = f"%{query.strip().lower()}%"
            clause = "WHERE LOWER(c.entity_key) LIKE ? OR LOWER(c.predicate) LIKE ? OR LOWER(c.claim_value) LIKE ?"
            params.extend([needle, needle, needle])
        params.append(max(1, min(int(limit), 1000)))
        with self._conn() as conn:
            rows = conn.execute(
                f"""
                SELECT c.*, s.url AS source_url, s.publisher, s.source_type,
                       s.content_hash, s.retrieved_at
                FROM claims c JOIN source_documents s ON s.id = c.source_id
                {clause}
                ORDER BY c.id DESC LIMIT ?
                """,
                tuple(params),
            ).fetchall()
            return [dict(row) for row in rows]

    # ==========================================
    # Durable Background Jobs Store
    # ==========================================

    def create_job(
        self,
        job_type: str,
        payload: Dict[str, Any],
        idempotency_key: Optional[str] = None,
        max_attempts: int = 3,
    ) -> dict:
        if self._mongo is not None:
            return self._mongo.create_job(
                job_type=job_type,
                payload=payload,
                idempotency_key=idempotency_key,
                max_attempts=max_attempts,
            )

        now_iso = datetime.now(timezone.utc).isoformat()
        with self._conn() as conn:
            if idempotency_key:
                existing = conn.execute(
                    "SELECT * FROM jobs WHERE idempotency_key = ?", (idempotency_key,)
                ).fetchone()
                if existing:
                    return self._format_sqlite_job(dict(existing))

            job_id = f"job_{uuid.uuid4().hex[:16]}"
            conn.execute(
                """
                INSERT INTO jobs (job_id, job_type, status, payload, attempts, max_attempts, idempotency_key, created_at, updated_at)
                VALUES (?, ?, 'QUEUED', ?, 0, ?, ?, ?, ?)
                """,
                (job_id, job_type, json.dumps(payload), max_attempts, idempotency_key, now_iso, now_iso),
            )
            conn.commit()
            row = conn.execute("SELECT * FROM jobs WHERE job_id = ?", (job_id,)).fetchone()
            return self._format_sqlite_job(dict(row))

    def get_job(self, job_id: str) -> Optional[dict]:
        if self._mongo is not None:
            return self._mongo.get_job(job_id)

        with self._conn() as conn:
            row = conn.execute("SELECT * FROM jobs WHERE job_id = ?", (job_id,)).fetchone()
            return self._format_sqlite_job(dict(row)) if row else None

    def list_jobs(self, status: Optional[str] = None, limit: int = 50) -> List[dict]:
        if self._mongo is not None:
            return self._mongo.list_jobs(status=status, limit=limit)

        with self._conn() as conn:
            if status:
                rows = conn.execute(
                    "SELECT * FROM jobs WHERE status = ? ORDER BY created_at DESC LIMIT ?",
                    (status, limit),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM jobs ORDER BY created_at DESC LIMIT ?", (limit,)
                ).fetchall()
            return [self._format_sqlite_job(dict(r)) for r in rows]

    def claim_next_job(self) -> Optional[dict]:
        if self._mongo is not None:
            return self._mongo.claim_next_job()

        now_iso = datetime.now(timezone.utc).isoformat()
        with self._conn() as conn:
            row = conn.execute(
                "SELECT * FROM jobs WHERE status = 'QUEUED' ORDER BY created_at ASC LIMIT 1"
            ).fetchone()
            if not row:
                return None
            job_id = row["job_id"]
            conn.execute(
                """
                UPDATE jobs
                SET status = 'RUNNING', attempts = attempts + 1, updated_at = ?
                WHERE job_id = ? AND status = 'QUEUED'
                """,
                (now_iso, job_id),
            )
            conn.commit()
            updated = conn.execute("SELECT * FROM jobs WHERE job_id = ?", (job_id,)).fetchone()
            return self._format_sqlite_job(dict(updated)) if updated else None

    def complete_job(self, job_id: str, result: Dict[str, Any]) -> Optional[dict]:
        if self._mongo is not None:
            return self._mongo.complete_job(job_id, result)

        now_iso = datetime.now(timezone.utc).isoformat()
        with self._conn() as conn:
            conn.execute(
                """
                UPDATE jobs
                SET status = 'COMPLETED', result = ?, error = NULL, updated_at = ?
                WHERE job_id = ?
                """,
                (json.dumps(result), now_iso, job_id),
            )
            conn.commit()
        return self.get_job(job_id)

    def fail_job(self, job_id: str, error: str) -> Optional[dict]:
        if self._mongo is not None:
            return self._mongo.fail_job(job_id, error)

        now_iso = datetime.now(timezone.utc).isoformat()
        existing = self.get_job(job_id)
        if not existing:
            return None
        attempts = int(existing.get("attempts", 1))
        max_attempts = int(existing.get("max_attempts", 3))
        next_status = "FAILED" if attempts >= max_attempts else "QUEUED"
        with self._conn() as conn:
            conn.execute(
                """
                UPDATE jobs
                SET status = ?, error = ?, updated_at = ?
                WHERE job_id = ?
                """,
                (next_status, error, now_iso, job_id),
            )
            conn.commit()
        return self.get_job(job_id)

    @staticmethod
    def _format_sqlite_job(doc: Dict[str, Any]) -> dict:
        cleaned = dict(doc)
        for field in ("payload", "result"):
            val = cleaned.get(field)
            if isinstance(val, str):
                try:
                    cleaned[field] = json.loads(val)
                except Exception:
                    pass
        return cleaned

    # ==========================================
    # System Settings & Profile Store
    # ==========================================

    def set_setting(self, key: str, value: str):
        if self._mongo is not None:
            self._mongo.set_setting(key, value)
            return

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
        if self._mongo is not None:
            return self._mongo.get_setting(key)

        with self._conn() as conn:
            row = conn.execute("SELECT value FROM settings WHERE key = ?", (key,)).fetchone()
            return row["value"] if row else None

    def get_candidate_profile(self) -> Optional[dict]:
        """Loads the candidate profile from the persistent settings store."""
        raw = self.get_setting("candidate_profile")
        if not raw:
            return None
        try:
            parsed = json.loads(raw)
        except (TypeError, json.JSONDecodeError):
            return None
        return parsed if isinstance(parsed, dict) else None

    def save_candidate_profile(self, profile_data: dict):
        """Persists the private candidate profile in the selected database."""
        self.set_setting("candidate_profile", json.dumps(profile_data, ensure_ascii=False))

    def get_candidate_profile(self) -> Optional[dict]:
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
        if self._mongo is not None:
            return self._mongo.get_system_stats()

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
                "total_suppressed_emails": supp_count,
                "storage_engine": "sqlite",
            }
