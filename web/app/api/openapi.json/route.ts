import { NextResponse } from "next/server";

export async function GET(request: Request) {
  const url = new URL(request.url);
  const host = url.origin;

  const spec = {
    openapi: "3.1.0",
    info: {
      title: "ACIOS Autonomous Career Intelligence & Outreach API",
      description:
        "Authenticated ACIOS API for sourced company research, candidate-approved draft preparation, and audited outreach operations. Deliverability results are probabilistic and never guarantee zero bounces.",
      version: "2.5.0",
      contact: { name: "ACIOS Maintainers" },
    },
    servers: [
      {
        url: host,
        description: "Active ACIOS Deployment Host",
      },
    ],
    security: [{ bearerAuth: [] }],
    components: {
      securitySchemes: {
        bearerAuth: { type: "http", scheme: "bearer", bearerFormat: "API token" },
      },
    },
    paths: {
      "/api/system/overview": {
        get: {
          operationId: "getSystemOverview",
          summary: "Get System Overview & Outreach Telemetry",
          description:
            "Fetches real-time metrics including total organizations, executive contacts, dispatched emails, positive replies, bounces caught, active master resume status, and the recent audit events ledger.",
          responses: {
            "200": {
              description: "System telemetry and audit ledger.",
              content: {
                "application/json": {
                  schema: {
                    type: "object",
                    properties: {
                      metrics: {
                        type: "object",
                        properties: {
                          total_organizations: { type: "integer" },
                          total_contacts: { type: "integer" },
                          verified_contacts: { type: "integer" },
                          staged_drafts: { type: "integer" },
                          dispatched_emails: { type: "integer" },
                          replies_count: { type: "integer" },
                          bounces_caught: { type: "integer" },
                        },
                      },
                      candidate: {
                        type: "object",
                        properties: {
                          name: { type: "string" },
                        },
                      },
                      resume: {
                        type: "object",
                        properties: {
                          filename: { type: "string" },
                          size_kb: { type: "number" },
                          is_ready: { type: "boolean" },
                        },
                      },
                      recent_events: {
                        type: "array",
                        items: {
                          type: "object",
                          properties: {
                            id: { type: "integer" },
                            recipient_email: { type: "string" },
                            event_type: { type: "string" },
                            timestamp: { type: "string" },
                            details: { type: "string" },
                          },
                        },
                      },
                      health: {
                        type: "object",
                        properties: {
                          backend: { type: "string" },
                          database: { type: "string" },
                        },
                      },
                    },
                  },
                },
              },
            },
          },
        },
      },
      "/api/system/stats": {
        get: {
          operationId: "getSystemStats",
          summary: "Get System Database Counters",
          description: "Returns quick numeric counters of total organizations, contacts, market signals, and staged drafts.",
          responses: {
            "200": {
              description: "High-level database counts.",
              content: {
                "application/json": {
                  schema: {
                    type: "object",
                    properties: {
                      total_organizations: { type: "integer" },
                      total_contacts: { type: "integer" },
                      total_signals: { type: "integer" },
                      total_staged_drafts: { type: "integer" },
                      total_suppressed_emails: { type: "integer" },
                    },
                  },
                },
              },
            },
          },
        },
      },
      "/api/settings": {
        get: {
          operationId: "getSettings",
          summary: "Get Candidate Profile & Settings",
          description: "Fetches candidate identity coordinates (name, email, phone, LinkedIn, Portfolio, academic background) and masked credentials status.",
          responses: {
            "200": {
              description: "Candidate profile and configuration.",
            },
          },
        },
        post: {
          operationId: "updateSettings",
          summary: "Update Candidate Profile & Credentials",
          description: "Updates permitted candidate profile fields. Credentials must be configured through the deployment secret manager.",
          requestBody: {
            required: true,
            content: {
              "application/json": {
                schema: {
                  type: "object",
                  properties: {
                    full_name: { type: "string" },
                    email: { type: "string" },
                    phone: { type: "string" },
                    linkedin_url: { type: "string" },
                    portfolio_url: { type: "string" },
                    academic_background: { type: "string" },
                  },
                },
              },
            },
          },
          responses: {
            "200": {
              description: "Confirmation of updated settings.",
            },
          },
        },
      },
      "/api/verification/reacher-check": {
        post: {
          operationId: "verifyEmailDeliverability",
          summary: "Verify Corporate Email Deliverability (0% Bounce Sieve)",
          description: "Executes 4-tier verification (RFC syntax, master suppression blocklist, DNS MX exchange, and non-blocking SMTP socket probe) to verify mailbox deliverability before dispatch.",
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
                      description: "Corporate email address to test for active existence.",
                      example: "ibtihal@hema.om",
                    },
                  },
                },
              },
            },
          },
          responses: {
            "200": {
              description: "Verification verdict and deliverability classification.",
              content: {
                "application/json": {
                  schema: {
                    type: "object",
                    properties: {
                      email: { type: "string" },
                      status: { type: "string" },
                      is_deliverable: { type: "boolean" },
                      confidence: { type: "number" },
                      details: { type: "string" },
                    },
                  },
                },
              },
            },
          },
        },
      },
      "/api/drafts/sync-gmail": {
        post: {
          operationId: "syncGmailDrafts",
          summary: "Stage Approved Pitches into Gmail with Resume Attached",
          description: "Connects to Gmail via IMAP TLS, purges outdated drafts, and stages verified cold email drafts into [Gmail]/Drafts with the candidate's master PDF resume attached.",
          responses: {
            "200": {
              description: "Staging confirmation.",
              content: {
                "application/json": {
                  schema: {
                    type: "object",
                    properties: {
                      status: { type: "string" },
                      message: { type: "string" },
                    },
                  },
                },
              },
            },
          },
        },
      },
      "/api/queue/dispatch": {
        post: {
          operationId: "dispatchQueue",
          summary: "Trigger Rate-Limited Sequential Dispatch Queue",
          description: "DISABLED until a durable worker, idempotency controls, and audited approval flow are configured.",
          parameters: [
            {
              name: "interval",
              in: "query",
              required: false,
              schema: {
                type: "integer",
                default: 60,
              },
              description: "Cooldown delay in seconds between consecutive emails (default: 60).",
            },
          ],
          responses: {
            "200": {
              description: "Dispatch queue launch status.",
              content: {
                "application/json": {
                  schema: {
                    type: "object",
                    properties: {
                      status: { type: "string" },
                      message: { type: "string" },
                    },
                  },
                },
              },
            },
          },
        },
      },
      "/api/mailbox/audit": {
        get: {
          operationId: "auditMailbox",
          summary: "Audit Mailbox for Inbound Replies and Bounce Notices",
          description: "Scans Gmail IMAP inbox for prospective employer responses and delivery bounce notices, automatically logging them into outreach_events.",
          responses: {
            "200": {
              description: "Mailbox scan findings and reply telemetry.",
            },
          },
        },
      },
    },
  };

  return NextResponse.json(spec, {
    headers: {
      "Content-Type": "application/json",
      "Access-Control-Allow-Origin": "*",
    },
  });
}
