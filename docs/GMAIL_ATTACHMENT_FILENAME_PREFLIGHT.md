# Gmail draft attachment filename preflight (2026-11-12)

The existing Gmail draft staging preflight rejects CR/LF in sender, recipient and subject before IMAP. However, `attachment_filename` is also placed into a MIME `Content-Disposition` header, and was previously passed to `MIMEApplication.add_header` only after an IMAP connection and login.

This change rejects actual carriage-return and newline characters in caller-provided attachment filenames before any mailbox connection. Synthetic offline tests verify CRLF, LF-only and CR-only inputs never call IMAP, and that a literal backslash-n is not mistaken for a newline. No external code or dependencies were added.

## Validate

```sh
pytest -q tests/test_draft_attachment_filename_preflight.py tests/test_draft_staging_preflight.py
ruff check acios/core/draft_engine.py tests/test_draft_attachment_filename_preflight.py
```

Run the full CI matrix for Python 3.11 and 3.12. Tests added in this PR are not proof of passing CI until a workflow reports success.

## Limits

This is a preflight-only repair, stacked on PR #18 (which depends on PR #17). It does **not** implement Gmail draft deduplication, suppression-at-staging, durable human approval, or comprehensive MIME filename sanitization. A transport error after `APPEND` can still leave an ambiguous remote draft. No automatic sending is enabled. Do not merge this stacked PR independently of its prerequisites.
