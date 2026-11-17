# Legacy weekly contact persistence: fail closed

The weekly enrichment generator is intentionally disabled until a source-backed discovery adapter exists (draft PR #20), and the flow avoids empty writes (draft PR #22). However, the public legacy `persist_enriched_contacts(leads)` function previously trusted arbitrary dictionaries, including caller-supplied `verification_status`, and wrote contact identity, role and email claims to SQLite.

This stacked change prevents **all nonempty batches** from entering that legacy write path. Empty batches return zero without initializing the repository. The function raises a clear error for nonempty batches, even when the caller supplies `source_url` or `approved`: those values alone are not proof or an authenticated human approval. Existing records are untouched. No network or mailbox operations are added.

This is deliberately a compatibility-breaking safety gate for the legacy workflow. Do not silently replace it with a check of user-controlled flags. To restore writes, first design a local SQLite evidence/claims/review ledger with immutable evidence references, explicit authenticated human review, and a transactionally enforced authorization boundary. Review source legitimacy, identity, role, email ownership, suppression and duplicates separately; evidence for one claim must not imply the others. Preserve private records locally. Draft staging remains distinct from sending, which must never be unattended.

Validation commands: `python -m pytest -q tests/test_weekly_enrichment_persistence_guard.py tests/test_weekly_enrichment_contact_safety.py tests/test_weekly_enrichment_empty_write_guard.py` and `ruff check acios/flows/weekly_enrichment.py tests/test_weekly_enrichment_persistence_guard.py`. Full Python 3.11/3.12 CI and security checks are required before review. No live integrations were used.

Dependency: stacked on PR #22, which depends on PR #20. Do not merge, deploy or enable outbound mail automatically.
