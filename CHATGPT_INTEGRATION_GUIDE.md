# ACIOS Integration and Deployment Guide

This guide describes the production architecture, security boundaries, and exact steps for connecting ChatGPT (via OpenAPI Actions or Authenticated MCP) to ACIOS.

## 1. Production Architecture

```
ChatGPT / MCP Client (Research · Drafting · Approved Actions)
        │
        ▼
Authenticated MCP Gateway & OpenAPI BFF (Vercel Next.js: /api/mcp, /api/openapi.json)
        │
        ▼
FastAPI Application (Persistent Container Service: Business Logic, Validation, /api/v1/tools/*)
        ├──► MongoDB Atlas (Persistent Records: organizations, signals, contacts, dossiers, drafts, dispatch_locks, jobs)
        ├──► Redis + Durable Worker (`python -m acios.worker`: Retries, Long-Running Scans, Controlled Dispatch)
        └──► Email Integration (Gmail OAuth / App Password with Approval & Idempotency Locks)
```

| Component | Recommendation | Purpose |
| :--- | :--- | :--- |
| **Frontend & Gateway** | Vercel + Next.js (`web/`) | Web cockpit, session auth, OpenAPI schema, and MCP tool gateway |
| **API** | FastAPI (`acios.api:app`) | Python intelligence, input validation, and versioned `/api/v1/*` endpoints |
| **Database** | MongoDB Atlas (`MONGODB_URI`) | Persistent storage for companies, contacts, dossiers, drafts, approvals, and job state (SQLite supported for local dev) |
| **Background Jobs** | Redis (`REDIS_URL`) + `acios.worker` | Durable job processing, retries, dead-letter tracking, and controlled email dispatch |
| **File Storage** | Private object storage / volume | Validated PDF resumes (`%PDF-` signature, <= 10 MB) |
| **AI Connection** | Authenticated MCP / OpenAPI | 8 narrow, explicitly authorized tools |

---

## 2. Environment Variables

Configure these only in local `.env` (git-ignored) or your cloud provider's secret manager. Never commit `.env` or prefix backend keys with `NEXT_PUBLIC_`.

- `ACIOS_BACKEND_URL`: HTTPS URL of the deployed FastAPI service.
- `ACIOS_BACKEND_API_KEY`: Shared service secret (minimum 32 random characters) required on all FastAPI endpoints except `GET /healthz` and `GET /api/v1/healthz`.
- `MONGODB_URI`: MongoDB Atlas connection string (`mongodb+srv://...`). When omitted locally, ACIOS falls back to local SQLite (`data/career_os.db`).
- `MONGODB_DB_NAME`: Database name in MongoDB Atlas (default: `acios`).
- `REDIS_URL`: Redis connection string (`redis://...` or `rediss://...`) for durable worker notifications.
- `ACIOS_UI_PASSWORD`: High-entropy password for the Next.js web cockpit.
- `ACIOS_SESSION_SECRET`: Minimum 32 random characters for HMAC-SHA256 signed HTTP-only session cookies.
- `ACIOS_API_KEY`: Independent Bearer token for ChatGPT OpenAPI Actions.
- `ACIOS_MCP_BEARER_TOKEN`: Independent Bearer token for authenticated MCP clients.
- `GMAIL_USER` and `GMAIL_APP_PASSWORD`: Configured only on the backend/worker when controlled email sending is enabled.

---

## 3. Narrow Authorized ChatGPT & MCP Tool Surface

Both the MCP server (`acios/mcp_server.py` and `/api/mcp`) and the OpenAPI specification (`/api/openapi.json` -> `/api/v1/tools/*`) expose 8 narrow, validated tools:

1. `search_growth_signals` — Query sourced company expansion, funding, and hiring signals from the database.
2. `get_company_dossier` — Retrieve a company's sourced signals, contacts, and outreach drafts.
3. `verify_contact` — Run evidence-based syntax, DNS MX, and non-intrusive SMTP banner checks without fabricating deliverability guarantees.
4. `create_outreach_draft` — Stage an outreach draft in `PENDING_APPROVAL` status without sending any email.
5. `list_pending_approvals` — List all drafts currently in `PENDING_APPROVAL` status awaiting human confirmation.
6. `approve_outreach` — Record explicit authenticated approval (`APPROVED`) with approver identity, note, and timestamp.
7. `send_approved_outreach` — Enqueue or dispatch only a previously `APPROVED` draft, protected by atomic `dispatch_locks` to prevent duplicate sends.
8. `get_job_status` — Inspect the state (`QUEUED`, `RUNNING`, `SUCCEEDED`, `RETRYING`, `DEAD_LETTER`), attempts, and result payload of a background job.

---

## 4. Local Development & Verification

1. Copy `.env.example` to `.env` and populate secrets (minimum 32 characters for `ACIOS_BACKEND_API_KEY` and `ACIOS_SESSION_SECRET`).
2. Copy `config/candidate_profile.example.yaml` to `config/candidate_profile.yaml` (git-ignored) and customize locally.
3. Install Python dependencies:
   ```bash
   pip install -r requirements.txt
   ```
4. Start the FastAPI backend and durable worker:
   ```bash
   python -m uvicorn acios.api:app --host 127.0.0.1 --port 8000
   python -m acios.worker
   ```
5. Start the Next.js cockpit:
   ```bash
   cd web && npm ci && npm run dev
   ```
6. Run the security and integration test suite:
   ```bash
   pytest -v
   ```
