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
    """Stage pending ACIOS drafts without touching unrelated Gmail drafts."""
    repo = CareerRepository()
    if not GMAIL_USER or not GMAIL_PASS:
        raise SystemExit("GMAIL_USER/GMAIL_APP_PASSWORD are not configured.")
    if not DEFAULT_RESUME.is_file():
        raise SystemExit(
            f"Resume PDF not found at {DEFAULT_RESUME}. Configure the local resume before staging."
        )

    supp = SuppressionEngine()
    pdf_bytes = DEFAULT_RESUME.read_bytes()
    pdf_filename = DEFAULT_RESUME.name
    cand_name, sig_text, _ = get_candidate_signature()
    mail = get_imap_connection()
    status, _ = mail.select('"[Gmail]/Drafts"', readonly=False)
    if status != "OK":
        mail.logout()
        raise SystemExit("Could not select Gmail Drafts; nothing was staged.")

    drafts = [
        d for d in repo.list_drafts()
        if d.get("status") in {"PENDING_APPROVAL", "STAGED"}
    ]
    staged = 0
    skipped = 0
    for draft in drafts:
        draft_id = str(draft["id"])
        recipient = draft["recipient_email"].strip().lower()
        if supp.is_suppressed(recipient) or repo.is_suppressed(recipient):
            print(f"[BLOCKED] Draft #{draft_id}: recipient is suppressed.")
            skipped += 1
            continue

        # A stable custom header makes staging idempotent without deleting
        # unrelated user drafts or expunging the mailbox.
        search_status, search_data = mail.search(
            None, "HEADER", "X-ACIOS-Draft-ID", draft_id
        )
        if search_status == "OK" and search_data and search_data[0]:
            print(f"[ALREADY STAGED] Draft #{draft_id}: left existing Gmail draft untouched.")
            skipped += 1
            continue

        message = MIMEMultipart("mixed")
        message["From"] = f"{cand_name} <{GMAIL_USER}>"
        message["To"] = recipient
        message["Subject"] = draft["subject_line"]
        message["Date"] = formatdate(localtime=True)
        message["Message-ID"] = make_msgid(domain="gmail.com")
        message["X-ACIOS-Draft-ID"] = draft_id
        message.attach(MIMEText(draft["body_text"] + "\n\n" + sig_text, "plain", "utf-8"))

        attachment = MIMEApplication(pdf_bytes, _subtype="pdf")
        attachment.add_header("Content-Disposition", "attachment", filename=pdf_filename)
        message.attach(attachment)

        append_status, _ = mail.append(
            '"[Gmail]/Drafts"',
            "\\Draft",
            imaplib.Time2Internaldate(time.time()),
            message.as_bytes(),
        )
        if append_status == "OK":
            repo.record_outreach_event(
                recipient, "DRAFT_STAGED",
                f"Draft #{draft_id} staged to Gmail Drafts for human review; not sent."
            )
            staged += 1
            print(f"[STAGED FOR REVIEW] Draft #{draft_id}: {recipient}")
        else:
            print(f"[STAGING FAILED] Draft #{draft_id}: Gmail returned {append_status}.")
            skipped += 1

    mail.logout()
    print(
        f"\nCompleted: {staged} staged for review; {skipped} skipped. "
        "No existing unrelated Gmail drafts were deleted and no message was sent."
    )


def cmd_dispatch_queue(args):
    """Disable legacy bulk SMTP dispatch; use Gmail Drafts for per-message human review."""
    repo = CareerRepository()
    drafts = repo.list_drafts()
    eligible = [d for d in drafts if d.get("status") == "APPROVED"]
    print("Automatic bulk dispatch is disabled in the local-first ACIOS workflow.")
    print(f"Approved records currently in the local ledger: {len(eligible)}")
    print(
        "No message was sent and no Gmail draft was deleted. Review each approved "
        "message and send it manually from Gmail. This command is intentionally "
        "retained as a safe compatibility stub."
    )


def cmd_approve_draft(args):
    """Display a complete draft and require a one-time explicit confirmation token."""
    repo = CareerRepository()
    draft = repo.get_draft_by_id(args.draft_id)
    if not draft:
        raise SystemExit(f"Draft #{args.draft_id} was not found.")
    if draft.get("status") == "DISPATCHED":
        raise SystemExit("This draft is already marked as dispatched and cannot be approved again.")

    print("\n--- DRAFT REVIEW ---")
    print(f"ID: {draft['id']}")
    print(f"To: {draft['recipient_name']} <{draft['recipient_email']}>")
    print(f"Role: {draft['recipient_role']}")
    print(f"Organization: {draft['organization_name']}")
    print(f"Subject: {draft['subject_line']}")
    print(f"Body words: {draft['word_count']}")
    print(f"Resume linked to snapshot: {'yes' if draft.get('cv_attached') else 'no'}")
    print("\n" + draft["body_text"] + "\n")
    token = f"APPROVE {draft['id']} {draft['approval_hash'][:12]}"
    print("To record human approval of this exact snapshot, type:")
    print(token)
    confirmation = input("> ").strip()
    if confirmation != token:
        print("Approval cancelled. The draft was not changed.")
        return
    approved = repo.approve_draft(
        draft_id=int(draft["id"]),
        approved_by=os.getenv("USERNAME") or os.getenv("USER") or "local-operator",
        confirmation_note="Confirmed interactively in local CLI.",
    )
    print(f"Approved snapshot recorded for draft #{approved['id']}.")
    print("This command does not send email. Sending remains disabled in the local-first CLI.")


def main():
    parser = argparse.ArgumentParser(description="ACIOS Career Operating System CLI")
    subparsers = parser.add_subparsers(dest="command", required=True)

    p_audit = subparsers.add_parser("audit-mailbox", help="Audit inbox and sent mail for replies/bounces")
    p_audit.set_defaults(func=cmd_audit_mailbox)

    p_verify = subparsers.add_parser("verify-drafts", help="Verify deliverability of all drafts via MX & Reacher")
    p_verify.set_defaults(func=cmd_verify_drafts)

    p_sync = subparsers.add_parser("sync-drafts", help="Stage drafts with resume PDF into Gmail Drafts")
    p_sync.set_defaults(func=cmd_sync_drafts)

    p_dispatch = subparsers.add_parser(
        "dispatch-queue",
        help="Compatibility command; bulk sending is disabled and no messages are sent",
    )
    p_dispatch.set_defaults(func=cmd_dispatch_queue)

    p_approve = subparsers.add_parser(
        "approve-draft", help="Review and record a human approval snapshot without sending"
    )
    p_approve.add_argument("draft_id", type=int, help="Local draft ID to review")
    p_approve.set_defaults(func=cmd_approve_draft)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
