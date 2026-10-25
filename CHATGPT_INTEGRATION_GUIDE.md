# ACIOS Integration and Deployment Guide

This guide describes the supported application boundaries and the steps required before connecting an external AI client.

## Production architecture

- **Next.js cockpit:** Vercel. Serves the UI, session login, same-origin API proxy, and OpenAPI schema.
- **FastAPI application:** persistent container service on Railway, Render, Fly.io, or Cloud Run. Holds business logic and requires `ACIOS_BACKEND_API_KEY` on all routes except `GET /healthz`.
- **Worker:** a separate, continuously running process for scheduled discovery, inbox synchronisation, retries, and slow email dispatch. Do not rely on a serverless request/thread to finish a long-running job.
- **Database:** PostgreSQL for production. SQLite is local-development-only unless using a persistent, single-writer volume.
- **Queue:** Redis-backed durable job queue (or managed equivalent) for retries, status transitions, and idempotent dispatch.
- **Files:** private object storage for resume documents. Credentials belong in each provider's secret manager, never in Git or the browser.
- **MCP:** authenticated, least-privilege tool surface. Start with read/search and draft preparation. Sending an email remains a separate, explicitly approved action.

MongoDB is not a backend by itself. It can store the records, but ACIOS also requires an API service, a durable worker, a queue, persistent file storage, and secret management. PostgreSQL is the recommended production store because records are relational and dispatch state must be auditable and transaction-safe.

## Environment variables

Configure these only in trusted local environment files or provider secret managers. Generate different random values for each setting.

- `ACIOS_BACKEND_URL`: HTTPS URL of the deployed FastAPI service.
- `ACIOS_BACKEND_API_KEY`: shared service secret used only by Next.js server routes and FastAPI.
- `ACIOS_UI_PASSWORD`: unique password for the private cockpit.
- `ACIOS_SESSION_SECRET`: at least 32 random characters for signed, HTTP-only sessions.
- `ACIOS_API_KEY`: token for OpenAPI Action requests.
- `ACIOS_MCP_BEARER_TOKEN`: separate token for compatible MCP clients that support bearer auth.
- `GMAIL_USER` and `GMAIL_APP_PASSWORD`: set only when email is enabled.
- `DATABASE_URL`: production PostgreSQL connection string when the database migration is implemented.

Keep production and preview environment values separate. Do not set fake secrets or enable email sending on untrusted preview deployments.

## Local development

1. Copy `.env.example` to `.env` and replace all placeholders with random values.
2. Configure `config/candidate_profile.yaml` locally. That file is intentionally git-ignored.
3. Install Python dependencies from `requirements.txt`.
4. Install frontend dependencies with `cd web && npm ci`.
5. Run FastAPI with `python -m uvicorn acios.api:app --host 127.0.0.1 --port 8000` and the web UI with `cd web && npm run dev`.
6. Confirm that `GET /healthz` is reachable, but authenticated application routes reject requests with no backend service token.

## Vercel + backend configuration

1. Deploy `web/` as the Vercel project root.
2. Deploy the FastAPI application as a persistent container service and set `ACIOS_BACKEND_API_KEY` in that service.
3. Add the same backend key and the HTTPS backend URL to Vercel's server-side environment variables. Do not prefix these values with `NEXT_PUBLIC_`.
4. Set `ACIOS_UI_PASSWORD` and `ACIOS_SESSION_SECRET` in Vercel. Use a high-entropy password and a unique 32+ character secret.
5. Configure PostgreSQL, durable queue, private resume storage, and a worker before treating the app as production-ready.
6. Test unauthenticated API calls, signed-in UI requests, file upload limits, and dispatch approval gates against a staging environment.

## OpenAPI Action connection

The schema is served at `/api/openapi.json`. Configure the action to use Bearer API-token authentication with the independently generated `ACIOS_API_KEY`. The API token is not the backend service key.

Restrict actions to the minimum tools needed. Keep data-reading actions distinct from writes. Do not expose database downloads or credential updates to external agents without a separate explicit policy and tests.

## ChatGPT custom MCP

The current web adapter is protected by `ACIOS_MCP_BEARER_TOKEN` for MCP clients that support bearer tokens. **That is not yet a complete OAuth 2.1 integration for ChatGPT custom remote MCP connections.** ChatGPT's current custom-MCP flow expects OAuth for authenticated data and write actions; configure an authorization provider that supports the MCP OAuth requirements before claiming ChatGPT remote-MCP production readiness. Test the integration in ChatGPT web, because account/workspace entitlements vary and mobile connection setup may not be available.

Begin with read-only tools. Before enabling writes, require explicit human approval, strong authorization, event auditing, idempotency, safe retries, request rate limits, and recipient suppression checks. Never claim that DNS MX records or an SMTP banner guarantees a zero-bounce email.

## Security checklist

- No candidate profile, resume, database, lead export, suppression list, Gmail credential, or secret belongs in source control.
- The backend rejects requests when `ACIOS_BACKEND_API_KEY` is missing or incorrect.
- The web UI requires a signed session; external OpenAPI/MCP requests use separate tokens.
- The production API URL uses HTTPS and is not exposed through `NEXT_PUBLIC_*` variables.
- Long-running work runs in a durable worker, not inside a short-lived serverless function.
- Profile and résumé data are stored outside Git.
- Test a known suppressed address and ensure all sending paths refuse it.
- Test that unverified contacts are not presented as verified.
