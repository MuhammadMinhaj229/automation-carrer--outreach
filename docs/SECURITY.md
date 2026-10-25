# Security and privacy controls

## Data handling

Never commit candidate profiles, phone numbers, private emails, CVs, contact lists, lead exports, databases, generated outreach drafts, suppression lists, or provider credentials. The real candidate profile belongs at the ignored local path `config/candidate_profile.yaml`; runtime data belongs under `data/`. A safe schema example is in `config/candidate_profile.example.yaml`.

## Secrets to rotate

Because identity information and runtime data were previously committed to this public repository, treat old values and artifacts as public. Rotate Gmail app passwords and any other credentials if they were ever committed. Replace deployment tokens with newly generated high-entropy values. Do not paste new values into GitHub, issues, PR discussions, or chat logs.

## Authentication boundaries

- FastAPI accepts only `Authorization: Bearer <ACIOS_BACKEND_API_KEY>`, except `GET /healthz`.
- The Next.js cockpit uses a signed HTTP-only, SameSite cookie gated by `ACIOS_UI_PASSWORD` and `ACIOS_SESSION_SECRET`.
- OpenAPI Actions and MCP clients have separate tokens. A user-facing token must never be reused as the backend-to-backend service token.
- The MCP adapter must fail closed when its token is missing or left at the example placeholder.
- Configure provider-level rate limiting for login, verification, discovery, and write routes.

## Git history limitation

Removing files from a new commit does not remove them from old commits, forks, clones, pull-request refs, or cached GitHub objects. Full cleanup requires `git-filter-repo` against a fresh local clone, a coordinated force-push, cleaning other clones/forks, and potentially GitHub Support for cached sensitive views. Make the repository private immediately while this is completed. Rotate credentials first; history rewrite cannot make already exposed values secret again.

## Outreach safety

MX records and SMTP banners do not prove that a specific mailbox exists. Treat verification as a confidence score, keep uncertain addresses unverified, respect suppression/opt-out state in every send path, and require human approval before dispatch. Use idempotency keys and immutable audit events to prevent duplicate sends.