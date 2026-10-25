# GCC Outreach System — Practical Automation Architecture

**Purpose:** Find the right person at each of the 24 GCC organizations, validate a professional work email, draft genuinely individualized outreach, and send messages one by one only after the user approves each exact email. The LinkedIn networking lane is intentionally manual because the available LinkedIn integration only searches people and LinkedIn prohibits unauthorized bots/scraping/automated engagement.

## Recommended stack

1. **Public research:** official organization pages, project releases, academic profiles, Exa/web search.
2. **Professional-profile search:** the LinkedIn people-search integration. Use direct profile links from the `LinkedIn & Mentor Map` sheet; where no exact match was returned, the sheet provides a LinkedIn people-search URL instead of guessing a profile.
3. **Contact enrichment:** Apollo MCP, then Clay's provider waterfall if authorized, or Hunter.io Email Finder/Verifier as an independent check. Use work emails only. Preserve the provider, returned status, source, and date.
4. **Workflow runner:** n8n is the stronger choice when MCP endpoints, HTTP APIs, approval stages, retries, and logs matter. Make.com is also a reasonable lower-code choice, but may need HTTP modules or a bridge for providers that do not have a native module.
5. **Review queue:** Google Sheets/Airtable or the provided Excel workbook. Keep one record per person and a separate audit row per send attempt.
6. **Email sending:** Gmail API via OAuth in n8n, or an explicitly connected and reviewed Apollo sending mailbox. No password or API key should be pasted into a prompt.
7. **LinkedIn connection activity:** manually open the profile, review it, and click Connect/Follow yourself. The agent may prepare a brief connection note and record a manual task; it must not automate LinkedIn clicks or invitations.

## Antigravity MCP setup

Antigravity supports remote MCP servers. Its current documentation describes configuring servers in `~/.gemini/config/mcp_config.json`, then opening Settings → Customizations / MCP Servers, refreshing the list, and authenticating each server where required. On Windows, the home-directory equivalent is generally under your user profile; use the path shown by your installed Antigravity version.

Official setup references:

- Antigravity MCP: https://antigravity.google/docs/mcp
- Apollo MCP: https://docs.apollo.io/docs/apollo-mcp
- Clay MCP: https://university.clay.com/docs/connect-to-clay-mcp
- Hunter API/MCP: https://hunter.io/api-documentation.md

Example remote server entries (placeholders only; do not commit actual secrets to a project or share them in chat):

```json
{
  "mcpServers": {
    "apollo": {
      "serverUrl": "https://mcp.apollo.io/mcp"
    },
    "clay": {
      "serverUrl": "https://api.clay.com/v3/mcp"
    },
    "hunter": {
      "serverUrl": "https://mcp.hunter.io/mcp",
      "headers": {
        "X-API-KEY": "YOUR_HUNTER_API_KEY"
      }
    }
  }
}
```

Notes:
- Apollo's remote MCP uses Streamable HTTP and OAuth. The account plan, workspace permissions, eligibility, and remaining credits still control which actions work.
- Apollo documents that enrichment actions use credits. Require approval for any credit-consuming tool and show the total maximum cost before a batch.
- Clay's MCP connection and available functions are governed by the workspace plan/admin settings and credit controls.
- Hunter's MCP needs an authorized API key. Use a local secret-management approach and never upload the key to GitHub or include it in a shared markdown document.
- These endpoints are for configuration in Antigravity, not proof that a service is already authenticated in that separate environment.

## One-run workflow for all 24 organizations

### Stage 1 — Load and deduplicate
- Read the existing master workbook, forensic audit, and email-draft file.
- Keep all 24 organization/project records and their source URLs.
- Deduplicate people by LinkedIn URL plus company; deduplicate email records by normalized work email. Do not treat joint-venture partners as one organization if the project owners differ.

### Stage 2 — Find the people
For each organization, search at least these role types:
- **Closest-to-work contact:** product, data, QA/testing, engineering, operations, research, project controls, commissioning, or programme lead.
- **Mentor/technical guide:** researcher, PI, technical leader, senior individual contributor, product manager, or experienced project lead whose public work overlaps the user's skills.
- **Referral sponsor:** founder, CEO, GM, centre/programme director, or research director, used when a direct functional lead cannot be identified.

Do not claim a person is interested in mentoring. Score only the *fit of their role* as a possible adviser/referral route. Prefer one primary person per organization and one backup only where there is a distinct reason.

### Stage 3 — Verify current identity and role
- Start from the LinkedIn profile returned by search, then check the person's current role against an official organization page, institutional page, project announcement, or publication.
- If several people share a name, keep a LinkedIn search link rather than picking one arbitrarily.
- If a person is no longer with the organization, mark them as an alumni/mentor route only if a valid current profile confirms that; do not use an old title as current.
- Never compile a claim that the list includes every employee. This is a targeted list of decision-makers, project owners and potentially useful professional contacts.

### Stage 4 — Find and verify the work email
- Search Apollo using the verified person plus company domain; if global people search is unavailable on the current Apollo plan, use the LinkedIn profile and official company domain to run the available contact-enrichment path only after approval.
- If available, use Clay to run a provider waterfall. Use Hunter Email Finder/Domain Search to find candidate addresses and Hunter Email Verifier (or another reputable verifier) to check deliverability.
- Prefer first-party published emails and valid institutional addresses; retain direct-source URLs. An address listed in an old publication may not be current.
- Never infer an email from a naming pattern and label it “verified.” Distinguish **published**, **provider-reported**, **verified/valid**, **accept-all**, **unknown**, and **invalid**.
- Use work emails, not private personal emails or phone numbers, unless the individual explicitly publishes a professional contact route for that purpose.
- Confirm the total number of credit-consuming enrichments and the maximum credit cost before making the calls. Enrich only the chosen primary contacts first.

### Stage 5 — Draft every email before any sending
- Complete the research/drafting pass for all 24 organizations before beginning any sends.
- Each email must contain a verified, concrete project observation; a short and truthful personal connection to PHFI research data/web support, Ejada Labs Sanad AI feature testing/modifications, and relevant client work; one genuine question; and a low-pressure close.
- Do not claim an open role unless a current source shows one. Do not invent pain points, outcomes, or a relationship with the recipient.
- Avoid sending multiple cold emails to the same organization simultaneously. The primary recipient gets the first note; a backup is only used later if there is a specific reason or referral.

### Stage 6 — Human approval and sending
For each email, one at a time, display:
1. Recipient's name, title, organization, LinkedIn URL, and confidence.
2. Exact destination email, source, verification label, and verification date.
3. Subject and full message body.
4. Any resume/portfolio attachment planned.

Ask the user to choose **SEND THIS EMAIL**, **EDIT**, or **SKIP**. Only a clear approval for that exact message permits sending. If edited, show the final revision again. Send one message only, verify the provider's success status, record the provider message ID/time, and then show the next message. Never send a batch, multi-recipient email, or an automated sequence without separate consent. If address is unverified or sending is not authenticated, mark it blocked and continue with other safe work.

### Stage 7 — LinkedIn networking lane (manual)
- Generate a short personalized connection note for each selected person, using the same project fact as the email but not duplicating the whole email.
- Provide a direct LinkedIn profile URL or search-result URL in the workbook.
- Add a `Connection status` field such as `Not reviewed`, `Profile checked`, `Invite sent manually`, `Accepted`, `Message sent`, `No response`, `Do not contact`.
- The user personally clicks Connect/Follow and sends the invitation. Do not automate this with scripts, browser extensions, headless browsers, or unofficial LinkedIn MCPs. LinkedIn's official Invitations API is restricted to approved partners, and unauthorized bots/automation can result in account restrictions.
- If the user wants follow-up reminders, create manual tasks/reminders outside LinkedIn; do not auto-message the person.

## Required output files

- `GCC_Master_Intelligence.xlsx` — organization tracker, LinkedIn & mentor map, chosen contacts/email evidence, email drafts, approval/send log, unresolved items, and automation stack.
- `GCC_All_Email_Drafts.md` — all 24 drafts with source evidence and contact confidence.
- `GCC_Connection_Notes.md` — manual connection note per selected person with direct profile URL and status.
- `GCC_Unresolved_Contacts.md` — missing/ambiguous person, profile, email, source, and next lookup.
- `GCC_Outreach_Run_Summary.md` — exact counts of organizations researched, direct profiles found, search-only profiles, verified work emails, drafts prepared, messages approved/sent/skipped/blocked.

## Safety and quality rules

- Do not scrape LinkedIn or use unofficial automation to send invitations, follow, like, message, or collect profile data in bulk.
- Respect API terms, plan limits, credit budgets and organizational privacy rules.
- Keep contact sourcing limited to business-relevant professional information.
- No guessed emails, no claims of mentoring interest, no invented open jobs, and no inflated “verified” counts.
- Store a source and confidence per person/email. Log user approvals, edits, skips, send outcomes and opt-outs.
- Stop contacting anyone who declines or asks not to be contacted.
