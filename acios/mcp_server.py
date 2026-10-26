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
    """
    Discovers companies and their sourced expansion evidence.
    Optionally queues a durable background scan job.
    """
    repo = CareerRepository()
    queue = DurableJobQueue(repo=repo)
    job = None
    if run_background_scan:
        job = queue.enqueue(
            job_type="search_growth_signals",
            payload={"query": query, "country": country or "Oman", "limit": limit},
        )
    signals = repo.search_growth_signals(
        query=query, country=country or None, limit=max(1, min(limit, 100))
    )
    return {
        "tool": "search_growth_signals",
        "count": len(signals),
        "signals": signals,
        "background_job": job,
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
    """
    Queues a previously human-approved draft for worker dispatch.
    Does not send synchronously and never auto-approves a draft.
    """
    repo = CareerRepository()
    draft = repo.get_draft_by_id(draft_id)
    if not draft:
        return {"tool": "send_approved_outreach", "status": "NOT_FOUND", "draft_id": draft_id}
    if draft.get("status") == "DISPATCHED":
        return {
            "tool": "send_approved_outreach",
            "status": "DUPLICATE_PREVENTED",
            "duplicate_prevented": True,
            "draft_id": draft_id,
        }
    if draft.get("status") != "APPROVED":
        return {
            "tool": "send_approved_outreach",
            "status": "NOT_APPROVED",
            "draft_id": draft_id,
            "current_status": draft.get("status"),
        }

    clean_email = (draft.get("recipient_email") or "").strip().lower()
    if repo.is_suppressed(clean_email) or suppression_engine.is_suppressed(clean_email):
        return {
            "tool": "send_approved_outreach",
            "status": "SUPPRESSED",
            "draft_id": draft_id,
        }

    request_key = idempotency_key.strip() or f"send-approved:{draft_id}"
    queue = DurableJobQueue(repo=repo)
    job = queue.enqueue(
        job_type="send_approved_outreach",
        payload={"draft_id": draft_id, "idempotency_key": request_key},
        idempotency_key=f"send-approved:{draft_id}:{request_key}",
        max_attempts=1,
    )
    return {
        "tool": "send_approved_outreach",
        "status": job.get("status", "QUEUED"),
        "draft_id": draft_id,
        "job_id": job["job_id"],
        "message": "Dispatch job queued. Check job status before further action.",
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
def validate_email_draft(
    recipient_name: str,
    recipient_email: str,
    recipient_role: str,
    organization_name: str,
    subject_line: str,
    paragraphs: List[str],
) -> Dict[str, Any]:
    """Validates that an email draft complies with ACIOS safety standards."""
    if suppression_engine.is_suppressed(recipient_email):
        return {
            "status": "REJECTED",
            "reason": f"Recipient '{recipient_email}' is in the master bounce/suppression list.",
        }

    try:
        draft = EmailDraft(
            recipient_name=recipient_name,
            recipient_email=recipient_email,
            recipient_role=recipient_role,
            organization_name=organization_name,
            subject_line=subject_line,
            paragraphs=paragraphs,
        )
        return {
            "status": "APPROVED",
            "word_count": draft.word_count,
            "approval_hash": draft.approval_hash,
            "recipient_email": draft.recipient_email,
            "subject_line": draft.subject_line,
            "body_preview": draft.body_text[:200] + "...",
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
    """Validates an email draft and uploads it into [Gmail]/Drafts via IMAP."""
    val_result = validate_email_draft(
        recipient_name,
        recipient_email,
        recipient_role,
        organization_name,
        subject_line,
        paragraphs,
    )
    if val_result.get("status") != "APPROVED":
        return val_result

    draft = EmailDraft(
        recipient_name=recipient_name,
        recipient_email=recipient_email,
        recipient_role=recipient_role,
        organization_name=organization_name,
        subject_line=subject_line,
        paragraphs=paragraphs,
    )

    engine = DraftEngine(
        gmail_user=GMAIL_USER, gmail_app_password=GMAIL_APP_PASSWORD
    )
    success = engine.upload_draft(draft)
    return {
        "status": "STAGED" if success else "UPLOAD_FAILED",
        "recipient": draft.recipient_email,
        "subject": draft.subject_line,
        "word_count": draft.word_count,
        "approval_hash": draft.approval_hash,
        "note": "Draft safely staged in [Gmail]/Drafts for manual inspection and CV attachment.",
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
