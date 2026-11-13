# Weekly enrichment: evidence-first safety boundary

The legacy `generate_and_verify_candidates` workflow previously constructed a fictitious "Engineering / Ops Lead" for every organization, guessed a domain when none existed, generated address permutations, and treated a verification confidence score as evidence of a real person's identity and role. This was not source-backed contact discovery.

The weekly flow now returns **zero** speculative contacts. It does not invoke the verification waterfall, write generated identities, or export them. Existing persisted contacts are not automatically deleted or reclassified; operators must review legacy records independently.

To restore enrichment, implement an explicitly approved discovery adapter that records an attributable public source URL, observation date, exact supported name/title and organization affiliation, and a separate email provenance/verification status. Unknown fields remain unknown. Domain syntax, MX records, SMTP probes and provider confidence are **not** proof of mailbox ownership or an individual's identity. Respect source terms, robots, privacy, rate limits, and access controls. Do not automate outreach.

Offline checks: `python -m pytest -q tests/test_weekly_enrichment_contact_safety.py`, `ruff check acios/flows/weekly_enrichment.py tests/test_weekly_enrichment_contact_safety.py`. Full Python 3.11/3.12 CI and security checks are required before merge.
