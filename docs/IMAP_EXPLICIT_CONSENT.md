# IMAP explicit consent gate (2026-11-09)

The legacy IMAP guard previously attempted a real Gmail connection whenever credentials happened to be present in the environment. This was unsafe for automated CLI/MCP workflows and offline test execution. It could read private mailbox metadata without an explicit per-run decision.

The scan and Prefect flow now default to `allow_live_imap=False`, returning `status="DISABLED"` **before** reading credentials, opening SQLite, or establishing IMAP connections. Existing callers that omit the argument remain safe. No environment variable can silently enable mailbox access. For a deliberate, operator-authorized local run only, pass `allow_live_imap=True` explicitly to `run_imap_reply_guard(...)`; this is NOT a recommendation to run it unattended.

A consented run still requires configured Gmail credentials and follows the existing legacy IMAP code. It is **not** a production authorization system: any code capable of calling the Python function can opt in. Treat this as a default-deny safety guard, not an access-control boundary. Do not expose the opt-in flag through an unauthenticated API or unattended worker. The existing IMAP path also has unresolved reply-event idempotency, message identity, review persistence, and backend compatibility issues.

The change stacks on PR #15, which prevents unsafe body-text bounce suppression. Review and integrate #15 before this PR. No outbound email, live mailbox, or candidate record is used by the synthetic tests.

Offline validation: `pytest -q tests/test_imap_explicit_consent.py tests/test_imap_delivery_notice.py`. Verify the GitHub Actions Python 3.11/3.12, Ruff, Bandit and dependency audit jobs before merging. No third-party code or dependency was introduced.
