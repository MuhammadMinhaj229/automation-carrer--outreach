# Legacy queued growth scan compatibility (2026-11-07)

## Problem and scope

The optional legacy `DurableJobQueue` handler for `search_growth_signals` invoked `GrowthSignalScanner.scan_market_signals`, which is not implemented by the maintained `GrowthSignalScanner` class. The resulting `AttributeError` caused queued research jobs to fail/retry without performing discovery. The canonical local-first CLI and FastMCP remain the preferred entry points; this repair does **not** introduce a hosted worker or enable sending.

## Adapter contract

The queue now calls `scan_ecosystem`, mapping old `city` to `region`, `trigger` to `trigger_category`, and `query` to `custom_keywords`. The result limit is clamped to 1–100; invalid numeric limits fail explicitly. The returned job result contains only a count, the **unverified discovery** status and local CSV/XLSX export paths. It does not embed raw discovery records, candidate profiles or contacts in job payloads. Source documents and claims still require provenance review; RSS headlines are not evidence of verified expansion.

`scan_ecosystem` may access public RSS and write local files when invoked in production. Its provider permissions, rate limits, source verification, error handling, and retry policy require separate review before enabling unattended scans. This PR does not alter job retry scheduling, dispatch behavior, or suppression handling.

## Validation

Offline contract tests in `tests/test_legacy_growth_worker_contract.py` mock the scanner method and assert parameter mapping, result shape, bounds, and invalid-limit failure without network or mailbox access.

Run:

```bash
python -m pytest -q tests/test_legacy_growth_worker_contract.py
ruff check acios/core/job_queue.py tests/test_legacy_growth_worker_contract.py
```

A passing GitHub Actions result is required before merging; test files being committed does not establish that they passed. No dependencies or third-party code are added.

## Integration research (not imported)

- Trafilatura (Apache-2.0): extract content and metadata from already-authorized pages; useful later, but not needed for this adapter.
- Scrapy (BSD-3-Clause): robust crawling framework, but excessive for one bounded RSS scan and does not grant permission to crawl a site.
- MCP Python SDK (MIT): protocol reference for the existing FastMCP interface; keep version compatibility checks isolated.
- google-api-python-client (Apache-2.0): optional future Gmail *draft* staging via OAuth; do not add autonomous sending.
- sqlite-utils (Apache-2.0): optional operator tooling for local SQLite inspection; not required in the core runtime.
- OpenTelemetry Python (Apache-2.0): possible opt-in local instrumentation, with private recipient data and message contents excluded.

Review exact dependency versions, transitive licenses and security advisories before adoption. This change copies no third-party code.
