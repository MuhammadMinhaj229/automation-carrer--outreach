# Persistent Work Session and Resume Protocol

This protocol exists to prevent opportunity research and outreach work from being restarted, duplicated, or reported as complete when only part of it has been done.

## Important execution boundary

A ChatGPT conversation is not a continuously running background worker. A response boundary does not leave the assistant running in the background. The ACIOS worker is a separate local application process; it only processes the job types registered in its code while that process is running. It does not continue a ChatGPT conversation or recover its hidden reasoning state.

The current ACIOS worker registers a growth-signal scan handler and a disabled outreach-send handler. It is not a generic assistant-session resume engine. Do not describe it as one.

## Source-of-truth split

- **Private Notion workspace:** user-visible operational checkpoint, organisation dossiers, contact directory, outreach stages, prototype plans and research reports.
- **Local ACIOS SQLite ledger:** detailed source provenance, claim reviews, local activity history, suppressions and validated draft/approval snapshots.
- **Public GitHub:** generic workflow code, reusable templates and documentation only. Never commit CVs, personal contact details, raw prospect exports, suppression lists, private outreach messages, browser state, credentials or local databases.

## Required checkpoint fields

At the end of each bounded work unit, persist:

1. Workstream name and checkpoint timestamp (include timezone).
2. Current phase and exact status.
3. Completed outputs, with links/IDs to the verified artefacts.
4. In-progress item and its last verified state.
5. Blockers, uncertainty and failed/retried tool actions.
6. External actions taken: sent messages, submitted applications, published changes, or an explicit **none**.
7. Git repository, branch, commit, pull request and test status when relevant.
8. The next exact action to execute; avoid vague instructions such as "continue research".

A task is only complete when its resulting artefact can be opened or a tool result verifies the action.

## Bounded execution loop

1. **Resume:** read the latest private checkpoint and the linked artefacts before searching, drafting or coding.
2. **Reconcile:** inspect the current Notion rows and GitHub branch state. Do not assume the previous checkpoint is still current.
3. **Select one work unit:** e.g. verify one vacancy PDF, qualify one organisation, validate one contact, or implement one prototype milestone.
4. **Execute:** use the smallest practical batch and retain source URLs, publication/event dates and evidence status.
5. **Persist:** write the result to its correct Notion database or GitHub feature branch immediately after validation.
6. **Verify:** read back the created/updated page or inspect the commit, diff and tests.
7. **Checkpoint:** update the private status page with new counts, artefact links, remaining work and the next exact action.
8. **Report:** provide a user-visible progress note. Do not silently perform a long sequence and return only a final summary.

## Outreach safety gate

- A draft is not an approval.
- An approval applies only to the exact reviewed recipient, subject, body and attachment snapshot.
- Re-check suppression and recipient/channel evidence before any execution boundary.
- Never guess email addresses or private contact numbers.
- Keep social-network outreach manual unless an official, permitted API is explicitly authorised.
- Do not send anything until the user has reviewed and explicitly approved the specific message.
- The ACIOS local-first workflow keeps bulk dispatch disabled.

## Reporting language

Use explicit states:

- **Researched:** a source was found and recorded.
- **Verified:** the relevant primary source supports the exact claim.
- **Drafted:** content exists but is not approved.
- **Approved:** the human review gate has been passed for the exact content snapshot.
- **Sent / Submitted:** only after a tool result or external confirmation establishes it.
- **Built:** code exists and the required tests/demo run were verified.
- **Planned:** a specification exists; no implementation should be implied.

Never convert a plan, a score, a search result or a draft into a completed application, sent message, prototype or hiring probability.

## Session-end checkpoint template

Use this compact template in the private status page:

- **Done:** exact completed artefacts and links.
- **In progress:** current item and current state.
- **Blocked / uncertain:** the missing evidence, permission, credential or decision.
- **Not done:** explicit list of external actions not taken.
- **Next action:** one precise operation that can be started immediately.
- **Validation:** tests run, tests not run, commits and verification status.
