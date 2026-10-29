"""
ACIOS Unified Command-Line Interface.
Consolidates all outreach operations into clean, reusable commands:
  - python -m acios.cli audit-mailbox
  - python -m acios.cli verify-drafts
  - python -m acios.cli sync-drafts
  - python -m acios.cli approve-draft ID (no sending)
"""

import sys
import os
import time
import argparse
import json
import re
import asyncio
import imaplib
from pathlib import Path
from email.utils import formatdate, make_msgid
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")

from acios.core.repository import CareerRepository
from acios.core.suppression import SuppressionEngine
from acios.core.draft_engine import DraftEngine
from acios.models.email_draft import EmailDraft
from acios.providers.verification.reacher_verifier import ReacherDeliverabilityEngine

GMAIL_USER = os.getenv("GMAIL_USER") or os.getenv("GMAIL_SENDER_EMAIL", "")
GMAIL_PASS = os.getenv("GMAIL_APP_PASSWORD", "")
DEFAULT_RESUME = BASE_DIR / "data" / "resume" / "master_resume.pdf"


def cmd_doctor(args):
    """Report local readiness without displaying secrets."""
    from acios.core.database import DEFAULT_DB_PATH
    from acios.crawling.catalog import integration_status

    print("ACIOS local-first health check")
    print(f"Python runtime: {sys.version.split()[0]}")
    print(f"Repository root: {BASE_DIR}")
    print(f"SQLite path: {DEFAULT_DB_PATH}")
    try:
        repo = CareerRepository()
        print("[OK] SQLite repository initialized")
        print(f"[INFO] Suppression records in canonical store: {repo.get_suppression_count()}")
    except Exception as exc:
        print(f"[FAIL] Local database: {type(exc).__name__}: {exc}")
        return

    profile_path = BASE_DIR / "config" / "candidate_profile.yaml"
    resume_path = Path(os.getenv("ACIOS_RESUME_DIR", str(BASE_DIR / "data" / "resume"))).expanduser() / "master_resume.pdf"
    if profile_path.is_file():
        print("[OK] Private candidate profile found")
    else:
        print("[WARN] Candidate profile not configured (copy config/candidate_profile.example.yaml)")
    if resume_path.is_file():
        try:
            valid_pdf = resume_path.read_bytes()[:5] == b"%PDF-"
        except OSError:
            valid_pdf = False
        print("[OK] Resume PDF found" if valid_pdf else "[FAIL] Resume path exists but is not a readable PDF")
    else:
        print("[WARN] Resume PDF missing; Gmail staging is unavailable")

    print(f"[INFO] Gmail draft staging configured: {'yes' if GMAIL_USER and GMAIL_PASS else 'no'}")
    print(f"[INFO] Firecrawl API configured: {'yes' if os.getenv('FIRECRAWL_API_KEY', '').strip() else 'no'}")
    print(f"[INFO] AI provider key configured: {'yes' if (os.getenv('GEMINI_API_KEY', '').strip() or os.getenv('GOOGLE_API_KEY', '').strip()) else 'no'}")
    print("[INFO] Automated email sending: disabled in local-first mode")
    for item in integration_status():
        state = "READY" if item.get("available") else "optional / unavailable"
        print(f"[INTEGRATION] {item['name']}: {state} — {item.get('reason', '')}")


def cmd_integrations(args):
    """List optional integration readiness without printing credentials."""
    from acios.crawling.catalog import integration_status

    statuses = integration_status()
    if args.json:
        print(json.dumps(statuses, indent=2, ensure_ascii=False))
        return
    for item in statuses:
        state = "READY" if item.get("available") else "NOT CONFIGURED"
        mode = "auto" if item.get("automatic") else "manual/opt-in"
        print(f"{item['id']:<18} {state:<16} {mode:<15} {item.get('reason', '')}")


def cmd_discover(args):
    """Discover candidate news events; outputs require primary-source verification."""
    from acios.tools.discovery.growth_scanner import GrowthSignalScanner

    repo = CareerRepository()
    scanner = GrowthSignalScanner(repo=repo)
    try:
        frame, excel_path, csv_path = scanner.scan_ecosystem(
            country=args.country,
            region=args.region,
            trigger_category=args.trigger,
            search_org=args.organization,
            search_website=args.website,
            custom_keywords=args.keywords,
            max_results=args.limit,
        )
    except Exception as exc:
        raise SystemExit(
            f"Discovery failed ({type(exc).__name__}). Check connectivity and provider configuration."
        ) from exc

    unresolved = 0
    if "entity_resolution_status" in frame.columns:
        unresolved = int((frame["entity_resolution_status"] == "UNRESOLVED").sum())
    print(f"Discovery rows: {len(frame)}")
    print("Verification status: DISCOVERED_NEEDS_PRIMARY_VERIFICATION")
    print("Do not contact anyone based on this report until the underlying claim and role are verified.")
    print(f"Unresolved organization candidates: {unresolved}")
    print(f"CSV: {csv_path}")
    print(f"Excel: {excel_path}")


def cmd_dossier(args):
    """Show a local organization record while flagging that stored facts may be stale."""
    repo = CareerRepository()
    dossier = repo.get_company_dossier(args.organization)
    if not dossier:
        print(json.dumps({
            "found": False,
            "organization_name": args.organization,
            "status": "NOT_FOUND",
            "note": "No local dossier exists. Run discovery, verify sources, and import evidence first."
        }, indent=2, ensure_ascii=False))
        return

    output = {
        "found": True,
        "status": "STORED_RECORD_NEEDS_CLAIM_LEVEL_REVALIDATION",
        "organization_name": args.organization,
        "dossier": dossier,
        "warning": (
            "Local records may be stale or based on legacy collection. Validate each claim, "
            "event date, role, domain, and contact channel against its actual source."
        ),
    }
    serialized = json.dumps(output, indent=2, ensure_ascii=False, default=str)
    if args.output:
        report_dir = BASE_DIR / "data" / "reports"
        report_dir.mkdir(parents=True, exist_ok=True)
        out_path = Path(args.output).expanduser()
        if not out_path.is_absolute():
            out_path = report_dir / out_path
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(serialized, encoding="utf-8")
        print(f"Dossier report written: {out_path}")
    else:
        print(serialized)


def cmd_capture_source(args):
    """Capture one permitted public page into the local source ledger for review."""
    import hashlib
    from datetime import datetime, timezone
    from urllib.parse import urlsplit
    from acios.crawling.engine import crawl_url

    try:
        result = asyncio.run(
            crawl_url(
                url=args.url,
                strategy=args.strategy,
                max_chars=max(500, min(args.max_chars, 50000)),
            )
        )
    except Exception as exc:
        raise SystemExit(
            f"Source capture failed ({type(exc).__name__}). No claim was marked verified."
        ) from exc

    text = str(result.get("content_markdown") or "").strip()
    final_url = str(result.get("final_url") or args.url)
    if not text:
        raise SystemExit("The provider returned no text. No source record was created.")
    content_hash = hashlib.sha256(text.encode("utf-8")).hexdigest()
    publisher = urlsplit(final_url).hostname or ""
    repo = CareerRepository()
    source_id = repo.record_source_document({
        "url": final_url,
        "canonical_url": final_url,
        "publisher": publisher,
        "title": result.get("title") or "",
        "source_type": "UNKNOWN",
        "retrieved_at": datetime.now(timezone.utc).isoformat(),
        "content_hash": content_hash,
        "excerpt": text[:3000],
        "content_text": text,
        "provider": result.get("provider") or "unknown",
        "verification_status": "CAPTURED_NEEDS_REVIEW",
        "metadata": {
            "duration_ms": result.get("duration_ms"),
            "warnings": result.get("warnings") or [],
            "robots_policy_checked": result.get("robots_policy_checked"),
            "truncated": result.get("truncated"),
        },
    })
    print(f"Source document ID: {source_id}")
    print(f"URL: {final_url}")
    print(f"Publisher host: {publisher or 'unknown'}")
    print(f"Title: {result.get('title') or '(no title returned)'}")
    print(f"Content SHA-256: {content_hash}")
    print("Classification: UNKNOWN — inspect the source before classifying it.")
    print("The successful fetch does not verify any factual claim.")


def cmd_source_list(args):
    repo = CareerRepository()
    print(json.dumps(repo.list_source_documents(query=args.query or "", limit=args.limit), indent=2, ensure_ascii=False))


def cmd_source_show(args):
    repo = CareerRepository()
    source = repo.get_source_document(args.source_id)
    if not source:
        raise SystemExit(f"Source document #{args.source_id} was not found.")
    print(json.dumps(source, indent=2, ensure_ascii=False, default=str))


def cmd_source_classify(args):
    repo = CareerRepository()
    source = repo.get_source_document(args.source_id)
    if not source:
        raise SystemExit(f"Source document #{args.source_id} was not found.")

    print(f"ID: {source['id']}")
    print(f"Title: {source['title']}")
    print(f"URL: {source['url']}")
    print(f"Publisher host: {source.get('publisher') or 'unknown'}")
    print(f"Current classification: {source['source_type']}")
    print(f"Excerpt: {(source.get('excerpt') or '')[:1200]}")
    token = f"CLASSIFY SOURCE {source['id']} {args.source_type.upper()}"
    print("Only classify a source as official/primary after checking who published it and what it supports.")
    print(f"Type this exact confirmation to continue: {token}")
    if input("> ").strip() != token:
        print("Cancelled. Source classification was not changed.")
        return
    reviewed_by = args.reviewed_by or os.getenv("USERNAME") or os.getenv("USER") or "local-operator"
    updated = repo.classify_source_document(
        source_id=source["id"],
        source_type=args.source_type,
        reviewed_by=reviewed_by,
        review_note=args.note,
    )
    print(f"Source #{updated['id']} classified as {updated['source_type']}; review event recorded.")


def cmd_claim_add(args):
    repo = CareerRepository()
    claim_id = repo.add_claim(
        entity_type=args.entity_type,
        entity_key=args.entity,
        predicate=args.predicate,
        claim_value=args.value,
        source_id=args.source_id,
        excerpt=args.excerpt,
        valid_from=args.valid_from,
        valid_to=args.valid_to,
    )
    print(f"Claim ID: {claim_id}")
    print("Status: UNCONFIRMED")
    print("Claim stored with a source reference; no verification was inferred.")


def cmd_claim_list(args):
    repo = CareerRepository()
    print(json.dumps(repo.list_claims(query=args.query or "", limit=args.limit), indent=2, ensure_ascii=False, default=str))


def cmd_claim_review(args):
    repo = CareerRepository()
    matches = [
        item for item in repo.list_claims(limit=1000)
        if int(item["id"]) == int(args.claim_id)
    ]
    if not matches:
        raise SystemExit(f"Claim #{args.claim_id} was not found.")
    claim = matches[0]
    print(json.dumps(claim, indent=2, ensure_ascii=False, default=str))
    token = f"REVIEW CLAIM {claim['id']} {args.status.upper()}"
    print("Review the cited excerpt and dates before selecting a status.")
    print(f"Type this exact confirmation to continue: {token}")
    if input("> ").strip() != token:
        print("Cancelled. Claim status was not changed.")
        return
    reviewed_by = args.reviewed_by or os.getenv("USERNAME") or os.getenv("USER") or "local-operator"
    reviewed = repo.review_claim(
        claim_id=claim["id"],
        verification_status=args.status,
        reviewed_by=reviewed_by,
        review_note=args.note,
        confidence=args.confidence,
    )
    print(f"Claim #{reviewed['id']} status: {reviewed['verification_status']}")
    print("The review decision was saved to the append-only claim review ledger.")


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
    if not pdf_bytes.startswith(b"%PDF-"):
        raise SystemExit("Configured resume does not have a valid PDF signature.")
    if len(pdf_bytes) > 10 * 1024 * 1024:
        raise SystemExit("Configured resume exceeds the 10 MB staging limit.")
    pdf_filename = DEFAULT_RESUME.name
    draft_engine = DraftEngine(gmail_user=GMAIL_USER, gmail_app_password=GMAIL_PASS)
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

        draft_model = EmailDraft(
            recipient_email=recipient,
            recipient_name=draft["recipient_name"],
            organization_name=draft["organization_name"],
            recipient_role=draft["recipient_role"],
            subject_line=draft["subject_line"],
            body_text=draft["body_text"],
            cv_attached=True,
        )
        message = draft_engine.build_mime_message(
            draft_model,
            attachment_bytes=pdf_bytes,
            attachment_filename=pdf_filename,
        )
        message["Date"] = formatdate(localtime=True)
        message["Message-ID"] = make_msgid(domain="gmail.com")
        message["X-ACIOS-Draft-ID"] = draft_id

        append_status, _ = mail.append(
            '"[Gmail]/Drafts"',
            "\\Draft",
            imaplib.Time2Internaldate(time.time()),
            message.as_bytes(),
        )
        if append_status == "OK":
            repo.record_outreach_event(
                recipient,
                "DRAFT_STAGED",
                status="LOCAL_STAGED",
                details=f"Draft #{draft_id} staged to Gmail Drafts for human review; not sent.",
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

    p_doctor = subparsers.add_parser("doctor", help="Check local database, profile, resume, and integrations")
    p_doctor.set_defaults(func=cmd_doctor)

    p_integrations = subparsers.add_parser("integrations", help="List optional provider readiness")
    p_integrations.add_argument("--json", action="store_true", help="Print machine-readable status JSON")
    p_integrations.set_defaults(func=cmd_integrations)

    p_discover = subparsers.add_parser("discover", help="Discover unverified organization/event leads from news")
    p_discover.add_argument("--country", default="Worldwide", help="Country or Worldwide")
    p_discover.add_argument("--region", default="All Regions")
    p_discover.add_argument("--trigger", default="All Strategic Triggers")
    p_discover.add_argument("--organization", help="Search around a known organization name")
    p_discover.add_argument("--website", help="Search around a user-supplied website; domain ownership remains unverified")
    p_discover.add_argument("--keywords", help="Additional or replacement search keywords")
    p_discover.add_argument("--limit", type=int, default=20)
    p_discover.set_defaults(func=cmd_discover)

    p_dossier = subparsers.add_parser("dossier", help="Inspect a stored organization dossier")
    p_dossier.add_argument("organization")
    p_dossier.add_argument("--output", help="Optional output filename; relative paths go under data/reports")
    p_dossier.set_defaults(func=cmd_dossier)

    p_source = subparsers.add_parser("source", help="Capture, inspect and classify source documents")
    source_commands = p_source.add_subparsers(dest="source_command", required=True)
    p_source_capture = source_commands.add_parser("capture", help="Fetch a public URL and store its content hash")
    p_source_capture.add_argument("url")
    p_source_capture.add_argument(
        "--strategy",
        choices=["auto", "httpx", "firecrawl", "crawl4ai", "crawlee", "scrapy", "scrapling"],
        default="auto",
    )
    p_source_capture.add_argument("--max-chars", type=int, default=20000)
    p_source_capture.set_defaults(func=cmd_capture_source)
    p_source_list = source_commands.add_parser("list", help="List captured sources")
    p_source_list.add_argument("--query")
    p_source_list.add_argument("--limit", type=int, default=100)
    p_source_list.set_defaults(func=cmd_source_list)
    p_source_show = source_commands.add_parser("show", help="Show a source's metadata and captured content")
    p_source_show.add_argument("source_id", type=int)
    p_source_show.set_defaults(func=cmd_source_show)
    p_source_classify = source_commands.add_parser("classify", help="Human-classify a captured source")
    p_source_classify.add_argument("source_id", type=int)
    p_source_classify.add_argument(
        "--source-type",
        choices=["UNKNOWN", "NEWS_AGGREGATOR_RESULT", "INDEPENDENT_SECONDARY",
                 "OFFICIAL_PRIMARY", "REGULATORY_PRIMARY", "OFFICIAL_PROFILE", "OFFICIAL_COMPANY_PAGE"],
        required=True,
    )
    p_source_classify.add_argument("--reviewed-by")
    p_source_classify.add_argument("--note", required=True)
    p_source_classify.set_defaults(func=cmd_source_classify)

    p_claim = subparsers.add_parser("claim", help="Record and review dated, source-linked factual claims")
    claim_commands = p_claim.add_subparsers(dest="claim_command", required=True)
    p_claim_add = claim_commands.add_parser("add", help="Record a new UNCONFIRMED claim")
    p_claim_add.add_argument("--entity-type", choices=["organization", "person", "project", "department"], required=True)
    p_claim_add.add_argument("--entity", required=True)
    p_claim_add.add_argument("--predicate", required=True, help="For example: founded_on, role_at_date, facility_opened")
    p_claim_add.add_argument("--value", required=True)
    p_claim_add.add_argument("--source-id", type=int, required=True)
    p_claim_add.add_argument("--excerpt", required=True, help="Exact relevant text from the cited source")
    p_claim_add.add_argument("--valid-from")
    p_claim_add.add_argument("--valid-to")
    p_claim_add.set_defaults(func=cmd_claim_add)
    p_claim_list = claim_commands.add_parser("list", help="List source-linked claims")
    p_claim_list.add_argument("--query")
    p_claim_list.add_argument("--limit", type=int, default=100)
    p_claim_list.set_defaults(func=cmd_claim_list)
    p_claim_review = claim_commands.add_parser("review", help="Human-review a claim with a required confirmation")
    p_claim_review.add_argument("claim_id", type=int)
    p_claim_review.add_argument(
        "--status",
        choices=["VERIFIED_PRIMARY", "CORROBORATED", "UNCONFIRMED", "CONFLICTED", "STALE", "REJECTED"],
        required=True,
    )
    p_claim_review.add_argument("--reviewed-by")
    p_claim_review.add_argument("--note", required=True)
    p_claim_review.add_argument("--confidence", type=float)
    p_claim_review.set_defaults(func=cmd_claim_review)

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
