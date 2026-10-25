import { NextResponse } from "next/server";

const BACKEND_URL = process.env.ACIOS_BACKEND_URL || "http://127.0.0.1:8000";
const API_KEY = process.env.ACIOS_API_KEY;

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
      "Updates candidate profile settings and credentials (e.g. full_name, email, phone, linkedin_url, portfolio_url, academic_background, gmail_user, gmail_app_password).",
    inputSchema: {
      type: "object",
      properties: {
        full_name: { type: "string", description: "Candidate's full legal name" },
        email: { type: "string", description: "Candidate's primary contact email" },
        phone: { type: "string", description: "Candidate's phone number" },
        linkedin_url: { type: "string", description: "Candidate's LinkedIn profile URL" },
        portfolio_url: { type: "string", description: "Candidate's portfolio or website URL" },
        academic_background: { type: "string", description: "Degree, university, graduation year" },
        gmail_user: { type: "string", description: "Gmail address for outreach dispatch" },
        gmail_app_password: { type: "string", description: "16-character Google App Password" },
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
      "Triggers the sequential cold outreach dispatch queue via SMTP TLS with a configurable safety cooldown interval between emails to protect sender domain reputation.",
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
  if (!API_KEY) return true;
  const authHeader = request.headers.get("Authorization");
  return authHeader === `Bearer ${API_KEY}`;
}

const CORS_HEADERS = {
  "Access-Control-Allow-Origin": "*",
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
      backend_target: BACKEND_URL,
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
        const res = await fetch(`${BACKEND_URL}/api/system/overview`);
        resultData = await res.json();
      } else if (toolName === "get_system_stats") {
        const res = await fetch(`${BACKEND_URL}/api/system/stats`);
        resultData = await res.json();
      } else if (toolName === "get_settings") {
        const res = await fetch(`${BACKEND_URL}/api/settings`);
        resultData = await res.json();
      } else if (toolName === "update_settings") {
        const res = await fetch(`${BACKEND_URL}/api/settings`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(args),
        });
        resultData = await res.json();
      } else if (toolName === "verify_email_deliverability") {
        const res = await fetch(`${BACKEND_URL}/api/verification/reacher-check`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ email: args.email }),
        });
        resultData = await res.json();
      } else if (toolName === "sync_gmail_drafts") {
        const res = await fetch(`${BACKEND_URL}/api/drafts/sync-gmail`, {
          method: "POST",
        });
        resultData = await res.json();
      } else if (toolName === "dispatch_queue") {
        const interval = args.interval || 60;
        const res = await fetch(`${BACKEND_URL}/api/queue/dispatch?interval=${interval}`, {
          method: "POST",
        });
        resultData = await res.json();
      } else if (toolName === "audit_mailbox") {
        const res = await fetch(`${BACKEND_URL}/api/mailbox/audit`);
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
