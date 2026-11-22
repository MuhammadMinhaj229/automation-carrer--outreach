# MCP email discovery and suppression boundary

The legacy FastMCP `permute_email` tool remains registered for client compatibility, but it no longer generates or returns guessed addresses. Email permutations derived from a person's name and an organization domain are speculative contact enrichment; they do not establish mailbox ownership, identity, role, consent, or relevance. The tool returns `DISABLED_POLICY` with an empty candidate list.

The MCP `verify_suppression` tool now checks both local sources used by the current application:

- the repository's SQLite suppression table;
- the compatibility JSON/in-memory suppression engine.

An invalid/empty input is blocked. If either suppression read raises, the result is `BLOCKED` with `FAILED_CLOSED`; a database failure is never converted into a clean result.

A successful check with no local match is labelled `NOT_SUPPRESSED`, not `CLEAN` or `SAFE TO PROCEED`. It is not evidence of deliverability, mailbox ownership, contact identity, permission, or legal basis. Source-backed public contact evidence and explicit human review remain required.

This change does not merge the two local suppression stores, perform network verification, read a mailbox, stage a draft, or send email. It adds no dependencies and uses synthetic test addresses only.

## Offline regression coverage

- The permutation compatibility tool returns no guessed addresses.
- A SQLite suppression match blocks the MCP status tool.
- An in-memory/JSON compatibility match blocks the MCP status tool.
- A repository read error returns `FAILED_CLOSED`.
- Automated sending remains disabled.
