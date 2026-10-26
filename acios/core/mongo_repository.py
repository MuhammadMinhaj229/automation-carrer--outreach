"""
ACIOS MongoDB Atlas Persistence Backend.
Stores organizations, signals, contacts, outreach drafts, approvals,
idempotent dispatch locks, suppression records, audit events, and durable jobs
in MongoDB Atlas (or any MongoDB-compatible cluster).
"""

import json
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from pymongo import ASCENDING, DESCENDING, MongoClient, ReturnDocument
from pymongo.errors import DuplicateKeyError

from acios.models.contact import Contact
from acios.models.email_draft import EmailDraft
from acios.models.organization import Organization


class MongoCareerBackend:
    """MongoDB Atlas implementation of the ACIOS persistence contract."""

    def __init__(
        self,
        mongo_uri: Optional[str] = None,
        db_name: str = "acios_production",
        mongo_client: Any = None,
    ):
        if mongo_client is not None:
            self.client = mongo_client
        elif mongo_uri:
            self.client = MongoClient(mongo_uri, serverSelectionTimeoutMS=5000)
        else:
            raise ValueError("Either mongo_uri or mongo_client must be provided.")

        self.db = self.client[db_name]
        self._ensure_indexes()

    def _ensure_indexes(self) -> None:
        self.db.organizations.create_index([("name", ASCENDING)], unique=True)
        self.db.signals.create_index(
            [("organization_name", ASCENDING), ("headline", ASCENDING)], unique=True
        )
        self.db.contacts.create_index(
            [("organization_name", ASCENDING), ("name", ASCENDING)], unique=True
        )
        self.db.contacts.create_index([("work_email", ASCENDING)])
        self.db.drafts.create_index([("recipient_email", ASCENDING)], unique=True)
        self.db.drafts.create_index([("id", ASCENDING)], unique=True)
        self.db.suppression.create_index([("email", ASCENDING)], unique=True)
        self.db.outreach_events.create_index([("id", DESCENDING)])
        self.db.settings.create_index([("key", ASCENDING)], unique=True)
        self.db.jobs.create_index([("job_id", ASCENDING)], unique=True)
        self.db.jobs.create_index([("status", ASCENDING), ("created_at", ASCENDING)])
        self.db.dispatch_locks.create_index([("idempotency_key", ASCENDING)], unique=True)
        self.db.dispatch_locks.create_index([("draft_id", ASCENDING)], unique=True)

    def _next_seq(self, counter_name: str) -> int:
        doc = self.db.counters.find_one_and_update(
            {"_id": counter_name},
            {"$inc": {"seq": 1}},
            upsert=True,
            return_document=ReturnDocument.AFTER,
        )
        return int(doc["seq"])

    @staticmethod
    def _strip_mongo_id(doc: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        if not doc:
            return None
        cleaned = dict(doc)
        cleaned.pop("_id", None)
        return cleaned

    # ==========================================
    # Organizations & Signals
    # ==========================================

    def upsert_organization(self, org: Organization) -> int:
        now_iso = datetime.now(timezone.utc).isoformat()
        existing = self.db.organizations.find_one({"name": org.name})
        org_id = existing["id"] if existing and "id" in existing else self._next_seq("organizations")

        update_fields: Dict[str, Any] = {
            "country": org.country,
            "sector": org.sector.value,
        }
        if org.city is not None or not existing:
            update_fields["city"] = org.city if org.city is not None else (existing or {}).get("city")
        if org.website is not None or not existing:
            update_fields["website"] = (
                str(org.website) if org.website else (existing or {}).get("website")
            )
        if org.value_proposition is not None or not existing:
            update_fields["value_proposition"] = (
                org.value_proposition
                if org.value_proposition is not None
                else (existing or {}).get("value_proposition")
            )

        self.db.organizations.update_one(
            {"name": org.name},
            {
                "$set": update_fields,
                "$setOnInsert": {"id": org_id, "name": org.name, "created_at": now_iso},
            },
            upsert=True,
        )

        for sig in org.signals:
            existing_sig = self.db.signals.find_one(
                {"organization_name": org.name, "headline": sig.headline}
            )
            sig_id = (
                existing_sig["id"]
                if existing_sig and "id" in existing_sig
                else self._next_seq("signals")
            )
            self.db.signals.update_one(
                {"organization_name": org.name, "headline": sig.headline},
                {
                    "$set": {
                        "signal_date": sig.signal_date,
                        "source_url": sig.source_url,
                        "evidence_tier": sig.evidence_tier,
                        "details": sig.details,
                    },
                    "$setOnInsert": {
                        "id": sig_id,
                        "organization_name": org.name,
                        "headline": sig.headline,
                        "score": 50,
                        "created_at": now_iso,
                    },
                },
                upsert=True,
            )

        return org_id

    def get_organization(self, name: str) -> Optional[dict]:
        doc = self._strip_mongo_id(self.db.organizations.find_one({"name": name}))
        if not doc:
            return None
        signals = [
            self._strip_mongo_id(s)
            for s in self.db.signals.find({"organization_name": name}).sort("id", ASCENDING)
        ]
        doc["signals"] = [s for s in signals if s is not None]
        return doc

    def list_organizations(self, country: Optional[str] = None) -> List[dict]:
        query = {"country": country} if country else {}
        cursor = self.db.organizations.find(query).sort(
            [("country", ASCENDING), ("name", ASCENDING)]
        )
        return [self._strip_mongo_id(doc) for doc in cursor if doc]

    def list_signals(self, country: Optional[str] = None, limit: int = 100) -> List[dict]:
        if country:
            org_names = [
                o["name"] for o in self.db.organizations.find({"country": country}, {"name": 1})
            ]
            cursor = (
                self.db.signals.find({"organization_name": {"$in": org_names}})
                .sort("id", DESCENDING)
                .limit(limit)
            )
            results = []
            for s in cursor:
                item = self._strip_mongo_id(s)
                if item:
                    item["country"] = country
                    results.append(item)
            return results
        cursor = self.db.signals.find().sort("id", DESCENDING).limit(limit)
        return [self._strip_mongo_id(s) for s in cursor if s]

    def search_growth_signals(
        self, query: str = "", country: Optional[str] = None, limit: int = 25
    ) -> List[dict]:
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
    # Contacts
    # ==========================================

    def upsert_contact(self, contact: Contact) -> int:
        now_iso = datetime.now(timezone.utc).isoformat()
        if not self.db.organizations.find_one({"name": contact.organization_name}):
            self.db.organizations.insert_one(
                {
                    "id": self._next_seq("organizations"),
                    "name": contact.organization_name,
                    "country": "GCC",
                    "city": None,
                    "sector": "Diversified Corporate",
                    "website": None,
                    "value_proposition": None,
                    "created_at": now_iso,
                }
            )

        existing = self.db.contacts.find_one(
            {"organization_name": contact.organization_name, "name": contact.name}
        )
        contact_id = (
            existing["id"] if existing and "id" in existing else self._next_seq("contacts")
        )

        self.db.contacts.update_one(
            {"organization_name": contact.organization_name, "name": contact.name},
            {
                "$set": {
                    "role": contact.role,
                    "work_email": contact.work_email,
                    "linkedin_url": contact.linkedin_url,
                    "verification_status": contact.verification_status.value,
                    "outreach_status": contact.outreach_status.value,
                    "is_suppressed": 1 if contact.is_suppressed else 0,
                    "notes": contact.notes,
                    "updated_at": now_iso,
                },
                "$setOnInsert": {
                    "id": contact_id,
                    "organization_name": contact.organization_name,
                    "name": contact.name,
                },
            },
            upsert=True,
        )
        return contact_id

    def list_contacts(self, org_name: Optional[str] = None) -> List[dict]:
        query = {"organization_name": org_name} if org_name else {}
        cursor = self.db.contacts.find(query).sort(
            [("organization_name", ASCENDING), ("name", ASCENDING)]
        )
        return [self._strip_mongo_id(c) for c in cursor if c]

    def update_contact_status(self, email: str, status: str) -> bool:
        clean_email = email.strip().lower()
        now_iso = datetime.now(timezone.utc).isoformat()
        matched = 0
        for c in self.db.contacts.find({"work_email": {"$ne": None}}):
            if (c.get("work_email") or "").strip().lower() == clean_email:
                self.db.contacts.update_one(
                    {"_id": c["_id"]},
                    {"$set": {"outreach_status": status, "updated_at": now_iso}},
                )
                matched += 1
        return matched > 0

    # ==========================================
    # Drafts & Explicit Approval Workflow
    # ==========================================

    def upsert_draft(self, draft: EmailDraft, status: str = "PENDING_APPROVAL") -> int:
        now_iso = datetime.now(timezone.utc).isoformat()
        existing = self.db.drafts.find_one({"recipient_email": draft.recipient_email})
        draft_id = existing["id"] if existing and "id" in existing else self._next_seq("drafts")

        self.db.drafts.update_one(
            {"recipient_email": draft.recipient_email},
            {
                "$set": {
                    "recipient_name": draft.recipient_name,
                    "organization_name": draft.organization_name,
                    "recipient_role": draft.recipient_role,
                    "subject_line": draft.subject_line,
                    "body_text": draft.body_text,
                    "word_count": draft.word_count,
                    "approval_hash": draft.approval_hash,
                    "status": status,
                },
                "$setOnInsert": {
                    "id": draft_id,
                    "recipient_email": draft.recipient_email,
                    "approved_by": None,
                    "approved_at": None,
                    "confirmation_note": None,
                    "idempotency_key": None,
                    "dispatched_at": None,
                    "created_at": now_iso,
                },
            },
            upsert=True,
        )
        return draft_id

    def list_drafts(self) -> List[dict]:
        cursor = self.db.drafts.find().sort("id", ASCENDING)
        return [self._strip_mongo_id(d) for d in cursor if d]

    def get_draft_by_id(self, draft_id: int) -> Optional[dict]:
        return self._strip_mongo_id(self.db.drafts.find_one({"id": int(draft_id)}))

    def get_draft_by_email(self, recipient_email: str) -> Optional[dict]:
        return self._strip_mongo_id(
            self.db.drafts.find_one({"recipient_email": recipient_email.strip()})
        )

    def list_pending_approvals(self) -> List[dict]:
        cursor = self.db.drafts.find(
            {"status": {"$in": ["STAGED", "PENDING_APPROVAL"]}}
        ).sort("id", ASCENDING)
        return [self._strip_mongo_id(d) for d in cursor if d]

    def approve_draft(
        self, draft_id: int, approved_by: str = "operator", confirmation_note: str = ""
    ) -> Optional[dict]:
        now_iso = datetime.now(timezone.utc).isoformat()
        existing = self.get_draft_by_id(draft_id)
        if not existing:
            return None
        if existing.get("status") == "DISPATCHED":
            raise ValueError(f"Draft {draft_id} has already been dispatched.")

        self.db.drafts.update_one(
            {"id": int(draft_id)},
            {
                "$set": {
                    "status": "APPROVED",
                    "approved_by": approved_by,
                    "approved_at": now_iso,
                    "confirmation_note": confirmation_note,
                }
            },
        )
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
        now_iso = datetime.now(timezone.utc).isoformat()
        existing = self.db.dispatch_locks.find_one(
            {"$or": [{"idempotency_key": idempotency_key}, {"draft_id": int(draft_id)}]}
        )
        if existing:
            return {
                "acquired": False,
                "duplicate_prevented": True,
                "existing_lock": self._strip_mongo_id(existing),
            }
        try:
            lock_doc = {
                "idempotency_key": idempotency_key,
                "draft_id": int(draft_id),
                "recipient_email": recipient_email.strip().lower(),
                "status": "LOCKED",
                "dispatched_at": now_iso,
            }
            self.db.dispatch_locks.insert_one(lock_doc)
            return {
                "acquired": True,
                "duplicate_prevented": False,
                "existing_lock": self._strip_mongo_id(lock_doc),
            }
        except DuplicateKeyError:
            existing_after = self.db.dispatch_locks.find_one(
                {"$or": [{"idempotency_key": idempotency_key}, {"draft_id": int(draft_id)}]}
            )
            return {
                "acquired": False,
                "duplicate_prevented": True,
                "existing_lock": self._strip_mongo_id(existing_after),
            }

    def mark_draft_dispatched(self, draft_id: int, idempotency_key: str) -> Optional[dict]:
        now_iso = datetime.now(timezone.utc).isoformat()
        self.db.drafts.update_one(
            {"id": int(draft_id)},
            {
                "$set": {
                    "status": "DISPATCHED",
                    "idempotency_key": idempotency_key,
                    "dispatched_at": now_iso,
                }
            },
        )
        self.db.dispatch_locks.update_one(
            {"draft_id": int(draft_id)},
            {"$set": {"status": "DISPATCHED", "dispatched_at": now_iso}},
        )
        return self.get_draft_by_id(draft_id)

    # ==========================================
    # Suppression & Events
    # ==========================================

    def add_suppression(
        self, email: str, reason: str = "Hard Bounce", source: str = "Audit"
    ) -> bool:
        clean_email = email.strip().lower()
        now_iso = datetime.now(timezone.utc).isoformat()
        self.db.suppression.update_one(
            {"email": clean_email},
            {
                "$setOnInsert": {
                    "id": self._next_seq("suppression"),
                    "email": clean_email,
                    "reason": reason,
                    "source": source,
                    "blocked_at": now_iso,
                }
            },
            upsert=True,
        )
        return True

    def is_suppressed(self, email: Optional[str]) -> bool:
        if not email:
            return True
        clean_email = email.strip().lower()
        return self.db.suppression.find_one({"email": clean_email}) is not None

    def get_suppression_count(self) -> int:
        return int(self.db.suppression.count_documents({}))

    def record_outreach_event(
        self,
        recipient_email: str,
        action_type: str,
        status: str = "DELIVERED",
        details: str = "",
        status_message: Optional[str] = None,
    ) -> None:
        now_iso = datetime.now(timezone.utc).isoformat()
        msg = status_message if status_message is not None else details
        self.db.outreach_events.insert_one(
            {
                "id": self._next_seq("outreach_events"),
                "recipient_email": recipient_email,
                "event_type": action_type,
                "timestamp": now_iso,
                "details": f"[{status}] {msg}" if status else msg,
            }
        )

    def list_outreach_events(self, limit: int = 50) -> List[dict]:
        cursor = self.db.outreach_events.find().sort("id", DESCENDING).limit(limit)
        result = []
        for r in cursor:
            det = r.get("details", "")
            stat = (
                "DELIVERED"
                if "DELIVERED" in det or "SUCCESS" in det
                else ("LOCAL_STAGED" if "LOCAL" in det else "STAGED")
            )
            result.append(
                {
                    "id": r["id"],
                    "recipient_email": r["recipient_email"],
                    "action_type": r["event_type"],
                    "status": stat,
                    "status_message": det,
                    "timestamp": r["timestamp"],
                }
            )
        return result

    # ==========================================
    # Durable Jobs
    # ==========================================

    def create_job(
        self,
        job_type: str,
        payload: Dict[str, Any],
        idempotency_key: Optional[str] = None,
        max_attempts: int = 3,
    ) -> dict:
        if idempotency_key:
            existing = self.db.jobs.find_one({"idempotency_key": idempotency_key})
            if existing:
                return self._format_job(existing)

        now_iso = datetime.now(timezone.utc).isoformat()
        job_id = f"job_{uuid.uuid4().hex[:16]}"
        doc = {
            "job_id": job_id,
            "job_type": job_type,
            "status": "QUEUED",
            "payload": json.dumps(payload),
            "result": None,
            "error": None,
            "attempts": 0,
            "max_attempts": max_attempts,
            "idempotency_key": idempotency_key,
            "created_at": now_iso,
            "updated_at": now_iso,
        }
        self.db.jobs.insert_one(doc)
        return self._format_job(doc)

    def get_job(self, job_id: str) -> Optional[dict]:
        doc = self.db.jobs.find_one({"job_id": job_id})
        return self._format_job(doc) if doc else None

    def list_jobs(self, status: Optional[str] = None, limit: int = 50) -> List[dict]:
        query = {"status": status} if status else {}
        cursor = self.db.jobs.find(query).sort("created_at", DESCENDING).limit(limit)
        return [self._format_job(doc) for doc in cursor if doc]

    def claim_next_job(self) -> Optional[dict]:
        now_iso = datetime.now(timezone.utc).isoformat()
        doc = self.db.jobs.find_one_and_update(
            {"status": "QUEUED"},
            {"$set": {"status": "RUNNING", "updated_at": now_iso}, "$inc": {"attempts": 1}},
            sort=[("created_at", ASCENDING)],
            return_document=ReturnDocument.AFTER,
        )
        return self._format_job(doc) if doc else None

    def complete_job(self, job_id: str, result: Dict[str, Any]) -> Optional[dict]:
        now_iso = datetime.now(timezone.utc).isoformat()
        doc = self.db.jobs.find_one_and_update(
            {"job_id": job_id},
            {
                "$set": {
                    "status": "COMPLETED",
                    "result": json.dumps(result),
                    "error": None,
                    "updated_at": now_iso,
                }
            },
            return_document=ReturnDocument.AFTER,
        )
        return self._format_job(doc) if doc else None

    def fail_job(self, job_id: str, error: str) -> Optional[dict]:
        now_iso = datetime.now(timezone.utc).isoformat()
        existing = self.db.jobs.find_one({"job_id": job_id})
        if not existing:
            return None
        attempts = int(existing.get("attempts", 1))
        max_attempts = int(existing.get("max_attempts", 3))
        next_status = "FAILED" if attempts >= max_attempts else "QUEUED"
        doc = self.db.jobs.find_one_and_update(
            {"job_id": job_id},
            {"$set": {"status": next_status, "error": error, "updated_at": now_iso}},
            return_document=ReturnDocument.AFTER,
        )
        return self._format_job(doc) if doc else None

    def _format_job(self, doc: Dict[str, Any]) -> dict:
        cleaned = self._strip_mongo_id(doc) or {}
        for field in ("payload", "result"):
            val = cleaned.get(field)
            if isinstance(val, str):
                try:
                    cleaned[field] = json.loads(val)
                except Exception:
                    pass
        return cleaned

    # ==========================================
    # Settings & Stats
    # ==========================================

    def set_setting(self, key: str, value: str) -> None:
        now_iso = datetime.now(timezone.utc).isoformat()
        self.db.settings.update_one(
            {"key": key},
            {"$set": {"key": key, "value": value, "updated_at": now_iso}},
            upsert=True,
        )

    def get_setting(self, key: str) -> Optional[str]:
        doc = self.db.settings.find_one({"key": key})
        return doc["value"] if doc else None

    def get_system_stats(self) -> Dict[str, Any]:
        return {
            "total_organizations": int(self.db.organizations.count_documents({})),
            "total_contacts": int(self.db.contacts.count_documents({})),
            "total_signals": int(self.db.signals.count_documents({})),
            "total_staged_drafts": int(self.db.drafts.count_documents({})),
            "total_suppressed_emails": int(self.db.suppression.count_documents({})),
            "storage_engine": "mongodb",
        }
