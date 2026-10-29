"""
ACIOS FastMCP Server.
Exposes the Autonomous Career Intelligence & Outreach Operating System
as a Model Context Protocol (MCP) server with narrow, explicitly authorized tools.
"""

import asyncio
import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional
from fastmcp import FastMCP
import yaml

PACKAGE_ROOT = Path(__file__).resolve().parent.parent
if str(PACKAGE_ROOT) not in sys.path:
    sys.path.insert(0, str(PACKAGE_ROOT))

from acios.core.ai_copilot import AICopilotWriter
from acios.core.draft_engine import DraftEngine
from acios.core.generator import DraftGenerator
from acios.core.job_queue import DurableJobQueue
from acios.core.permutator import EmailPermutator
from acios.core.repository import CareerRepository
from acios.core.suppression import SuppressionEngine
from acios.models.contact import Contact, VerificationStatus
from acios.models.email_draft import EmailDraft
from acios.providers.verification.reacher_verifier import ReacherDeliverabilityEngine
from acios.providers.verification.waterfall import EmailVerificationWaterfall
from acios.tools.discovery.firecrawl_client import FirecrawlProvider
from acios.tools.discovery.ror import RORClient
from acios.tools.discovery.wikidata import WikidataClient

GMAIL_USER = os.getenv("GMAIL_USER", "")
GMAIL_APP_PASSWORD = os.getenv("GMAIL_APP_PASSWORD", "")

mcp = FastMCP(
    name="ACIOS Career Intelligence Gateway",
    instructions=(
        "Autonomous Career Intelligence & Outreach Operating System. "
        "Provides narrow, explicitly authorized tools for growth signal discovery, "
        "company dossier retrieval, evidence-based contact verification, draft creation, "
        "approval listing, explicit draft approval, idempotent dispatch, and job monitoring."
    ),
)

suppression_engine = SuppressionEngine()


# ==========================================
# Narrow Authorized Production MCP Tools (8 Core Tools)
# ==========================================


@mcp.tool()
def search_growth_signals(
    query: str = "",
    country: str = "",
    limit: int = 20,
    run_background_scan: bool = False,
) -> Dict[str, Any]:
    """Run a bounded local discovery scan; results remain unverified leads.

    The legacy run_background_scan argument is accepted for compatibility. A local
    scan runs synchronously because the local-first workflow does not require a worker.
    The output is not a verified signal dossier and must be checked against primary sources.
    """
    _ = run_background_scan
    from acios.tools.discovery.growth_scanner import GrowthSignalScanner

    repo = CareerRepository()
    scanner = GrowthSignalScanner(repo=repo)
    scan_country = country.strip() or "Worldwide"
    try:
        frame, excel_path, csv_path = scanner.scan_ecosystem(
            country=scan_country,
            region="All Regions",
            trigger_category="All Strategic Triggers",
            custom_keywords=query.strip() or None,
            max_results=max(1, min(int(limit), 50)),
        )
        records = frame.where(frame.notna(), None).to_dict(orient="records")
        return {
            "tool": "search_growth_signals",
            "status": "DISCOVERED_NEEDS_PRIMARY_VERIFICATION",
            "count": len(records),
            "signals": records,
            "outputs": {"csv": str(csv_path), "xlsx": str(excel_path)},
            "note": (
                "These are news-feed discovery leads, not verified facts. Confirm the "
                "underlying publisher page and event date before qualifying an opportunity."
            ),
            "background_job": None,
        }
    except Exception as exc:
        return {
            "tool": "search_growth_signals",
            "status": "FAILED",
            "count": 0,
            "signals": [],
            "error_type": type(exc).__name__,
            "message": (
                "Local discovery failed. Check provider connectivity and local dependencies; "
                "no signal was promoted to verified."
            ),
            "background_job": None,
        }


@mcp.tool()
def get_company_dossier(organization_name: str) -> Dict[str, Any]:
    """
    Retrieves sourced company, expansion signals, and decision-maker information.
    """
    repo = CareerRepository()
    dossier = repo.get_company_dossier(organization_name.strip())
    if not dossier:
        return {
            "tool": "get_company_dossier",
            "found": False,
            "organization_name": organization_name,
            "dossier": None,
        }
    return {"tool": "get_company_dossier", "found": True, "dossier": dossier}


@mcp.tool()
def verify_contact(email: str) -> Dict[str, Any]:
    """
    Returns verification evidence and confidence score, never an unsupported guarantee.
    """
    clean_email = email.strip().lower()
    repo = CareerRepository()
    if repo.is_suppressed(clean_email) or suppression_engine.is_suppressed(clean_email):
        return {
            "tool": "verify_contact",
            "email": clean_email,
            "valid": False,
            "verified": False,
            "is_suppressed": True,
            "confidence": 0.0,
            "status": "SUPPRESSED",
            "evidence": ["master_suppression_match"],
            "details": "Address is on the suppression list and cannot be contacted.",
        }

    verifier = ReacherDeliverabilityEngine()
    ver = asyncio.run(verifier.verify(clean_email))
    return {
        "tool": "verify_contact",
        "email": clean_email,
        "valid": bool(ver.get("valid", False)),
        "verified": bool(ver.get("verified", False)),
        "is_suppressed": False,
        "confidence": float(ver.get("confidence", 0.0)),
        "status": ver.get("status", "UNKNOWN"),
        "mx_host": ver.get("mx_host"),
        "is_catch_all": ver.get("is_catch_all", False),
        "evidence": ver.get("evidence", []),
        "details": ver.get("details", ""),
    }


@mcp.tool()
def create_outreach_draft(
    recipient_email: str,
    recipient_name: str,
    organization_name: str,
    recipient_role: str,
    subject_line: str = "",
    body_text: str = "",
    signal_headline: str = "",
) -> Dict[str, Any]:
    """
    Creates an outreach draft in PENDING_APPROVAL status without sending it.
    """
    clean_email = recipient_email.strip().lower()
    repo = CareerRepository()
    if repo.is_suppressed(clean_email) or suppression_engine.is_suppressed(clean_email):
        return {
            "tool": "create_outreach_draft",
            "status": "REJECTED",
            "reason": f"Recipient '{clean_email}' is on the suppression list.",
        }

    if body_text and subject_line:
        draft_obj = EmailDraft(
            recipient_email=clean_email,
            recipient_name=recipient_name,
            organization_name=organization_name,
            recipient_role=recipient_role,
            subject_line=subject_line,
            body_text=body_text,
        )
    else:
        writer = AICopilotWriter()
        draft_obj = writer.generate_initial_draft(
            target_name=recipient_name,
            target_role=recipient_role,
            target_org=organization_name,
            target_email=clean_email,
            target_history={"career_summary": signal_headline},
            signal_headline=signal_headline,
        )

    draft_id = repo.upsert_draft(draft_obj, status="PENDING_APPROVAL")
    return {
        "tool": "create_outreach_draft",
        "draft_id": draft_id,
        "status": "PENDING_APPROVAL",
        "draft": repo.get_draft_by_id(draft_id),
    }


@mcp.tool()
def list_pending_approvals() -> Dict[str, Any]:
    """
    Retrieves all outreach drafts awaiting explicit approval.
    """
    repo = CareerRepository()
    pending = repo.list_pending_approvals()
    return {
        "tool": "list_pending_approvals",
        "count": len(pending),
        "pending_drafts": pending,
    }


# Approval is intentionally not a machine-callable MCP tool. The authenticated
# web cockpit is the only place where the operator can approve an outreach draft.


@mcp.tool()
def send_approved_outreach(
    draft_id: int, idempotency_key: str = ""
) -> Dict[str, Any]:
    """Retained compatibility tool; programmatic sending is disabled locally."""
    _ = (draft_id, idempotency_key)
    return {
        "tool": "send_approved_outreach",
        "status": "DISABLED_LOCAL_FIRST",
        "message": (
            "ACIOS will not send email through an automated tool in local-first mode. "
            "Review the exact message and send it manually from Gmail."
        ),
    }

@mcp.tool()
def get_job_status(job_id: str) -> Dict[str, Any]:
    """
    Checks status, attempts, and result of a long-running background job.
    """
    repo = CareerRepository()
    queue = DurableJobQueue(repo=repo)
    job = queue.get_job_status(job_id)
    return {"tool": "get_job_status", "found": job is not None, "job": job}


# ==========================================
# Legacy / Local Studio Tools
# ==========================================


@mcp.tool()
def verify_suppression(email: str) -> Dict[str, Any]:
    """Checks if a target email address is on the master suppression list."""
    clean_email = email.strip().lower()
    is_blocked = suppression_engine.is_suppressed(clean_email)
    return {
        "email": clean_email,
        "is_suppressed": is_blocked,
        "status": "BLOCKED" if is_blocked else "CLEAN",
        "action_required": "DO NOT CONTACT" if is_blocked else "SAFE TO PROCEED",
    }


@mcp.tool()
def permute_email(name: str, domain: str) -> List[Dict[str, Any]]:
    """Generates RFC-822 candidate email permutations and checks suppression."""
    patterns = EmailPermutator.generate_patterns(name, domain)
    annotated = []
    for p in patterns:
        is_blocked = suppression_engine.is_suppressed(p)
        annotated.append(
            {
                "candidate_email": p,
                "status": "BLOCKED" if is_blocked else "CLEAN",
                "is_suppressed": is_blocked,
            }
        )
    return annotated


@mcp.tool()
def verify_email_waterfall(email: str) -> Dict[str, Any]:
    """Executes the 4-stage email verification waterfall."""
    waterfall = EmailVerificationWaterfall()
    res = waterfall.verify_email(email)
    return {
        "email": res.email,
        "status": res.status.value,
        "confidence_score": res.confidence_score,
        "mx_valid": res.mx_valid,
        "mx_records": res.mx_records,
        "is_disposable": res.is_disposable,
        "is_role_account": res.is_role_account,
        "provider": res.provider,
        "details": res.details,
    }


@mcp.tool()
def get_database_metrics() -> Dict[str, Any]:
    """Returns live statistics from the career intelligence repository."""
    repo = CareerRepository()
    return repo.get_system_stats()


@mcp.tool()
def generate_calibrated_draft(
    name: str,
    work_email: str,
    role: str,
    organization_name: str,
    sector: str = "Technology",
    trigger_signal: str = "",
) -> Dict[str, Any]:
    """Generates a calibrated outreach draft strictly within 100-160 words."""
    contact = Contact(
        name=name,
        role=role,
        organization_name=organization_name,
        work_email=work_email,
        verification_status=VerificationStatus.PATTERN_PREDICTED,
    )
    generator = DraftGenerator()
    draft = generator.generate_draft(
        contact, sector=sector, signal_headline=trigger_signal or None
    )
    return {
        "recipient_name": draft.recipient_name,
        "recipient_email": draft.recipient_email,
        "subject_line": draft.subject_line,
        "word_count": draft.word_count,
        "approval_hash": draft.approval_hash,
        "body_text": draft.body_text,
    }


@mcp.tool()
def run_prefect_workflow(workflow_name: str) -> Dict[str, Any]:
    """Triggers an automated workflow."""
    name = workflow_name.lower().replace("-", "_")
    if name in ["daily", "daily_scan", "daily_signal_scan"]:
        from acios.flows.daily_signal_scan import run_daily_signal_scan

        count = run_daily_signal_scan()
        return {
            "workflow": "daily_signal_scan",
            "status": "COMPLETED",
            "signals_processed": count,
        }
    elif name in ["weekly", "weekly_enrichment"]:
        from acios.flows.weekly_enrichment import run_weekly_enrichment

        count = run_weekly_enrichment()
        return {
            "workflow": "weekly_enrichment",
            "status": "COMPLETED",
            "leads_enriched": count,
        }
    elif name in ["imap", "imap_guard", "imap_reply_guard"]:
        from acios.flows.imap_reply_guard import run_imap_reply_guard

        res = run_imap_reply_guard()
        return {
            "workflow": "imap_reply_guard",
            "status": "COMPLETED",
            "result": res,
        }
    return {
        "error": f"Unknown workflow '{workflow_name}'. Available: daily-scan, weekly-enrichment, imap-guard"
    }


@mcp.tool()
def search_research_orgs(query: str, country_code: str = "") -> List[Dict[str, Any]]:
    """Searches the Research Organization Registry (ROR)."""
    c_code = country_code.strip() if country_code else None
    return RORClient.search_organizations(query=query, country_code=c_code)


@mcp.tool()
def search_wikidata_companies(
    country_code: str = "SA", sector_qid: str = "Q11451"
) -> List[Dict[str, Any]]:
    """Queries Wikidata SPARQL knowledge graph for registered companies."""
    return WikidataClient.search_companies(
        country_code=country_code, sector_qid=sector_qid, limit=25
    )


@mcp.tool()
def firecrawl_scrape_page(
    url: str, api_key: str = "", api_url: str = ""
) -> Dict[str, Any]:
    """Scrapes a target company website or newsroom URL into Markdown."""
    provider = FirecrawlProvider(api_key=api_key or None, api_url=api_url or None)
    return provider.scrape(url)


@mcp.tool()
def firecrawl_map_domain(
    domain_url: str, api_key: str = "", api_url: str = ""
) -> Dict[str, Any]:
    """Discovers subpages and internal URLs on a target company website."""
    provider = FirecrawlProvider(api_key=api_key or None, api_url=api_url or None)
    return provider.map_urls(domain_url)


@mcp.tool()
def firecrawl_search_and_scrape(
    query: str, api_key: str = "", api_url: str = ""
) -> Dict[str, Any]:
    """Searches the web via Firecrawl and scrapes the top result."""
    provider = FirecrawlProvider(api_key=api_key or None, api_url=api_url or None)
    return provider.search_and_scrape_top(query)


@mcp.tool()
async def crawl_web(
    url: str,
    strategy: str = "auto",
    max_chars: int = 20000,
    wanted_list: Optional[List[str]] = None,
    browser_instruction: str = "",
) -> Dict[str, Any]:
    """Extract one public web page through the shared ACIOS crawling gateway.

    Auto mode prefers configured local adapters and only uses Firecrawl when configured.
    URL and robots policies are checked; this tool does not send emails or change site state.
    """
    from acios.crawling.engine import crawl_url

    result = await crawl_url(
        url=url,
        strategy=strategy,
        max_chars=max(500, min(int(max_chars), 50000)),
        wanted_list=wanted_list,
        browser_instruction=browser_instruction or None,
    )
    return {"tool": "crawl_web", "status": "success", "result": result}


@mcp.tool()
def list_crawling_integrations() -> Dict[str, Any]:
    """List the readiness of all ten crawling/document integrations without exposing secrets."""
    from acios.crawling.catalog import integration_status

    tools = integration_status()
    return {"tool": "list_crawling_integrations", "count": len(tools), "tools": tools}


@mcp.tool()
def validate_email_draft(
    recipient_name: str,
    recipient_email: str,
    recipient_role: str,
    organization_name: str,
    subject_line: str,
    paragraphs: List[str],
) -> Dict[str, Any]:
    """Checks draft wording and known suppression records; this does not approve or stage."""
    clean_email = (recipient_email or "").strip().lower()
    if not clean_email:
        return {"status": "REJECTED", "reason": "Recipient email is required."}

    repo = CareerRepository()
    if suppression_engine.is_suppressed(clean_email) or repo.is_suppressed(clean_email):
        return {
            "status": "REJECTED",
            "reason": "Recipient is on a suppression registry; do not contact.",
        }

    try:
        draft = EmailDraft(
            recipient_name=recipient_name,
            recipient_email=clean_email,
            recipient_role=recipient_role,
            organization_name=organization_name,
            subject_line=subject_line,
            paragraphs=paragraphs,
        )
        return {
            "status": "VALIDATED_PENDING_APPROVAL",
            "word_count": draft.word_count,
            "approval_hash": draft.approval_hash,
            "recipient_email": draft.recipient_email,
            "subject_line": draft.subject_line,
            "body_preview": draft.body_text[:200] + "...",
            "note": "Validation is not human approval. Review the exact draft before staging or sending.",
        }
    except Exception as e:
        return {"status": "VALIDATION_FAILED", "reason": str(e)}


@mcp.tool()
def stage_draft_to_gmail(
    recipient_name: str,
    recipient_email: str,
    recipient_role: str,
    organization_name: str,
    subject_line: str,
    paragraphs: List[str],
) -> Dict[str, Any]:
    """Stages a resume-attached message for review; the tool never approves or sends."""
    val_result = validate_email_draft(
        recipient_name,
        recipient_email,
        recipient_role,
        organization_name,
        subject_line,
        paragraphs,
    )
    if val_result.get("status") != "VALIDATED_PENDING_APPROVAL":
        return val_result

    resume_path = PACKAGE_ROOT / "data" / "resume" / "master_resume.pdf"
    if not resume_path.is_file():
        return {
            "status": "RESUME_REQUIRED",
            "reason": "Place the current resume at data/resume/master_resume.pdf before staging.",
        }
    try:
        resume_bytes = resume_path.read_bytes()
    except OSError:
        return {"status": "RESUME_UNREADABLE", "reason": "The local resume could not be read."}
    if not resume_bytes.startswith(b"%PDF-"):
        return {"status": "RESUME_INVALID", "reason": "The local resume file is not a valid PDF signature."}

    import hashlib
    resume_hash = hashlib.sha256(resume_bytes).hexdigest()
    draft = EmailDraft(
        recipient_name=recipient_name,
        recipient_email=(recipient_email or "").strip().lower(),
        recipient_role=recipient_role,
        organization_name=organization_name,
        subject_line=subject_line,
        paragraphs=paragraphs,
        cv_attached=True,
        attachment_sha256=resume_hash,
    )
    repo = CareerRepository()
    if repo.is_suppressed(draft.recipient_email) or suppression_engine.is_suppressed(draft.recipient_email):
        return {"status": "REJECTED", "reason": "Recipient is on a suppression registry; do not contact."}
    try:
        draft_id = repo.upsert_draft(draft, status="PENDING_APPROVAL")
        stored = repo.get_draft_by_id(draft_id)
        if stored:
            draft = EmailDraft(
                recipient_name=stored["recipient_name"],
                recipient_email=stored["recipient_email"],
                recipient_role=stored["recipient_role"],
                organization_name=stored["organization_name"],
                subject_line=stored["subject_line"],
                body_text=stored["body_text"],
                cv_attached=bool(stored.get("cv_attached")),
                attachment_sha256=stored.get("attachment_sha256"),
            )
    except Exception as exc:
        return {"status": "DRAFT_PERSISTENCE_FAILED", "reason": str(exc)}

    engine = DraftEngine(gmail_user=GMAIL_USER, gmail_app_password=GMAIL_APP_PASSWORD)
    success, detail = engine.stage_draft(
        draft, attachment_bytes=resume_bytes, attachment_filename=resume_path.name
    )
    if success:
        repo.record_outreach_event(
            draft.recipient_email,
            "DRAFT_STAGED",
            f"Draft #{draft_id} staged in Gmail Drafts for human review. It was not approved or sent.",
        )
    return {
        "status": "STAGED_PENDING_APPROVAL" if success else "UPLOAD_FAILED",
        "draft_id": draft_id,
        "recipient": draft.recipient_email,
        "subject": draft.subject_line,
        "word_count": draft.word_count,
        "approval_hash": draft.approval_hash,
        "detail": detail,
        "note": "Staging is not human approval. Review the Gmail Draft and send manually.",
    }


@mcp.resource("resource://suppression/stats")
def get_suppression_stats() -> str:
    """Returns the total number of blocked and hard-bounced addresses in ACIOS."""
    return f"ACIOS Master Suppression Engine: {suppression_engine.total_blocked:,} total blocked addresses."


@mcp.resource("resource://candidate/profile")
def get_candidate_profile() -> str:
    """Returns only the locally configured candidate profile."""
    profile_path = PACKAGE_ROOT / "config" / "candidate_profile.yaml"
    if not profile_path.exists():
        return "Candidate profile is not configured."
    try:
        data = yaml.safe_load(profile_path.read_text(encoding="utf-8")) or {}
        return json.dumps(data, ensure_ascii=False, indent=2)
    except (OSError, yaml.YAMLError):
        return "Candidate profile could not be loaded."


@mcp.prompt()
def compose_career_outreach(
    company_name: str, decision_maker_name: str, trigger_event: str
) -> str:
    """Provides the master system prompt for writing a 100-160 word cold outreach email."""
    return f"""Draft a professional, personalized career inquiry email to {decision_maker_name} at {company_name}.
Context / Trigger Milestone: {trigger_event}
Strict Constraints:
1. Length: Exactly 100 to 160 words (excluding signature).
2. Tone: Humble, candid, conversational. Zero sales pitch, zero agency buzzwords.
3. Candidate identity and experience: Use only the configured private profile; if it is empty, do not invent details.
4. Evidence: Use only supplied verified experience anchors and source-backed company evidence.
5. Goal: Draft for human review; this prompt never sends or stages email.
"""


def main():
    """Runs the FastMCP server via STDIO transport by default."""
    print("[*] Starting ACIOS FastMCP Server...", file=sys.stderr)
    mcp.run()


if __name__ == "__main__":
    main()
