# Gmail draft transport preflight (2026-11-10)

The legacy `DraftEngine.stage_draft()` previously opened an IMAP SSL connection before checking whether credentials were configured or whether header values contained CR/LF. This change fails locally when the Gmail account or app password is empty and rejects newline characters in the sender, recipient, or subject before any network access. It does not send email.

## Offline regression checks

`pytest -q tests/test_draft_staging_preflight.py`

The four tests use synthetic `.test` addresses and mock `IMAP4_SSL` to assert no connection occurs for missing credentials or malformed headers. They must pass in CI before merge; adding tests is not evidence that they have executed successfully.

## Deliberate limitations

This is a narrow transport preflight, **not** Gmail draft deduplication, full RFC address validation, authentication, or human approval. Callers must still enforce current suppression records, draft approval/integrity, authorized mailbox access, and safe retry/idempotency before staging. IMAP APPEND may create duplicates if retried after an ambiguous response. Never automatically send or delete unrelated drafts. Keep credentials in local secure storage; do not commit private records or real email addresses.

No new dependencies, migrations, or external source code were introduced.
