"""
Gmail IMAP Drafts Engine.
Uploads pre-addressed, personalized emails with clickable HTML signatures and
optional PDF resume attachments directly into [Gmail]/Drafts.
"""

import imaplib
import os
import time
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.application import MIMEApplication
from typing import Any, Callable, Dict, Optional, Tuple
from pathlib import Path
import yaml
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent.parent
load_dotenv(BASE_DIR / ".env")

from acios.models.email_draft import EmailDraft

DEFAULT_RESUME_PATH = BASE_DIR / "data" / "resume" / "master_resume.pdf"

def get_candidate_signature(
    profile_data: Optional[Dict[str, Any]] = None,
) -> Tuple[str, str, str]:
    """Build a signature from an explicitly supplied persistent profile or local dev YAML."""
    from html import escape

    if profile_data is None:
        # Local YAML is a development fallback only. Production identity comes from
        # the database and must never depend on an ephemeral container filesystem.
        profile_data = {}
        if os.getenv("ACIOS_ENV", "development").strip().lower() != "production":
            profile_path = BASE_DIR / "config" / "candidate_profile.yaml"
            try:
                if profile_path.exists():
                    profile_data = yaml.safe_load(
                        profile_path.read_text(encoding="utf-8")
                    ) or {}
            except (OSError, yaml.YAMLError):
                profile_data = {}

    candidate = (profile_data or {}).get("candidate", {}) or {}

    name = str(candidate.get("full_name") or "").strip()
    email = str(candidate.get("email") or "").strip()
    phone = str(candidate.get("phone") or "").strip()
    linkedin = str(candidate.get("linkedin_url") or "").strip()
    portfolio = str(candidate.get("portfolio_url") or "").strip()

    lines = ["Best regards,"]
    if name:
        lines.extend(["", name])
    if phone or email:
        lines.append(" | ".join(v for v in (phone, email) if v))
    if linkedin:
        lines.append(f"LinkedIn: {linkedin}")
    if portfolio:
        lines.append(f"Portfolio: {portfolio}")
    text_sig = "\n".join(lines)

    html_lines = ['<p>Best regards,</p>']
    if name:
        html_lines.append(f"<p><strong>{escape(name)}</strong></p>")
    contact_bits = [escape(v) for v in (phone, email) if v]
    if contact_bits:
        html_lines.append(f"<p>{' | '.join(contact_bits)}</p>")
    if linkedin.startswith(("https://", "http://")):
        target = escape(linkedin, quote=True)
        html_lines.append(f'<p>LinkedIn: <a href="{target}">{escape(linkedin)}</a></p>')
    if portfolio.startswith(("https://", "http://")):
        target = escape(portfolio, quote=True)
        html_lines.append(f'<p>Portfolio: <a href="{target}">{escape(portfolio)}</a></p>')
    return name, text_sig, "".join(html_lines)



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

        # Attachment resolution: provided bytes OR default resume file
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

    def stage_draft(
        self,
        draft: EmailDraft,
        attachment_bytes: Optional[bytes] = None,
        attachment_filename: Optional[str] = None
    ) -> Tuple[bool, str]:
        """Uploads an EmailDraft into [Gmail]/Drafts via IMAP."""
        mail = None
        try:
            mail = imaplib.IMAP4_SSL("imap.gmail.com")
            mail.login(self.gmail_user, self.gmail_app_password)
            
            msg = self.build_mime_message(draft, attachment_bytes, attachment_filename)
            raw_bytes = msg.as_bytes()
            
            # RFC-3501 folder selection with quotes for spaces
            mailbox = '"[Gmail]/Drafts"'
            status, response = mail.append(mailbox, "\\Draft", imaplib.Time2Internaldate(time.time()), raw_bytes)
            
            if status == "OK":
                has_att = "with PDF CV attached" if (attachment_bytes or DEFAULT_RESUME_PATH.exists()) else "without attachment"
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
