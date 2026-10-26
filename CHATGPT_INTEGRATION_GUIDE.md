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

## 2. Environment Variables — Set Them on the Correct Service

**Do not copy every variable into Vercel.** Vercel hosts the Next.js UI and gateway; FastAPI and the worker own the database, resume storage, and email credentials.

### A. Vercel → Project → Settings → Environment Variables

Add these to **Production**. Use separate, non-production values for Preview; do not let preview deployments access the production database or mail account.

| Variable | Value / where it comes from | Required? |
| :--- | :--- | :--- |
| `ACIOS_BACKEND_URL` | Public HTTPS base URL of the deployed FastAPI service, with no trailing slash (for example, `https://<your-api-service-domain>`). This URL does not exist until the backend is deployed. | Yes |
| `ACIOS_BACKEND_API_KEY` | A unique random secret, at least 32 characters. Set the **same value** on FastAPI and Vercel. Never expose it to browser code. | Yes |
| `ACIOS_UI_PASSWORD` | A strong, unique password of at least 20 characters for the web cockpit. | Yes |
| `ACIOS_SESSION_SECRET` | At least 32 random bytes, used to sign the HTTP-only session cookie. Do not reuse another key. | Yes |
| `ACIOS_API_KEY` | A separate random bearer token for the documented OpenAPI Actions routes. Put the same token in the ChatGPT Actions authentication configuration. | Only for OpenAPI Actions |
| `ACIOS_MCP_BEARER_TOKEN` | A separate random bearer token for MCP clients that explicitly support bearer-token authentication. | Only for static-token MCP clients |

Keep every variable server-side. **Never** name these `NEXT_PUBLIC_*`. The app reads them at runtime, but after changing Vercel variables you must redeploy the project for the deployment to use the new values.

The API key is now restricted to the documented `/api/v1/tools/*` action routes. The UI session is used for the web cockpit. MCP has its own token and backend-service token; these three credentials must remain different.

### B. FastAPI backend service

Configure these in the backend host's environment/secret manager:

| Variable | Value / rule |
| :--- | :--- |
| `ACIOS_BACKEND_API_KEY` | Exact same value as the Vercel variable with this name. |
| `ACIOS_ENV` | `production` |
| `MONGODB_URI` | MongoDB Atlas connection string; grant least-privilege access to the ACIOS database only. |
| `MONGODB_DB_NAME` | For example, `acios_production`. |
| `RESUME_STORAGE_BACKEND` | Use `s3` when API and worker are separate services. `local` is for development or deployments where both processes truly share the same private persistent volume. |
| `RESUME_STORAGE_BUCKET` | Name of a **private** S3-compatible bucket for the master resume. |
| `RESUME_STORAGE_REGION` | Region configured for the bucket, commonly `us-east-1` for S3-compatible services. |
| `RESUME_STORAGE_ENDPOINT_URL` | Optional S3-compatible endpoint (for example, the provider's R2 endpoint). Leave blank for AWS S3. |
| `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY` | Credentials restricted to reading/writing this bucket only; inject through the secret manager, not Git. Prefer a hosting identity/role when the provider supports it. |
| `GMAIL_USER` or `GMAIL_SENDER_EMAIL` | Your authenticated sender address. |
| `GMAIL_APP_PASSWORD` | Gmail app password, if using the current SMTP transport. Never send this through the settings API. |
| `GEMINI_API_KEY` | Optional Google Gemini API key for AI-assisted drafting; set it on the backend only. The current implementation uses the Google GenAI Python SDK. |
| `DRY_RUN` | Keep `true` until all connection and worker tests pass. For live sending, set to `false` on **both** backend and worker only after explicit readiness checks. |
| `REDIS_URL` | Optional Redis URL for worker wake-up notifications. MongoDB job records remain the durable source of truth; the worker can fall back to polling. |

Optional provider variables such as `FIRECRAWL_API_KEY` and `REACHER_API_KEY` belong on the backend/worker only if those integrations are enabled. If `GEMINI_API_KEY` is not configured, the code falls back to a deterministic profile-grounded drafting path. `ACIOS_ALLOWED_ORIGINS` is not required for the normal server-to-server Vercel proxy flow; keep direct browser CORS disabled unless you deliberately expose an API origin to a browser.

### C. Worker service

The worker must use the same `MONGODB_URI`, `MONGODB_DB_NAME`, resume-storage settings and S3 credentials, Gmail sender credentials, and `DRY_RUN` value as the backend. Deploy it as a separate long-running process with command:

```bash
python -m acios.worker
```

The worker and API must be able to read the same private resume. In production, use the configured private S3-compatible storage rather than assuming separate containers share local files. Keep `DRY_RUN=true` until the worker can retrieve the resume and a test job completes without sending a live message.

### D. Generate strong secrets

Generate a **different** random value for each secret; never reuse one value for backend, UI, OpenAPI, and MCP authentication. For example, run this locally once per secret:

```bash
python -c "import secrets; print(secrets.token_urlsafe(48))"
```

For `ACIOS_SESSION_SECRET`, the same command produces more than the required 32 characters. Save secrets directly into the relevant provider's secret manager and password manager; do not commit them, paste them into source files, or put them in a `NEXT_PUBLIC_*` variable.

### E. ChatGPT connection compatibility

- **OpenAPI Actions:** use `https://<your-vercel-domain>/api/openapi.json` as the schema URL and configure HTTP Bearer authentication with the Vercel `ACIOS_API_KEY`. Only the action routes in the spec should be exposed.
- **Remote MCP:** use `https://<your-vercel-domain>/api/mcp` only with an MCP client/account plan that supports the required custom-server authentication method. This implementation uses a static bearer token; it does **not** implement an OAuth authorization server. If your ChatGPT connection flow requires OAuth, setting `ACIOS_MCP_BEARER_TOKEN` alone will not make it work—OAuth must be implemented and configured separately.
- Test read-only discovery first. The approval action stays in the signed-in cockpit. Keep live worker dispatch disabled until the backend, private resume storage, and worker checks pass. Never use a production email sender for a first test.


---

## 3. Narrow Authorized ChatGPT & MCP Tool Surface

The Vercel MCP gateway and OpenAPI Actions expose the following operational tools:

1. `search_growth_signals` — Read sourced company expansion and hiring signals; optionally enqueue a discovery job.
2. `get_company_dossier` — Retrieve sourced company, signal, and decision-maker records.
3. `verify_contact` — Return syntax, DNS/MX and SMTP-banner evidence without claiming that a mailbox is guaranteed to exist.
4. `create_outreach_draft` — Create a draft in `PENDING_APPROVAL` without sending an email.
5. `list_pending_approvals` — Inspect drafts that need the operator's review.
6. `send_approved_outreach` — Queue a draft only if its status is already `APPROVED`; the worker performs the SMTP operation.
7. `get_job_status` — Inspect a queued or completed background task.

The gateway also exposes read-only overview and stats tools for compatible MCP clients.

**Approval is intentionally not an MCP/OpenAPI tool.** The operator must approve/edit the draft in the authenticated web cockpit; this writes the approver and timestamp to the audit trail. ChatGPT's API or MCP bearer token cannot approve a draft for the operator. A send tool can queue only a draft that has already been approved, and one dispatch attempt is allowed per job. If SMTP delivery is ambiguous, the job is failed and the lock changes to `REQUIRES_RECONCILIATION`; reconcile the mailbox before any manual retry.

### Tool permissions

| Surface | Allowed role |
| :--- | :--- |
| OpenAPI Actions bearer token | Discovery, verification, draft creation, listing pending approvals, job status, and queueing already-approved drafts |
| MCP bearer token | The corresponding narrow tools plus read-only telemetry |
| Signed-in cockpit session | Edit profile, review/approve drafts, upload the master resume, and operate cockpit workflows |
| Backend service token | Server-to-server calls only; never provide this token to ChatGPT or browser JavaScript |


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
