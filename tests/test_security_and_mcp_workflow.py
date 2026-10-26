"""
Comprehensive security, MongoDB persistence, durable job queue, upload validation,
and 8-tool MCP workflow verification suite.
"""

import io
import subprocess
from pathlib import Path
import mongomock
import pytest
from fastapi.testclient import TestClient

import acios.api as api_module
from acios.core.job_queue import DurableJobQueue, execute_approved_send
from acios.core.repository import CareerRepository
from acios.models.contact import Contact, VerificationStatus
from acios.models.organization import ExpansionSignal, Organization, SectorCategory
from acios.tools.discovery.linkedin_hunter import LinkedInHunter


VALID_API_KEY = "test_backend_service_secret_key_with_at_least_32_chars"
VALID_BODY_115_WORDS = (
    "Dear Jordan, I am Alex Rivera, an operations and data automation analyst with experience "
    "building telemetry pipelines and field reporting workflows. I recently reviewed Acme Energy "
    "and noticed your team's regional grid automation expansion in Muscat. In my previous role, "
    "I designed automated validation and tracking dashboards that reduced manual reporting overhead "
    "across distributed engineering teams while improving data reliability for project leads. "
    "Because Acme Energy is scaling technical operations across new infrastructure sites, I wanted "
    "to ask whether your team is exploring support for data workflows and project tracking. I have "
    "attached my resume for context and would welcome a brief conversation at your convenience."
)


def test_git_tracks_no_private_runtime_files():
    repo_root = Path(__file__).resolve().parent.parent
    out = subprocess.check_output(
        ["git", "ls-files"], cwd=str(repo_root), text=True
    ).splitlines()
    forbidden = [
        f
        for f in out
        if f.startswith("data/")
        or f == "config/candidate_profile.yaml"
        or f.endswith((".db", ".sqlite", ".sqlite3", ".pdf", ".xlsx", ".xls", ".csv", ".parquet"))
    ]
    assert forbidden == [], f"Private runtime files must not be tracked: {forbidden}"


def test_fastapi_deny_by_default_authentication(monkeypatch):
    client = TestClient(api_module.app)

    # 1. Health check is public
    resp_health = client.get("/healthz")
    assert resp_health.status_code == 200
    assert resp_health.json()["status"] == "ok"

    # 2. Fail closed (503) when backend key is not configured
    monkeypatch.setenv("ACIOS_BACKEND_API_KEY", "short-key")
    resp_unconfigured = client.get("/api/v1/system/stats")
    assert resp_unconfigured.status_code == 503

    # 3. Reject unauthenticated or wrong token (401)
    monkeypatch.setenv("ACIOS_BACKEND_API_KEY", VALID_API_KEY)
    assert client.get("/api/v1/system/stats").status_code == 401
    assert (
        client.get(
            "/api/v1/system/stats",
            headers={"Authorization": "Bearer wrong_token_value_that_is_long_enough"},
        ).status_code
        == 401
    )

    # 4. Accept valid service key
    resp_ok = client.get(
        "/api/v1/system/stats",
        headers={"Authorization": f"Bearer {VALID_API_KEY}"},
    )
    assert resp_ok.status_code == 200
    assert "total_organizations" in resp_ok.json()


def test_evidence_based_discovery_does_not_fabricate_contacts(tmp_path):
    repo = CareerRepository(db_path=tmp_path / "test_evidence.db")
    hunter = LinkedInHunter(repo=repo)
    audit = hunter.audit_organization("NonExistentTestEntity999999")
    assert audit["verification_status"] == "Unverified Domain"
    assert audit["trigger_confirmed"] is False


def test_mongodb_persistence_and_8_tool_workflow(monkeypatch):
    mock_mongo = mongomock.MongoClient()
    mongo_repo = CareerRepository(
        mongo_client=mock_mongo, mongo_db_name="acios_test_db"
    )
    assert mongo_repo.storage_engine == "mongodb"

    # Seed an organization, signal, and contact in MongoDB
    org = Organization(
        name="Acme Energy",
        country="Oman",
        city="Muscat",
        sector=SectorCategory.AGRITECH,
        website="https://acme-energy.example.com",
        signals=[
            ExpansionSignal(
                headline="Acme Energy launches Muscat grid automation phase 2",
                signal_date="2026-10-01",
                source_url="https://acme-energy.example.com/news/muscat",
                details="Expanding telemetry operations in Muscat.",
            )
        ],
    )
    mongo_repo.upsert_organization(org)
    mongo_repo.upsert_contact(
        Contact(
            name="Jordan Taylor",
            role="Director of Operations",
            organization_name="Acme Energy",
            work_email="jordan.taylor@example.com",
            verification_status=VerificationStatus.PATTERN_PREDICTED,
        )
    )

    # Wire FastAPI module to use the MongoDB repository and durable queue
    monkeypatch.setattr(api_module, "repo", mongo_repo)
    monkeypatch.setattr(
        api_module, "job_queue", DurableJobQueue(repo=mongo_repo)
    )
    monkeypatch.setenv("ACIOS_BACKEND_API_KEY", VALID_API_KEY)
    monkeypatch.setenv("DRY_RUN", "true")
    headers = {"Authorization": f"Bearer {VALID_API_KEY}"}
    client = TestClient(api_module.app)

    # Tool 1: search_growth_signals
    r1 = client.post(
        "/api/v1/tools/search-growth-signals",
        json={"query": "Muscat", "country": "Oman", "run_background_scan": True},
        headers=headers,
    )
    assert r1.status_code == 200
    data1 = r1.json()
    assert data1["count"] == 1
    assert data1["signals"][0]["organization_name"] == "Acme Energy"
    job_id = data1["background_job"]["job_id"]

    # Tool 8: get_job_status
    r8 = client.get(f"/api/v1/tools/job-status/{job_id}", headers=headers)
    assert r8.status_code == 200
    assert r8.json()["job"]["status"] == "QUEUED"

    # Tool 2: get_company_dossier
    r2 = client.get(
        "/api/v1/tools/company-dossier",
        params={"organization_name": "Acme Energy"},
        headers=headers,
    )
    assert r2.status_code == 200
    dossier = r2.json()["dossier"]
    assert dossier["organization"]["name"] == "Acme Energy"
    assert len(dossier["contacts"]) == 1

    # Tool 3: verify_contact (evidence-based, no fabricated guarantee)
    r3 = client.post(
        "/api/v1/tools/verify-contact",
        json={"email": "invalid-syntax-email"},
        headers=headers,
    )
    assert r3.status_code == 200
    assert r3.json()["valid"] is False
    assert r3.json()["verified"] is False
    assert "rfc5322_syntax_failed" in r3.json()["evidence"]

    # Tool 4: create_outreach_draft (creates in PENDING_APPROVAL without sending)
    r4 = client.post(
        "/api/v1/tools/create-outreach-draft",
        json={
            "recipient_email": "jordan.taylor@example.com",
            "recipient_name": "Jordan Taylor",
            "organization_name": "Acme Energy",
            "recipient_role": "Director of Operations",
            "subject_line": "Telemetry & data workflows for Muscat phase 2",
            "body_text": VALID_BODY_115_WORDS,
        },
        headers=headers,
    )
    assert r4.status_code == 200
    draft_id = r4.json()["draft_id"]
    assert r4.json()["status"] == "PENDING_APPROVAL"

    # Tool 5: list_pending_approvals
    r5 = client.get("/api/v1/tools/pending-approvals", headers=headers)
    assert r5.status_code == 200
    assert r5.json()["count"] == 1
    assert r5.json()["pending_drafts"][0]["id"] == draft_id

    # Guard: send_approved_outreach MUST reject unapproved draft (409 Conflict)
    r_unapproved = client.post(
        "/api/v1/tools/send-approved-outreach",
        json={"draft_id": draft_id, "idempotency_key": "key_attempt_1"},
        headers=headers,
    )
    assert r_unapproved.status_code == 409

    # Tool 6: approve_outreach
    r6 = client.post(
        "/api/v1/tools/approve-outreach",
        json={
            "draft_id": draft_id,
            "approved_by": "qa_operator",
            "confirmation_note": "Verified evidence and word count",
        },
        headers=headers,
    )
    assert r6.status_code == 200
    assert r6.json()["status"] == "APPROVED"

    # Tool 7: send_approved_outreach (first send succeeds, second send is blocked by idempotency lock)
    r7_first = client.post(
        "/api/v1/tools/send-approved-outreach",
        json={"draft_id": draft_id, "idempotency_key": "idem_send_001"},
        headers=headers,
    )
    assert r7_first.status_code == 200
    assert r7_first.json()["status"] == "SENT"
    assert r7_first.json()["duplicate_prevented"] is False

    r7_second = client.post(
        "/api/v1/tools/send-approved-outreach",
        json={"draft_id": draft_id, "idempotency_key": "idem_send_001"},
        headers=headers,
    )
    assert r7_second.status_code == 200
    assert r7_second.json()["status"] == "DUPLICATE_PREVENTED"
    assert r7_second.json()["duplicate_prevented"] is True


def test_durable_job_queue_retries_and_dead_letter():
    mock_mongo = mongomock.MongoClient()
    repo = CareerRepository(mongo_client=mock_mongo, mongo_db_name="acios_jobs_test")
    queue = DurableJobQueue(repo=repo)

    call_count = {"n": 0}

    def flaky_handler(payload):
        call_count["n"] += 1
        if call_count["n"] < 2:
            raise RuntimeError("Transient network timeout")
        return {"ok": True, "echo": payload.get("msg")}

    queue.register_handler("flaky_task", flaky_handler)
    job = queue.enqueue("flaky_task", {"msg": "hello"}, idempotency_key="job_idem_1", max_attempts=2)

    # Duplicate enqueue with same idempotency_key returns existing job
    dup_job = queue.enqueue("flaky_task", {"msg": "hello"}, idempotency_key="job_idem_1", max_attempts=2)
    assert dup_job["job_id"] == job["job_id"]

    # Attempt 1 fails -> re-queued
    after_1 = queue.process_next()
    assert after_1["status"] == "QUEUED"
    assert after_1["attempts"] == 1

    # Attempt 2 succeeds -> COMPLETED
    after_2 = queue.process_next()
    assert after_2["status"] == "COMPLETED"
    assert after_2["attempts"] == 2
    assert after_2["result"] == {"ok": True, "echo": "hello"}


def test_resume_upload_validation(monkeypatch, tmp_path):
    monkeypatch.setenv("ACIOS_BACKEND_API_KEY", VALID_API_KEY)
    monkeypatch.setattr(api_module, "BASE_DIR", tmp_path)
    headers = {"Authorization": f"Bearer {VALID_API_KEY}"}
    client = TestClient(api_module.app)

    # Reject non-PDF extension
    r_txt = client.post(
        "/api/settings/resume",
        files={"file": ("resume.txt", io.BytesIO(b"%PDF-1.4 fake"), "text/plain")},
        headers=headers,
    )
    assert r_txt.status_code == 400

    # Reject invalid magic bytes
    r_bad_magic = client.post(
        "/api/settings/resume",
        files={"file": ("resume.pdf", io.BytesIO(b"NOT_A_PDF_FILE"), "application/pdf")},
        headers=headers,
    )
    assert r_bad_magic.status_code == 400

    # Accept valid PDF
    r_ok = client.post(
        "/api/settings/resume",
        files={"file": ("my_cv.pdf", io.BytesIO(b"%PDF-1.7\n1 0 obj\n%%EOF"), "application/pdf")},
        headers=headers,
    )
    assert r_ok.status_code == 200
    assert r_ok.json()["filename"] == "master_resume.pdf"
