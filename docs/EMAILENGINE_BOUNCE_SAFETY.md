# Legacy EmailEngine bounce adapter safety (2026-11-04)

This adapter is **not an autonomous sending service**. It processes webhook-shaped dictionaries when invoked by an operator-controlled application.

## Repair
The previous bounce branch called `SuppressionEngine.add_to_suppression(email, reason=...)`, a method that does not exist. The repair uses the existing `block(email)` method for **explicitly hard/permanent** bounces, before attempting repository status and audit updates. Soft, unclassified, and recipient-less events are flagged for review rather than falsely logged as permanently suppressed. Malformed payloads are ignored.

## Important remaining limitations
`SuppressionEngine.block` is **in-memory only**: the block is lost on process restart, is not shared across workers, and does not guarantee protection at the final dispatch boundary. The webhook endpoint's signature/authentication and sender authenticity require separate threat-model review. Do not expose this adapter to untrusted webhook traffic until verified. Repository status/event writes are not atomic with the in-memory block; a database error may leave incomplete auditing. No live mailbox or external webhook was used in tests.

Next: design an idempotent, durable SQLite suppression table with a unique normalized email key, audited reason and timestamp, and a suppression check in the final human-approved dispatch path. Only then advertise persistent suppression.

## Validation
Run `python -m pytest tests/test_emailengine_bounce_guard.py -q` and `ruff check acios/core/emailengine_gateway.py tests/test_emailengine_bounce_guard.py`. Review the GitHub Actions matrix before merging. The tests use synthetic addresses and fake repositories.

## Open-source integration assessment
- [FastMCP / MCP Python SDK](https://github.com/modelcontextprotocol/python-sdk) (MIT): preserve tool boundaries; no need to introduce new dependencies for this bug.
- [Trafilatura](https://github.com/adbar/trafilatura) (Apache-2.0): useful for authorized source-text extraction, unrelated to suppression.
- [Scrapy](https://github.com/scrapy/scrapy) (BSD-3-Clause): powerful but high-complexity crawler; unnecessary here.
- [sqlite-utils](https://github.com/simonw/sqlite-utils) (Apache-2.0): migration/inspection design reference for durable suppression, not required.
- [OpenTelemetry Python](https://github.com/open-telemetry/opentelemetry-python) (Apache-2.0): optional local metrics only; never export recipient identifiers.
- [Google API Python Client](https://github.com/googleapis/google-api-python-client) (Apache-2.0): consider for human-approved Gmail draft staging only; no sending.
No third-party code was copied or dependencies introduced.
