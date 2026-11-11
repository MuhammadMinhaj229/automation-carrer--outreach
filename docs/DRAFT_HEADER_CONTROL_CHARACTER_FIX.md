# Gmail draft header control-character regression (2026-11-11)

This change fixes the preflight guard introduced in PR #17. The guard previously checked literal backslash-plus-letter strings (\\r and \\n), not the actual carriage-return (CR) and line-feed (LF) characters. GitHub Actions run 42834531386 recorded three failed tests in both Python matrices because header injection inputs reached the MIME builder after IMAP connection was attempted.

The guard now checks actual CR/LF characters before opening IMAP, constructing MIME, or reading optional attachment files. Synthetic offline tests cover recipient, subject, sender, CR-only, and the distinction between a literal backslash sequence and an actual control character.

## Operational safety

This is a **stacked repair** on PR #17, not an independent feature. Review and integrate #17 before this change. It does not add draft idempotency, suppression enforcement, authentication, or per-call human authorization. Never stage a live draft from unattended jobs; no sending is implemented here. All tests must mock IMAP; no real mailbox or candidate data is needed.

## Verification

Run `pytest -q tests/test_draft_staging_preflight.py`, `ruff check acios/core/draft_engine.py tests/test_draft_staging_preflight.py`, and the full CI matrix. Do not merge until both Python versions and security jobs pass.