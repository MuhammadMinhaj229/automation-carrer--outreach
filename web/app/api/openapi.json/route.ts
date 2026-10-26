import { NextResponse } from "next/server";

export async function GET(request: Request) {
  const url = new URL(request.url);
  const host = url.origin;

  const spec = {
    openapi: "3.1.0",
    info: {
      title: "ACIOS Authenticated Career Intelligence & Outreach API",
      description:
        "Versioned OpenAPI 3.1.0 specification for ChatGPT Actions and authenticated MCP clients. Exposes narrow, explicitly authorized tools for growth signal discovery, company dossiers, evidence-based contact verification, draft creation, approval workflow, idempotent dispatch, and durable job monitoring.",
      version: "2.5.0",
    },
    servers: [
      {
        url: host,
        description: "Authenticated ACIOS BFF & API Gateway",
      },
    ],
    components: {
      securitySchemes: {
        bearerAuth: {
          type: "http",
          scheme: "bearer",
          description: "Scoped Bearer token (ACIOS_API_KEY).",
        },
      },
    },
    security: [{ bearerAuth: [] }],
    paths: {
      "/api/v1/tools/search-growth-signals": {
        post: {
          operationId: "search_growth_signals",
          summary: "Discover companies and their expansion evidence",
          requestBody: {
            required: false,
            content: {
              "application/json": {
                schema: {
                  type: "object",
                  properties: {
                    query: { type: "string" },
                    country: { type: "string" },
                    limit: { type: "integer", default: 20 },
                    run_background_scan: { type: "boolean", default: false },
                  },
                },
              },
            },
          },
          responses: {
            "200": { description: "Discovered growth signals and optional job." },
          },
        },
      },
      "/api/v1/tools/company-dossier": {
        get: {
          operationId: "get_company_dossier",
          summary: "Retrieve sourced company and decision-maker information",
          parameters: [
            {
              name: "organization_name",
              in: "query",
              required: true,
              schema: { type: "string" },
            },
          ],
          responses: {
            "200": { description: "Company dossier." },
            "404": { description: "Organization not found." },
          },
        },
      },
      "/api/v1/tools/verify-contact": {
        post: {
          operationId: "verify_contact",
          summary: "Return verification evidence and confidence score",
          requestBody: {
            required: true,
            content: {
              "application/json": {
                schema: {
                  type: "object",
                  required: ["email"],
                  properties: {
                    email: {
                      type: "string",
                      description: "Corporate email address to verify.",
                      example: "contact@example.com",
                    },
                  },
                },
              },
            },
          },
          responses: {
            "200": { description: "Evidence-based verification verdict." },
          },
        },
      },
      "/api/v1/tools/create-outreach-draft": {
        post: {
          operationId: "create_outreach_draft",
          summary: "Create an outreach draft in PENDING_APPROVAL state without sending it",
          requestBody: {
            required: true,
            content: {
              "application/json": {
                schema: {
                  type: "object",
                  required: [
                    "recipient_email",
                    "recipient_name",
                    "organization_name",
                    "recipient_role",
                  ],
                  properties: {
                    recipient_email: { type: "string", example: "contact@example.com" },
                    recipient_name: { type: "string" },
                    organization_name: { type: "string" },
                    recipient_role: { type: "string" },
                    subject_line: { type: "string" },
                    body_text: { type: "string" },
                    signal_headline: { type: "string" },
                  },
                },
              },
            },
          },
          responses: {
            "200": { description: "Created draft awaiting approval." },
          },
        },
      },
      "/api/v1/tools/pending-approvals": {
        get: {
          operationId: "list_pending_approvals",
          summary: "Retrieve drafts awaiting explicit approval",
          responses: {
            "200": { description: "List of pending drafts." },
          },
        },
      },
      "/api/v1/tools/approve-outreach": {
        post: {
          operationId: "approve_outreach",
          summary: "Approve a specific draft after authenticated confirmation",
          requestBody: {
            required: true,
            content: {
              "application/json": {
                schema: {
                  type: "object",
                  required: ["draft_id"],
                  properties: {
                    draft_id: { type: "integer" },
                    approved_by: { type: "string" },
                    confirmation_note: { type: "string" },
                  },
                },
              },
            },
          },
          responses: {
            "200": { description: "Approved draft confirmation." },
          },
        },
      },
      "/api/v1/tools/send-approved-outreach": {
        post: {
          operationId: "send_approved_outreach",
          summary: "Send only a previously approved draft with duplicate-send protection",
          requestBody: {
            required: true,
            content: {
              "application/json": {
                schema: {
                  type: "object",
                  required: ["draft_id"],
                  properties: {
                    draft_id: { type: "integer" },
                    idempotency_key: { type: "string" },
                  },
                },
              },
            },
          },
          responses: {
            "200": { description: "Idempotent dispatch result." },
            "409": { description: "Draft not approved or recipient suppressed." },
          },
        },
      },
      "/api/v1/tools/job-status/{job_id}": {
        get: {
          operationId: "get_job_status",
          summary: "Check status of a durable background job",
          parameters: [
            {
              name: "job_id",
              in: "path",
              required: true,
              schema: { type: "string" },
            },
          ],
          responses: {
            "200": { description: "Durable job record." },
            "404": { description: "Job not found." },
          },
        },
      },
    },
  };

  return NextResponse.json(spec, {
    headers: {
      "Content-Type": "application/json",
    },
  });
}
