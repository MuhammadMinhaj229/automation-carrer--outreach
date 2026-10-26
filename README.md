# ACIOS — Autonomous Career Intelligence & Outreach Operating System

ACIOS is a private-by-default career research and outreach workspace. It discovers company expansion signals, records sources and confidence, helps prepare evidence-backed drafts, and tracks approved outreach activity.

## Security posture

- Do not commit resumes, candidate profiles, databases, leads, contact exports, suppression lists, credentials, or generated reports.
- Store candidate profile data in the ignored local `config/candidate_profile.yaml`.
- Store runtime output under the ignored `data/` directory.
- All production API endpoints must be authenticated. Email dispatch must require explicit approval and use idempotent jobs.
- Email verification is probabilistic; MX records and SMTP banners do not prove that a recipient mailbox exists. Never label a contact “verified” without evidence from a suitable verification provider.

## Architecture

- **Web cockpit:** Next.js on Vercel, serving the UI and authenticated same-origin API proxy.
- **Application API:** FastAPI in a persistent container service (for example, Railway, Render, Fly.io, or Cloud Run). It validates requests and owns business logic.
- **Worker:** A separate long-running worker process for discovery, inbox polling, retries, and paced dispatch. Use a durable queue so jobs survive deploys and restarts.
- **Database:** PostgreSQL for organizations, contacts, signals, drafts, approvals, dispatch events, and suppression records. SQLite remains for local development only.
- **Files/secrets:** Object storage for approved resume documents and a managed secret store for credentials. Never store private files in the Git repository.
- **ChatGPT/MCP:** A dedicated authenticated MCP adapter exposes narrow read/search and draft-preparation tools. Add OAuth 2.1 for ChatGPT custom MCP connections; never expose unauthenticated write tools.

MongoDB can store this data, but it does not replace the API, worker, or queue. PostgreSQL is the recommended production database because the current workflow relies on related entities, unique constraints, durable status transitions, and auditability.

## Local setup

1. Create a virtual environment and install `requirements.txt`.
2. Copy `.env.example` to `.env` and replace all placeholder secrets with random values.
3. Create your private `config/candidate_profile.yaml` and keep runtime files under `data/`.
4. Start FastAPI with `python -m uvicorn acios.api:app --host 127.0.0.1 --port 8000`.
5. Start the web cockpit from `web/` with `npm ci` and `npm run dev`.

The backend will fail closed when its service authentication key is not configured. Do not use production credentials during development.

## Production deployment

Deploy the web cockpit and FastAPI as separate services. Inject `ACIOS_BACKEND_API_KEY` into both services through the deployment secret manager; keep the frontend copy server-side only. Set a production database URL, durable queue, and worker service before enabling scans or dispatch. Keep previews isolated from production data and credentials.

## ChatGPT connections

The repository includes an OpenAPI Actions schema and an MCP adapter. OpenAPI Actions can use a dedicated bearer token. A ChatGPT custom remote MCP connection should use the OAuth 2.1 authorization flow supported by the chosen identity provider, and should begin with read-only tools. Enable writes only after authenticated approval flows, rate limits, idempotency, and audit logging are tested.

## License

See [LICENSE](LICENSE).


## Modular crawling integrations

ACIOS includes a policy-aware adapter gateway for Firecrawl, Crawl4AI, Browser Use, Crawlee, Scrapy, MarkItDown, Scrapling, scrcpy, AutoScraper, and curl-impersonate. Optional packages are loaded lazily so the core API can stay lightweight. See [the crawling toolkit guide](docs/CRAWLING_TOOLKIT.md) for roles, setup, API routes, and safety controls.
