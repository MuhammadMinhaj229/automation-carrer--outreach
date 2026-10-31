"""
ACIOS Durable Job Queue and Idempotent Dispatch Coordinator.
Combines Redis queue notification (when REDIS_URL is configured) with
MongoDB/SQLite durable job state, automatic retry handling, and atomic
duplicate-send protection for approved outreach drafts.
"""

import os
import time
from typing import Any, Callable, Dict, Optional

from acios.core.repository import CareerRepository
from acios.core.resume_storage import load_master_resume
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
            """Fail closed for any legacy queued sends after switching to local-first mode."""
            _ = payload
            return {
                "status": "DISABLED_LOCAL_FIRST",
                "sent": False,
                "message": (
                    "Legacy queued send was not executed. Review the draft and send it "
                    "manually from the mail client."
                ),
            }

        self.register_handler("search_growth_signals", _handle_growth_scan)
        self.register_handler("send_approved_outreach", _handle_send_approved)


def execute_approved_send(
    repo: CareerRepository,
    draft_id: int,
    idempotency_key: Optional[str] = None,
    supp: Optional[SuppressionEngine] = None,
    dispatcher: Optional[SMTPDispatcher] = None,
) -> Dict[str, Any]:
    """Validate the approved snapshot; this local-first executor never sends mail."""
    _ = (idempotency_key, dispatcher)
    suppression = supp or SuppressionEngine()
    draft_row = repo.get_draft_by_id(draft_id)
    if not draft_row:
        raise LookupError(f"Draft #{draft_id} was not found.")

    recipient_email = (draft_row.get("recipient_email") or "").strip().lower()
    if repo.is_suppressed(recipient_email) or suppression.is_suppressed(recipient_email):
        raise ValueError(f"Recipient '{recipient_email}' is on the suppression list.")

    if draft_row.get("status") == "DISPATCHED":
        return {
            "status": "DUPLICATE_PREVENTED",
            "duplicate_prevented": True,
            "sent": False,
            "draft_id": draft_id,
            "recipient_email": recipient_email,
        }
    if draft_row.get("status") != "APPROVED":
        raise PermissionError(
            f"Draft #{draft_id} has status '{draft_row.get('status')}'. "
            "Only a human-approved draft can pass preflight."
        )

    draft_obj = EmailDraft(
        recipient_email=recipient_email,
        recipient_name=draft_row["recipient_name"],
        organization_name=draft_row["organization_name"],
        recipient_role=draft_row["recipient_role"],
        subject_line=draft_row["subject_line"],
        body_text=draft_row["body_text"],
        cv_attached=bool(draft_row.get("cv_attached", False)),
        attachment_sha256=draft_row.get("attachment_sha256"),
    )
    approved_snapshot = draft_row.get("approved_snapshot_hash")
    if not approved_snapshot or draft_obj.approval_hash != approved_snapshot:
        raise PermissionError(
            "Draft content no longer matches its human-approved snapshot. "
            "Review and approve it again."
        )

    dry_run = os.getenv("DRY_RUN", "true").strip().lower() in ("1", "true", "yes")
    if dry_run:
        return {
            "status": "DRY_RUN",
            "dry_run": True,
            "sent": False,
            "draft_id": draft_id,
            "recipient_email": recipient_email,
            "message": "Preflight passed in dry-run mode; no message was sent.",
        }

    return {
        "status": "DISABLED_LOCAL_FIRST",
        "dry_run": False,
        "sent": False,
        "draft_id": draft_id,
        "recipient_email": recipient_email,
        "message": (
            "Programmatic sending is disabled in local-first ACIOS. "
            "Stage the draft and send it manually from the mail client."
        ),
    }
