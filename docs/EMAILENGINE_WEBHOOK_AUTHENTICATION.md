# EmailEngine webhook authentication

The legacy `POST /api/webhooks/emailengine` route previously parsed and
processed arbitrary JSON without authenticating its origin. A caller could
forge reply or bounce events and change contact state or suppression behavior.

## Authentication boundary

The route now requires `EMAILENGINE_SERVICE_SECRET` to be configured in the
local, untracked `.env` file or the deployment's secret manager. Its value
must exactly match EmailEngine's `serviceSecret` setting. EmailEngine signs
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

A deployment cannot process EmailEngine webhooks until an operator obtains
the EmailEngine `serviceSecret`, stores the same value as
`EMAILENGINE_SERVICE_SECRET` in the runtime secret manager, and configures
the webhook target to send `X-EE-Wh-Signature`. This change does not access
EmailEngine or change its live settings.

## Remaining work

HMAC authenticates the sender and body but does not make event handling
idempotent. A later change should persist the stable
`X-EE-Wh-Event-Id` in a local event ledger and atomically deduplicate before
mutating contacts or suppression state. The current legacy bounce handler and
its persistence limitations are addressed separately by PR #10 and PR #11.

No real webhook, mailbox, recipient, or secret was used in tests. No message
sending is enabled by this change.
