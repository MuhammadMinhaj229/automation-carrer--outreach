# IMAP explicit-consent gate

The legacy IMAP guard previously attempted a real Gmail connection whenever credentials were present in the environment. This could expose private mailbox metadata when a CLI, MCP, dashboard, or API caller invoked the scan without a deliberate per-run decision.

## Default-deny contract

`scan_inbox_for_replies_and_bounces(...)` and `run_imap_reply_guard(...)` default to `allow_live_imap=False`. The function returns `status="DISABLED"` before it reads the Gmail credential variables, initializes `CareerRepository`, or creates an IMAP connection.

Existing CLI, MCP, dashboard, and API call sites do not pass the opt-in flag, so they remain disabled by default. The HTTP API does not expose a request parameter that can enable mailbox access. No environment variable silently enables IMAP.

For a deliberate, operator-authorized local Python invocation only, a caller may explicitly pass `allow_live_imap=True`. This flag is a safety interlock, not an authentication or authorization system: code that can call the function can pass it. Do not expose it through an HTTP endpoint, MCP tool, scheduled worker, or unattended automation. An explicitly consented scan still uses the legacy sender-match reply handling, which is not message-idempotent; it must not be run unattended.

The module loads the project's local dotenv file at import time as part of existing application configuration, but the default-deny function path does not read the Gmail credential variables or initialize the repository. Keep real credentials in untracked local configuration or a secret manager; never commit them.

## Delivery-notice boundary

Generic IMAP delivery notices are header-classified for review only. The scan does not fetch message bodies to extract addresses and does not automatically add recipients to suppression. Suspected notices are not persisted as a durable queue; repeated scans may count them again. A future structured DSN parser must correlate original message/recipient identifiers and require human review before changing suppression state.

## Offline verification

```bash
python -m pytest -q tests/test_imap_delivery_notice.py tests/test_imap_explicit_consent.py
ruff check acios/flows/imap_reply_guard.py tests/test_imap_delivery_notice.py tests/test_imap_explicit_consent.py
```

No test opens a real mailbox. CI must verify the complete supported matrix and security checks before merge.
