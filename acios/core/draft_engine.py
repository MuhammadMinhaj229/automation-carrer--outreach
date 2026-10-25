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
from typing import Optional, Tuple
from pathlib import Path
import yaml
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent.parent
load_dotenv(BASE_DIR / ".env")

from acios.models.email_draft import EmailDraft

DEFAULT_RESUME_PATH = BASE_DIR / "data" / "resume" / "Mohammed_Minhaj_Mahmood_CV.pdf"

def get_candidate_signature() -> Tuple[str, str, str]:
    """Returns (candidate_name, text_signature, html_signature) dynamically from config/candidate_profile.yaml."""
    profile_path = BASE_DIR / "config" / "candidate_profile.yaml"
    name = "Mohammed Minhaj Mahmood"
    email = "minhajmuhammad229@gmail.com"
    phone = "+91 9908597337"
    linkedin = "https://www.linkedin.com/in/muhammadminhaj229"
    portfolio = "https://mohammed-minhaj.netlify.app/"
    
    if profile_path.exists():
        try:
            with open(profile_path, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f)
                cand = data.get("candidate", {})
                name = cand.get("full_name") or name
                email = cand.get("email") or email
                phone = cand.get("phone") or phone
                linkedin = cand.get("linkedin_url") or linkedin
                portfolio = cand.get("portfolio_url") or portfolio
        except Exception:
            pass

    text_sig = f"Best regards,\n\n{name}\nData & Business Automation Analyst\n{phone} | {email}\nLinkedIn: {linkedin}\nPortfolio: {portfolio}"
    html_sig = f"""<p style="margin-top: 18px; margin-bottom: 4px;">Best regards,</p>
<p style="margin-top: 0; line-height: 1.55; color: #222222;">
  <strong>{name}</strong><br>
  Data & Business Automation Analyst<br>
  {phone} &bull; <a href="mailto:{email}" style="color: #0b57d0; text-decoration: none;">{email}</a><br>
  LinkedIn: <a href="{linkedin}" style="color: #0b57d0; text-decoration: none;">{linkedin}</a><br>
  Portfolio: <a href="{portfolio}" style="color: #0b57d0; text-decoration: none;">{portfolio}</a>
</p>"""
    return name, text_sig, html_sig


class DraftEngine:
    def __init__(self, gmail_user: Optional[str] = None, gmail_app_password: Optional[str] = None):
        self.gmail_user = gmail_user or os.getenv("GMAIL_SENDER_EMAIL") or os.getenv("GMAIL_USER", "minhajmuhammad229@gmail.com")
        self.gmail_app_password = gmail_app_password or os.getenv("GMAIL_APP_PASSWORD", "")

    def build_mime_message(
        self,
        draft: EmailDraft,
        attachment_bytes: Optional[bytes] = None,
        attachment_filename: Optional[str] = None
    ) -> MIMEMultipart:
        cand_name, sig_text, sig_html = get_candidate_signature()

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
        filename = attachment_filename or "Mohammed_Minhaj_Mahmood_CV.pdf"

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
