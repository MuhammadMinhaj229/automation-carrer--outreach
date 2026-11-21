"""
Gmail IMAP Drafts Engine.
Uploads pre-addressed, personalized emails with clickable HTML signatures and
optional PDF resume attachments directly into [Gmail]/Drafts.
"""

import hashlib
import imaplib
import json
import os
import time
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.application import MIMEApplication
from typing import Any, Callable, Dict, Optional, Tuple
from pathlib import Path
import yaml
from html import escape
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent.parent
load_dotenv(BASE_DIR / ".env")

from acios.models.email_draft import EmailDraft

DEFAULT_RESUME_PATH = BASE_DIR / "data" / "resume" / "master_resume.pdf"


def _resolve_attachment_bytes(attachment_bytes: Optional[bytes]) -> Optional[bytes]:
    """Resolve the explicit attachment or the configured local resume, if readable."""
    if attachment_bytes is not None:
        return attachment_bytes
    try:
        return DEFAULT_RESUME_PATH.read_bytes()
    except OSError:
        return None


def build_staging_marker(
    draft: EmailDraft,
    *,
    draft_id: Optional[int] = None,
    attachment_bytes: Optional[bytes] = None,
    attachment_filename: Optional[str] = None,
) -> str:
    """Build an opaque, content-versioned key shared by every Gmail staging surface."""
    if draft_id is not None and (
        isinstance(draft_id, bool) or not isinstance(draft_id, int) or draft_id < 1
    ):
        raise ValueError("draft_id must be a positive integer when supplied.")

    has_attachment = bool(attachment_bytes)
    attachment_sha256 = (
        hashlib.sha256(attachment_bytes).hexdigest() if has_attachment else None
    )
    snapshot = draft.model_copy(update={
        "cv_attached": has_attachment,
        "attachment_sha256": attachment_sha256,
    })
    payload = {
        "schema": 1,
        "draft_id": draft_id,
        "approval_hash": snapshot.approval_hash,
        "attachment_filename": (
            attachment_filename or "master_resume.pdf"
            if has_attachment else None
        ),
    }
    canonical = json.dumps(
        payload, ensure_ascii=True, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


def get_candidate_signature(
    profile_data: Optional[Dict[str, Any]] = None,
) -> Tuple[str, str, str]:
    """Return the project's immutable plain-text and clickable HTML signature."""
    from html import escape

    # The candidate signature is a project invariant, not generated model content.
    # profile_data remains accepted for backward compatibility but cannot alter it.
    _ = profile_data
    candidate_name = "Mohammed Minhaj Mahmood"
    candidate_email = "minhajmuhammad229@gmail.com"
    candidate_phone = "+91 9908597337"
    portfolio = "https://mohammed-minhaj.netlify.app/"
    github = "https://github.com/MuhammadMinhaj229/"
    linkedin = "https://www.linkedin.com/in/muhammadminhaj229"

    text_sig = "\n".join([
        "Regards,",
        "",
        candidate_name,
        f"{candidate_phone} • {candidate_email}",
        "Hyderabad, India • Open to Relocate Anywhere Worldwide",
        f"Portfolio & Case Studies: {portfolio}",
        f"GitHub Repository: {github}",
        f"LinkedIn Profile: {linkedin}",
    ])

    html_sig = (
        "<p>Regards,</p>"
        f"<p><strong>{escape(candidate_name)}</strong></p>"
        f'<p>{escape(candidate_phone)} • <a href="mailto:{escape(candidate_email, quote=True)}">'
        f"{escape(candidate_email)}</a></p>"
        "<p>Hyderabad, India • Open to Relocate Anywhere Worldwide</p>"
        f'<p>Portfolio &amp; Case Studies: <a href="{escape(portfolio, quote=True)}">'
        f"{escape(portfolio)}</a></p>"
        f'<p>GitHub Repository: <a href="{escape(github, quote=True)}">'
        f"{escape(github)}</a></p>"
        f'<p>LinkedIn Profile: <a href="{escape(linkedin, quote=True)}">'
        f"{escape(linkedin)}</a></p>"
    )
    return candidate_name, text_sig, html_sig


class DraftEngine:
    def __init__(
        self,
        gmail_user: Optional[str] = None,
        gmail_app_password: Optional[str] = None,
        profile_provider: Optional[Callable[[], Dict[str, Any]]] = None,
    ):
        self.gmail_user = gmail_user or os.getenv("GMAIL_SENDER_EMAIL") or os.getenv("GMAIL_USER", "")
        self.gmail_app_password = gmail_app_password or os.getenv("GMAIL_APP_PASSWORD", "")
        self.profile_provider = profile_provider

    def build_mime_message(
        self,
        draft: EmailDraft,
        attachment_bytes: Optional[bytes] = None,
        attachment_filename: Optional[str] = None
    ) -> MIMEMultipart:
        profile_data = self.profile_provider() if self.profile_provider else None
        cand_name, sig_text, sig_html = get_candidate_signature(profile_data=profile_data)

        # Outer container: mixed to support attachments
        outer_msg = MIMEMultipart("mixed")
        outer_msg["From"] = f"{cand_name} <{self.gmail_user}>"
        outer_msg["To"] = draft.recipient_email
        outer_msg["Subject"] = draft.subject_line

        # Inner container for alternative text + HTML
        alt_msg = MIMEMultipart("alternative")

        # Plain text
        text_body = draft.body_text + "\n\n" + sig_text
        
        # HTML formatted
        html_paragraphs = "\n".join(
            f'<p style="margin: 0 0 14px 0; line-height: 1.55; color: #222222;">{escape(p)}</p>'
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

        # Attachment resolution: explicit bytes take precedence over the local default.
        pdf_bytes = _resolve_attachment_bytes(attachment_bytes)
        filename = attachment_filename or "master_resume.pdf"

        if pdf_bytes:
            pdf_part = MIMEApplication(pdf_bytes, _subtype="pdf")
            pdf_part.add_header("Content-Disposition", "attachment", filename=filename)
            outer_msg.attach(pdf_part)

        return outer_msg

    def stage_draft(
        self,
        draft: EmailDraft,
        attachment_bytes: Optional[bytes] = None,
        attachment_filename: Optional[str] = None,
        *,
        draft_id: Optional[int] = None,
    ) -> Tuple[bool, str]:
        """Stage one content version once, failing closed when IMAP cannot check first."""
        mail = None
        try:
            if not self.gmail_user or not self.gmail_app_password:
                return False, "Gmail credentials are not configured."

            pdf_bytes = _resolve_attachment_bytes(attachment_bytes)
            staging_marker = build_staging_marker(
                draft,
                draft_id=draft_id,
                attachment_bytes=pdf_bytes,
                attachment_filename=attachment_filename,
            )

            mail = imaplib.IMAP4_SSL("imap.gmail.com")
            mail.login(self.gmail_user, self.gmail_app_password)

            # Search only ACIOS-marked messages in the user's Drafts folder.
            mailbox = '"[Gmail]/Drafts"'
            select_status, _ = mail.select(mailbox, readonly=False)
            if select_status != "OK":
                return False, "Could not select Gmail Drafts; staging was not attempted."

            search_status, search_data = mail.search(
                None, "HEADER", "X-ACIOS-Draft-ID", staging_marker
            )
            if search_status != "OK" or not search_data or search_data[0] is None:
                return False, "Could not verify existing Gmail drafts; staging failed closed."

            if search_data[0].strip():
                return True, "This exact ACIOS draft version is already staged; no duplicate was created."

            msg = self.build_mime_message(
                draft, attachment_bytes=pdf_bytes, attachment_filename=attachment_filename
            )
            # The opaque marker binds the local draft identity to its exact content
            # and attachment version; it contains no recipient or candidate data.
            msg["X-ACIOS-Draft-ID"] = staging_marker
            raw_bytes = msg.as_bytes()

            status, _ = mail.append(
                mailbox,
                "\\Draft",
                imaplib.Time2Internaldate(time.time()),
                raw_bytes,
            )

            if status == "OK":
                has_att = "with PDF CV attached" if pdf_bytes else "without attachment"
                return True, f"Successfully staged in [Gmail]/Drafts ({has_att})"
            return False, f"IMAP returned status: {status}"
        except Exception as e:
            return False, f"IMAP staging exception: {e}"
        finally:
            if mail:
                try:
                    mail.logout()
                except Exception:
                    pass

    def upload_draft(self, draft: EmailDraft) -> bool:
        """Backward-compatible alias for stage_draft."""
        ok, _ = self.stage_draft(draft)
        return ok
