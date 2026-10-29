# ACIOS — Local Career Intelligence & Outreach Workbench

ACIOS is a private-by-default, local-first Python application for discovering evidence-backed organization opportunities, researching dated company and project history, evaluating professional contact relevance, preparing personalized communication drafts, and keeping a durable local activity ledger.

The default product is a **local CLI + MCP server**, not a deployed website. There is no required frontend, cloud database, container, or hosted worker. Core records are stored in SQLite under `data/`; external provider integrations are optional and independently configured.

## Safety rules

- A search result is a lead, not proof. Keep event date, publication date, retrieval time, source URL, excerpt, and verification status separate.
- Do not claim an exact headcount, current role, personal history, or contact identity unless the cited source supports it.
- Email verification is probabilistic. MX records and SMTP responses do not prove that a mailbox exists.
- The suppression registry takes precedence over all contact discovery and drafting.
- Validating a draft is not approving it. A human approval is bound to a content snapshot and a separate attachment digest.
- The local CLI does not perform bulk automatic email sends. Review and send messages manually from the configured mail client.
- Never delete unrelated mailbox drafts during a sync operation.
- Never commit `.env`, candidate profiles, browser session files, resumes, local databases, leads, suppression exports, or credentials.

## Requirements

- Python 3.11 or 3.12 recommended.
- Git, for version history.
- API credentials only for providers you explicitly enable.
- Gmail configured only when you want ACIOS to stage reviewable drafts.

## Local setup

### Windows PowerShell

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
Copy-Item .env.example .env
```

### macOS / Linux

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
cp .env.example .env
```

Edit `.env` and add only the provider keys you actually need. Keep `DRY_RUN=true`. Put your candidate profile in the ignored `config/candidate_profile.yaml` and your resume at `data/resume/master_resume.pdf`. These are private local files and must never be committed.

SQLite is initialized automatically on first repository use. Confirm available CLI commands with:

```bash
python -m acios.cli --help
```

The MCP server can be run from the repository root:

```bash
python -m acios.mcp_server
```

Configure your MCP client to launch that command with the repository root as its working directory. Copy and adapt `mcp_config.example.json`; do not commit machine-specific absolute paths or credentials.

## Current local commands

- `python -m acios.cli doctor` — check local SQLite, candidate profile, resume, and optional provider readiness without printing secret values.
- `python -m acios.cli integrations` — list optional integration capabilities and setup status.
- `python -m acios.cli discover --country Worldwide --keywords "pilot funding expansion"` — discover dated news leads; every result still needs primary-source verification.
- `python -m acios.cli dossier "Organization Name"` — inspect stored records while flagging that legacy facts may be stale.
- `python -m acios.cli audit-mailbox` — read recent inbox headers for replies and delivery failures.
- `python -m acios.cli verify-drafts` — inspect deliverability evidence for locally recorded drafts.
- `python -m acios.cli sync-drafts` — stage pending drafts with the configured resume into Gmail Drafts, leaving unrelated drafts untouched.
- `python -m acios.cli approve-draft ID` — display a complete draft and require a one-time confirmation token to record human approval; it does not send.
- `python -m acios.cli dispatch-queue` — compatibility stub. Bulk dispatch is intentionally disabled.

The existing FastAPI, MongoDB, and background-job code is optional compatibility functionality and is not required by the local CLI/MCP setup. SQLite is selected by default even if an old MONGODB_URI remains in your environment. MongoDB is used only when you deliberately set ACIOS_STORAGE_BACKEND=mongodb or inject a Mongo client/URI in code. Do not configure production/cloud credentials for routine local use.

## Developer quality checks

Install the development and compatibility extras when running the full legacy test suite:

```bash
pip install -e ".[dev,legacy-api,mongodb,s3,ai,documents]"
ruff check acios tests --select E7,E9
pytest -q
pip-audit -r requirements.txt
bandit -r acios/core acios/models -ll
```

The unit tests should use fixtures and mocked providers; they must not require live websites, live mailboxes, or real outreach. Provider integration tests are opt-in and use dedicated test credentials.

## Architecture principles

1. Domain rules live in `acios/`, not in a UI or provider SDK.
2. Research, crawling, contact discovery, email verification, Gmail, and MCP are adapters around those rules.
3. Every factual claim has source provenance and date semantics.
4. Scoring is explainable and labeled as a heuristic until calibrated on actual outcomes.
5. Approval, suppression, and duplicate safeguards run at the final execution boundary.
6. Optional integrations remain optional; install tools only when a tested use case justifies their costs and risks.

See `docs/LOCAL_FIRST_ARCHITECTURE.md` for the target structure and acceptance criteria. The legacy deployment architecture is retired from the default workflow.
