# Verification syntax gate and suppression evidence

The `/api/v1/tools/verify-contact` endpoint now classifies malformed email
syntax **before** querying either suppression backend. Invalid addresses are
not eligible for outreach, but an invalid address alone is **not** proof that
a suppression registry contains it. The response therefore returns
`INVALID_SYNTAX` and `rfc5322_syntax_failed`, without claiming
`master_suppression_match`.

Syntactically valid suppressed addresses still return `SUPPRESSED` and
`master_suppression_match`. Neither case performs external DNS or SMTP
checks. A syntactically valid unsuppressed address follows the existing
evidence-based verifier; MX reachability does not prove mailbox existence.

This small repair is intentionally stacked on PR #11 because the stricter
SQLite suppression implementation exposed the ambiguity in CI. No sending,
mailbox access, or crawling is enabled. Tests use offline doubles.

Review/merge order: PR #11's parent changes first, then this PR; rerun both
Python-version test jobs and security checks after the final integration.
