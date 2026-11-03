# Legacy RSS signal workflow: provenance-first safety contract

**Updated:** 3 November 2026  
**Scope:** `acios/core/interfaces.py`, `acios/providers/signals/rss_provider.py`, `acios/flows/daily_signal_scan.py`  
**Status:** proposed; review and merge required.

## Why this change is necessary

The old Prefect-compatible workflow created five prewritten Oman/Sohar expansion
narratives even when every RSS provider returned zero results. It used an ROR
organization homepage as supposed evidence for an *event*, or fell back to a
synthetic `verified-news.gcc` URL. It assigned today's date, a score of 85 and
`Verified Primary` without a supporting article or human review.

A registry result can support organizational identity; it does **not** prove
an investment, pilot, expansion, contract or event date. An RSS aggregator is
a discovery channel, not an official primary source.

## New behavior

1. The five existing strings are **search topics only**, never event records.
   User-selected sectors add at most eight bounded search topics.
2. A provider result without a title or URL is discarded. Repeated
   (URL, headline) pairs are deduplicated within the run.
3. An RSS hit has an unknown organization unless independently resolved and
   reviewed. The search query is not an organization name.
4. A missing feed publication timestamp stays `None`; it is never replaced
   with today's date. Even a valid publication date is **not** an event date.
5. All incoming provider labels are treated as unverified at this boundary.
   Keyword score means *relevance heuristic*, not probability or truth.
6. The workflow writes to `source_documents` and `organization_events`
   through `CareerRepository.record_discovery_event`. It does not populate
   the legacy `organizations` or `signals` tables or export those old
   tables as if the new discoveries had been verified.
7. The result count is the number of qualifying records stored/updated, not
   a count of unique newly discovered companies. Repeated runs are
   idempotent for identical source/headline/description content.

### Operator workflow

Run the existing Prefect-compatible function explicitly when desired:

```python
from acios.flows.daily_signal_scan import run_daily_signal_scan
count = run_daily_signal_scan(["Green Tech"])
```

Use the local repository to inspect the resulting unverified leads:

```python
from acios.core.repository import CareerRepository
for lead in CareerRepository().list_discovery_events(limit=20):
    print(lead["headline"], lead["source_url"], lead["verification_status"])
```

The recommended CLI/MCP discovery commands remain `acios discover` and
`search_growth_signals`. Neither this legacy flow nor the CLI/MCP path
automatically verifies events or sends messages.

**Manual verification remains required:** capture a permitted primary page,
inspect the event statement and relevant date, classify its publisher with a
recorded review, and review each claim individually. Do not infer an event date
from an article's publication timestamp.

## Test and rollout boundaries

- `tests/test_prefect_flows.py` now mocks RSS feeds and local storage.
- Tests cover empty feeds, unknown organization/date, explicit parsed
  publication date, duplicate results, unsafe provider verification labels,
  idempotent SQLite persistence, and invalid/missing source URLs.
- The unrelated weekly enrichment integration test is opt-in
  (`pytest -m live_integration`); it is not a network dependency of default CI.
- This branch is stacked on the deterministic-test branch from PR #6.
  Merge PR #6 first, then retarget/rebase this branch to `main`.
- Existing local SQLite databases may already contain fabricated legacy
  `signals` rows. **This change does not delete or automatically upgrade
  those historical records.** Back up the DB and review/mark old records
  separately before using them in a dossier.
- The legacy `signals.evidence_tier` schema default is still unsafe for
  other writers; a later additive migration should address that separately.
- Feedparser's direct network fetch lacks the bounded HTTPX/robots/rate-budget
  policy used by the newer crawler. A subsequent focused adapter change
  should introduce explicit timeouts, response limits and backoff.

## Open-source research check (3 November 2026)

No third-party source code was copied and no dependency was added. These
are candidates and references, not permissions to crawl arbitrary sites.

| Project / source | License | Fit, maintenance and integration cost | Security/privacy gate |
|---|---|---|---|
| [Scrapy](https://github.com/scrapy/scrapy) | BSD-3-Clause | Actively released (2.19 in Sep 2026); robust larger crawl jobs, but heavyweight for one RSS adapter and now Python 3.11+. Defer. | Explicit robots/rate policy, public hosts only; no bypass features. |
| [Trafilatura](https://github.com/adbar/trafilatura) | Apache-2.0 (current versions) | Maintained extraction library; low/medium cost if fed already-authorized HTML. Benchmark against BeautifulSoup before adoption. | Do not enable a separate downloader without equivalent SSRF and robots checks. |
| [MCP Python SDK](https://github.com/modelcontextprotocol/python-sdk) | MIT | Active v2 SDK, Python 3.11+; migration may conflict with ACIOS's declared 3.10 compatibility and current FastMCP integration. Defer. | Keep tool permissions narrow; no remote write/sending surface. |
| [sqlite-utils](https://github.com/simonw/sqlite-utils) | Apache-2.0 | Mature local SQLite inspection/migration reference; medium integration cost. Existing sqlite3 is sufficient today. | Back up before migration; never upload private local databases. |
| [OpenTelemetry Python](https://github.com/open-telemetry/opentelemetry-python) | Apache-2.0 | Maintained metrics/tracing API; medium integration cost. Optional local-only telemetry if diagnostic need is demonstrated. | Disable remote exporters by default; redact candidate/contact content. |
| [Google API Python Client](https://github.com/googleapis/google-api-python-client) | Apache-2.0 | Maintained official API client, but large and in maintenance mode; Gmail drafts can use `drafts.create`. No integration in this PR. | OAuth with minimum scope; never call `drafts.send`, stage only with explicit approval and dedupe. |
| [GLEIF LEI API](https://www.gleif.org/en/lei-data/gleif-api/) | CC0 data (not a code-library license) | Public legal-entity reference data, optional thin HTTPX identity adapter; it does not prove business events. | Rate budgets, date/status checks and no person profiling. |

The research reinforces the decision to fix provenance semantics **before**
adding another crawler or verification vendor. Source repositories retain
their respective licenses; no vendor code was vendored.
