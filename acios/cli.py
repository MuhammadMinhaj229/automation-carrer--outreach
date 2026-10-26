"""
ACIOS Unified Command-Line Interface.
Consolidates all outreach operations into clean, reusable commands:
  - python -m acios.cli audit-mailbox
  - python -m acios.cli verify-drafts
  - python -m acios.cli sync-drafts
  - python -m acios.cli dispatch-queue [--interval 60]
"""

import sys
import os
import time
import argparse
import asyncio
import sqlite3
import smtplib
import imaplib
import email
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.application import MIMEApplication
from email.utils import formatdate, make_msgid
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")

from acios.core.repository import CareerRepository
from acios.core.suppression import SuppressionEngine
from acios.core.draft_engine import get_candidate_signature
from acios.providers.verification.reacher_verifier import ReacherDeliverabilityEngine

GMAIL_USER = os.getenv("GMAIL_USER") or os.getenv("GMAIL_SENDER_EMAIL", "")
GMAIL_PASS = os.getenv("GMAIL_APP_PASSWORD", "")
DEFAULT_RESUME = BASE_DIR / "data" / "resume" / "master_resume.pdf"
if not DEFAULT_RESUME.exists():
    DEFAULT_RESUME = BASE_DIR / "data" / "resume" / "master_resume.pdf"


def get_imap_connection():
    if not GMAIL_PASS:
        raise ValueError("GMAIL_APP_PASSWORD is not configured.")
    m = imaplib.IMAP4_SSL("imap.gmail.com", 993)
    m.login(GMAIL_USER, GMAIL_PASS)
    return m


def cmd_audit_mailbox(args):
    """Scans INBOX and Sent mail for prospect replies and delivery failures."""
    print(f"Connecting to Gmail IMAP as {GMAIL_USER}...")
    repo = CareerRepository()
    m = get_imap_connection()
    
    # 1. Sent Mail
    m.select('"[Gmail]/Sent Mail"', readonly=True)
    typ, data = m.search(None, "ALL")
    sent_count = len(data[0].split()) if typ == "OK" and data[0] else 0
    print(f"Total Sent Mail records: {sent_count}")

    # 2. INBOX
    m.select("INBOX", readonly=True)
    typ, data = m.search(None, "ALL")
    in_ids = data[0].split() if typ == "OK" and data[0] else []
    print(f"Inspecting last 50 emails in INBOX...")
    
    replies = []
    bounces = []
    for mid in reversed(in_ids[-50:]):
        typ, mdata = m.fetch(mid, "(BODY.PEEK[HEADER.FIELDS (FROM SUBJECT DATE)])")
        if typ == "OK" and mdata and mdata[0]:
            header_text = mdata[0][1].decode('utf-8', errors='replace')
            import re
            from_m = re.search(r"From:\s*(.+)", header_text, re.I)
            subj_m = re.search(r"Subject:\s*(.+)", header_text, re.I)
            f_val = from_m.group(1).strip() if from_m else ""
            s_val = subj_m.group(1).strip() if subj_m else ""

            if any(k in f_val.lower() for k in ["mailer-daemon", "postmaster"]) or any(k in s_val.lower() for k in ["failure", "undeliverable", "returned"]):
                bounces.append((f_val, s_val))
            elif s_val.lower().startswith("re:"):
                replies.append((f_val, s_val))

    m.logout()
    print(f"\n--- AUDIT RESULTS ---")
    print(f"Replies Detected ({len(replies)}):")
    for r in replies:
        print(f"  [REPLY] {r[0]} | Subj: {r[1]}")
    print(f"\nBounces Detected ({len(bounces)}):")
    for b in bounces:
        print(f"  [BOUNCE] {b[0]} | Subj: {b[1]}")


def cmd_verify_drafts(args):
    """Verifies all staged drafts in SQLite against DNS MX and Reacher SMTP probes."""
    repo = CareerRepository()
    reacher = ReacherDeliverabilityEngine()
    drafts = repo.list_drafts()
    print(f"Auditing deliverability for {len(drafts)} drafts...")

    async def _run():
        for idx, d in enumerate(drafts):
            em = d["recipient_email"]
            res = await reacher.verify(em)
            status = res.get("status", "UNKNOWN")
            mx = res.get("mx_host", "NONE")
            valid = res.get("valid", False)
            print(f"[{idx+1:02d}/{len(drafts)}] {em:<35} | {status:<15} | MX: {str(mx):<30} | Deliverable: {valid}")

    asyncio.run(_run())


def cmd_sync_drafts(args):
    """Purges old drafts and stages all approved drafts into [Gmail]/Drafts with resume PDF."""
    repo = CareerRepository()
    m = get_imap_connection()
    m.select('"[Gmail]/Drafts"', readonly=False)

    typ, data = m.search(None, "ALL")
    existing = data[0].split() if typ == "OK" and data[0] else []
    print(f"Purging {len(existing)} existing drafts from Gmail Drafts...")
    for mid in existing:
        m.store(mid, '+FLAGS', '\\Deleted')
    m.expunge()

    # Load Resume PDF
    pdf_bytes = DEFAULT_RESUME.read_bytes()
    pdf_filename = DEFAULT_RESUME.name
    cand_name, sig_text, sig_html = get_candidate_signature()

    drafts = repo.list_drafts()
    staged = 0
    for d in drafts:
        if d["status"] not in ["APPROVED", "STAGED", "STAGED_IN_GMAIL"]:
            continue
        
        msg = MIMEMultipart("mixed")
        msg["From"] = f"{cand_name} <{GMAIL_USER}>"
        msg["To"] = d["recipient_email"]
        msg["Subject"] = d["subject_line"]
        msg["Date"] = formatdate(localtime=True)
        msg["Message-ID"] = make_msgid(domain="gmail.com")

        # Plain text
        body = d["body_text"]
        if "Best regards," not in body and "Regards," not in body:
            body = body.strip() + "\n\n" + sig_text
        msg.attach(MIMEText(body, "plain", "utf-8"))

        # PDF attachment
        att = MIMEApplication(pdf_bytes, _subtype="pdf")
        att.add_header("Content-Disposition", "attachment", filename=pdf_filename)
        msg.attach(att)

        now_internal = imaplib.Time2Internaldate(time.time())
        m.append('"[Gmail]/Drafts"', '(\\Draft)', now_internal, msg.as_bytes())
        repo.update_contact_status(d["recipient_email"], "Draft Staged")
        staged += 1
        print(f"Staged draft: {d['recipient_email']} ({d['organization_name']})")

    m.logout()
    print(f"\nSUCCESS: {staged} drafts staged in Gmail Drafts with {pdf_filename} attached.")


def cmd_dispatch_queue(args):
    """Dispatches all staged drafts sequentially with a pacing cooldown."""
    interval = getattr(args, "interval", 60.0)
    repo = CareerRepository()
    supp = SuppressionEngine()
    m = get_imap_connection()
    m.select('"[Gmail]/Drafts"', readonly=False)

    pdf_bytes = DEFAULT_RESUME.read_bytes()
    pdf_filename = DEFAULT_RESUME.name
    cand_name, sig_text, sig_html = get_candidate_signature()

    drafts = [d for d in repo.list_drafts() if d["status"] in ["APPROVED", "STAGED", "STAGED_IN_GMAIL"]]
    print(f"Starting sequential dispatch for {len(drafts)} drafts (Interval: {interval}s)...")

    for idx, d in enumerate(drafts):
        em = d["recipient_email"]
        org = d["organization_name"]
        subj = d["subject_line"]

        # Safety Suppression Check
        if supp.is_suppressed(em):
            print(f"[{idx+1}/{len(drafts)}] SKIPPED (Suppressed): {em}")
            continue

        msg = MIMEMultipart("mixed")
        msg["From"] = f"{cand_name} <{GMAIL_USER}>"
        msg["To"] = em
        msg["Subject"] = subj
        msg["Date"] = formatdate(localtime=True)
        msg["Message-ID"] = make_msgid(domain="gmail.com")

        body = d["body_text"]
        if "Best regards," not in body and "Regards," not in body:
            body = body.strip() + "\n\n" + sig_text
        msg.attach(MIMEText(body, "plain", "utf-8"))

        att = MIMEApplication(pdf_bytes, _subtype="pdf")
        att.add_header("Content-Disposition", "attachment", filename=pdf_filename)
        msg.attach(att)

        # Dispatch via SMTP
        try:
            smtp = smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=25)
            smtp.login(GMAIL_USER, GMAIL_PASS)
            smtp.sendmail(GMAIL_USER, [em], msg.as_bytes())
            smtp.quit()

            repo.record_outreach_event(em, "DISPATCHED", f"Dispatched via CLI queue to {em} ({org})")
            repo.update_contact_status(em, "Outreach Sent")
            
            # Expunge from Gmail Drafts
            typ, s_res = m.search(None, f'(HEADER TO "{em}")')
            if typ == "OK" and s_res[0]:
                for mid in s_res[0].split():
                    m.store(mid, '+FLAGS', '\\Deleted')
                m.expunge()

            print(f"[{idx+1:02d}/{len(drafts)}] DISPATCHED: {em} ({org})")
        except Exception as e:
            print(f"[{idx+1:02d}/{len(drafts)}] FAILED: {em} - {e}")
            repo.record_outreach_event(em, "DISPATCH_FAILED", str(e))

        if idx + 1 < len(drafts):
            print(f"Pacing cooldown: waiting {interval}s...")
            time.sleep(interval)

    m.logout()
    print("\nDispatch queue completed.")


def main():
    parser = argparse.ArgumentParser(description="ACIOS Career Operating System CLI")
    subparsers = parser.add_subparsers(dest="command", required=True)

    p_audit = subparsers.add_parser("audit-mailbox", help="Audit inbox and sent mail for replies/bounces")
    p_audit.set_defaults(func=cmd_audit_mailbox)

    p_verify = subparsers.add_parser("verify-drafts", help="Verify deliverability of all drafts via MX & Reacher")
    p_verify.set_defaults(func=cmd_verify_drafts)

    p_sync = subparsers.add_parser("sync-drafts", help="Stage drafts with resume PDF into Gmail Drafts")
    p_sync.set_defaults(func=cmd_sync_drafts)

    p_dispatch = subparsers.add_parser("dispatch-queue", help="Execute 60s sequential dispatch queue")
    p_dispatch.add_argument("--interval", type=float, default=60.0, help="Seconds between sends (default: 60)")
    p_dispatch.set_defaults(func=cmd_dispatch_queue)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
