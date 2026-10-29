# ACIOS Agent Operating Protocol

ACIOS is a local-first career intelligence research and outreach workbench. The default runtime is the Python CLI and FastMCP server, with SQLite storage. Do not assume that a frontend, hosted API, worker service, cloud database, or deployment platform is required.

## Working rules

1. Read README.md and docs/LOCAL_FIRST_ARCHITECTURE.md before changing architecture.
2. Inspect source and tests before changing behavior. Never claim tests were run unless the execution result is available.
3. Make changes on a feature/refactor branch; do not rewrite main directly.
4. Keep adapters replaceable. Do not add a package to core dependencies when it can be an optional integration.
5. Add a test for each bug or guardrail changed. Prefer deterministic mocks and fixtures; tests must not contact real prospects.
6. Use evidence-backed facts only. Every organization trigger and contact claim needs a source URL and relevant date. Represent unknown and conflicting data explicitly.
7. Never invent names, job titles, emails, phone numbers, headcounts or employment probabilities.
8. Candidate experience and signature data must come from the private configured profile, not from invented example biographies.

## Outreach safety contract

- Suppression checks run before drafting/staging and again at any execution boundary.
- Email verification results are probabilistic; MX/SMTP reachability alone cannot prove mailbox ownership.
- Draft validation is not human approval.
- Approval is tied to an immutable snapshot of recipient, subject, body and attachment identity. Editing any field invalidates approval.
- Keep bulk email dispatch disabled in the local workflow. Stage reviewable drafts and let the user send them manually.
- Do not delete or expunge unrelated Gmail Drafts.
- Do not request a Gmail App Password or other secrets in chat. Guide the operator to local environment/OS credential storage or OAuth.
- Never commit .env, config/candidate_profile.yaml, resumes, data exports, local databases, suppression lists, or browser session state.
- Do not automate prohibited LinkedIn/Instagram/X activity, or use WhatsApp Web session bots. Use permitted official APIs or manual draft links.

## Quality gate

Run from the repository root:

~~~bash
ruff check acios tests --select E4,E7,E9
pytest -q
pip-audit -r requirements.txt
bandit -r acios/core acios/models -ll
~~~

The full legacy test set may require optional extras, documented in README.md. Report exact test command and results; distinguish static inspection from executed validation.

## Operating sequence

1. Map the current code path and related tests.
2. State the invariant being protected or capability being added.
3. Make the smallest maintainable change.
4. Add regression tests, including failure/negative cases.
5. Run applicable quality checks or use GitHub Actions if local execution is unavailable.
6. Review the complete diff for data loss, security regressions, secrets and stale documentation.
7. Commit on a branch and open a pull request with a clear test report.
