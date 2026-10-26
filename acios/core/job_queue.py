"""
ACIOS Durable Job Queue and Idempotent Dispatch Coordinator.
Combines Redis queue notification (when REDIS_URL is configured) with
MongoDB/SQLite durable job state, automatic retry handling, and atomic
duplicate-send protection for approved outreach drafts.
"""

import os
import time
from pathlib import Path
from typing import Any, Callable, Dict, Optional

from acios.core.repository import CareerRepository
from acios.core.smtp_dispatcher import SMTPDispatcher
from acios.core.suppression import SuppressionEngine
from acios.models.email_draft import EmailDraft


class DurableJobQueue:
    """Manages durable background jobs with Redis queue signaling and DB state."""

    REDIS_QUEUE_KEY = "acios:jobs:queue"

    def __init__(
        self,
        repo: Optional[CareerRepository] = None,
        redis_url: Optional[str] = None,
        redis_client: Any = None,
    ):
        self.repo = repo or CareerRepository()
        self.redis_url = (redis_url if redis_url is not None else os.getenv("REDIS_URL", "")).strip()
        self._redis = redis_client
        if self._redis is None and self.redis_url:
            try:
                import redis

                self._redis = redis.Redis.from_url(self.redis_url, decode_responses=True)
            except Exception:
                self._redis = None
        self._handlers: Dict[str, Callable[[Dict[str, Any]], Dict[str, Any]]] = {}
        self._register_default_handlers()

    def register_handler(
        self, job_type: str, handler: Callable[[Dict[str, Any]], Dict[str, Any]]
    ) -> None:
        self._handlers[job_type] = handler

    def enqueue(
        self,
        job_type: str,
        payload: Dict[str, Any],
        idempotency_key: Optional[str] = None,
        max_attempts: int = 3,
    ) -> Dict[str, Any]:
        job = self.repo.create_job(
            job_type=job_type,
            payload=payload,
            idempotency_key=idempotency_key,
            max_attempts=max_attempts,
        )
        if self._redis is not None and job.get("status") == "QUEUED":
            try:
                self._redis.rpush(self.REDIS_QUEUE_KEY, job["job_id"])
            except Exception:
                pass
        return job

    def get_job_status(self, job_id: str) -> Optional[Dict[str, Any]]:
        return self.repo.get_job(job_id)

    def wait_for_notification(self, timeout_seconds: float = 2.0) -> None:
        """Wait for a Redis wake-up when configured; database polling remains authoritative."""
        timeout = max(1, int(timeout_seconds))
        if self._redis is None:
            time.sleep(timeout_seconds)
            return
        try:
            # Redis is only a wake-up signal. The durable job record remains in the database.
            self._redis.blpop(self.REDIS_QUEUE_KEY, timeout=timeout)
        except Exception:
            # Redis outages must not stop the worker; it continues polling durable storage.
            time.sleep(timeout_seconds)

    def process_next(self) -> Optional[Dict[str, Any]]:
        """Claims and executes the next queued job with retry/dead-letter transitions."""
        job = self.repo.claim_next_job()
        if not job:
            return None

        job_id = job["job_id"]
        job_type = job["job_type"]
        payload = job.get("payload") or {}
        if not isinstance(payload, dict):
            payload = {}

        handler = self._handlers.get(job_type)
        if not handler:
            return self.repo.fail_job(job_id, f"Unknown job_type '{job_type}'")

        try:
            result = handler(payload)
            return self.repo.complete_job(job_id, result)
        except Exception as exc:
            return self.repo.fail_job(job_id, str(exc))

    def _register_default_handlers(self) -> None:
        def _handle_growth_scan(payload: Dict[str, Any]) -> Dict[str, Any]:
            from acios.tools.discovery.growth_scanner import GrowthSignalScanner

            scanner = GrowthSignalScanner(repo=self.repo)
            country = payload.get("country", "Oman")
            city = payload.get("city", "All")
            trigger = payload.get("trigger", "All")
            query = payload.get("query", "")
            signals = scanner.scan_market_signals(
                country=country,
                city=city,
                trigger_category=trigger,
                custom_query=query,
                max_results=int(payload.get("limit", 10)),
            )
            return {"discovered_count": len(signals), "signals": signals}

        def _handle_send_approved(payload: Dict[str, Any]) -> Dict[str, Any]:
            draft_id = int(payload["draft_id"])
            idempotency_key = str(payload.get("idempotency_key") or f"send_draft_{draft_id}")
            return execute_approved_send(
                repo=self.repo,
                draft_id=draft_id,
                idempotency_key=idempotency_key,
            )

        self.register_handler("search_growth_signals", _handle_growth_scan)
        self.register_handler("send_approved_outreach", _handle_send_approved)


def execute_approved_send(
    repo: CareerRepository,
    draft_id: int,
    idempotency_key: Optional[str] = None,
    supp: Optional[SuppressionEngine] = None,
    dispatcher: Optional[SMTPDispatcher] = None,
) -> Dict[str, Any]:
    """
    Executes an explicitly approved outreach draft with strict duplicate-send protection.
    - Rejects unapproved drafts.
    - Rejects suppressed recipients.
    - Enforces atomic idempotency lock per draft_id and idempotency_key.
    """
    suppression = supp or SuppressionEngine()
    draft_row = repo.get_draft_by_id(draft_id)
    if not draft_row:
        raise LookupError(f"Draft #{draft_id} was not found.")

    recipient_email = (draft_row.get("recipient_email") or "").strip().lower()
    if repo.is_suppressed(recipient_email) or suppression.is_suppressed(recipient_email):
        raise ValueError(f"Recipient '{recipient_email}' is on the suppression list.")

    effective_key = (idempotency_key or f"draft_{draft_id}_send").strip()

    # Check if already dispatched before checking status so idempotent retries return cleanly
    if draft_row.get("status") == "DISPATCHED":
        return {
            "status": "DUPLICATE_PREVENTED",
            "duplicate_prevented": True,
            "draft_id": draft_id,
            "recipient_email": recipient_email,
            "idempotency_key": draft_row.get("idempotency_key") or effective_key,
            "dispatched_at": draft_row.get("dispatched_at"),
        }

    if draft_row.get("status") != "APPROVED":
        raise PermissionError(
            f"Draft #{draft_id} has status '{draft_row.get('status')}'. Only 'APPROVED' drafts can be sent."
        )

    smtp = dispatcher or SMTPDispatcher(repo=repo, supp=suppression)
    draft_obj = EmailDraft(
        recipient_email=draft_row["recipient_email"],
        recipient_name=draft_row["recipient_name"],
        organization_name=draft_row["organization_name"],
        recipient_role=draft_row["recipient_role"],
        subject_line=draft_row["subject_line"],
        body_text=draft_row["body_text"],
    )

    # A dry-run is not a send. Avoid taking a permanent dispatch lock or marking
    # the draft as dispatched so a later explicitly enabled live send remains possible.
    if os.getenv("DRY_RUN", "true").strip().lower() in ("1", "true", "yes"):
        result = smtp.dispatch(draft_obj, approved=True)
        return {
            "status": "DRY_RUN",
            "dry_run": True,
            "duplicate_prevented": False,
            "draft_id": draft_id,
            "recipient_email": recipient_email,
            "transport_status": result.get("status", "DRY_RUN_DISPATCHED"),
            "message": "Dry-run only: no email was sent and the draft remains approved.",
        }

    # Live outreach must use the configured master resume. This check happens
    # before taking a dispatch lock, so a missing file cannot strand the draft.
    resume_path = Path(__file__).resolve().parents[2] / "data" / "resume" / "master_resume.pdf"
    if not resume_path.is_file():
        raise FileNotFoundError(
            "Master resume is not available to the worker. Upload it and ensure the API "
            "and worker share the same private persistent resume storage before dispatch."
        )
    attachment_bytes = resume_path.read_bytes()

    lock_res = repo.claim_dispatch_lock(
        draft_id=draft_id,
        recipient_email=recipient_email,
        idempotency_key=effective_key,
    )
    if not lock_res.get("acquired"):
        return {
            "status": "DUPLICATE_PREVENTED",
            "duplicate_prevented": True,
            "draft_id": draft_id,
            "recipient_email": recipient_email,
            "idempotency_key": effective_key,
            "existing_lock": lock_res.get("existing_lock"),
        }

    send_res = smtp.dispatch(
        draft_obj,
        approved=True,
        attachment_bytes=attachment_bytes,
        attachment_filename=resume_path.name,
    )
    if send_res.get("dry_run") or send_res.get("status") == "DRY_RUN_DISPATCHED":
        raise RuntimeError("Dry-run dispatch cannot be committed as a real send.")
    if send_res.get("status") not in ("DISPATCHED", "SENT") and not send_res.get("success", False):
        raise RuntimeError(send_res.get("message") or send_res.get("reason") or "SMTP dispatch failed.")

    updated = repo.mark_draft_dispatched(draft_id=draft_id, idempotency_key=effective_key)
    repo.update_contact_status(recipient_email, "Sent")
    return {
        "status": "SENT",
        "duplicate_prevented": False,
        "draft_id": draft_id,
        "recipient_email": recipient_email,
        "idempotency_key": effective_key,
        "dispatched_at": (updated or {}).get("dispatched_at"),
        "transport_status": send_res.get("status", "SENT"),
    }
