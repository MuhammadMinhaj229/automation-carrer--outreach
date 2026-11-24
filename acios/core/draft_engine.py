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
from email.utils import formataddr
from typing import Any, Callable, Dict, Optional, Tuple
from pathlib import Path
import yaml
from html import escape
from urllib.parse import urlsplit
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent.parent
load_dotenv(BASE_DIR / ".env")

from acios.models.email_draft import EmailDraft

DEFAULT_RESUME_PATH = BASE_DIR / "data" / "resume" / "master_resume.pdf"

def _profile_text(candidate: Dict[str, Any], key: str) -> str:
    """Read a profile string without accepting header/control-character injection."""
    value = candidate.get(key)
    if not isinstance(value, str):
        return ""
    value = value.strip()
    if any(ord(char) < 32 or ord(char) == 127 for char in value):
        return ""
    return value


def _https_profile_url(value: str) -> str:
    """Return only credential-free HTTPS URLs suitable for a signature link."""
    if not value:
        return ""
    try:
        parsed = urlsplit(value)
    except ValueError:
        return ""
    if (
        parsed.scheme.lower() != "https"
        or not parsed.hostname
        or parsed.username is not None
        or parsed.password is not None
    ):
        return ""
    return value


def get_candidate_signature(
    profile_data: Optional[Dict[str, Any]] = None,
) -> Tuple[str, str, str]:
    """Build a signature only from an explicitly supplied or private local profile.

    No candidate identity, contact details, or social URLs are embedded in source.
    When no profile is configured, the result contains only a generic closing.
    """
    if profile_data is None:
        profile_data = {}
        profile_path = BASE_DIR / "config" / "candidate_profile.yaml"
        try:
            if profile_path.is_file():
                profile_data = yaml.safe_load(
                    profile_path.read_text(encoding="utf-8")
                ) or {}
        except (OSError, yaml.YAMLError):
            profile_data = {}

    if not isinstance(profile_data, dict):
        profile_data = {}
    candidate = profile_data.get("candidate", {})
    if not isinstance(candidate, dict):
        candidate = {}

    candidate_name = _profile_text(candidate, "full_name")
    candidate_email = _profile_text(candidate, "email")
    candidate_phone = _profile_text(candidate, "phone")
    candidate_location = _profile_text(candidate, "current_location")

    # Do not create a mailto link from malformed or whitespace/control-bearing input.
    if (
        candidate_email.count("@") != 1
        or any(char.isspace() for char in candidate_email)
        or candidate_email.startswith("@")
        or candidate_email.endswith("@")
    ):
        candidate_email = ""

    portfolio = _https_profile_url(_profile_text(candidate, "portfolio_url"))
    github = _https_profile_url(_profile_text(candidate, "github_url"))
    linkedin = _https_profile_url(_profile_text(candidate, "linkedin_url"))

    text_lines = ["Regards,"]
    if candidate_name:
        text_lines.extend(["", candidate_name])
    contact_line = " • ".join(value for value in (candidate_phone, candidate_email) if value)
    if contact_line:
        text_lines.append(contact_line)
    if candidate_location:
        text_lines.append(candidate_location)
    for label, url in (
        ("Portfolio", portfolio),
        ("GitHub", github),
        ("LinkedIn", linkedin),
    ):
        if url:
            text_lines.append(f"{label}: {url}")
    text_signature = "\\n".join(text_lines)

    html_lines = ["<p>Regards,</p>"]
    if candidate_name:
        html_lines.append(f"<p><strong>{escape(candidate_name)}</strong></p>")

    html_contact = []
    if candidate_phone:
        html_contact.append(escape(candidate_phone))
    if candidate_email:
        email_text = escape(candidate_email)
        email_href = escape(candidate_email, quote=True)
        html_contact.append(f'<a href="mailto:{email_href}">{email_text}</a>')
    if html_contact:
        html_lines.append(f"<p>{' • '.join(html_contact)}</p>")
    if candidate_location:
        html_lines.append(f"<p>{escape(candidate_location)}</p>")

    for label, url in (
        ("Portfolio", portfolio),
        ("GitHub", github),
        ("LinkedIn", linkedin),
    ):
        if url:
            href = escape(url, quote=True)
            html_lines.append(
                f'<p>{label}: <a href="{href}">{escape(url)}</a></p>'
            )

    return candidate_name, text_signature, "".join(html_lines)


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
        outer_msg["From"] = formataddr((cand_name, self.gmail_user)) if cand_name else self.gmail_user
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
