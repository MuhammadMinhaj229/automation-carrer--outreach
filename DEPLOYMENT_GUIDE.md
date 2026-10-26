# ACIOS Secure Deployment Runbook

This is the deployment order for the current architecture. Do not add placeholder values as if they were working credentials.

## Target topology

- **Vercel:** Next.js UI, login/session, same-origin API proxy, OpenAPI schema, current bearer-token MCP adapter.
- **Persistent backend service:** FastAPI from the repository root Dockerfile. Must have a stable HTTPS URL and must not be publicly useful without `ACIOS_BACKEND_API_KEY`.
- **Database:** MongoDB Atlas for production persistence. Do not use the repository's local SQLite file in a multi-instance deployment.
- **Worker:** A separate long-running service using the same image and environment as the backend, with command `python -m acios.worker`.
- **Queue:** MongoDB durable job records are the source of truth. Redis is currently an optional wake-up mechanism, not a replacement for the durable job records.
- **Files:** Private object storage for resumes when the API and worker run on separate hosts. Do not commit resumes or mount local laptop folders in production.

## Before deployment

1. Keep the repository private while cleaning history. Removing a file from the current branch does not remove it from old commits, forks, clones, caches, or downloaded artifacts.
2. Rotate any real passwords, app passwords, API keys, and tokens that were ever committed or otherwise exposed.
3. Merge the security PR only after its checks pass and the final diff has been reviewed.
4. Provision MongoDB Atlas, the persistent FastAPI service, and a separate worker. Do not enable live email dispatch during initial smoke tests.
5. Set the backend's `ACIOS_ENV=production` and `MONGODB_URI`. Use a dedicated least-privilege MongoDB database user and restrict Atlas network access to the backend/worker's known egress where feasible.
6. Confirm the backend's public URL is HTTPS and its `GET /healthz` endpoint returns healthy status. Health checks intentionally do not require the service key; all other routes must.

## Vercel environment variables

Open **Vercel → Project → Settings → Environment Variables** for project `automation-carrer-outreach`. Add the following server-side variables. Do not prefix any of them with `NEXT_PUBLIC_`.

| Key | Value | Target | Notes |
| --- | --- | --- | --- |
| `ACIOS_BACKEND_URL` | Your deployed FastAPI HTTPS base URL, e.g. `https://your-api-service.example.com` | Production; Preview only if a separate preview backend exists | No trailing slash. Do not use localhost in Vercel. |
| `ACIOS_BACKEND_API_KEY` | A random secret of at least 32 characters | Production; Preview only with the matching preview backend secret | Must match the backend service's `ACIOS_BACKEND_API_KEY` exactly. Use a different key for preview. |
| `ACIOS_UI_PASSWORD` | A unique strong workspace password, at least 20 characters | Production; Preview only if preview access is intentionally enabled | This is the password for the private UI login. |
| `ACIOS_SESSION_SECRET` | A cryptographically random secret, at least 32 characters | Production; Preview only with a different secret | Signs the HttpOnly session cookie. Rotate by invalidating existing sessions. |
| `ACIOS_API_KEY` | A separate random secret of at least 32 characters | Production; Preview only with a different secret | Bearer credential for the explicitly allowlisted OpenAPI Actions endpoints. Never reuse the backend key. |

Set each value as **Sensitive/Encrypted** if Vercel offers that type. Assign Production and Preview separately. Do not share production backend credentials with preview deployments.

### Generate secrets locally

Run these commands on your own computer. Keep the output in a password manager; do not paste real secrets into Git, code, screenshots, or public issue comments.

```bash
# Generate a distinct secret for each purpose
openssl rand -hex 32  # ACIOS_BACKEND_API_KEY
openssl rand -hex 32  # ACIOS_API_KEY
openssl rand -hex 32  # ACIOS_SESSION_SECRET
openssl rand -hex 32  # ACIOS_MCP_BEARER_TOKEN, only for compatible MCP clients
```

Create a strong, unique human-entered password for `ACIOS_UI_PASSWORD`; do not reuse an account password. Paste the backend key into both the backend provider's secret settings and Vercel's `ACIOS_BACKEND_API_KEY`. All other keys should be unique.

## Backend environment variables

Configure these on both the FastAPI service and worker (the worker needs the same data and job credentials). Never set them in the Vercel frontend unless specifically listed in the Vercel table above.

| Key | Required? | Purpose |
| --- | --- | --- |
| `ACIOS_BACKEND_API_KEY` | Yes | Same service key configured in Vercel. |
| `ACIOS_ENV` | Yes | Set to `production`; prevents silent SQLite fallback. |
| `MONGODB_URI` | Yes | MongoDB Atlas connection string, stored as a secret. |
| `MONGODB_DB_NAME` | Recommended | Use a dedicated database name such as `acios_production`. |
| `ACIOS_ALLOWED_ORIGINS` | Optional | Only exact trusted origins if a browser must call the API directly. The Vercel BFF does not require browser-to-backend CORS. |
| `DRY_RUN` | Yes initially | Set to `true` during deployment and acceptance tests. Do not switch to `false` until a human-approved end-to-end send has been validated. |
| `RESUME_STORAGE_BACKEND` | Yes for separate API/worker hosts | Configure the repository-supported private shared/object-storage backend and its credentials. A local filesystem is not shared or durable across independent ephemeral services. |
| `REDIS_URL` | Optional | Redis can wake the worker; MongoDB job records remain durable. Confirm the worker's queue behavior before relying on Redis operationally. |
| `GMAIL_SENDER_EMAIL` | Only if live SMTP is approved | Sender account, stored only in the backend/worker secret manager. |
| `GMAIL_APP_PASSWORD` | Only if live SMTP is approved | Gmail app password; never put it in Vercel. Prefer OAuth before a wider production rollout. |
| `FIRECRAWL_API_KEY` | Optional | Only if the discovery integration is enabled. Store on backend/worker only. |
| `REACHER_API_KEY` | Optional | Only if using the configured verification provider. Store on backend only. |

Do not configure Gmail credentials until database persistence, private resume storage, worker recovery, suppression checks, approval, and audit logging have passed tests.

## MCP and ChatGPT connection

- `ACIOS_MCP_BEARER_TOKEN` protects the repository's current bearer-token MCP adapter for compatible clients. If you use it, generate a separate token and keep it server-side.
- **Do not assume that this bearer-token adapter is a production-ready ChatGPT custom remote MCP connection.** The repository does not implement the OAuth 2.1 authorization flow required for that integration. Implement and configure OAuth with an appropriate identity provider before exposing it to ChatGPT as a remote MCP server.
- For an OpenAPI Actions connection, use `/api/openapi.json` and configure bearer authentication with `ACIOS_API_KEY`. The code allowlists specific versioned tool routes; test that the key cannot access settings, mailbox, profile, or legacy dispatch endpoints.
- Start with read-only tools. Keep draft creation as pending approval, and require an explicit signed-in operator approval before sending.

## Post-deployment smoke tests

1. Open the Vercel production URL and confirm the login page loads.
2. Sign in with `ACIOS_UI_PASSWORD`; verify a valid session is issued and logout invalidates it.
3. Request a backend API route without credentials directly; expect `401`. If the key is unconfigured, expect `503`. The public health endpoint is the only intentional exception.
4. From the authenticated UI, check system stats and the backend status. A Vercel `502` means the backend URL, TLS, networking, or backend service needs investigation; a `503` means required backend configuration is missing.
5. Verify a wrong `ACIOS_API_KEY` is rejected and a valid one only reaches the documented `/api/v1/tools/*` allowlist.
6. Verify unauthenticated MCP requests are rejected. Do not call the send tool against live credentials during smoke testing.
7. Create a test draft, confirm it is pending approval, approve it manually, and test a dry-run send. Confirm the draft remains `APPROVED`, no real email is sent, and no dispatch lock is created in dry-run.
8. Confirm a queued job is processed by the separate worker and that the job status endpoint updates.
9. Check production and preview environment scopes separately. Redeploy after changing environment variables; existing deployments do not automatically inherit new values.
10. Keep live SMTP disabled until the full acceptance checklist has passed.
