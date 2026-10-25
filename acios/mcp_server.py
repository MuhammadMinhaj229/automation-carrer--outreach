"""
ACIOS FastMCP Server.
Exposes the entire Autonomous Career Intelligence & Outreach Operating System
as a Model Context Protocol (MCP) server for Antigravity, Claude Desktop, Cursor, and ChatGPT.
"""

import os
import sys
from pathlib import Path
from typing import Dict, Any, List, Optional
from fastmcp import FastMCP
import yaml
import json

# Ensure package root is in sys.path
PACKAGE_ROOT = Path(__file__).resolve().parent.parent
if str(PACKAGE_ROOT) not in sys.path:
    sys.path.insert(0, str(PACKAGE_ROOT))

from acios.core.suppression import SuppressionEngine
from acios.core.permutator import EmailPermutator
from acios.core.draft_engine import DraftEngine
from acios.core.repository import CareerRepository
from acios.core.generator import DraftGenerator
from acios.providers.verification.waterfall import EmailVerificationWaterfall
from acios.models.email_draft import EmailDraft
from acios.models.contact import Contact, VerificationStatus
from acios.tools.discovery.ror import RORClient
from acios.tools.discovery.wikidata import WikidataClient
from acios.tools.discovery.firecrawl_client import FirecrawlProvider

try:
    from email_campaign_system.config.settings import get_settings
    _settings = get_settings(force_reload=True)
    GMAIL_USER = _settings.gmail_user
    GMAIL_APP_PASSWORD = _settings.gmail_app_password
except Exception:
    GMAIL_USER = os.getenv("GMAIL_USER", "")
    GMAIL_APP_PASSWORD = os.getenv("GMAIL_APP_PASSWORD", "")

# Initialize FastMCP Server
mcp = FastMCP(
    name="ACIOS Career Intelligence Gateway",
    instructions="Autonomous Career Intelligence & Outreach Operating System. Provides tools for organization discovery, signal crawling via Firecrawl, contact email permuting, suppression checking, safety validation, and IMAP draft staging."
)

suppression_engine = SuppressionEngine()


# ==========================================
# 1. Verification & Suppression Tools
# ==========================================

@mcp.tool()
def verify_suppression(email: str) -> Dict[str, Any]:
    """
    Checks if a target email address is on the master suppression/hard-bounce blacklist.
    Returns deliverability safety status before any message is drafted or permuted.
    """
    clean_email = email.strip().lower()
    is_blocked = suppression_engine.is_suppressed(clean_email)
    return {
        "email": clean_email,
        "is_suppressed": is_blocked,
        "status": "BLOCKED" if is_blocked else "CLEAN",
        "action_required": "DO NOT CONTACT" if is_blocked else "SAFE TO PROCEED"
    }


@mcp.tool()
def permute_email(name: str, domain: str) -> List[Dict[str, Any]]:
    """
    Generates standard RFC-822 candidate email address permutations for a decision-maker
    and cross-references each candidate against the master suppression list.
    """
    patterns = EmailPermutator.generate_patterns(name, domain)
    annotated = []
    for p in patterns:
        is_blocked = suppression_engine.is_suppressed(p)
        annotated.append({
            "candidate_email": p,
            "status": "BLOCKED" if is_blocked else "CLEAN",
            "is_suppressed": is_blocked
        })
    return annotated


@mcp.tool()
def verify_email_waterfall(email: str) -> Dict[str, Any]:
    """
    Executes the comprehensive 4-stage email verification waterfall:
    Gate 0 (Suppression) -> Gate 1 (DNS & MX) -> Gate 2 (Disposable & Role) -> Gate 3 (Hunter.io SMTP).
    Returns deliverability status, confidence score, and audit details.
    """
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
        "details": res.details
    }


@mcp.tool()
def get_database_metrics() -> Dict[str, Any]:
    """
    Returns live statistics from the canonical SQLite database (data/acios.db),
    including counts of organizations, decision-makers, expansion signals, staged drafts, and suppressed inboxes.
    """
    repo = CareerRepository()
    return repo.get_system_stats()


@mcp.tool()
def generate_calibrated_draft(
    name: str,
    work_email: str,
    role: str,
    organization_name: str,
    sector: str = "Technology",
    trigger_signal: str = ""
) -> Dict[str, Any]:
    """
    Generates a calibrated outreach draft strictly within 100-160 words,
    selecting a relevant experience from the private profile configured outside version control.
    """
    contact = Contact(
        name=name,
        role=role,
        organization_name=organization_name,
        work_email=work_email,
        verification_status=VerificationStatus.PATTERN_PREDICTED
    )
    generator = DraftGenerator()
    draft = generator.generate_draft(contact, sector=sector, signal_headline=trigger_signal or None)
    return {
        "recipient_name": draft.recipient_name,
        "recipient_email": draft.recipient_email,
        "subject_line": draft.subject_line,
        "word_count": draft.word_count,
        "approval_hash": draft.approval_hash,
        "body_text": draft.body_text
    }


@mcp.tool()
def run_prefect_workflow(workflow_name: str) -> Dict[str, Any]:
    """
    Triggers an automated Prefect pipeline:
    - 'daily-scan': Monitors GCC expansion signals and news RSS.
    - 'weekly-enrichment': Enriches untouched organizations and runs verification waterfall.
    - 'imap-guard': Inspects Gmail inbox for replies and delivery failure bounces.
    """
    name = workflow_name.lower().replace("-", "_")
    if name in ["daily", "daily_scan", "daily_signal_scan"]:
        from acios.flows.daily_signal_scan import run_daily_signal_scan
        count = run_daily_signal_scan()
        return {"workflow": "daily_signal_scan", "status": "COMPLETED", "signals_processed": count}
    elif name in ["weekly", "weekly_enrichment"]:
        from acios.flows.weekly_enrichment import run_weekly_enrichment
        count = run_weekly_enrichment()
        return {"workflow": "weekly_enrichment", "status": "COMPLETED", "leads_enriched": count}
    elif name in ["imap", "imap_guard", "imap_reply_guard"]:
        from acios.flows.imap_reply_guard import run_imap_reply_guard
        res = run_imap_reply_guard()
        return {"workflow": "imap_reply_guard", "status": "COMPLETED", "result": res}
    else:
        return {"error": f"Unknown workflow '{workflow_name}'. Available: daily-scan, weekly-enrichment, imap-guard"}


# ==========================================
# 2. Organization Discovery Tools
# ==========================================

@mcp.tool()
def search_research_orgs(query: str, country_code: str = "") -> List[Dict[str, Any]]:
    """
    Searches the Research Organization Registry (ROR) for universities, research institutes,
    and government scientific bodies (e.g. KAUST, SQU, Qatar University, MEWA).
    """
    c_code = country_code.strip() if country_code else None
    return RORClient.search_organizations(query=query, country_code=c_code)


@mcp.tool()
def search_wikidata_companies(country_code: str = "SA", sector_qid: str = "Q11451") -> List[Dict[str, Any]]:
    """
    Queries Wikidata SPARQL knowledge graph for registered companies by country and sector.
    Default sector Q11451 = Agriculture / AgriTech. Other codes: Q21198 (Computer Science), Q11446 (Renewable energy).
    """
    return WikidataClient.search_companies(country_code=country_code, sector_qid=sector_qid, limit=25)


# ==========================================
# 3. Firecrawl Web Extraction & Signal Crawling
# ==========================================

@mcp.tool()
def firecrawl_scrape_page(url: str, api_key: str = "", api_url: str = "") -> Dict[str, Any]:
    """
    Scrapes a target company website, newsroom, or press release URL and converts it into
    clean, LLM-ready 'Fit-Markdown'. Works with Firecrawl Cloud or Self-Hosted Docker fork.
    """
    provider = FirecrawlProvider(api_key=api_key or None, api_url=api_url or None)
    return provider.scrape(url)


@mcp.tool()
def firecrawl_map_domain(domain_url: str, api_key: str = "", api_url: str = "") -> Dict[str, Any]:
    """
    Discovers all subpages, paths, and internal URLs on a target company website (e.g. /news, /press, /team)
    using Firecrawl's /map endpoint to pinpoint exact expansion signals without blind crawling.
    """
    provider = FirecrawlProvider(api_key=api_key or None, api_url=api_url or None)
    return provider.map_urls(domain_url)


@mcp.tool()
def firecrawl_search_and_scrape(query: str, api_key: str = "", api_url: str = "") -> Dict[str, Any]:
    """
    Searches the live web via Firecrawl for a query (e.g. 'latest AI news 2026')
    and immediately scrapes the top result into clean Fit-Markdown.
    """
    provider = FirecrawlProvider(api_key=api_key or None, api_url=api_url or None)
    return provider.search_and_scrape_top(query)


# ==========================================
# 4. Draft Validation & Gmail Staging Tools
# ==========================================

@mcp.tool()
def validate_email_draft(
    recipient_name: str,
    recipient_email: str,
    recipient_role: str,
    organization_name: str,
    subject_line: str,
    paragraphs: List[str]
) -> Dict[str, Any]:
    """
    Validates that an email draft strictly complies with ACIOS safety standards:
    - Body length strictly between 100 and 160 words (excluding signature)
    - Zero corporate sales/agency buzzwords (synergy, spearheading, game-changer, etc.)
    - Honest, conversational tone referencing real candidate experience
    """
    # 1. Suppression pre-flight check
    if suppression_engine.is_suppressed(recipient_email):
        return {
            "status": "REJECTED",
            "reason": f"Recipient '{recipient_email}' is in the master bounce/suppression list."
        }

    # 2. Pydantic Model Validation
    try:
        draft = EmailDraft(
            recipient_name=recipient_name,
            recipient_email=recipient_email,
            recipient_role=recipient_role,
            organization_name=organization_name,
            subject_line=subject_line,
            paragraphs=paragraphs
        )
        return {
            "status": "APPROVED",
            "word_count": draft.word_count,
            "approval_hash": draft.approval_hash,
            "recipient_email": draft.recipient_email,
            "subject_line": draft.subject_line,
            "body_preview": draft.body_text[:200] + "..."
        }
    except Exception as e:
        return {
            "status": "VALIDATION_FAILED",
            "reason": str(e)
        }


@mcp.tool()
def stage_draft_to_gmail(
    recipient_name: str,
    recipient_email: str,
    recipient_role: str,
    organization_name: str,
    subject_line: str,
    paragraphs: List[str]
) -> Dict[str, Any]:
    """
    Validates an email draft and uploads it directly into [Gmail]/Drafts via IMAP
    with clickable HTML signatures for human review and resume attachment. Zero autonomous sending.
    """
    # Run validation first
    val_result = validate_email_draft(
        recipient_name, recipient_email, recipient_role, organization_name, subject_line, paragraphs
    )
    if val_result.get("status") != "APPROVED":
        return val_result

    # Build Pydantic draft
    draft = EmailDraft(
        recipient_name=recipient_name,
        recipient_email=recipient_email,
        recipient_role=recipient_role,
        organization_name=organization_name,
        subject_line=subject_line,
        paragraphs=paragraphs
    )

    # Upload via IMAP
    engine = DraftEngine(gmail_user=GMAIL_USER, gmail_app_password=GMAIL_APP_PASSWORD)
    success = engine.upload_draft(draft)
    return {
        "status": "STAGED" if success else "UPLOAD_FAILED",
        "recipient": draft.recipient_email,
        "subject": draft.subject_line,
        "word_count": draft.word_count,
        "approval_hash": draft.approval_hash,
        "note": "Draft safely staged in [Gmail]/Drafts for manual inspection and CV attachment."
    }


# ==========================================
# 5. Resources & Prompts
# ==========================================

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
def compose_career_outreach(company_name: str, decision_maker_name: str, trigger_event: str) -> str:
    """Provides the master system prompt for writing a 100-160 word humble cold outreach email."""
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
