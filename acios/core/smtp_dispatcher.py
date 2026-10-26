"""
ACIOS Direct SMTP Dispatcher.
Authenticates with Gmail SMTP (smtp.gmail.com:465 SSL) using app password,
enforces master suppression checks, attaches PDF candidate resume,
dispatches direct outreach emails, and logs every dispatch into outreach_events.
"""

import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.application import MIMEApplication
from typing import Optional, Tuple
from pathlib import Path
from datetime import datetime, timezone
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent.parent
load_dotenv(BASE_DIR / ".env")

from acios.models.email_draft import EmailDraft
from acios.core.repository import CareerRepository
from acios.core.suppression import SuppressionEngine
from acios.core.draft_engine import get_candidate_signature

DEFAULT_RESUME_PATH = BASE_DIR / "data" / "resume" / "master_resume.pdf"


class SMTPDispatcher:
    def __init__(
        self,
        gmail_user: Optional[str] = None,
        gmail_app_password: Optional[str] = None,
        repo: Optional[CareerRepository] = None,
        supp: Optional[SuppressionEngine] = None
    ):
        self.gmail_user = gmail_user or os.getenv("GMAIL_SENDER_EMAIL") or os.getenv("GMAIL_USER", "")
        self.gmail_app_password = gmail_app_password or os.getenv("GMAIL_APP_PASSWORD", "")
        self.repo = repo or CareerRepository()
        self.supp = supp or SuppressionEngine()

    def build_message(
        self,
        draft: EmailDraft,
        attachment_bytes: Optional[bytes] = None,
        attachment_filename: Optional[str] = None
    ) -> MIMEMultipart:
        cand_name, sig_text, sig_html = get_candidate_signature()

        outer_msg = MIMEMultipart("mixed")
        outer_msg["From"] = f"{cand_name} <{self.gmail_user}>"
        outer_msg["To"] = draft.recipient_email
        outer_msg["Subject"] = draft.subject_line

        alt_msg = MIMEMultipart("alternative")
        text_body = draft.body_text + "\n\n" + sig_text
        html_paragraphs = "\n".join(
            f'<p style="margin: 0 0 14px 0; line-height: 1.55; color: #222222;">{p}</p>'
            for p in draft.paragraphs
        )
        html_body = f"""<html>
<body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Arial, sans-serif; font-size: 14.5px; color: #222222;">
{html_paragraphs}
{sig_html}
</body>
</html>"""

        alt_msg.attach(MIMEText(text_body, "plain", "utf-8"))
        alt_msg.attach(MIMEText(html_body, "html", "utf-8"))
        outer_msg.attach(alt_msg)

        pdf_bytes = attachment_bytes
        filename = attachment_filename or "master_resume.pdf"

        if not pdf_bytes and DEFAULT_RESUME_PATH.exists():
            try:
                pdf_bytes = DEFAULT_RESUME_PATH.read_bytes()
            except Exception:
                pdf_bytes = None

        if pdf_bytes:
            pdf_part = MIMEApplication(pdf_bytes, _subtype="pdf")
            pdf_part.add_header("Content-Disposition", "attachment", filename=filename)
            outer_msg.attach(pdf_part)

        return outer_msg

    def send_direct(
        self,
        draft: EmailDraft,
        attachment_bytes: Optional[bytes] = None,
        attachment_filename: Optional[str] = None
    ) -> Tuple[bool, str]:
        """
        Executes pre-flight suppression check, connects via SMTP SSL, sends message,
        and logs the dispatch event to outreach_events.
        """
        if not self.gmail_user or not self.gmail_app_password:
            return False, "Gmail SMTP credentials are not configured."
        if self.supp.is_suppressed(draft.recipient_email) or self.repo.is_suppressed(draft.recipient_email):
            reason = f"Pre-Flight Safety Block: {draft.recipient_email} is on Master Suppression List"
            self._log_event(draft.recipient_email, "BLOCKED", reason)
            return False, reason

        msg = self.build_message(draft, attachment_bytes, attachment_filename)

        server = None
        try:
            server = smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=15)
            server.login(self.gmail_user, self.gmail_app_password)
            server.sendmail(self.gmail_user, [draft.recipient_email], msg.as_bytes())

            now_iso = datetime.now(timezone.utc).isoformat()
            self._log_event(
                draft.recipient_email,
                "DISPATCHED",
                f"Direct SMTP dispatch to {draft.recipient_name} ({draft.organization_name}). Subject: '{draft.subject_line}'"
            )

            if self.repo.storage_engine == "mongodb" and self.repo._mongo is not None:
                self.repo._mongo.db.drafts.update_one(
                    {"recipient_email": draft.recipient_email.strip().lower()},
                    {"$set": {"status": "DISPATCHED", "dispatched_at": now_iso}},
                )
            else:
                with self.repo._conn() as conn:
                    conn.execute(
                        "UPDATE drafts SET status = 'DISPATCHED' WHERE recipient_email = ?",
                        (draft.recipient_email,)
                    )
                    conn.commit()

            return True, f"Successfully dispatched email directly to {draft.recipient_email} via SMTP SSL."
        except Exception as e:
            err = f"SMTP dispatch failed: {e}"
            self._log_event(draft.recipient_email, "DISPATCH_FAILED", err)
            return False, err
        finally:
            if server:
                try:
                    server.quit()
                except Exception:
                    pass

    def dispatch(
        self,
        draft: EmailDraft,
        approved: bool = False,
        attachment_bytes: Optional[bytes] = None,
        attachment_filename: Optional[str] = None,
    ) -> dict:
        """
        Structured dispatch entrypoint used by DurableJobQueue and approved tool execution.
        Honors DRY_RUN environment variable so tests and staging runs do not send live emails.
        """
        if not approved:
            raise PermissionError("Explicit human approval is required before dispatching outreach.")

        if self.supp.is_suppressed(draft.recipient_email) or self.repo.is_suppressed(draft.recipient_email):
            reason = f"Pre-Flight Safety Block: {draft.recipient_email} is on Master Suppression List"
            self._log_event(draft.recipient_email, "BLOCKED", reason)
            return {"status": "BLOCKED", "message": reason}

        dry_run = os.getenv("DRY_RUN", "true").strip().lower() in ("1", "true", "yes")
        if dry_run:
            self._log_event(
                draft.recipient_email,
                "DRY_RUN_DISPATCHED",
                f"Dry-run approved dispatch to {draft.recipient_name} ({draft.organization_name}).",
            )
            return {
                "status": "DRY_RUN_DISPATCHED",
                "dry_run": True,
                "recipient_email": draft.recipient_email,
                "message": f"Dry-run dispatch verified for {draft.recipient_email}.",
            }

        ok, msg = self.send_direct(
            draft,
            attachment_bytes=attachment_bytes,
            attachment_filename=attachment_filename,
        )
        return {
            "status": "DISPATCHED" if ok else "DISPATCH_FAILED",
            "dry_run": False,
            "recipient_email": draft.recipient_email,
            "message": msg,
        }

    def _log_event(self, recipient_email: str, event_type: str, details: str):
        try:
            self.repo.log_outreach_event(recipient_email, event_type, details)
        except Exception as ex:
            print(f"[SMTPDispatcher Warning] Failed to log outreach event: {ex}")
