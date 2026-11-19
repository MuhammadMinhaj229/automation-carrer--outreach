# EmailEngine bounce and native-event safety (2026-11-19)

This adapter is **not an autonomous sending service**. It processes webhook-shaped dictionaries when invoked by an operator-controlled application. It never sends email.

## Existing legacy bounce repair

The previous generic bounce branch called the nonexistent
`SuppressionEngine.add_to_suppression(email, reason=...)`. The legacy normalized
adapter uses `block(email)` only when its caller explicitly supplies
`bounce_type=hard|permanent`. That block is **process-local only**. Soft,
unclassified, and recipient-less legacy events require review.

## Native EmailEngine event semantics

EmailEngine's documented event names and payloads are not interchangeable with
the older generic aliases:

| Native event | ACIOS result | Side effects |
|---|---|---|
| `messageNew` | `REVIEW_INBOUND_MESSAGE` | None; a new mailbox message is not necessarily an outreach reply |
| `messageBounce` | `REVIEW_BOUNCE` | None; preserve recipient, original Message-ID and structured response fields for review |
| `messageDeliveryError` | `REVIEW_DELIVERY_FAILURE` | None; an individual delivery attempt can be retried |
| `messageFailed` | `REVIEW_DELIVERY_FAILURE` | None; terminal delivery failure is not by itself a confirmed mailbox bounce |
| `messageComplaint` | `REVIEW_COMPLAINT` | None; require an operator decision and durable suppression |
| `messageSent` | `LOG_DELIVERY` | No contact or suppression mutation; provider acceptance is not inbox delivery |

In particular, EmailEngine emits `messageNew` for newly observed mailbox
messages, including a bounce notification before the corresponding
`messageBounce` event. Treating every `messageNew` as a reply can incorrectly
mark a contact as `REPLIED` and halt future work. ACIOS now keeps it review-only.

A native `messageBounce` includes `data.recipient`, `data.action`,
`data.messageId`, and optional structured `data.response` fields such as
`status`, `category`, and `recommendedAction`. The adapter exposes those
fields to the authenticated operator for review but does not infer an automatic
suppression decision. `messageDeliveryError` and `messageFailed` are distinct
delivery lifecycle events and are not treated as hard bounces.

The native event identifier is delivered in the `X-EE-Wh-Event-Id` HTTP header,
not in the JSON body; EmailEngine reuses it for retries of the same event.
This change does not persist or deduplicate that header. Replay-safe handling
still requires a durable unique-key inbox and atomic processing before any
contact or suppression side effects.

The legacy normalized aliases `reply` / `incoming_message` and
`bounce` / `delivery_failed` / `dsn` remain for existing internal callers.
Do not pass raw EmailEngine payloads through those aliases.

## Important remaining limitations

- Legacy `SuppressionEngine.block` is in-memory: it is lost on process restart,
  is not shared across workers, and does not guarantee protection at the final
  dispatch boundary.
- Native events are review-only. A durable, atomic SQLite event inbox with
  unique `X-EE-Wh-Event-Id` handling is still required before replay-safe
  processing can be claimed.
- The separate PR #24 adds raw-body HMAC authentication for the FastAPI
  webhook route. This branch is stacked on PR #10 and does not contain PR #24;
  do not expose the route to untrusted webhook traffic until the authentication
  change and required runtime configuration have been reviewed and integrated.
- Repository status and outreach-event writes in the legacy normalized path
  are not atomic with the process-local suppression block.

## Validation

Run:

```bash
python -m pytest tests/test_emailengine_bounce_guard.py -q
ruff check acios/core/emailengine_gateway.py tests/test_emailengine_bounce_guard.py
```

The tests use synthetic addresses, event IDs, Message-IDs and fake repositories.
No real mailbox or external webhook is used.

## Open-source integration assessment

- [FastMCP](https://github.com/PrefectHQ/fastmcp) (Apache-2.0): retain the current
  pinned major until Python 3.10 support and security advisories are reviewed.
- [Trafilatura](https://github.com/adbar/trafilatura) (Apache-2.0 for current
  releases): useful for authorized source-text extraction, unrelated to bounce
  classification; check version-specific licensing.
- [Scrapy](https://github.com/scrapy/scrapy) (BSD-3-Clause): powerful but
  unnecessary for this webhook adapter.
- [sqlite-utils](https://github.com/simonw/sqlite-utils) (Apache-2.0): optional
  SQLite inspection/migration reference; no runtime dependency is required.
- [OpenTelemetry Python](https://github.com/open-telemetry/opentelemetry-python)
  (Apache-2.0): optional local metrics/tracing; never export recipient
  identifiers, subjects, message bodies or candidate data.
- [Google API Python Client](https://github.com/googleapis/google-api-python-client)
  (Apache-2.0): consider only for human-approved Gmail draft staging, not
  unattended sending.

No third-party code was copied and no dependency was introduced.
