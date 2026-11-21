# Gmail draft staging suppression preflight

Gmail draft staging is not message delivery, but it still creates an external mailbox artifact and must respect ACIOS suppression decisions.

## Enforced behavior

The authenticated FastAPI `/api/dispatch/stage-gmail` endpoint now checks both local suppression sources before reading the private resume or opening an IMAP connection:

- the repository's durable suppression store (`repo.is_suppressed`);
- the compatibility JSON/in-memory suppression engine (`supp.is_suppressed`).

A match returns HTTP 409 and performs no resume read, Gmail login, IMAP SELECT/SEARCH/APPEND, or draft mutation.

The Streamlit dashboard uses the same two checks and disables its Gmail staging control for a suppressed recipient. The CLI and MCP staging entry points already checked both stores; the direct-send API also checks both.

## Verification boundary

Regression tests use a temporary SQLite database, synthetic `example.org` addresses, a synthetic suppression fixture, and forbidden resume/IMAP functions. No real mailbox, credential, recipient, or candidate data is used.

This does not consolidate the two suppression stores. The SQLite registry remains the local durable source and the JSON/in-memory engine remains a compatibility source until the dedicated suppression-registry migration is reviewed and merged. Any failure while checking suppression must fail closed; it must never be interpreted as a clean recipient.

ACIOS still does not send automatically. Gmail staging only creates a reviewable draft; the human operator remains responsible for inspecting and manually sending any message.
