# EmailEngine webhook authentication

The legacy `POST /api/webhooks/emailengine` route was protected by the application's
shared bearer API key, but it did not verify EmailEngine's per-request HMAC over
the raw body. That left no cryptographic body-integrity check and no independent
EmailEngine event authentication at this boundary.

## Authentication boundary

The route now requires `EMAILENGINE_SERVICE_SECRET` to be configured in the
local, untracked `.env` file or the deployment's secret manager. Its value
must exactly match EmailEngine's `serviceSecret` setting. The existing global
API middleware also still requires `ACIOS_BACKEND_API_KEY` (at least 32
characters) as `Authorization: Bearer ...`; EmailEngine must send that value
through its `webhooksCustomHeaders`. Keep these two secrets distinct. EmailEngine signs
the **raw request body** with HMAC-SHA256 and sends the URL-safe Base64 digest
without padding in `X-EE-Wh-Signature`.

The API verifies the signature using constant-time comparison before parsing
JSON or invoking the event gateway. It returns:

- `503` when the application secret is not configured (webhook processing is
  disabled);
- `401` when the signature is absent or invalid;
- `400` when an authenticated body is not a JSON object.

Do not log request bodies, signatures, or the service secret. Configure the
EmailEngine target over HTTPS. Never put the service secret in Git, a URL,
candidate data, or a public issue.

## Operator configuration blocker

A deployment cannot process EmailEngine webhooks until an operator stores the
EmailEngine `serviceSecret` as `EMAILENGINE_SERVICE_SECRET`, stores the ACIOS
bearer key as `ACIOS_BACKEND_API_KEY`, and configures EmailEngine's
`webhooksCustomHeaders` to send `Authorization: Bearer <ACIOS_BACKEND_API_KEY>`.
EmailEngine supplies `X-EE-Wh-Signature` automatically. This change does not
access EmailEngine or change its live settings.

## Remaining work

HMAC authenticates the sender and body but does not make event handling
idempotent. A later change should persist the stable
`X-EE-Wh-Event-Id` in a local event ledger and atomically deduplicate before
mutating contacts or suppression state. The current legacy bounce handler and
its persistence limitations are addressed separately by PR #10 and PR #11.

No real webhook, mailbox, recipient, or secret was used in tests. No message
sending is enabled by this change.
