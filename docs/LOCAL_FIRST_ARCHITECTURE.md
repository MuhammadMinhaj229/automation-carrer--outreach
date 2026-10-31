# ACIOS Local-First Architecture

## Product boundary

ACIOS is a local Python research and outreach workbench. The default entry points are the CLI and the FastMCP server. SQLite is the canonical local ledger. Provider SDKs and remote APIs are adapters, never domain dependencies.

The Next.js cockpit and hosted API/worker deployment are retired from the default architecture. The legacy FastAPI/MongoDB/job modules remain compatibility code while usages are migrated; they are not required for everyday local CLI/MCP operation. Do not add a new frontend or deployment layer as a shortcut for a domain capability.

## Runtime shape

~~~text
CLI / MCP client
      |
      v
Application services (research, evidence, scoring, drafting, review)
      |
      +---- provider adapters: search, registries, crawling, verification, Gmail
      |
      v
SQLite repositories + append-only activity/evidence ledger
      |
      +---- ignored local evidence archive, reports, resume, and logs
~~~

Core records and rules live under acios/. MCP methods call the same services as CLI commands. Providers are lazy/optional and return typed results with their provider, status, timing, failure category and source metadata.

## Repository responsibilities

- acios/domain (target): organization, event, claim, contact, opportunity, draft and approval contracts.
- acios/services (target): orchestration and decision rules independent of provider SDKs.
- acios/providers, acios/tools, and acios/crawling (existing adapters to consolidate): public search, ROR/Wikidata, crawling, verification and AI provider integrations.
- acios/core/database.py / acios/core/repository.py: local SQLite persistence and migrations.
- acios/mcp_server.py: narrow tool interface; no provider-specific business rules.
- acios/cli.py: local operations, inspection, review and configuration diagnostics.
- tests/: fixture-based unit, security, integration-contract and research-quality tests.
- data/: private runtime state only; ignored by Git.
- config/candidate_profile.yaml: user-owned private candidate profile; ignored by Git.

## Provider policy

Use a provider only for a documented capability gap. Keep a small deterministic fallback chain and set per-request timeouts, response size limits, rate limits, and provider spend budgets.

| Capability | Initial default | Optional alternatives |
|---|---|---|
| Basic public page extraction | Existing bounded HTTP/HTML adapter | Crawl4AI for JS-rendered pages; Firecrawl when configured |
| Research organization identity | ROR | Wikidata as discovery/corroboration, not sole authority |
| Organization events | Official press rooms, filings, regulators, partner announcements | GDELT/search API for discovery only |
| Deep dossier | Multi-source search/crawl with citations | GPT Researcher on selected high-value targets |
| Email evidence | Syntax, domain/MX, vetted provider result, suppression lookup | Reacher service or commercial verification API |
| LLM output contracts | Pydantic models and deterministic validation | PydanticAI or Instructor only if a tested need arises |
| Observability | Structured local JSON logs and usage rows | Langfuse only after deciding whether external telemetry is acceptable |

Do not activate all crawlers for every URL. Avoid bypassing access controls, CAPTCHA, robots policies, or a site's terms. Never use fingerprint impersonation or session reuse as a way to evade restrictions.

## Research provenance model

Every accepted factual claim should retain:

- canonical organization/person identifier and normalized aliases;
- claim type and value;
- event date, publication date, retrieval timestamp, and any valid-from/valid-to dates;
- source URL, publisher, source type (primary / independent secondary / aggregator);
- cited excerpt or bounded text span, content hash, extractor/provider version;
- confidence and verification status, including UNKNOWN, CONFLICTED, and STALE states.

Do not mark a whole organization as verified because one claim has a primary source. Verify claims individually. Preserve conflicting assertions and history; do not replace prior facts when a leadership role or company status changes.

## Source and claim provenance operations

The SQLite schema includes source_documents, organization_events, claims, source_reviews, and claim_reviews. Fetched source text is captured with URL, retrieval time, publisher host, provider, content hash and excerpt. Every new discovery event starts as DISCOVERED_NEEDS_PRIMARY_VERIFICATION. Claims start UNCONFIRMED.

A human operator must classify the source before a claim can be marked VERIFIED_PRIMARY. The source classification is recorded in source_reviews; claim decisions are recorded in claim_reviews. CORROBORATED requires at least two distinct named publishers supporting the same entity/predicate/value. This is a conservative workflow control, not a substitute for legal or professional verification.

## Scoring contract

Maintain distinct interpretable scores:

1. Opportunity fit: trigger evidence, skill match, project relevance and eligibility/geography.
2. Contact relevance: role fit, project connection, hiring/referral influence, and current-role evidence.
3. Identity/channel confidence: source strength for identity, role and contact channel; this is not the same as desirability.

Initial weights are decision heuristics and must be labeled as such. A probability of a reply, referral, interview or hire is not valid until a labelled outcome dataset, time-separated validation, calibration checks, and uncertainty reporting exist. ACIOS must never present a heuristic score as a probability of getting hired.

## Draft and approval contract

- Drafts are validated at 100–160 body words, excluding the signature, with the forbidden-cliché list and the configured candidate profile.
- A validation result means only “valid for review”, never “approved”.
- The approval snapshot covers normalized recipient, recipient name/role, organization, persona, subject, complete body, attachment-present flag, and attachment SHA-256.
- Any edit resets approval and invalidates the snapshot.
- Dispatch preflight rechecks the stored snapshot and suppression state, and validates the current attachment digest.
- Unknown verification, stale identity evidence, suppression hits, conflicting evidence or missing required attachments must fail closed.
- SMTP outcome uncertainty means reconcile before retry; never auto-retry a possibly accepted message.
- Bulk sending is disabled in the local CLI. Gmail staging creates reviewable drafts; the user sends manually.

## Credential and session storage

- Use OS-backed credential stores where available; do not print or export secrets.
- OAuth should be preferred to Gmail App Passwords when implemented.
- Keep profile files, resume PDFs, SQLite databases, evidence caches and browser state out of Git.
- Browser session state is an authentication secret. Protect it with restrictive OS permissions/encryption, add explicit disconnect/expiry/clear controls, and never sync it to cloud storage by default.
- Use official channel APIs and permitted user-directed actions. Do not build unauthorized LinkedIn/Instagram/X automation or WhatsApp Web session bots. A 60-second delay is only a pacing choice and does not grant permission to automate.

## Quality and release checks

Before a code change is accepted:

1. Ruff syntax/error checks pass.
2. The complete fixture-based pytest suite passes.
3. The dependency audit has no unreviewed known vulnerabilities.
4. Bandit findings in domain/execution modules are resolved or explicitly documented.
5. Tests cover strict word-count bounds, snapshot tampering, suppression, duplicate sends, uncertain send results, crawler SSRF/redirect constraints, provider timeouts and secret redaction.
6. A small manually labelled benchmark measures claim/citation support, date accuracy, organization resolution and contact-role precision.
7. Local setup succeeds without Docker, hosted database, web runtime or production credentials.

## Data migration and backup

Before upgrading an existing local database, make a timestamped backup. Use schema migrations that are additive first. When changing the hash contract, treat older approval hashes as stale and require drafts to be reviewed and approved again. Never silently migrate or reuse old approvals as if they covered the new hash fields.

## Explicitly out of scope for local MVP

- Hosted multi-user web cockpit and cloud database.
- Unbounded “scrape the whole internet” jobs.
- Guaranteed complete organization history or exact live employee counts without evidence.
- Personal-life profiling unrelated to professional relevance.
- Automated social direct messages or connection requests through unauthorized methods.
- Bulk autonomous email sending.
