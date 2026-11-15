# Weekly enrichment: empty evidence must not write

The legacy weekly enrichment workflow intentionally produces no contacts until an approved, source-backed discovery adapter exists. Previously, the orchestration still called `persist_enriched_contacts([])`, which opened the repository and started a write transaction. This also failed the offline no-write regression in draft PR #20.

This stacked repair returns immediately when no contacts are produced, before opening persistence or exporting reports. The empty-organization path already returns before enrichment. It does not enable speculative contact creation, mailbox access, crawling or sending. Existing stored contacts are not changed.

Review PR #20 first. The separate persistence function remains available to other callers and is **not** an evidence-validation or authorization boundary. Future source-backed enrichment must validate identity, provenance, suppression and human review before any persistence or draft staging.

Offline validation: `python -m pytest -q tests/test_weekly_enrichment_contact_safety.py tests/test_weekly_enrichment_empty_write_guard.py`; `ruff check acios/flows/weekly_enrichment.py tests/test_weekly_enrichment_empty_write_guard.py`. Full Python 3.11/3.12 CI and security checks are required before merge.
