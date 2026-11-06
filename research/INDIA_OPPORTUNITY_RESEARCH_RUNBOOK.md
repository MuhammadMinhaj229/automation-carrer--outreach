# India Opportunity Research Runbook

This document defines the reusable, evidence-led workflow for the ACIOS career intelligence and direct-outreach process. It is a methodology document only. Live organisations, contact records, candidate information and outreach history belong in private Notion/local SQLite stores, never in this public repository.

## 1. Scope and operating principles

Use this workflow when researching government recruitment, publicly funded project roles, or employer opportunities signalled by expansion, funding, a new facility, a major contract, a new product/programme, a leadership initiative or a new location.

- Default geography: Hyderabad and Telangana first; expand across India when the profile and relocation constraints support it.
- Employer opportunity research must be trigger-led. Do not search job boards, job portals or corporate career pages to manufacture a shortlist. A trigger is a reason to investigate an organisation, not proof that a vacancy exists.
- Government recruitment is a separate track. For eligibility and application dates, inspect the issuing authority's official notification and application instructions.
- Start from the candidate's current private resume/profile. Do not assume experience or qualifications that are not evidenced.
- Prefer realistic junior/project/operations roles over inflated senior titles.
- Never promise or infer a 90% selection probability. Scores prioritise research effort; they are not hiring probabilities.
- Keep facts, hypotheses and recommendations clearly separate.

## 2. Required inputs

At the start of each run:
1. Fetch the enabled Notion Skills relevant to the request and follow the applicable skill instructions.
2. Read the latest candidate resume and private candidate profile from the configured private path or user-provided files.
3. Confirm target geography, relocation constraints, role families, date window and any employer/contact exclusions from current instructions.
4. Reuse the existing Opportunity-Led Job Research OS databases and ACIOS local-first SQLite workflow. Do not create a duplicate repository, database or automation architecture.

If the resume/profile is not available, state that the fit assessment is provisional. Do not infer degree percentage, age eligibility, experience duration, certifications or location availability.

## 3. Track A — Government and public-funded recruitment

Search only official or issuing-authority sources for live notices:
- SSC, UPSC, relevant State Public Service Commissions and state departments.
- CAG, CGDA, government audit bodies and public-sector institutions.
- CSIR laboratories, ICMR institutes, IITs, NITs, central universities and government-funded research centres.
- Ministry, department and institutional notices for project-funded contractual appointments.

For every possible role capture:
- Notice number and issuing authority.
- Official publication date, application opening/closing date and time zone.
- Qualification exactly as stated, including eligible degrees/branches and percentage/CGPA rules.
- Age limit and cutoff date, relaxation, experience, language, domicile and category conditions.
- Post title, number of vacancies, pay, tenure, location, appointment type and selection method.
- Official application route and original PDF/notice URL.

Classify each result as:
- **Open and apparently eligible** — all hard gates supported by the supplied evidence.
- **Open but conditional** — a material criterion or document still needs confirmation.
- **Closed / exam underway** — relevant for preparation, not a current application.
- **Not eligible** — one or more hard requirements are not met.
- **Unverified** — official notice or application route not confirmed.

Never report a sanctioned post, old recruitment, exam update, answer key, result or merit list as a newly open vacancy. Distinguish permanent cadre recruitment from project-funded, contractual and temporary work.

For audit roles, separate:
- General graduate examination-based roles (e.g., Auditor / Divisional Accountant pathways).
- Higher-tier audit/accounting roles with additional papers, language or professional expectations.
- Data/statistical roles that may have stronger degree alignment than audit roles.
- Private-sector technology-risk/IT-audit roles, which have a different skill and experience profile.

## 4. Track B — Employer signals and expansion-led opportunity research

Use a rolling window of the most recent 90 days for new signals and a forward window of up to 180 days for planned openings, commissioning, ramp-up or funding milestones. Respect any dates specified by the user.

### Signal categories
- New facility, GCC, office, R&D centre, manufacturing unit or delivery centre.
- Capacity expansion, commissioning, additional production lines or site expansion.
- Funding, grant, investment, strategic partnership or new programme.
- New contract, award, public procurement or long-duration project.
- New product/service, digital transformation, AI/data programme or leadership mandate.
- New region, market entry, acquisition or strategic operating model change.

### Source hierarchy
1. **Primary**: company newsroom, official investor disclosure, exchange filing, government investment portal, ministry/PIB release, institution notice, official project/programme page.
2. **Corroborating**: established financial/news outlet, reputable trade publication, credible local business reporting.
3. **Discovery only**: aggregators, social posts, scraped directories or automated trend trackers.

Use secondary sources to discover a lead, then find the underlying primary announcement. If the original cannot be found, keep the source status as **Verify Source** or **Conflicted** and do not promote the signal to primary-verified.

For every signal store separately:
- Event date (when the event occurred or was announced).
- Publication date (when the source was published).
- Retrieval date/time.
- Exact source URL, publisher, excerpt and content hash where supported.
- Source quality and verification status.
- Whether a number is an announced plan, a current fact or a future target.

Do not convert planned headcount, building capacity or investment into open vacancies. Do not extrapolate hiring quotas from square footage, a capex figure or a new project.

## 5. Qualification and prioritisation

Score each opportunity using the existing ACIOS / Notion dimensions:
- Source credibility and recency.
- Candidate capability fit.
- Operational complexity and plausible need for data/reporting/automation support.
- Budget or investment evidence.
- Decision-maker visibility.
- Prototype feasibility.
- Geographic and relocation fit.

Keep the score on a 0–100 scale consistent with the existing workspace. Explain the components and data quality. The score is an **outreach research priority**, not an estimated probability of selection or an assertion that a job exists.

Use three practical tiers:
- **Prioritise**: strong source, meaningful fit, plausible operational need and feasible contact path.
- **Investigate**: promising signal but missing a source, owner, timing or fit detail.
- **Archive**: low fit, stale/contradicted signal, weak evidence or no reasonable route.

Reject or downgrade leads with discipline mismatch, senior-only requirements, unclear location, stale announcements, no plausible entry-level work or a need for unsupported credentials.

## 6. Organisation dossier and problem hypothesis

For each qualified organisation create or update one account in the existing private Notion organisation database. Include:
- Organisation, site/area, sector, official website and public company profile.
- Verified trigger summary with event and publication dates.
- Growth stage and account status.
- Candidate-fit explanation tied to resume evidence.
- One likely workflow-friction hypothesis, clearly labelled as a hypothesis.
- One small first solution/demo and its measurable outcome.
- Next action and review date.
- At least one primary source; add corroboration if available.

Good candidate-facing role families include research data support, data quality, MIS/reporting, business/operations analysis, junior QA/AI feature testing, project coordination with data responsibilities, platform support and manufacturing/quality reporting. Select the family only when the source and candidate profile support it.

Do not invent internal pain points. Phrase the first conversation as a request to validate a possible workflow problem.

## 7. Decision-maker and contact research

Identify 2–4 relevant professional routes per priority organisation where evidence permits:
1. Process owner or local site/centre leader.
2. Technical evaluator or function/team lead.
3. Hiring/recruitment contact or early-career programme owner.
4. Economic sponsor only where the role is directly relevant.

For each named contact record:
- Current public title, employer and relevant location.
- Why this person is relevant to the particular signal.
- Public professional profile URL and source confirming the title.
- Publicly published work email or business phone only when explicitly published by the organisation or the professional.
- Date last verified, source quality and contact confidence.
- Preferred channel and contact status.

Rules:
- Never guess an email address using a company pattern.
- Never present a personal mobile number or private WhatsApp as a business contact.
- Never infer that a senior executive is the hiring manager merely because they attended an inauguration or appear in a press release.
- A professional-data provider result is a discovery lead until the current title and relevance are checked against a public profile or official source.
- Respect opt-outs, suppression records, privacy law, platform terms and reasonable contact frequency.
- Do not use LinkedIn scraping bots, WhatsApp Web session automation or personal-data harvesting.

## 8. Candidate-specific value proposition and prototype

Map each organisation to one small, verifiable proof-of-work prototype. Examples:
- Research / life sciences: synthetic dataset validation, missingness checks, metadata QA and audit-ready exception report.
- Manufacturing / battery / food: synthetic shift-output, defect, downtime, inventory and traceability dashboard.
- GCC / technology delivery: test-case evidence, data-quality checks, defect trends and release-readiness dashboard.
- Education / skilling: cohort attendance, assessment progress, learner outcomes and placement pipeline.
- Operations / service centre: case ageing, escalation classification, quality sampling and service-level monitoring.

Use synthetic or openly licensed data unless explicit permission is granted to use internal data. Never upload patient, customer, employee, supplier or confidential company data into an unapproved tool.

The prototype should be a small, reviewable demonstration rather than a speculative large product. Measure something concrete (e.g., checks run, records flagged, report time, defects categorised) and disclose the data source.

## 9. Personalised outreach and follow-up

Draft a short, tailored first message:
- Reference one verified trigger and why it matters.
- State the candidate's relevant evidence in one or two lines.
- Offer one specific, small capability/demo related to the organisation.
- Ask for a short conversation or the correct team/contact.
- Avoid claims of solving an unverified internal problem.
- Do not mass-send generic CVs.

Prepare drafts in the private Notion/Gmail workflow. The user reviews recipients, claims, attachments and wording before any message is sent. Keep bulk dispatch disabled. Follow up once after roughly 3–5 business days, then once more only where appropriate; stop on no-contact or opt-out.

## 10. Tooling and data boundaries

Use already connected tools first:
- **Web search / Browser**: discover official announcements and inspect source pages.
- **Notion MCP**: private research cockpit for signals, accounts, people, outreach, prototypes and research reports.
- **GitHub MCP**: version-controlled, public-safe workflow code and generic templates. Use a feature branch and pull request.
- **ACIOS Python CLI + FastMCP + SQLite**: local-first source provenance, claim review, account dossiers, suppression, draft validation and audit trail.
- **Clay / Apollo**: optional people/company discovery only within the connected plan's entitlements. Do not spend paid credits or enable paid enrichment without approval. Revalidate provider data.
- **Gmail**: stage reviewable drafts only; human approval and manual sending remain required.
- **Firecrawl / Exa / Playwright / feed readers**: optional discovery or extraction adapters where the target permits it. Respect robots.txt, terms, rate limits, authentication boundaries and privacy requirements.

Public GitHub must not contain candidate CVs, email/phone, private candidate profiles, raw lead/contact exports, suppression lists, browser sessions, credentials, local SQLite files or private outreach notes. Those remain in private local storage / private Notion. Do not reintroduce MongoDB or a cloud database unless the user explicitly changes architecture.

## 11. Repeat-run outputs and completion checks

Each run should produce:
1. A short executive brief with an explicit research date and geographic scope.
2. A government/public-funded role table with exact eligibility and status.
3. A trigger-led organisation shortlist with primary-source evidence.
4. A private decision-maker directory with public contact routes and confidence labels.
5. One candidate-specific value proposition and a proposed prototype per top account.
6. Outreach drafts awaiting human review.
7. A list of facts requiring confirmation and rejected leads with reasons.
8. A short improvement log recording what changed in the method.

Before reporting completion, verify:
- All links open and the source supports the associated claim.
- Event date and publication date are not conflated.
- Current eligibility and deadline were checked against the original notice.
- Hypotheses are labelled; no vacancy or hiring probability is fabricated.
- Duplicate organisations/contacts were checked before insertion.
- All private data stayed out of public GitHub.
- Notion writes and GitHub branch/PR results were read back and confirmed.

## 12. Suggested prompt

"Run the India Opportunity Research workflow using my latest resume and enabled Notion skills. Check fresh government/public-funded notices separately from expansion- and funding-led employer signals. Prioritise Hyderabad/Telangana, then include relevant India-wide opportunities. Do not use job boards or company career pages to build the employer shortlist. Verify primary sources, update the existing private Notion signal/account/contact databases, map relevant public professional contacts, recommend one proof-of-work idea per top lead, and prepare outreach drafts for my review. Do not send messages or spend paid enrichment credits."
