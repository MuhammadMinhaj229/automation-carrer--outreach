# Deep Codebase Audit Report: ACIOS

## 1. Executive Summary
The **Autonomous Career Intelligence & Outreach Operating System (ACIOS)** is an advanced open-source repository designed to automate job searching through intelligence-gathering rather than mass-applying. It identifies company expansions, finds decision-makers, verifies emails, and orchestrates highly personalized, AI-generated email drafts for review before dispatch.

## 2. Architecture & Tech Stack
The project follows a decoupled, modular architecture:
- **Frontend (Cockpit):** Built with Next.js in the `web/` directory. Acts as the UI and an API proxy.
- **Backend API:** Built with FastAPI (`acios/api.py`), exposing modular REST and MCP endpoints.
- **Worker/Job Queue:** A Redis-backed durable worker (`acios/worker.py`, `acios/core/job_queue.py`) for pacing email dispatch and long-running discovery tasks.
- **Database:** Uses MongoDB Atlas for production persistent storage and SQLite (`data/acios.db`) for local development and testing.
- **Discovery Pipeline:**
  - **Tab 1 (Discovery):** Scans for company expansions using growth signals (`GrowthSignalScanner`).
  - **Tab 2 (Audit):** Hunts for organizational domains and decision-makers (`LinkedInHunter`).
  - **Tab 3 (Dossier):** Extracts career histories and intelligence (`ExecutiveIntelligenceFinder`).
  - **Tab 4 (AI Copilot):** Generates 100-160 word personalized emails (`AICopilotWriter`).
  - **Tab 5 (Dispatch):** Manages safe SMTP dispatch with attachments and suppression checks (`SMTPDispatcher`).

## 3. Security & Safety Controls
ACIOS includes strict safeguards to maintain domain reputation and prevent automated spam:
- **Suppression Engine:** `acios/core/suppression.py` rigorously blocks known bounced or suppressed emails.
- **Word Count Validator:** Drafts strictly require 100-160 words to avoid rambling AI text.
- **Buzzword Rejection:** Rejects common marketing clichés.
- **Idempotency & Tamper Detection:** Hashing mechanisms invalidate approvals if a draft is tampered with before sending.

## 4. Identified Issues & Test Failures
During the audit, the test suite (`pytest`) revealed several issues:
1. **Missing Data Dependencies in Tests:**
   - `tests/test_5tab_pipeline.py` fails because assertions rely on hardcoded, live network responses or pre-seeded database records (e.g., expecting "Hema Energy" to be verified or return 2 milestones).
   - `tests/test_importer_and_exporter.py` fails because it asserts the exported Excel file contains `\>= 320` rows and the exported markdown contains specific content, assuming a populated `data/acios.db` exists.
2. **Missing Local Setup Directories:**
   - `test_safety_controls.py` initially failed because the directory `data/suppression/` and file `master_suppression.json` did not exist by default. Creating the directory and an empty JSON structure resolved this test failure.
3. **Environment Setup:**
   - The `.env` file does not exist out-of-the-box (only `.env.example`). The application gracefully handles this in some places, but tests shouldn't require it if they are intended to run in CI.

## 5. Recommendations
- **Test Isolation & Mocking:** Tests should use `pytest` fixtures with in-memory SQLite databases or mocked data instead of assuming `data/acios.db` is pre-populated with hundreds of rows. Network calls in `LinkedInHunter` and `ExecutiveIntelligenceFinder` should be mocked (using `responses` or `pytest-httpx`) to prevent intermittent failures.
- **Directory Initialization:** The application (or setup script) should automatically initialize required paths like `data/suppression` to prevent startup or test crashes.
- **Documentation:** The `README.md` correctly mentions keeping runtime files under `data/`, but a `make setup` or similar bootstrap command would vastly improve developer onboarding.
