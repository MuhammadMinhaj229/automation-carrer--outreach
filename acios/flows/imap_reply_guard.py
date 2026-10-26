"""
ACIOS Workflow: IMAP Reply & Bounce Guard Monitor.
Orchestrated with Prefect to monitor the connected Gmail account for incoming replies
and delivery failures (hard bounces), ensuring automatic suppression and outreach protection.
Supports real-time progress callbacks and timing metrics for the Streamlit UI.
"""

import imaplib
import email
from email.header import decode_header
import os
import re
import sys
import time
from pathlib import Path
from typing import Dict, Any, List, Optional, Callable
from datetime import datetime, timezone
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(BASE_DIR))
load_dotenv(BASE_DIR / ".env")

try:
    from prefect import flow, task
    PREFECT_ENABLED = True
except ImportError:
    def task(name=None, **kwargs):
        def decorator(fn):
            return fn
        return decorator
    def flow(name=None, **kwargs):
        def decorator(fn):
            return fn
        return decorator
    PREFECT_ENABLED = False

from acios.core.repository import CareerRepository


def decode_str(header_val: str) -> str:
    if not header_val:
        return ""
    decoded_parts = decode_header(header_val)
    res = []
    for part, encoding in decoded_parts:
        if isinstance(part, bytes):
            try:
                res.append(part.decode(encoding or "utf-8", errors="replace"))
            except Exception:
                res.append(part.decode("latin1", errors="replace"))
        else:
            res.append(str(part))
    return "".join(res)


@task(name="check_replies_and_bounces")
def scan_inbox_for_replies_and_bounces(
    progress_callback: Optional[Callable[[float, str], None]] = None,
    limit: int = 30
) -> Dict[str, Any]:
    start_time = time.time()
    repo = CareerRepository()
    email_user = (os.getenv("GMAIL_SENDER_EMAIL") or os.getenv("GMAIL_USER") or "").strip()
    email_pass = os.getenv("GMAIL_APP_PASSWORD")

    if not email_user or not email_pass:
        msg = "Gmail credentials not configured. Running in dry-run mode."
        if progress_callback:
            progress_callback(1.0, msg)
        return {"replies_detected": 0, "bounces_detected": 0, "status": "DRY_RUN", "message": msg}

    if progress_callback:
        progress_callback(0.08, "Connecting to Gmail IMAP SSL (imap.gmail.com:993)...")

    replies = []
    bounces = []

    try:
        mail = imaplib.IMAP4_SSL("imap.gmail.com", 993)
        mail.login(email_user, email_pass)

        if progress_callback:
            progress_callback(0.18, f"Authenticated as {email_user}. Accessing INBOX...")

        mail.select("INBOX", readonly=True)

        known_emails = {
            c.get("work_email", "").strip().lower()
            for c in repo.list_contacts()
            if c.get("work_email")
        }

        typ, data = mail.search(None, "ALL")
        if typ == "OK" and data[0]:
            msg_ids = data[0].split()
            # Sample recent messages
            recent_ids = msg_ids[-limit:] if len(msg_ids) >= limit else msg_ids
            total_msgs = len(recent_ids)

            for idx, mid in enumerate(recent_ids):
                current_num = idx + 1
                elapsed = time.time() - start_time
                rate = current_num / max(elapsed, 0.05)
                remaining = (total_msgs - current_num) / max(rate, 0.05)
                pct = 0.20 + (0.70 * (current_num / max(total_msgs, 1)))

                if progress_callback:
                    progress_callback(
                        pct,
                        f"Inspecting message {current_num} of {total_msgs} &bull; Elapsed: {elapsed:.1f}s (Est. remaining: {remaining:.1f}s)"
                    )

                typ_h, msg_data = mail.fetch(mid, "(BODY.PEEK[HEADER.FIELDS (FROM SUBJECT DATE)])")
                if typ_h != "OK" or not msg_data or not msg_data[0]:
                    continue

                header_text = msg_data[0][1].decode("utf-8", errors="replace")
                
                from_match = re.search(r"From:\s*(.+)", header_text, re.IGNORECASE)
                subj_match = re.search(r"Subject:\s*(.+)", header_text, re.IGNORECASE)
                
                from_str = decode_str(from_match.group(1)) if from_match else ""
                subj_str = decode_str(subj_match.group(1)) if subj_match else ""

                clean_from = ""
                email_submatch = re.search(r"<([^>]+)>", from_str)
                if email_submatch:
                    clean_from = email_submatch.group(1).lower().strip()
                elif "@" in from_str:
                    clean_from = from_str.lower().strip()

                # 1. Delivery bounce detection
                if any(k in clean_from for k in ["mailer-daemon", "postmaster"]) or any(k in subj_str.lower() for k in ["failure", "undeliverable", "returned"]):
                    typ_b, b_data = mail.fetch(mid, "(BODY.PEEK[TEXT])")
                    if typ_b == "OK" and b_data and b_data[0]:
                        body_txt = b_data[0][1].decode("utf-8", errors="replace")
                        failed_emails = re.findall(r"([a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+)", body_txt)
                        for fe in failed_emails:
                            if fe.lower() != email_user.lower() and "google" not in fe.lower():
                                bounces.append(fe.lower())

                # 2. Reply detection from known candidate contacts
                elif clean_from in known_emails:
                    replies.append(clean_from)

        mail.close()
        mail.logout()

    except Exception as e:
        err_msg = f"IMAP scan exception: {e}"
        if progress_callback:
            progress_callback(1.0, err_msg)
        return {"replies_detected": 0, "bounces_detected": 0, "error": str(e), "elapsed_seconds": round(time.time() - start_time, 2)}

    # Commit findings to database
    if progress_callback:
        progress_callback(0.95, "Syncing replies and suppression lists with database...")

    now_iso = datetime.now(timezone.utc).isoformat()
    with repo._conn() as conn:
        cursor = conn.cursor()
        for r_email in set(replies):
            cursor.execute("""
                UPDATE contacts
                SET outreach_status = 'Replied (Protected)',
                    notes = COALESCE(notes, '') || ' | Reply received on ' || ?
                WHERE LOWER(work_email) = ?
            """, (now_iso, r_email))

            cursor.execute("""
                INSERT INTO outreach_events (recipient_email, event_type, timestamp, details)
                VALUES (?, 'REPLIED', ?, 'Incoming email reply detected via IMAP Guard')
            """, (r_email, now_iso))

        for b_email in set(bounces):
            repo.add_suppression(b_email, "Permanent Delivery Failure", "IMAP Reply Guard")
            cursor.execute("""
                UPDATE contacts
                SET is_suppressed = 1,
                    verification_status = 'Bounced / Suppressed',
                    notes = COALESCE(notes, '') || ' | Hard bounce recorded via IMAP Guard on ' || ?
                WHERE LOWER(work_email) = ?
            """, (now_iso, b_email))

            cursor.execute("""
                INSERT INTO outreach_events (recipient_email, event_type, timestamp, details)
                VALUES (?, 'BOUNCED', ?, 'Hard delivery failure detected via Mailer-Daemon')
            """, (b_email, now_iso))

        conn.commit()

    total_time = round(time.time() - start_time, 2)
    fin_text = f"Scan complete in {total_time}s &bull; {len(set(replies))} replies protected &bull; {len(set(bounces))} hard bounces suppressed."
    if progress_callback:
        progress_callback(1.0, fin_text)

    return {
        "replies_detected": len(set(replies)),
        "bounces_detected": len(set(bounces)),
        "status": "SUCCESS",
        "elapsed_seconds": total_time,
        "summary": fin_text
    }


@flow(name="imap_reply_guard_flow")
def run_imap_reply_guard(
    progress_callback: Optional[Callable[[float, str], None]] = None,
    limit: int = 30
):
    """Prefect orchestration flow for incoming reply and bounce protection."""
    return scan_inbox_for_replies_and_bounces(progress_callback=progress_callback, limit=limit)


if __name__ == "__main__":
    run_imap_reply_guard()
