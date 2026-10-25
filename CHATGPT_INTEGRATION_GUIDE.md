# ACIOS ChatGPT & Remote AI Agent Integration Guide
### Connect OpenAI ChatGPT (Mobile & Desktop), Claude, and Remote MCP Clients to Your Production Pipeline

---

## 1. Executive Summary & Architecture

The **Career Intelligence & Outreach Operating System (ACIOS)** provides an enterprise-grade AI integration layer designed to allow **ChatGPT** (via OpenAI Custom GPT Actions) and **Remote Agents** (via Model Context Protocol - MCP) to control the entire 8-phase cold outreach lifecycle directly from a mobile phone, tablet, or web browser.

```
┌────────────────────────────────────────────────────────┐
│             ChatGPT iOS / Android / Desktop            │
│         (Voice Mode, Chat Commands, Custom GPT)        │
└──────────────────────────┬─────────────────────────────┘
                           │ HTTPS (OpenAPI Actions / MCP)
                           ▼
┌────────────────────────────────────────────────────────┐
│            Vercel Edge & Serverless Next.js            │
│  ├─ /api/openapi.json (OpenAPI 3.1.0 Endpoint Schema)  │
│  ├─ /api/mcp          (JSON-RPC 2.0 MCP Protocol Hub)  │
│  └─ /api/*            (Reverse Proxy to Backend)       │
└──────────────────────────┬─────────────────────────────┘
                           │ Internal TLS / API Key
                           ▼
┌────────────────────────────────────────────────────────┐
│              ACIOS Python Intelligence Core             │
│  ├─ 4-Tier 0% Bounce Verifier (DNS MX + SMTP Probe)    │
│  ├─ IMAP TLS Draft Engine (Master PDF Resume Stager)   │
│  ├─ Rate-Limited Sequential SMTP Dispatch Queue        │
│  └─ IMAP Inbox Sentinel & Reply Detection Engine       │
└────────────────────────────────────────────────────────┘
```

### Why This Architecture?
- **Zero-Leak Security**: ChatGPT **never** sees or stores your Gmail App Password or sensitive credentials. All secrets remain strictly isolated in your deployment environment variables (`.env` or Vercel Secrets).
- **Mobile First**: You can tap "Voice Mode" in the ChatGPT iPhone/Android app while walking, say *"Check my outreach status and stage approved drafts"*, and ChatGPT triggers the tools on your server.
- **Dual-Standard Compatibility**: Supports both **OpenAI Actions** (`/api/openapi.json`) and **Model Context Protocol** (`/api/mcp`).

---

## 2. Setting Up Your Custom GPT in ChatGPT (Step-by-Step)

Follow these exact steps to create your private, mobile-ready ACIOS Career Assistant in ChatGPT.

### Step 1: Open GPT Builder
1. Open [ChatGPT](https://chatgpt.com/).
2. In the left sidebar, click **Explore GPTs** -> **+ Create** (top right).
3. Select the **Configure** tab.

### Step 2: Basic Profile Information
- **Name**: `ACIOS Career Outreach Agent`
- **Description**: `Autonomous career intelligence copilot for market discovery, verified cold pitches, and mailbox monitoring.`
- **Instructions**: Copy and paste the exact system instructions below:

```text
You are ACIOS (Autonomous Career Intelligence & Outreach Operating System), an executive career strategist and cold outreach agent.

Your mission is to assist Mohammed Minhaj Mahmood in discovering high-growth enterprise opportunities, sieving corporate decision-makers, validating 0% bounce deliverability, staging personalized pitches into Gmail with the master PDF resume attached, and executing paced outreach dispatches.

Core Rules & Operational Conduct:
1. Always check system telemetry (getSystemOverview or getSystemStats) before recommending dispatch actions.
2. Deliverability Protection: Never send emails to unverified contacts. Always verify deliverability using verifyEmailDeliverability before staging or queuing.
3. Master PDF Resume: Ensure the candidate's master PDF resume is verified and attached during Gmail draft syncs.
4. Tone & Style: Executive, concise, data-driven, and authoritative. Avoid fluff and emojis.
5. Pacing Safeguards: Cold email dispatches must maintain a minimum 60-second cooldown interval between messages to protect domain reputation.
6. Mobile Brevity: When reporting via mobile chat or voice, summarize key metrics: Total Contacts, Verified Deliverable %, Drafts Ready, Dispatched Count, and Inbound Replies.
```

### Step 3: Configure Capabilities & Actions
1. Under **Capabilities**, enable **Web Browsing** and **Code Interpreter**.
2. Scroll to the bottom and click **Create new action**.
3. In the Action Editor:
   - **Authentication**: Select `None` (or `API Key` with `Bearer` if you have configured `ACIOS_API_KEY`).
   - **Schema**: Click **Import from URL** and enter your deployed URL:
     ```
     https://<your-vercel-domain>.vercel.app/api/openapi.json
     ```
     *(Or if running locally with a cloudflared/ngrok tunnel: `https://<tunnel-id>.trycloudflare.com/api/openapi.json`)*
   - Click **Import**.
4. ChatGPT will automatically parse and display all 8 native actions:
   - `getSystemOverview`
   - `getSystemStats`
   - `getSettings`
   - `updateSettings`
   - `verifyEmailDeliverability`
   - `syncGmailDrafts`
   - `dispatchQueue`
   - `auditMailbox`
5. **Privacy Policy**: Enter `https://<your-vercel-domain>.vercel.app/api/system/overview` (or your personal website URL).

### Step 4: Save and Test
1. In the top right corner, click **Save** -> Select **Only me** (Private).
2. Open the preview pane or the ChatGPT mobile app, navigate to your Custom GPT, and test!

---

## 3. Remote Model Context Protocol (MCP) Setup

For developers using **Cursor IDE**, **Anthropic Claude Desktop**, **Continue.dev**, or any MCP-compatible agent framework, ACIOS exposes a native HTTP JSON-RPC 2.0 endpoint at `/api/mcp`.

### Claude Desktop Configuration
Add the following to your `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "acios-pipeline": {
      "url": "https://<your-vercel-domain>.vercel.app/api/mcp",
      "headers": {
        "Authorization": "Bearer YOUR_ACIOS_API_KEY_IF_CONFIGURED"
      }
    }
  }
}
```

### MCP Tool Registry
The endpoint implements standard JSON-RPC 2.0 with the following registered tools:
| Tool Name | Action | Parameters |
| :--- | :--- | :--- |
| `get_system_overview` | Fetch live outreach metrics, candidate status, and audit events | None |
| `get_system_stats` | Quick count of organizations, contacts, signals, and staged drafts | None |
| `get_settings` | Retrieve candidate coordinates and credential status | None |
| `update_settings` | Update candidate identity or Gmail credentials | Candidate profile JSON |
| `verify_email_deliverability` | 4-tier zero-bounce socket & MX verification | `{ email: string }` |
| `sync_gmail_drafts` | Purge stale drafts and stage new drafts with PDF resume | None |
| `dispatch_queue` | Launch sequential SMTP queue with delay cooldown | `{ interval?: integer }` |
| `audit_mailbox` | Scan IMAP inbox for prospective replies and bounce notices | None |

---

## 4. Production Deployment Architectures

You have two scalable deployment options:

### Option A: Vercel Frontend + Render / Railway Backend (Recommended)
1. **Frontend (Vercel)**:
   - Connect your GitHub repository to [Vercel](https://vercel.com).
   - Set Root Directory to `web`.
   - Add Environment Variable:
     - `ACIOS_BACKEND_URL`: URL of your deployed Python backend (e.g. `https://acios-backend.up.railway.app`).
     - `ACIOS_API_KEY`: *(Optional)* Secret token for authenticating ChatGPT Actions.
2. **Backend (Railway / Render / Fly.io / GCP Cloud Run)**:
   - Deploy the root repository using the included `Dockerfile` or Python runtime.
   - Set Environment Variables:
     - `GMAIL_USER`: Candidate email address.
     - `GMAIL_APP_PASSWORD`: 16-character Google App Password.
     - `CANDIDATE_NAME`: Full legal name.

### Option B: Local Engine with Cloudflare Tunnel (Zero Cloud Cost)
If you prefer keeping SQLite and Gmail connections entirely local on your personal machine:
1. Run both services locally:
   ```powershell
   python -m uvicorn acios.api:app --host 127.0.0.1 --port 8000
   cd web && npm run start -- -p 3000
   ```
2. Start a secure tunnel:
   ```bash
   cloudflared tunnel --url http://localhost:3000
   ```
3. Copy the generated `https://<id>.trycloudflare.com` URL into ChatGPT Actions.

---

## 5. Mobile Voice & Chat Command Playbook

Once linked, speak or type naturally to ChatGPT from your phone:

### 1. Morning Telemetry Check
> **User**: *"ChatGPT, give me my ACIOS morning outreach briefing."*
> 
> **ChatGPT**: Calls `getSystemOverview()`.
> *"You currently have 447 organizations and 495 decision-maker contacts mapped. 20 cold pitches have been dispatched. Your master PDF resume ('MOHAMMED MINHAJ MAHMOOD_Data & Business Automation Analyst.pdf') is active and ready. Mailbox audit indicates 1 positive inbound response."*

### 2. Verify Deliverability
> **User**: *"Can you test if ibtihal@hema.om is safe to email?"*
> 
> **ChatGPT**: Calls `verifyEmailDeliverability({ email: "ibtihal@hema.om" })`.
> *"Deliverability test complete: The address is confirmed active with MX exchange reachability and passed the zero-bounce safety sieve."*

### 3. Stage Gmail Drafts
> **User**: *"Stage our verified pitches into Gmail with my resume attached."*
> 
> **ChatGPT**: Calls `syncGmailDrafts()`.
> *"Connecting to Gmail IMAP... Stale drafts purged and 32 verified personalized pitches have been staged into [Gmail]/Drafts with your master PDF resume attached for review."*

### 4. Controlled Sequential Dispatch
> **User**: *"Let's dispatch the queued emails with a 60-second cooldown."*
> 
> **ChatGPT**: Calls `dispatchQueue({ interval: 60 })`.
> *"Outreach dispatch queue initiated. Emails are being transmitted sequentially via SMTP TLS with a 60-second pacing interval between messages."*

### 5. Check for Responses
> **User**: *"Did any recruiters reply to my applications today?"*
> 
> **ChatGPT**: Calls `auditMailbox()`.
> *"IMAP inbox audit complete: 1 new hiring inquiry detected from CSCEC Middle East and 0 delivery bounces logged."*

---

## 6. Zero-Leak Security Guarantee

All ACIOS integration endpoints follow the **Least-Privilege Principle**:
- **Credential Segregation**: Passwords and TLS tokens are read exclusively by server-side processes from disk or encrypted memory.
- **Sanitized Outputs**: Endpoints that report credential status mask strings (e.g. `gmai********`).
- **Idempotent Queueing**: Dispatch operations enforce mutual exclusion locks to prevent double-sends.
