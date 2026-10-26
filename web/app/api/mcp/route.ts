import { NextResponse } from "next/server";
import { timingSafeEqual } from "node:crypto";

const BACKEND_URL = (process.env.ACIOS_BACKEND_URL || "").replace(/\/$/, "");
const BACKEND_API_KEY = process.env.ACIOS_BACKEND_API_KEY || "";
const MCP_BEARER_TOKEN = process.env.ACIOS_MCP_BEARER_TOKEN || "";

async function backendFetch(
  path: string,
  init: RequestInit = {}
): Promise<Response> {
  if (
    !BACKEND_URL ||
    BACKEND_API_KEY.length < 32 ||
    BACKEND_API_KEY.startsWith("replace-with-")
  ) {
    throw new Error("ACIOS backend connection is not securely configured.");
  }
  const headers = new Headers(init.headers);
  headers.set("Authorization", `Bearer ${BACKEND_API_KEY}`);
  if (init.body && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }
  return fetch(`${BACKEND_URL}${path}`, {
    ...init,
    headers,
    cache: "no-store",
    signal: AbortSignal.timeout(25_000),
  });
}

function safeEqual(a: string, b: string): boolean {
  const aa = Buffer.from(a);
  const bb = Buffer.from(b);
  if (aa.length !== bb.length) {
    const dummy = Buffer.alloc(Math.max(aa.length, bb.length, 1));
    timingSafeEqual(dummy, dummy);
    return false;
  }
  return timingSafeEqual(aa, bb);
}

const TOOLS = [
  {
    name: "search_growth_signals",
    description:
      "Discover companies and their sourced expansion evidence. Optionally queues a durable background scan job.",
    inputSchema: {
      type: "object",
      properties: {
        query: {
          type: "string",
          description: "Search keywords or company name filter",
        },
        country: {
          type: "string",
          description: "Country filter (e.g. Oman, UAE, Saudi Arabia)",
        },
        limit: {
          type: "integer",
          description: "Maximum number of signals to return (1-100)",
          default: 20,
        },
        run_background_scan: {
          type: "boolean",
          description: "Enqueue a durable background discovery scan job",
          default: false,
        },
      },
    },
  },
  {
    name: "get_company_dossier",
    description:
      "Retrieve sourced company profile, expansion signals, and decision-maker information.",
    inputSchema: {
      type: "object",
      properties: {
        organization_name: {
          type: "string",
          description: "Exact name of the organization",
        },
      },
      required: ["organization_name"],
    },
  },
  {
    name: "verify_contact",
    description:
      "Return verification evidence and confidence score for a contact email address without fabricating deliverability guarantees.",
    inputSchema: {
      type: "object",
      properties: {
        email: {
          type: "string",
          description: "Corporate email address to verify",
        },
      },
      required: ["email"],
    },
  },
  {
    name: "create_outreach_draft",
    description:
      "Create a calibrated 100-160 word outreach draft in PENDING_APPROVAL state without sending it.",
    inputSchema: {
      type: "object",
      properties: {
        recipient_email: { type: "string", description: "Recipient email address" },
        recipient_name: { type: "string", description: "Recipient full name" },
        organization_name: { type: "string", description: "Target organization name" },
        recipient_role: { type: "string", description: "Recipient role or title" },
        subject_line: { type: "string", description: "Optional explicit subject line" },
        body_text: {
          type: "string",
          description: "Optional explicit 100-160 word body text",
        },
        signal_headline: {
          type: "string",
          description: "Sourced expansion signal headline for personalization",
        },
      },
      required: [
        "recipient_email",
        "recipient_name",
        "organization_name",
        "recipient_role",
      ],
    },
  },
  {
    name: "list_pending_approvals",
    description: "Retrieve all outreach drafts awaiting explicit approval.",
    inputSchema: {
      type: "object",
      properties: {},
    },
  },
  {
    name: "approve_outreach",
    description:
      "Approve a specific outreach draft after authenticated operator confirmation.",
    inputSchema: {
      type: "object",
      properties: {
        draft_id: {
          type: "integer",
          description: "Numeric ID of the draft to approve",
        },
        approved_by: {
          type: "string",
          description: "Identifier of the approving operator",
        },
        confirmation_note: {
          type: "string",
          description: "Audit note confirming review",
        },
      },
      required: ["draft_id"],
    },
  },
  {
    name: "send_approved_outreach",
    description:
      "Send only a previously approved outreach draft, enforcing atomic duplicate-send protection.",
    inputSchema: {
      type: "object",
      properties: {
        draft_id: {
          type: "integer",
          description: "Numeric ID of the APPROVED draft to send",
        },
        idempotency_key: {
          type: "string",
          description: "Unique idempotency key to prevent duplicate sends",
        },
      },
      required: ["draft_id"],
    },
  },
  {
    name: "get_job_status",
    description: "Check status, attempts, and result of a durable background job.",
    inputSchema: {
      type: "object",
      properties: {
        job_id: {
          type: "string",
          description: "Job identifier returned when a background task was enqueued",
        },
      },
      required: ["job_id"],
    },
  },
  {
    name: "get_system_overview",
    description:
      "Fetch real-time outreach telemetry, resume readiness, and recent audit events.",
    inputSchema: {
      type: "object",
      properties: {},
    },
  },
  {
    name: "get_system_stats",
    description:
      "Retrieve database counters for organizations, contacts, signals, drafts, and suppressed addresses.",
    inputSchema: {
      type: "object",
      properties: {},
    },
  },
];

function checkAuth(request: Request): boolean {
  if (
    MCP_BEARER_TOKEN.length < 32 ||
    MCP_BEARER_TOKEN.startsWith("replace-with-")
  ) {
    return false;
  }
  const authHeader = request.headers.get("Authorization") || "";
  const match = /^Bearer\s+(.+)$/i.exec(authHeader);
  return Boolean(match && safeEqual(match[1], MCP_BEARER_TOKEN));
}

const CORS_HEADERS = {
  "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
  "Access-Control-Allow-Headers": "Content-Type, Authorization",
};

export async function OPTIONS() {
  return new NextResponse(null, {
    status: 204,
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
      name: "ACIOS Authenticated Model Context Protocol (MCP) Gateway",
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

  let body: Record<string, unknown>;
  try {
    body = (await request.json()) as Record<string, unknown>;
  } catch {
    return NextResponse.json(
      {
        jsonrpc: "2.0",
        id: null,
        error: { code: -32700, message: "Parse error: Invalid JSON" },
      },
      { status: 400, headers: CORS_HEADERS }
    );
  }

  const { id, method, params } = body as {
    id?: unknown;
    method?: string;
    params?: { name?: string; arguments?: Record<string, unknown> };
  };

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

  if (method === "notifications/initialized") {
    return NextResponse.json(
      { jsonrpc: "2.0", id, result: {} },
      { headers: CORS_HEADERS }
    );
  }

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

  if (method === "tools/call") {
    const toolName = params?.name;
    const args = params?.arguments || {};

    try {
      let res: Response;

      if (toolName === "search_growth_signals") {
        res = await backendFetch("/api/v1/tools/search-growth-signals", {
          method: "POST",
          body: JSON.stringify({
            query: typeof args.query === "string" ? args.query : "",
            country: typeof args.country === "string" ? args.country : undefined,
            limit: typeof args.limit === "number" ? args.limit : 20,
            run_background_scan: Boolean(args.run_background_scan),
          }),
        });
      } else if (toolName === "get_company_dossier") {
        const orgName = String(args.organization_name || "").trim();
        if (!orgName) throw new Error("organization_name is required.");
        res = await backendFetch(
          `/api/v1/tools/company-dossier?organization_name=${encodeURIComponent(orgName)}`
        );
      } else if (toolName === "verify_contact") {
        const email = String(args.email || "").trim();
        if (!email) throw new Error("email is required.");
        res = await backendFetch("/api/v1/tools/verify-contact", {
          method: "POST",
          body: JSON.stringify({ email }),
        });
      } else if (toolName === "create_outreach_draft") {
        res = await backendFetch("/api/v1/tools/create-outreach-draft", {
          method: "POST",
          body: JSON.stringify(args),
        });
      } else if (toolName === "list_pending_approvals") {
        res = await backendFetch("/api/v1/tools/pending-approvals");
      } else if (toolName === "approve_outreach") {
        res = await backendFetch("/api/v1/tools/approve-outreach", {
          method: "POST",
          body: JSON.stringify({
            draft_id: Number(args.draft_id),
            approved_by:
              typeof args.approved_by === "string"
                ? args.approved_by
                : "mcp_operator",
            confirmation_note:
              typeof args.confirmation_note === "string"
                ? args.confirmation_note
                : "Approved via authenticated MCP gateway",
          }),
        });
      } else if (toolName === "send_approved_outreach") {
        res = await backendFetch("/api/v1/tools/send-approved-outreach", {
          method: "POST",
          body: JSON.stringify({
            draft_id: Number(args.draft_id),
            idempotency_key:
              typeof args.idempotency_key === "string"
                ? args.idempotency_key
                : undefined,
          }),
        });
      } else if (toolName === "get_job_status") {
        const jobId = String(args.job_id || "").trim();
        if (!jobId) throw new Error("job_id is required.");
        res = await backendFetch(
          `/api/v1/tools/job-status/${encodeURIComponent(jobId)}`
        );
      } else if (toolName === "get_system_overview") {
        res = await backendFetch("/api/v1/system/overview");
      } else if (toolName === "get_system_stats") {
        res = await backendFetch("/api/v1/system/stats");
      } else {
        return NextResponse.json(
          {
            jsonrpc: "2.0",
            id,
            error: {
              code: -32601,
              message: `Method '${String(toolName)}' not found in ACIOS MCP registry`,
            },
          },
          { status: 404, headers: CORS_HEADERS }
        );
      }

      const resultData: unknown = await res.json();
      return NextResponse.json(
        {
          jsonrpc: "2.0",
          id,
          result: {
            isError: !res.ok,
            content: [
              {
                type: "text",
                text:
                  typeof resultData === "string"
                    ? resultData
                    : JSON.stringify(resultData, null, 2),
              },
            ],
          },
        },
        { headers: CORS_HEADERS }
      );
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : "Unknown error";
      return NextResponse.json(
        {
          jsonrpc: "2.0",
          id,
          result: {
            isError: true,
            content: [
              {
                type: "text",
                text: `Execution failed for tool '${String(toolName)}': ${message}`,
              },
            ],
          },
        },
        { headers: CORS_HEADERS }
      );
    }
  }

  return NextResponse.json(
    {
      jsonrpc: "2.0",
      id,
      error: {
        code: -32601,
        message: `Unsupported JSON-RPC method: ${String(method)}`,
      },
    },
    { status: 400, headers: CORS_HEADERS }
  );
}
