# IMAP delivery-notice safety

The legacy IMAP reply guard previously fetched every suspected delivery-notice body, extracted arbitrary email-looking strings, and treated them as permanent bounces. A delivery-status message can quote unrelated senders, recipients, and diagnostic contacts; a sender name or subject keyword is not proof that a specific recipient suffered a permanent delivery failure. The old path also opened a second suppression connection while an outer SQLite write transaction was active, risking a database-lock error.

## Current behavior

- Suspected delivery notices are classified from sender/subject headers only.
- Message bodies are not fetched for bounce-address extraction.
- Suspected notices are counted as `delivery_notices_needing_review`; `bounces_detected` remains zero.
- The IMAP path never writes permanent suppression from these generic notices.
- Live IMAP access is disabled by default; see [IMAP explicit consent](IMAP_EXPLICIT_CONSENT.md).

The review count is not a durable queue. Repeated scans can count the same notice again. The legacy reply path still matches sender addresses against known contacts and writes reply events without a durable message-level idempotency key. Therefore, even an explicitly consented scan is not suitable for unattended operation.

## Future safe design

A future delivery-status parser should inspect structured `message/delivery-status` fields, correlate the original recipient and message identifiers to locally staged drafts, distinguish permanent 5.x.x from transient 4.x.x status codes, and place evidence in a durable local review ledger. A human must approve any suppression decision, and the final draft/dispatch preflight must independently consult the authoritative suppression registry.

## Offline tests

`pytest -q tests/test_imap_delivery_notice.py tests/test_imap_explicit_consent.py`

Tests use synthetic headers and fake repository/IMAP objects. They do not contact a mailbox, access real recipients, or send email.
