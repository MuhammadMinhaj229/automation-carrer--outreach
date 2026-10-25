import { NextResponse } from "next/server";
import { timingSafeEqual } from "node:crypto";

const BACKEND_URL = (process.env.ACIOS_BACKEND_URL || "").replace(/\/$/, "");
const BACKEND_API_KEY = process.env.ACIOS_BACKEND_API_KEY || "";
const MCP_BEARER_TOKEN = process.env.ACIOS_MCP_BEARER_TOKEN || "";

async function backendFetch(path: string, init: RequestInit = {}) {
  if (!BACKEND_URL || BACKEND_API_KEY.length < 32 || BACKEND_API_KEY.startsWith("replace-with-")) {
    throw new Error("ACIOS backend connection is not securely configured.");
  }
  const headers = new Headers(init.headers);
  headers.set("Authorization", `Bearer ${BACKEND_API_KEY}`);
  if (init.body && !headers.has("Content-Type")) headers.set("Content-Type", "application/json");
  return backendFetch(`${path}`, { ...init, headers, cache: "no-store", signal: AbortSignal.timeout(25_000) });
}

function safeEqual(a: string, b: string): boolean {
  const aa = Buffer.from(a); const bb = Buffer.from(b);
  if (aa.length !== bb.length) {
    const dummy = Buffer.alloc(Math.max(aa.length, bb.length, 1));
    timingSafeEqual(dummy, dummy);
    return false;
  }
  return timingSafeEqual(aa, bb);
}

const TOOLS = [
  {
    name: "get_system_overview",
    description:
      "Fetches real-time ACIOS outreach telemetry, candidate profile coordinates, active master resume status, and recent audit events ledger.",
    inputSchema: {
      type: "object",
      properties: {},
    },
  },
  {
    name: "get_system_stats",
    description:
      "Retrieves database counters: total organizations, executive contacts, market signals, staged drafts, and suppressed emails.",
    inputSchema: {
      type: "object",
      properties: {},
    },
  },
  {
    name: "get_settings",
    description:
      "Retrieves the candidate's profile settings (name, email, phone, links, academic background) and credential status.",
    inputSchema: {
      type: "object",
      properties: {},
    },
  },
  {
    name: "update_settings",
    description:
      "Updates permitted candidate profile fields only. Credentials must be configured through the deployment secret manager.",
    inputSchema: {
      type: "object",
      properties: {
        full_name: { type: "string", description: "Candidate's full legal name" },
        email: { type: "string", description: "Candidate's primary contact email" },
        phone: { type: "string", description: "Candidate's phone number" },
        linkedin_url: { type: "string", description: "Candidate's LinkedIn profile URL" },
        portfolio_url: { type: "string", description: "Candidate's portfolio or website URL" },
        academic_background: { type: "string", description: "Degree, university, graduation year" },
      },
    },
  },
  {
    name: "verify_email_deliverability",
    description:
      "Executes 4-tier zero-bounce deliverability verification (RFC syntax, blocklist sieve, DNS MX exchange, and SMTP socket probe) on a corporate email.",
    inputSchema: {
      type: "object",
      properties: {
        email: {
          type: "string",
          description: "Corporate email address to test for active deliverability",
        },
      },
      required: ["email"],
    },
  },
  {
    name: "sync_gmail_drafts",
    description:
      "Connects to Gmail via IMAP TLS, clears stale drafts, and stages verified cold outreach pitches into [Gmail]/Drafts with the master PDF resume attached.",
    inputSchema: {
      type: "object",
      properties: {},
    },
  },
  {
    name: "dispatch_queue",
    description:
      "Dispatch is disabled until a durable worker, idempotency controls, and audited approval flow are configured.",
    inputSchema: {
      type: "object",
      properties: {
        interval: {
          type: "integer",
          description: "Cooldown delay in seconds between consecutive emails (default: 60)",
          default: 60,
        },
      },
    },
  },
  {
    name: "audit_mailbox",
    description:
      "Scans Gmail IMAP inbox for prospective employer responses, scheduling requests, and delivery bounce notices, logging all events into the database.",
    inputSchema: {
      type: "object",
      properties: {},
    },
  },
];

function checkAuth(request: Request): boolean {
  if (MCP_BEARER_TOKEN.length < 32 || MCP_BEARER_TOKEN.startsWith("replace-with-")) return false;
  const match = /^Bearer\s+(.+)$/i.exec(request.headers.get("Authorization") || "");
  return Boolean(match && safeEqual(match[1], MCP_BEARER_TOKEN));
}

const CORS_HEADERS = {
  "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
  "Access-Control-Allow-Headers": "Content-Type, Authorization",
};

export async function OPTIONS() {
  return new NextResponse(null, {
    status: 200,
    headers: CORS_HEADERS,
  });
}

export async function GET(request: Request) {
  if (!checkAuth(request)) {
    return NextResponse.json(
      { error: "Unauthorized: Invalid or missing Bearer token" },
      { status: 401, headers: CORS_HEADERS }
    );
  }

  return NextResponse.json(
    {
      name: "ACIOS Remote Model Context Protocol (MCP) Server",
      protocol_version: "2024-11-05",
      version: "2.5.0",
      status: "operational",
      tools_available: TOOLS.length,
      tools: TOOLS,
    },
    { headers: CORS_HEADERS }
  );
}

export async function POST(request: Request) {
  if (!checkAuth(request)) {
    return NextResponse.json(
      { error: "Unauthorized: Invalid or missing Bearer token" },
      { status: 401, headers: CORS_HEADERS }
    );
  }

  let body: any;
  try {
    body = await request.json();
  } catch {
    return NextResponse.json(
      { jsonrpc: "2.0", id: null, error: { code: -32700, message: "Parse error: Invalid JSON" } },
      { status: 400, headers: CORS_HEADERS }
    );
  }

  const { jsonrpc, id, method, params } = body;

  // Handle MCP initialize
  if (method === "initialize") {
    return NextResponse.json(
      {
        jsonrpc: "2.0",
        id,
        result: {
          protocolVersion: "2024-11-05",
          capabilities: {
            tools: {},
          },
          serverInfo: {
            name: "acios-remote-mcp",
            version: "2.5.0",
          },
        },
      },
      { headers: CORS_HEADERS }
    );
  }

  // Handle initialized notification
  if (method === "notifications/initialized") {
    return NextResponse.json(
      { jsonrpc: "2.0", id, result: {} },
      { headers: CORS_HEADERS }
    );
  }

  // Handle tools/list
  if (method === "tools/list") {
    return NextResponse.json(
      {
        jsonrpc: "2.0",
        id,
        result: {
          tools: TOOLS,
        },
      },
      { headers: CORS_HEADERS }
    );
  }

  // Handle tools/call
  if (method === "tools/call") {
    const toolName = params?.name;
    const args = params?.arguments || {};

    try {
      let resultData: any;

      if (toolName === "get_system_overview") {
        const res = await backendFetch(`/api/system/overview`);
        resultData = await res.json();
      } else if (toolName === "get_system_stats") {
        const res = await backendFetch(`/api/system/stats`);
        resultData = await res.json();
      } else if (toolName === "get_settings") {
        const res = await backendFetch(`/api/settings`);
        resultData = await res.json();
      } else if (toolName === "update_settings") {
        if (args.gmail_app_password || args.gmail_user) {
          throw new Error("Credential changes are not allowed through MCP. Configure secrets in the hosting provider.");
        }
        const { full_name, email, phone, linkedin_url, portfolio_url, academic_background, custom_footer } = args;
        const res = await backendFetch("/api/settings", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ full_name, email, phone, linkedin_url, portfolio_url, academic_background, custom_footer }),
        });
        resultData = await res.json();
      } else if (toolName === "verify_email_deliverability") {
        const res = await backendFetch(`/api/verification/reacher-check`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ email: args.email }),
        });
        resultData = await res.json();
      } else if (toolName === "sync_gmail_drafts") {
        throw new Error("Gmail draft synchronization is disabled until a durable worker and non-destructive approval flow are configured.");
      } else if (toolName === "dispatch_queue") {
        const interval = args.interval || 60;
        const res = await backendFetch(`/api/queue/dispatch?interval=${interval}`, {
          method: "POST",
        });
        resultData = await res.json();
      } else if (toolName === "audit_mailbox") {
        const res = await backendFetch(`/api/mailbox/audit`);
        resultData = await res.json();
      } else {
        return NextResponse.json(
          {
            jsonrpc: "2.0",
            id,
            error: {
              code: -32601,
              message: `Method '${toolName}' not found in ACIOS MCP registry`,
            },
          },
          { status: 404, headers: CORS_HEADERS }
        );
      }

      return NextResponse.json(
        {
          jsonrpc: "2.0",
          id,
          result: {
            content: [
              {
                type: "text",
                text: typeof resultData === "string" ? resultData : JSON.stringify(resultData, null, 2),
              },
            ],
          },
        },
        { headers: CORS_HEADERS }
      );
    } catch (err: any) {
      return NextResponse.json(
        {
          jsonrpc: "2.0",
          id,
          result: {
            isError: true,
            content: [
              {
                type: "text",
                text: `Execution failed for tool '${toolName}': ${err?.message || "Unknown error"}. Verify that ACIOS backend is running at ${BACKEND_URL}.`,
              },
            ],
          },
        },
        { headers: CORS_HEADERS }
      );
    }
  }

  // Fallback for unknown methods
  return NextResponse.json(
    {
      jsonrpc: "2.0",
      id,
      error: {
        code: -32601,
        message: `Unsupported JSON-RPC method: ${method}`,
      },
    },
    { status: 400, headers: CORS_HEADERS }
  );
}
