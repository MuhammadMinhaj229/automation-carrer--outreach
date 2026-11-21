# Gmail draft staging idempotency

ACIOS has several ways to stage a reviewable Gmail draft: the CLI, API, MCP tool, and dashboard. The CLI already searched Gmail Drafts for an ACIOS marker, but the API/MCP/dashboard paths called `DraftEngine.stage_draft` directly and appended without that check.

## Shared marker

All staging paths now use the same opaque `X-ACIOS-Draft-ID` marker. It is a SHA-256 key derived from:

- the persisted local draft ID, when available;
- the exact `EmailDraft.approval_hash` snapshot;
- the attachment content digest; and
- the attachment filename.

The marker contains no recipient address, name, organization, subject, or body. A content or attachment change produces a new version key, so a changed draft is not mistaken for an already-staged older version.

## Fail-closed behavior

Before APPEND, the staging path selects `[Gmail]/Drafts` and searches for the exact marker. If the marker exists, it reports the existing version and does not append. If folder selection or IMAP SEARCH fails, it does not append. The CLI uses the same marker and follows the same fail-closed rule.

ACIOS does not delete old or unrelated Gmail drafts. If a local draft is revised, the new version can be staged while the previous Gmail draft remains for the operator to review and clean up manually.

## Important limitation

IMAP SEARCH followed by APPEND is not an atomic operation. Sequential retries are deduplicated, and a retry after an ambiguous APPEND can discover an already-created message, but two independent processes can still race between SEARCH and APPEND. This change does **not** claim strict exactly-once semantics. A future provider-backed implementation should use Gmail API draft resource IDs or a durable local staging lease plus explicit reconciliation.

All regression tests use synthetic draft data and a fake IMAP client. No mailbox, credential, recipient, or live Gmail service is accessed.
