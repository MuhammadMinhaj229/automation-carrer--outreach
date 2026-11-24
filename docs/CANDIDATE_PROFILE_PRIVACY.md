# Private candidate profile and draft signature

ACIOS must not contain a real candidate's name, email address, phone number, location, portfolio, GitHub, or LinkedIn URL in Python source.

## Source of signature data

The draft signature is generated from the `candidate` object supplied by the local profile:

- The API uses the candidate profile stored in the local SQLite settings table. In development it may fall back to `config/candidate_profile.yaml`.
- The dashboard uses the SQLite profile first and the ignored local YAML profile as a fallback.
- CLI/MCP local workflows may read `config/candidate_profile.yaml` when no profile provider is injected.
- Draft exports use the local SQLite profile first and the ignored YAML fallback when the database profile is absent.

The tracked template is `config/candidate_profile.example.yaml`. Copy it to `config/candidate_profile.yaml` and fill it locally. The real file is ignored by Git. Never paste candidate records into issues, pull requests, logs, or test fixtures.

## Fail-safe behavior

If no profile is configured, ACIOS produces only a generic `Regards,` closing. It does not fall back to an identity embedded in source code.

Profile text is HTML-escaped. Signature links are rendered only for credential-free HTTPS URLs. Email values containing whitespace or control characters are not rendered as mail links. The authenticated Gmail account remains the message `From` address; a configured profile name is used only as its display name.

## Verification

The regression tests use synthetic `example.invalid` values and verify:

- explicit profile values are used;
- HTML markup in profile text is escaped;
- non-HTTPS links are omitted;
- a missing profile yields no candidate identity.

No mailbox is opened, no message is sent, and no private candidate data is included in the repository.
