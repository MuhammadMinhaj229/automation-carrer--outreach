# Legacy signal evidence default (2026-11-14)

The SQLite `signals` table previously defaulted omitted `evidence_tier` values to `Verified Primary`. An omitted field is not evidence that a primary source corroborated an expansion event. New databases now default omitted values to `UNVERIFIED_NEEDS_PRIMARY_SOURCE`.

## Scope and limits

This is **schema-level defense in depth**, not a verification engine. Callers can still explicitly supply `Verified Primary`, so a separate review gate is required. The legacy table is not the canonical evidence ledger: prefer `source_documents`, `organization_events`, `claims` and append-only reviews. Do not treat RSS, organization registries or a homepage as proof of an event. PR #7 separately proposes stopping fabricated daily signal records; this change does not replace that fix.

Existing SQLite tables are intentionally **not rebuilt or relabeled** by `init_db`. Their previous default and any historical rows may still say `Verified Primary`. Those records require a source-by-source human audit and an explicit migration plan before any reclassification. Do not bulk rewrite evidence labels without preserving history.

## Offline verification

Run `python -m pytest -q tests/test_legacy_signal_schema_default.py` and `ruff check acios/core/database.py tests/test_legacy_signal_schema_default.py`. CI must independently verify Python 3.11/3.12 and security checks before review. The tests use only temporary synthetic SQLite databases; they do not access mailboxes, contacts, web sources or external services.

No dependencies, sending capabilities, crawling behavior, or candidate records are introduced.
