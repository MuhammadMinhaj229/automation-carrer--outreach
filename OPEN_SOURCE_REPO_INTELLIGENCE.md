# 🛠️ ACIOS Open-Source Tool & Repository Intelligence Catalog
## Verified, Production-Grade Repositories & APIs for Career Intelligence & Automation

---

## Tool 1: Global Organization Grounding & Discovery

| Repository / API | GitHub / Official URL | Stars | License | Core Capability | Integration Pattern in ACIOS |
|---|---|---|---|---|---|
| **Wikidata SPARQL (`qwikidata` / `SPARQLWrapper`)** | [Wikidata Query Service](https://query.wikidata.org/) | N/A (W3C Standard) | CC0 (Public Domain) | Global knowledge graph querying millions of registered enterprises by country code (`P17`), industry sector (`P452`), and inception date (`P571`). | Python script executing SPARQL queries. Zero API cost, unlimited requests. |
| **OpenCorporates API (`openc/opencorporates-python`)** | [OpenCorporates API](https://api.opencorporates.com/) | 250+ ⭐ | Open Database License (ODbL) | The largest open database of companies in the world (220M+ entities across 140 jurisdictions). Legal company names, status, and jurisdiction. | REST API client for company verification and registration cross-checking. |
| **ROR (Research Organization Registry) API** | [ror-community/ror-api](https://github.com/ror-community/ror-api) | 120+ ⭐ | CC0 1.0 (Public Domain) | 105,000+ research institutes, university labs, and government R&D bodies (KAUST, SQU, Qatar University, CGIAR). | Fast REST API (`/organizations?query=...`) without authentication or rate limits. |
| **GLEIF (Global Legal Entity Identifier)** | [GLEIF API](https://www.gleif.org/en/lei-data/gleif-api) | N/A (Global Standard) | CC0 (Public Domain) | Authoritative global database of legal entities (LEIs) covering industrial facilities, holdings, and joint ventures. | REST API search endpoint resolving official corporate umbrellas. |

---

## Tool 2: Signal Scraping & Breakthrough Filtering

| Repository | GitHub URL | Stars | License | Core Capability | Integration Pattern in ACIOS |
|---|---|---|---|---|---|
| **Crawl4AI** | [unclecode/crawl4ai](https://github.com/unclecode/crawl4ai) | 20,000+ ⭐ | Apache-2.0 | High-performance, asynchronous web crawler designed specifically for LLMs. Handles JavaScript rendering, headless Chromium, anti-bot mitigation, and extracts clean Markdown. | Crawls company `/newsroom`, press pages, and regional news (Zawya, Wamda) to extract raw project announcements. |
| **GDELT 2.0 Global Knowledge Graph (`gdeltdoc`)** | [alex9smith/gdeltdoc](https://github.com/alex9smith/gdeltdoc) | 400+ ⭐ | MIT | Monitors worldwide broadcast, print, and web news globally in 100+ languages every 15 minutes. | Real-time news filter searching for expansion keywords (`pilot plant`, `seed funding`, `facility expansion`). |
| **GLiNER** | [urchade/gliner](https://github.com/urchade/gliner) | 5,200+ ⭐ | Apache-2.0 | Generalist Named Entity Recognition model using bidirectional transformers. Zero-shot extraction of arbitrary entity types. | Ingests news text and extracts: `[Funding Amount]`, `[Facility Location]`, `[Partner Org]`, `[Technology Name]`. |
| **Trafilatura** | [adbar/trafilatura](https://github.com/adbar/trafilatura) | 4,600+ ⭐ | Apache-2.0 | Lightweight Python package to scrape web text, stripping ads, navigation bars, and boilerplate. | Fast fallback HTML text stripper for non-JS news feeds. |

---

## Tool 3: Deep OSINT & Company Journey Reconstruction

| Repository | GitHub URL | Stars | License | Core Capability | Integration Pattern in ACIOS |
|---|---|---|---|---|---|
| **GPT-Researcher** | [assafelovic/gpt-researcher](https://github.com/assafelovic/gpt-researcher) | 16,500+ ⭐ | Apache-2.0 | Autonomous agent that aggregates 20+ web sources, cross-checks facts, and writes cited research dossiers. | Produces the deep background dossiers on target companies (origin story, patent background, pilot results). |
| **Wayback Machine CDX API** | [internetarchive/wayback-cdx-server](https://github.com/internetarchive/wayback-cdx-server) | 1,200+ ⭐ | AGPL-3.0 | Indexes historical snapshots of websites back to their inception. | Traces early product versions, founder changes, and original pilot announcements from previous years. |
| **TheHarvester** | [laramies/theHarvester](https://github.com/laramies/theHarvester) | 12,000+ ⭐ | GPL-2.0 | Passive OSINT tool gathering corporate subdomains, public employee names, and public PGP keys. | Passive domain footprinting to locate corporate domains, secondary websites, and email routing patterns. |
| **Compliant LinkedIn Gateway** | Built-in Python Google/Bing OSINT Dorker | Custom | MIT | Deterministic query generator (`site:linkedin.com/in "Company Name" "Title"`) that parses public snippets. | Avoids account-banning scraping bots; provides direct clickable URLs for manual networking. |

---

## Tool 4: Decision-Maker Contact Discovery & Deliverability

| Tool / Repository | Official URL / GitHub | Stars | License | Core Capability | Integration Pattern in ACIOS |
|---|---|---|---|---|---|
| **Hunter.io API & MCP** | [hunter.io/api-documentation](https://hunter.io/api-documentation) | Official API | Commercial / Free Tier (25 searches/mo) | Domain pattern search (`{first}.{last}`), direct Email Finder, and SMTP email verifier. | Primary commercial enrichment endpoint with native MCP support. |
| **Reacher** | [reacherhq/check-if-email-exists](https://github.com/reacherhq/check-if-email-exists) | 5,500+ ⭐ | AGPL-3.0 / Commercial | Open-source, self-hostable email verification server written in Rust. Performs real-time DNS MX lookups and connects via SMTP port 25 without sending mail. | Zero-cost self-hosted email verifier checking inbox existence before sending. |
| **Email Permutator Engine** | Built-in RFC-822 Generator | Custom | MIT | Algorithmic candidate address generator (`first@`, `first.last@`, `flast@`, `first_last@`). | Generates candidate emails for domain-verified companies to test against Reacher/Hunter. |
| **Master Suppression Engine** | Custom JSON/SQLite Ledger | Custom | MIT | Real-time suppression checker containing 1,455+ previously bounced or opted-out addresses. | Hard stop: blocks any message whose recipient appears on the suppression list. |

---

## Tool 5: AI Brain & Hyper-Personalized Email Generator

| Repository | GitHub URL | Stars | License | Core Capability | Integration Pattern in ACIOS |
|---|---|---|---|---|---|
| **Instructor** | [567-labs/instructor](https://github.com/567-labs/instructor) | 7,100+ ⭐ | MIT | Structured LLM outputs using Pydantic models. Supports automatic retries on validation errors. | Enforces strict word count (100–160 words), subject line constraints, and buzzword rejection. |
| **PydanticAI** | [pydantic/pydantic-ai](https://github.com/pydantic/pydantic-ai) | 8,500+ ⭐ | MIT | Type-safe agent framework from the creators of Pydantic. Validates tool calling and agent responses. | Builds the career-intelligence reasoning agent that selects candidate experience based on recipient role. |
| **LiteLLM** | [BerriAI/litellm](https://github.com/BerriAI/litellm) | 16,000+ ⭐ | MIT | Universal proxy routing requests across Gemini, Claude, OpenAI, Bedrock, or local Ollama models. | Single interface allowing zero-downtime provider switching and budget tracking. |

---

## Tool 6: Gmail Integration, Dispatcher & Safety Engine

| Component | Standard / Technology | Role in System | Key Safety Controls |
|---|---|---|---|
| **IMAP Drafts Engine** | RFC-3501 IMAP `APPEND` with `\Draft` flag | Uploads pre-addressed emails with clickable HTML signatures directly into `[Gmail]/Drafts`. | Non-destructive; requires human operator to open Gmail, inspect, attach CV, and send. |
| **SMTP Jitter Dispatcher** | RFC-5321 SMTP with SSL / TLS | Dispatches approved emails over port 465 with randomized intervals (60–180 seconds). | Protects sender domain reputation; mimics human sending cadence. |
| **IMAP Reply-Guard** | Python `imaplib` Inbox Scanner | Checks recipient domain in `INBOX` before sending follow-ups. | Automatically halts subsequent sequence emails if a human reply is detected. |
| **Human Approval Gate** | CLI / Streamlit UI Modal | Renders full email body, recipient evidence, and verification status for explicit approval. | Zero autonomous bulk sending; requires deliberate user consent per email. |
