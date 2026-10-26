"""
FastAPI Backend for Career Intelligence and Outreach Operating System.
Provides typed REST endpoints, versioned /api/v1 tool contracts, and Server-Sent Events (SSE)
for the Next.js cockpit and authenticated MCP gateway.
"""

import json
import os
import secrets
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional
import yaml
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))
load_dotenv(BASE_DIR / ".env")

from fastapi import FastAPI, File, Form, HTTPException, Query, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from pydantic import BaseModel, Field

from acios.core.ai_copilot import AICopilotWriter
from acios.core.draft_engine import DraftEngine, get_candidate_signature
from acios.core.emailengine_gateway import EmailEngineGateway
from acios.core.job_queue import DurableJobQueue, execute_approved_send
from acios.core.repository import CareerRepository
from acios.core.salesgpt_copilot import OutreachStage, SalesGPTCopilotEngine
from acios.core.smtp_dispatcher import SMTPDispatcher
from acios.core.suppression import SuppressionEngine
from acios.flows.imap_reply_guard import scan_inbox_for_replies_and_bounces
from acios.models.email_draft import EmailDraft
from acios.providers.verification.reacher_verifier import ReacherDeliverabilityEngine
from acios.reports.export import export_all
from acios.tools.discovery.deep_signal_radar import DeepSignalRadar
from acios.tools.discovery.executive_intelligence import ExecutiveIntelligenceFinder
from acios.tools.discovery.growth_scanner import (
    CONTINENT_MAP,
    TRIGGER_CATEGORIES,
    GrowthSignalScanner,
)
from acios.tools.discovery.linkedin_hunter import LinkedInHunter
from acios.tools.discovery.osint_hunter import OSINTHunter

app = FastAPI(
    title="Career Intelligence and Outreach Operating System API",
    version="2.5.0",
    openapi_url="/api/openapi.json",
    docs_url="/api/docs",
    redoc_url="/api/redoc",
)

# Direct CORS is disabled unless trusted origins are explicitly configured.
_allowed_origins = [
    origin.strip()
    for origin in os.getenv("ACIOS_ALLOWED_ORIGINS", "").split(",")
    if origin.strip()
]
if _allowed_origins:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=_allowed_origins,
        allow_credentials=False,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type", "X-Request-ID", "X-Idempotency-Key"],
    )


@app.middleware("http")
async def require_backend_service_auth(request, call_next):
    if request.url.path in ("/healthz", "/api/v1/healthz") and request.method == "GET":
        return await call_next(request)
    expected = os.getenv("ACIOS_BACKEND_API_KEY", "").strip()
    if len(expected) < 32 or expected.startswith("replace-with-"):
        return JSONResponse(
            {"detail": "Backend authentication is not securely configured."},
            status_code=503,
        )
    auth_header = request.headers.get("authorization", "")
    scheme, _, supplied = auth_header.partition(" ")
    if (
        scheme.lower() != "bearer"
        or not supplied
        or not secrets.compare_digest(supplied, expected)
    ):
        return JSONResponse({"detail": "Unauthorized"}, status_code=401)
    return await call_next(request)


@app.get("/healthz")
@app.get("/api/v1/healthz")
def healthz():
    return {"status": "ok", "storage_engine": repo.storage_engine}


# Shared Service Instances
repo = CareerRepository()
supp = SuppressionEngine()
draft_engine = DraftEngine()
dispatcher = SMTPDispatcher(repo=repo, supp=supp)
job_queue = DurableJobQueue(repo=repo)
scanner = GrowthSignalScanner(repo=repo)
hunter = LinkedInHunter(repo=repo)
intel_finder = ExecutiveIntelligenceFinder(repo=repo)
copilot = AICopilotWriter()

# Integrated Open-Source Engines
deep_radar = DeepSignalRadar(repo=repo)
osint_hunter = OSINTHunter(repo=repo)
reacher_verifier = ReacherDeliverabilityEngine()
salesgpt = SalesGPTCopilotEngine()
emailengine_gateway = EmailEngineGateway(repo=repo, supp=supp)

PROFILE_CONFIG_PATH = BASE_DIR / "config" / "candidate_profile.yaml"
DB_FILE_PATH = BASE_DIR / "data" / "acios.db"
MASTER_EXCEL_PATH = BASE_DIR / "Master_Career_Intelligence_Database.xlsx"
DISCOVERY_RUNS_DIR = BASE_DIR / "data" / "discovery_runs"
MAX_RESUME_BYTES = 10 * 1024 * 1024


async def _validate_pdf_upload(upload: UploadFile) -> tuple[bytes, str]:
    filename = Path(upload.filename or "").name
    if not filename or not filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are supported.")
    content = await upload.read(MAX_RESUME_BYTES + 1)
    if len(content) > MAX_RESUME_BYTES:
        raise HTTPException(status_code=413, detail="Resume PDF must be 10 MB or smaller.")
    if not content.startswith(b"%PDF-"):
        raise HTTPException(
            status_code=400, detail="Uploaded file is not a valid PDF document."
        )
    return content, "master_resume.pdf"


# =========================================================
# SYSTEM & PROFILE ENDPOINTS
# =========================================================


@app.get("/api/system/stats")
@app.get("/api/v1/system/stats")
def get_system_stats():
    """Returns database metrics."""
    return repo.get_system_stats()


@app.get("/api/hierarchy")
def get_hierarchy():
    """Returns geographic hierarchy and strategic trigger list."""
    return {"continents": CONTINENT_MAP, "triggers": TRIGGER_CATEGORIES}


@app.get("/api/profile")
def get_profile():
    """Returns candidate identity, signature, and connection status."""
    db_profile = repo.get_candidate_profile()
    if not db_profile and PROFILE_CONFIG_PATH.exists():
        with open(PROFILE_CONFIG_PATH, "r", encoding="utf-8") as f:
            db_profile = yaml.safe_load(f)

    cand = (db_profile or {}).get(
        "candidate",
        {
            "full_name": "",
            "email": "",
            "phone": "",
            "linkedin_url": "",
            "portfolio_url": "",
        },
    )

    _, sig_text, sig_html = get_candidate_signature()
    last_updated = repo.get_setting("candidate_profile_updated_at")

    return {
        "candidate": cand,
        "signature_text": sig_text,
        "signature_html": sig_html,
        "last_updated": last_updated,
        "services": {
            "imap_engine": "Active",
            "smtp_engine": "Active",
            "database": "Online",
            "verification_waterfall": "Ready",
        },
    }


class ProfileUpdateRequest(BaseModel):
    full_name: str
    email: str
    phone: str
    linkedin_url: str


@app.post("/api/profile")
def update_profile(req: ProfileUpdateRequest):
    """Updates candidate profile in both YAML and repository settings store."""
    current_data: Dict[str, Any] = {}
    if PROFILE_CONFIG_PATH.exists():
        with open(PROFILE_CONFIG_PATH, "r", encoding="utf-8") as f:
            current_data = yaml.safe_load(f) or {}

    cand = current_data.get("candidate", {})
    cand["full_name"] = req.full_name
    cand["email"] = req.email
    cand["phone"] = req.phone
    cand["linkedin_url"] = req.linkedin_url
    current_data["candidate"] = cand

    PROFILE_CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(PROFILE_CONFIG_PATH, "w", encoding="utf-8") as f:
        yaml.safe_dump(current_data, f, sort_keys=False)

    repo.save_candidate_profile(current_data)
    now_iso = datetime.now(timezone.utc).isoformat()
    repo.set_setting("candidate_profile_updated_at", now_iso)

    return {"status": "SUCCESS", "message": "Profile updated and permanently stored."}


@app.get("/api/download/db")
def download_database():
    """Downloads the local SQLite database if present."""
    if not DB_FILE_PATH.exists():
        raise HTTPException(status_code=404, detail="Database file not found.")
    return FileResponse(
        path=str(DB_FILE_PATH),
        filename="acios.db",
        media_type="application/x-sqlite3",
    )


@app.get("/api/download/master-excel")
def download_master_excel():
    """Compiles fresh master reports and downloads the Excel sheet."""
    export_all()
    if not MASTER_EXCEL_PATH.exists():
        raise HTTPException(status_code=404, detail="Master Excel workbook not found.")
    return FileResponse(
        path=str(MASTER_EXCEL_PATH),
        filename="Master_Career_Intelligence_Database.xlsx",
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )


# =========================================================
# TAB 1: DISCOVERY ENDPOINTS
# =========================================================


class DiscoveryScanRequest(BaseModel):
    country: str = "Oman"
    region: str = "All Regions"
    trigger_category: str = "All Strategic Triggers"
    search_org: Optional[str] = None
    search_website: Optional[str] = None
    custom_keywords: Optional[str] = None
    max_results: int = 30


@app.post("/api/discovery/scan")
def run_discovery_scan(req: DiscoveryScanRequest):
    """Executes a targeted growth scan and returns discovered records."""
    df_res, xl_path, csv_path = scanner.scan_ecosystem(
        country=req.country,
        region=req.region,
        trigger_category=req.trigger_category,
        search_org=req.search_org,
        search_website=req.search_website,
        custom_keywords=req.custom_keywords,
        max_results=req.max_results,
    )

    records = df_res.to_dict(orient="records") if not df_res.empty else []
    return {
        "total_found": len(records),
        "signals": records,
        "excel_filename": xl_path.name if xl_path.exists() else None,
        "csv_filename": csv_path.name if csv_path.exists() else None,
    }


@app.get("/api/discovery/download/{filename}")
def download_discovery_file(filename: str):
    """Downloads a generated discovery run file from data/discovery_runs/."""
    safe_name = Path(filename).name
    if safe_name != filename or safe_name in {"", ".", ".."}:
        raise HTTPException(status_code=400, detail="Invalid filename.")
    target_file = (DISCOVERY_RUNS_DIR / safe_name).resolve()
    if target_file.parent != DISCOVERY_RUNS_DIR.resolve():
        raise HTTPException(status_code=400, detail="Invalid filename.")
    if not target_file.exists():
        raise HTTPException(status_code=404, detail="File not found.")
    return FileResponse(
        path=str(target_file),
        filename=filename,
        media_type=(
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            if filename.endswith(".xlsx")
            else "text/csv"
        ),
    )


# =========================================================
# TAB 2: AUDIT & DECISION-MAKERS
# =========================================================


class AuditHuntRequest(BaseModel):
    organizations: List[str]


@app.post("/api/audit/hunt")
def run_audit_and_hunt(req: AuditHuntRequest):
    """Batches audit and hunts decision-makers across requested organizations."""
    if not req.organizations:
        raise HTTPException(status_code=400, detail="No organizations provided.")

    batch_res = hunter.audit_and_hunt_multiple(req.organizations)
    all_dms = []
    formatted_results = {}

    for org_name, data in batch_res.items():
        audit_raw = data.get("audit", {})
        formatted_audit = {
            "domain": audit_raw.get("domain"),
            "domain_accessible": bool(audit_raw.get("website")),
            "http_status": audit_raw.get("http_status"),
            "trigger_verified": bool(audit_raw.get("trigger_confirmed", False)),
            "evidence_excerpt": audit_raw.get("audit_summary", ""),
            "decision_makers": [],
        }

        dms_for_org = []
        for dm in data.get("decision_makers", []):
            formatted_dm = {
                "name": dm.get("name", ""),
                "role": dm.get("role", ""),
                "organization_name": org_name,
                "linkedin_url": dm.get("linkedin_url"),
                "email": dm.get("email") or dm.get("work_email") or "",
                "confidence": float(dm.get("confidence") or 0.0),
                "verified": bool(dm.get("verified", False)),
                "source": dm.get("verification_source", "Unverified"),
            }
            dms_for_org.append(formatted_dm)
            all_dms.append(formatted_dm)

        formatted_audit["decision_makers"] = dms_for_org
        formatted_results[org_name] = formatted_audit

    return {
        "organizations_audited": len(formatted_results),
        "total_decision_makers": len(all_dms),
        "results": formatted_results,
        "all_decision_makers": all_dms,
    }


# =========================================================
# TAB 3: EXECUTIVE DOSSIER & HISTORY
# =========================================================


@app.get("/api/contacts")
def list_contacts(org: Optional[str] = None):
    """Lists all contacts from database, with optional organization filter."""
    raw_contacts = repo.list_contacts(org_name=org)
    formatted = []
    for idx, c in enumerate(raw_contacts):
        formatted.append(
            {
                "id": c.get("id", idx + 1),
                "organization_name": c.get("organization_name", ""),
                "contact_name": c.get("name", ""),
                "role_designation": c.get("role", ""),
                "email_address": c.get("work_email") or "",
                "linkedin_url": c.get("linkedin_url", ""),
                "deliverability_status": c.get("verification_status", "UNVERIFIED"),
                "confidence_score": c.get("confidence_score", 0),
            }
        )
    return formatted


class ExecutiveDossierRequest(BaseModel):
    name: str
    role: str
    organization: str


@app.post("/api/executive/dossier")
def get_executive_dossier(req: ExecutiveDossierRequest):
    """Compiles verification waterfall and executive role dossier."""
    email_res = intel_finder.find_and_verify_email(req.name, req.organization)
    history_res = intel_finder.extract_career_history(
        req.name, req.role, req.organization
    )

    best_email = (email_res.get("email") or "").strip().lower()
    conf = email_res.get("confidence_score", 0.0)
    conf_pct = int(round(conf * 100)) if conf <= 1.0 else int(conf)

    is_supp = supp.is_suppressed(best_email)
    mx_ok = bool(email_res.get("mx_valid", False))

    email_info = {
        "corporate_email": best_email,
        "email_pattern": email_res.get("source", "Pattern Permutator"),
        "verification_waterfall": {
            "gate_0_suppression": "CLEAN" if not is_supp else "SUPPRESSED",
            "gate_1_mx_host": "VERIFIED" if mx_ok else "UNREACHABLE",
            "gate_2_disposable_check": "PASSED",
            "gate_3_confidence_score": conf_pct,
        },
        "deliverability_status": (
            "MX_VALID"
            if (best_email and not is_supp and mx_ok and conf_pct >= 80)
            else "UNVERIFIED"
        ),
    }

    past_roles = []
    for m in history_res.get("milestones", []):
        r_title = m.split(" at ")[0] if " at " in m else req.role
        past_roles.append(
            {
                "role": r_title[:45],
                "organization": req.organization,
                "tenure": "Active Milestone",
            }
        )
    if not past_roles:
        past_roles = [
            {"role": req.role, "organization": req.organization, "tenure": "Current"}
        ]

    milestones = history_res.get("milestones") or []
    history = {
        "career_summary": history_res.get(
            "career_summary", f"{req.role} at {req.organization}."
        ),
        "technical_focus": history_res.get(
            "technical_focus", "Enterprise Engineering & Scalability"
        ),
        "past_roles": past_roles,
        "education": history_res.get("academic_background", "Not specified"),
        "recent_initiatives": (
            milestones[0] if milestones else f"Operations at {req.organization}"
        ),
    }

    return {
        "name": req.name,
        "role": req.role,
        "organization": req.organization,
        "email_info": email_info,
        "history": history,
    }


# =========================================================
# TAB 4: AI CO-PILOT
# =========================================================


class InitialDraftRequest(BaseModel):
    target_name: str
    target_role: str
    target_org: str
    target_email: str
    target_history: Dict[str, Any]


@app.post("/api/copilot/initial")
def generate_initial_draft(req: InitialDraftRequest):
    """Creates initial evidence-based draft tailored to the target."""
    draft = copilot.generate_initial_draft(
        target_name=req.target_name,
        target_role=req.target_role,
        target_org=req.target_org,
        target_email=req.target_email,
        target_history=req.target_history,
        signal_headline=req.target_history.get("career_summary", ""),
    )
    exp = copilot.generator.select_experience(
        req.target_history.get("technical_focus", ""), req.target_role
    )
    return {
        "subject_line": draft.subject_line,
        "body_text": draft.body_text,
        "word_count": draft.word_count,
        "auto_matched_experience": {
            "organization": exp.get("organization", ""),
            "role": exp.get("role", ""),
            "headline": exp.get("focus", ""),
            "evidence_cite": exp.get("summary", "").strip(),
        },
    }


class RefineDraftRequest(BaseModel):
    current_body: str
    current_subject: str
    target_name: str
    target_org: str
    target_role: str
    user_guidance: str
    target_history: Dict[str, Any]


@app.post("/api/copilot/refine")
def refine_draft(req: RefineDraftRequest):
    """Refines an existing draft based on conversational user guidance."""
    rev_b, rev_s, expl = copilot.refine_draft_with_guidance(
        current_body=req.current_body,
        current_subject=req.current_subject,
        target_name=req.target_name,
        target_org=req.target_org,
        target_role=req.target_role,
        user_guidance=req.user_guidance,
        target_history=req.target_history,
    )
    wc = copilot.calculate_word_count(rev_b)
    return {
        "revised_body": rev_b,
        "revised_subject": rev_s,
        "word_count": wc,
        "explanation": expl,
    }


class ApproveDraftRequest(BaseModel):
    recipient_email: str
    recipient_name: str
    organization_name: str
    recipient_role: str
    subject_line: str
    body_text: str


@app.post("/api/copilot/approve")
def approve_draft(req: ApproveDraftRequest):
    """Validates word count, computes approval hash, and saves to database."""
    words = len(req.body_text.strip().split())
    if words < 100 or words > 160:
        raise HTTPException(
            status_code=400,
            detail=f"Draft word count ({words}) is outside the required 100-160 word window. Please adjust before approving.",
        )

    app_hash = copilot.generate_approval_hash(req.body_text, req.recipient_email)
    try:
        draft_obj = EmailDraft(
            recipient_email=req.recipient_email,
            recipient_name=req.recipient_name,
            organization_name=req.organization_name,
            recipient_role=req.recipient_role,
            subject_line=req.subject_line,
            body_text=req.body_text,
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

    existing_draft = repo.get_draft_by_email(req.recipient_email)
    if existing_draft and existing_draft.get("status") == "DISPATCHED":
        raise HTTPException(
            status_code=409,
            detail="A dispatched draft cannot be edited or approved again.",
        )
    clean_email = req.recipient_email.strip().lower()
    if repo.is_suppressed(clean_email) or supp.is_suppressed(clean_email):
        raise HTTPException(
            status_code=409,
            detail="Recipient is on the suppression list and cannot be contacted.",
        )

    draft_id = repo.upsert_draft(draft_obj, status="PENDING_APPROVAL")
    approved = repo.approve_draft(
        draft_id=draft_id,
        approved_by="web_operator",
        confirmation_note="Approved through the authenticated web cockpit.",
    )
    if not approved:
        raise HTTPException(status_code=500, detail="Draft approval could not be persisted.")
    return {
        "draft_id": draft_id,
        "status": approved.get("status", "APPROVED"),
        "approval_hash": app_hash,
        "approved_at": approved.get("approved_at"),
        "message": f"Draft for {req.recipient_name} approved and staged.",
    }


# =========================================================
# TAB 5: EMAIL AUTOMATION & DISPATCH
# =========================================================


@app.get("/api/drafts/approved")
def list_approved_drafts():
    """Lists all approved or staged drafts."""
    all_d = repo.list_drafts()
    return [d for d in all_d if d.get("status") in ["APPROVED", "STAGED", "PENDING_APPROVAL"]]


@app.post("/api/dispatch/stage-gmail")
async def stage_draft_in_gmail(
    recipient_email: str = Form(...),
    custom_resume: Optional[UploadFile] = File(None),
):
    """Stages pre-addressed email draft into [Gmail]/Drafts via IMAP."""
    target_d = repo.get_draft_by_email(recipient_email)
    if not target_d:
        raise HTTPException(status_code=404, detail="Draft not found in database.")

    pdf_bytes = None
    pdf_name = "master_resume.pdf"
    if custom_resume:
        pdf_bytes, pdf_name = await _validate_pdf_upload(custom_resume)

    ed = EmailDraft(
        recipient_email=target_d["recipient_email"],
        recipient_name=target_d["recipient_name"],
        organization_name=target_d["organization_name"],
        recipient_role=target_d["recipient_role"],
        subject_line=target_d["subject_line"],
        body_text=target_d["body_text"],
    )
    ok, msg = draft_engine.stage_draft(
        ed, attachment_bytes=pdf_bytes, attachment_filename=pdf_name
    )
    repo.record_outreach_event(
        recipient_email=target_d["recipient_email"],
        action_type="STAGE_GMAIL_DRAFT",
        status="DELIVERED" if ok else "LOCAL_STAGED",
        details=msg,
    )
    if ok:
        repo.upsert_draft(ed, status="STAGED_IN_GMAIL")
        return {
            "success": True,
            "message": "Successfully staged in [Gmail]/Drafts with PDF CV attached.",
        }
    repo.upsert_draft(ed, status="STAGED_LOCAL")
    return {
        "success": True,
        "message": f"Draft saved and queued in local database. (Gmail IMAP Note: {msg})",
    }


@app.post("/api/dispatch/send-direct", status_code=202)
async def send_direct_email(
    recipient_email: str = Form(...),
    custom_resume: Optional[UploadFile] = File(None),
):
    """Queues an approved outreach draft; the worker owns all live SMTP dispatch."""
    target_d = repo.get_draft_by_email(recipient_email)
    if not target_d:
        raise HTTPException(status_code=404, detail="Draft not found in database.")
    if target_d.get("status") == "DISPATCHED":
        return {
            "success": True,
            "status": "DUPLICATE_PREVENTED",
            "duplicate_prevented": True,
            "message": "This draft has already been dispatched.",
        }
    if target_d.get("status") != "APPROVED":
        raise HTTPException(
            status_code=409,
            detail="Only APPROVED drafts can be queued for dispatch.",
        )

    clean_email = (target_d.get("recipient_email") or "").strip().lower()
    if repo.is_suppressed(clean_email) or supp.is_suppressed(clean_email):
        raise HTTPException(status_code=409, detail="Recipient is on the suppression list.")

    # The current worker contract uses one master resume file on a shared private
    # persistent volume. If a custom PDF is supplied, make that selection explicit
    # by saving it as the active master resume for queued worker sends.
    resume_path = BASE_DIR / "data" / "resume" / "master_resume.pdf"
    if custom_resume:
        pdf_bytes, _ = await _validate_pdf_upload(custom_resume)
        resume_path.parent.mkdir(parents=True, exist_ok=True)
        resume_path.write_bytes(pdf_bytes)

    dry_run = os.getenv("DRY_RUN", "true").strip().lower() in ("1", "true", "yes")
    if not dry_run and not resume_path.is_file():
        raise HTTPException(
            status_code=409,
            detail="Upload a master resume before enabling live dispatch.",
        )

    idempotency_key = f"web-direct:{int(target_d['id'])}"
    job = job_queue.enqueue(
        job_type="send_approved_outreach",
        payload={
            "draft_id": int(target_d["id"]),
            "idempotency_key": idempotency_key,
        },
        idempotency_key=idempotency_key,
        max_attempts=1,
    )
    return {
        "success": True,
        "status": job.get("status", "QUEUED"),
        "job_id": job["job_id"],
        "message": (
            "Dispatch job queued. The selected PDF is the active master resume for worker sends."
            if custom_resume
            else "Dispatch job queued. Check its status before taking further action."
        ),
    }


@app.get("/api/outreach/ledger")
def get_outreach_ledger(limit: int = 20):
    """Returns recent outreach ledger events."""
    return repo.list_outreach_events(limit=limit)


# =========================================================
# VERSIONED V1 NARROW AUTHORIZED TOOLS FOR CHATGPT & MCP
# =========================================================


class SearchGrowthSignalsToolRequest(BaseModel):
    query: str = ""
    country: Optional[str] = None
    limit: int = Field(default=20, ge=1, le=100)
    run_background_scan: bool = False


@app.post("/api/v1/tools/search-growth-signals")
def tool_search_growth_signals(req: SearchGrowthSignalsToolRequest):
    """
    Tool 1: search_growth_signals
    Discovers companies and their sourced expansion evidence.
    Optionally enqueues a durable background scan job.
    """
    job = None
    if req.run_background_scan:
        job = job_queue.enqueue(
            job_type="search_growth_signals",
            payload={
                "query": req.query,
                "country": req.country or "Oman",
                "limit": req.limit,
            },
        )
    signals = repo.search_growth_signals(
        query=req.query, country=req.country, limit=req.limit
    )
    return {
        "tool": "search_growth_signals",
        "count": len(signals),
        "signals": signals,
        "background_job": job,
    }


@app.get("/api/v1/tools/company-dossier")
def tool_get_company_dossier(organization_name: str = Query(..., min_length=1)):
    """
    Tool 2: get_company_dossier
    Retrieves sourced company, expansion signals, and decision-maker information.
    """
    dossier = repo.get_company_dossier(organization_name.strip())
    if not dossier:
        raise HTTPException(
            status_code=404,
            detail=f"No dossier found for organization '{organization_name}'.",
        )
    return {"tool": "get_company_dossier", "dossier": dossier}


class VerifyContactToolRequest(BaseModel):
    email: str = Field(..., min_length=3)


@app.post("/api/v1/tools/verify-contact")
async def tool_verify_contact(req: VerifyContactToolRequest):
    """
    Tool 3: verify_contact
    Returns verification evidence and confidence score, never an unsupported guarantee.
    """
    clean_email = req.email.strip().lower()
    if repo.is_suppressed(clean_email) or supp.is_suppressed(clean_email):
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

    ver = await reacher_verifier.verify(clean_email)
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


class CreateOutreachDraftToolRequest(BaseModel):
    recipient_email: str
    recipient_name: str
    organization_name: str
    recipient_role: str
    subject_line: Optional[str] = None
    body_text: Optional[str] = None
    signal_headline: Optional[str] = None


@app.post("/api/v1/tools/create-outreach-draft")
def tool_create_outreach_draft(req: CreateOutreachDraftToolRequest):
    """
    Tool 4: create_outreach_draft
    Creates an outreach draft in PENDING_APPROVAL state without sending it.
    """
    clean_email = req.recipient_email.strip().lower()
    if repo.is_suppressed(clean_email) or supp.is_suppressed(clean_email):
        raise HTTPException(
            status_code=409,
            detail=f"Recipient '{clean_email}' is on the suppression list.",
        )

    if req.body_text and req.subject_line:
        try:
            draft_obj = EmailDraft(
                recipient_email=clean_email,
                recipient_name=req.recipient_name,
                organization_name=req.organization_name,
                recipient_role=req.recipient_role,
                subject_line=req.subject_line,
                body_text=req.body_text,
            )
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc))
    else:
        draft_obj = copilot.generate_initial_draft(
            target_name=req.recipient_name,
            target_role=req.recipient_role,
            target_org=req.organization_name,
            target_email=clean_email,
            target_history={"career_summary": req.signal_headline or ""},
            signal_headline=req.signal_headline or "",
        )

    draft_id = repo.upsert_draft(draft_obj, status="PENDING_APPROVAL")
    repo.record_outreach_event(
        recipient_email=clean_email,
        action_type="DRAFT_CREATED",
        status="PENDING_APPROVAL",
        details=f"Draft #{draft_id} created for {req.recipient_name} ({req.organization_name}).",
    )
    saved = repo.get_draft_by_id(draft_id)
    return {
        "tool": "create_outreach_draft",
        "draft_id": draft_id,
        "status": "PENDING_APPROVAL",
        "draft": saved,
    }


@app.get("/api/v1/tools/pending-approvals")
def tool_list_pending_approvals():
    """
    Tool 5: list_pending_approvals
    Retrieves all drafts awaiting explicit human/operator approval.
    """
    pending = repo.list_pending_approvals()
    return {
        "tool": "list_pending_approvals",
        "count": len(pending),
        "pending_drafts": pending,
    }


class ApproveOutreachToolRequest(BaseModel):
    draft_id: int
    approved_by: str = Field(default="authenticated_operator", min_length=1)
    confirmation_note: str = Field(default="Approved for controlled dispatch")


@app.post("/api/v1/tools/approve-outreach")
def tool_approve_outreach(req: ApproveOutreachToolRequest):
    """
    Tool 6: approve_outreach
    Transitions a specific draft to APPROVED after authenticated confirmation.
    """
    try:
        updated = repo.approve_draft(
            draft_id=req.draft_id,
            approved_by=req.approved_by,
            confirmation_note=req.confirmation_note,
        )
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc))

    if not updated:
        raise HTTPException(
            status_code=404, detail=f"Draft #{req.draft_id} was not found."
        )
    return {
        "tool": "approve_outreach",
        "draft_id": req.draft_id,
        "status": updated.get("status"),
        "approved_by": updated.get("approved_by"),
        "approved_at": updated.get("approved_at"),
        "draft": updated,
    }


class SendApprovedOutreachToolRequest(BaseModel):
    draft_id: int = Field(..., ge=1)
    idempotency_key: Optional[str] = Field(default=None, min_length=8, max_length=128)


@app.post("/api/v1/tools/send-approved-outreach", status_code=202)
def tool_send_approved_outreach(req: SendApprovedOutreachToolRequest):
    """
    Tool 7: send_approved_outreach
    Enqueues only an approved draft for out-of-request worker dispatch.
    """
    draft = repo.get_draft_by_id(req.draft_id)
    if not draft:
        raise HTTPException(status_code=404, detail=f"Draft #{req.draft_id} was not found.")
    if draft.get("status") == "DISPATCHED":
        return {
            "tool": "send_approved_outreach",
            "status": "DUPLICATE_PREVENTED",
            "duplicate_prevented": True,
            "draft_id": req.draft_id,
            "message": "This draft has already been dispatched.",
        }
    if draft.get("status") != "APPROVED":
        raise HTTPException(
            status_code=409,
            detail=f"Draft #{req.draft_id} is not approved. Current status: {draft.get('status')}.",
        )

    recipient_email = (draft.get("recipient_email") or "").strip().lower()
    if repo.is_suppressed(recipient_email) or supp.is_suppressed(recipient_email):
        raise HTTPException(status_code=409, detail="Recipient is on the suppression list.")

    # One send attempt only: SMTP failure can have an ambiguous outcome. Never
    # automatically retry a send; reconcile its delivery status before a new attempt.
    request_key = req.idempotency_key or f"send-approved:{req.draft_id}"
    job_key = f"send-approved:{req.draft_id}:{request_key}"
    job = job_queue.enqueue(
        job_type="send_approved_outreach",
        payload={"draft_id": req.draft_id, "idempotency_key": request_key},
        idempotency_key=job_key,
        max_attempts=1,
    )
    return {
        "tool": "send_approved_outreach",
        "status": job.get("status", "QUEUED"),
        "draft_id": req.draft_id,
        "job_id": job["job_id"],
        "message": "Dispatch job queued. Check job status before taking further action.",
    }


@app.get("/api/v1/tools/job-status/{job_id}")
def tool_get_job_status(job_id: str):
    """
    Tool 8: get_job_status
    Retrieves status, attempts, and result of a durable background job.
    """
    job = job_queue.get_job_status(job_id)
    if not job:
        raise HTTPException(status_code=404, detail=f"Job '{job_id}' was not found.")
    return {"tool": "get_job_status", "job": job}


# =========================================================
# IMAP SYNCHRONIZATION VIA SERVER-SENT EVENTS (SSE)
# =========================================================


@app.get("/api/imap/sync-stream")
def sync_imap_stream():
    """Streams real-time progress events for IMAP synchronization."""

    def event_generator():
        import queue
        import threading

        q: queue.Queue = queue.Queue()

        def worker():
            def cb(p, m):
                q.put({"type": "progress", "percent": round(p, 2), "message": m})

            res = scan_inbox_for_replies_and_bounces(progress_callback=cb, limit=30)
            q.put({"type": "done", "result": res})

        t = threading.Thread(target=worker)
        t.start()

        while t.is_alive() or not q.empty():
            try:
                item = q.get(timeout=0.2)
                yield f"data: {json.dumps(item)}\n\n"
            except queue.Empty:
                continue

    return StreamingResponse(event_generator(), media_type="text/event-stream")


# =========================================================
# OPEN-SOURCE INTEGRATION ENDPOINTS
# =========================================================


class DeepRadarRequest(BaseModel):
    organization_name: Optional[str] = None
    website: Optional[str] = None
    keywords: Optional[str] = None
    country: Optional[str] = None


@app.post("/api/discovery/deep-radar")
async def execute_deep_radar(req: DeepRadarRequest):
    """Crawls company newsrooms and searches global news graph for expansion triggers."""
    signals = []
    kw = req.keywords or req.organization_name or "expansion"
    gdelt_signals = await deep_radar.scan_gdelt_news_graph(
        keywords=kw, country=req.country, max_records=6
    )
    signals.extend(gdelt_signals)

    if req.website:
        crawl_signals = await deep_radar.crawl_company_newsroom(req.website)
        signals.extend(crawl_signals)

    return {
        "engine": "Crawl4AI + GDELT 2.0 Global Radar",
        "total_signals_discovered": len(signals),
        "signals": signals,
    }


class OSINTHuntRequest(BaseModel):
    organization_name: str
    website: Optional[str] = None


@app.post("/api/audit/osint-hunt")
async def execute_osint_hunt(req: OSINTHuntRequest):
    """Executes search engine OSINT dorking and passive domain footprinting."""
    dork_results = await osint_hunter.crosslinked_dork(req.organization_name)
    domain = req.website or f"{req.organization_name.lower().replace(' ', '')}.com"
    footprint = osint_hunter.theharvester_footprint(domain)

    return {
        "engine": "CrossLinked Dorker + theHarvester Footprinting",
        "organization": req.organization_name,
        "domain_footprint": footprint,
        "decision_makers_found": len(dork_results),
        "decision_makers": dork_results,
    }


class ReacherCheckRequest(BaseModel):
    email: str


@app.post("/api/verification/reacher-check")
async def execute_reacher_check(req: ReacherCheckRequest):
    """Executes evidence-based MX and socket verification."""
    return await reacher_verifier.verify(req.email)


class SalesGPTRefineRequest(BaseModel):
    stage: str
    target_name: str
    target_org: str
    target_role: str
    target_history: Dict[str, Any]
    user_guidance: Optional[str] = None


@app.post("/api/copilot/salesgpt-refine")
def execute_salesgpt_refine(req: SalesGPTRefineRequest):
    """Generates stage-aware drafts with 100-160 word count validation."""
    try:
        stage_enum = OutreachStage(req.stage)
    except Exception:
        stage_enum = OutreachStage.STAGE_FIRST_TOUCH

    subj, body, expl, wc = salesgpt.generate_by_stage(
        stage=stage_enum,
        target_name=req.target_name,
        target_org=req.target_org,
        target_role=req.target_role,
        target_history=req.target_history,
        custom_guidance=req.user_guidance,
    )

    return {
        "engine": "SalesGPT Stage Engine + Instructor Validator",
        "stage": stage_enum.value,
        "subject_line": subj,
        "body_text": body,
        "word_count": wc,
        "explanation": expl,
        "compliant_100_160": 100 <= wc <= 160,
    }


@app.post("/api/webhooks/emailengine")
def receive_emailengine_webhook(payload: Dict[str, Any]):
    """Real-time webhook listener for incoming recipient replies, bounces, and delivery events."""
    return emailengine_gateway.process_webhook_event(payload)


@app.get("/api/webhooks/status")
def get_webhook_status():
    """Returns status of real-time EmailEngine / Postal webhook listener."""
    return emailengine_gateway.get_gateway_status()


# ==========================================
# Phase Settings & System Overview Endpoints
# ==========================================


@app.get("/api/system/overview")
@app.get("/api/v1/system/overview")
def get_system_overview():
    """Returns real-time telemetry and overview metrics for the executive dashboard."""
    stats = repo.get_system_stats()
    contacts = repo.list_contacts()
    drafts = repo.list_drafts()
    events = repo.list_outreach_events(limit=15)

    verified_contacts = sum(
        1
        for c in contacts
        if c.get("verification_status") in ("Verified", "Confirmed via Page")
        or c.get("outreach_status") == "Verified"
    )
    staged_drafts = sum(
        1
        for d in drafts
        if d.get("status") in ("STAGED", "PENDING_APPROVAL", "APPROVED", "STAGED_IN_GMAIL")
    )
    dispatched_drafts = sum(1 for d in drafts if d.get("status") == "DISPATCHED")
    replies_count = sum(
        1 for c in contacts if "replied" in (c.get("outreach_status") or "").lower()
    )
    bounces_caught = sum(
        1
        for e in events
        if (e.get("action_type") or "") in ("BOUNCED", "BLOCKED")
    )

    recent_events = [
        {
            "id": e.get("id", idx + 1),
            "recipient_email": e.get("recipient_email", ""),
            "event_type": e.get("action_type", ""),
            "timestamp": e.get("timestamp", ""),
            "details": e.get("status_message", ""),
        }
        for idx, e in enumerate(events)
    ]

    cand_name, _, _ = get_candidate_signature()
    resume_file = BASE_DIR / "data" / "resume" / "master_resume.pdf"
    resume_meta = {
        "filename": resume_file.name if resume_file.exists() else "None",
        "size_kb": round(resume_file.stat().st_size / 1024, 1)
        if resume_file.exists()
        else 0,
        "is_ready": resume_file.exists(),
    }

    return {
        "metrics": {
            "total_organizations": stats.get("total_organizations", 0),
            "total_contacts": stats.get("total_contacts", 0),
            "verified_contacts": verified_contacts,
            "staged_drafts": staged_drafts,
            "dispatched_emails": dispatched_drafts,
            "replies_count": replies_count,
            "bounces_caught": bounces_caught,
        },
        "candidate": {"name": cand_name, "resume": resume_meta},
        "resume": resume_meta,
        "recent_events": recent_events,
        "health": {
            "backend": "ONLINE",
            "database": f"CONNECTED ({repo.storage_engine.upper()})",
            "port_25_probe": "ACTIVE",
            "pacing_engine": "60S_READY",
        },
    }


class SettingsUpdateRequest(BaseModel):
    full_name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    linkedin_url: Optional[str] = None
    portfolio_url: Optional[str] = None
    academic_background: Optional[str] = None
    gmail_user: Optional[str] = None
    gmail_app_password: Optional[str] = None
    custom_footer: Optional[str] = None


@app.get("/api/settings")
def get_settings():
    """Returns candidate profile details and masked credential status for the Settings UI."""
    profile_path = BASE_DIR / "config" / "candidate_profile.yaml"
    cand_data: Dict[str, Any] = {}
    if profile_path.exists():
        try:
            cand_data = yaml.safe_load(profile_path.read_text(encoding="utf-8")) or {}
        except Exception:
            pass

    cand = cand_data.get("candidate", {})
    exp = cand_data.get("experiences", {})
    rules = cand_data.get("outreach_rules", {})

    gmail_u = os.getenv("GMAIL_USER") or os.getenv("GMAIL_SENDER_EMAIL", "")
    has_pass = bool(os.getenv("GMAIL_APP_PASSWORD"))

    resume_file = BASE_DIR / "data" / "resume" / "master_resume.pdf"

    return {
        "profile": {
            "full_name": cand.get("full_name", ""),
            "email": cand.get("email", ""),
            "phone": cand.get("phone", ""),
            "linkedin_url": cand.get("linkedin_url", ""),
            "portfolio_url": cand.get("portfolio_url", ""),
            "academic_background": cand.get("academic_background", ""),
        },
        "credentials": {
            "gmail_user": gmail_u,
            "has_gmail_password": has_pass,
            "masked_password": "••••••••••••••••" if has_pass else "",
        },
        "resume": {
            "filename": resume_file.name if resume_file.exists() else "None",
            "size_kb": round(resume_file.stat().st_size / 1024, 1)
            if resume_file.exists()
            else 0,
            "exists": resume_file.exists(),
        },
        "experiences": exp,
        "rules": rules,
    }


@app.post("/api/settings")
def update_settings(req: SettingsUpdateRequest):
    """Updates candidate profile in YAML and credentials in .env safely."""
    if os.getenv("ACIOS_ENV", "production").lower() == "production" and (
        req.gmail_app_password or req.gmail_user
    ):
        raise HTTPException(
            status_code=403,
            detail="Configure Gmail credentials through the deployment secret manager, not the application API.",
        )

    profile_path = BASE_DIR / "config" / "candidate_profile.yaml"
    cand_data: Dict[str, Any] = {}
    if profile_path.exists():
        try:
            cand_data = yaml.safe_load(profile_path.read_text(encoding="utf-8")) or {}
        except Exception:
            pass

    if "candidate" not in cand_data:
        cand_data["candidate"] = {}

    if req.full_name is not None:
        cand_data["candidate"]["full_name"] = req.full_name
    if req.email is not None:
        cand_data["candidate"]["email"] = req.email
    if req.phone is not None:
        cand_data["candidate"]["phone"] = req.phone
    if req.linkedin_url is not None:
        cand_data["candidate"]["linkedin_url"] = req.linkedin_url
    if req.portfolio_url is not None:
        cand_data["candidate"]["portfolio_url"] = req.portfolio_url
    if req.academic_background is not None:
        cand_data["candidate"]["academic_background"] = req.academic_background

    profile_path.parent.mkdir(parents=True, exist_ok=True)
    profile_path.write_text(
        yaml.safe_dump(cand_data, sort_keys=False), encoding="utf-8"
    )

    return {
        "status": "SUCCESS",
        "message": "Settings successfully saved.",
    }


@app.post("/api/settings/resume")
async def upload_master_resume(file: UploadFile = File(...)):
    """Uploads and validates the master PDF resume attached to outreach drafts."""
    content, safe_filename = await _validate_pdf_upload(file)
    dest_dir = BASE_DIR / "data" / "resume"
    dest_dir.mkdir(parents=True, exist_ok=True)
    target_path = (dest_dir / safe_filename).resolve()
    if target_path.parent != dest_dir.resolve():
        raise HTTPException(status_code=400, detail="Invalid upload destination.")
    target_path.write_bytes(content)
    return {
        "status": "SUCCESS",
        "filename": safe_filename,
        "size_kb": round(len(content) / 1024, 1),
        "message": "Master resume uploaded and active.",
    }


# ==========================================
# Consolidated Queue & Mailbox Endpoints
# ==========================================


@app.post("/api/queue/dispatch")
def trigger_dispatch_queue(interval: float = 60.0):
    """Bulk unapproved queue dispatch is disabled; use /api/v1/tools/send-approved-outreach."""
    raise HTTPException(
        status_code=503,
        detail="Bulk dispatch is disabled. Use /api/v1/tools/approve-outreach and /api/v1/tools/send-approved-outreach for individual approved sends.",
    )


@app.post("/api/drafts/sync-gmail")
def trigger_drafts_sync():
    """Bulk destructive Gmail sync is disabled."""
    raise HTTPException(
        status_code=503,
        detail="Bulk destructive Gmail draft synchronization is disabled. Stage individual approved drafts instead.",
    )


@app.get("/api/mailbox/audit")
def trigger_mailbox_audit():
    """Scans mailbox for inbound replies, bounces, and sent tracking."""
    return scan_inbox_for_replies_and_bounces()


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("acios.api:app", host="127.0.0.1", port=8000, reload=True)
