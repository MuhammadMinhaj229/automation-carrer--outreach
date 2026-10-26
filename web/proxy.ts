import { NextRequest, NextResponse } from "next/server";
import { verifySessionToken, SESSION_COOKIE_NAME } from "@/lib/session";

function apiTokenMatches(request: NextRequest): boolean {
  const expected = process.env.ACIOS_API_KEY || "";
  if (expected.length < 32 || expected.startsWith("replace-with-")) return false;
  const match = /^Bearer\\s+(.+)$/i.exec(request.headers.get("authorization") || "");
  if (!match || match[1].length !== expected.length) return false;

  let diff = 0;
  for (let i = 0; i < expected.length; i += 1) {
    diff |= expected.charCodeAt(i) ^ match[1].charCodeAt(i);
  }
  return diff === 0;
}

/**
 * OpenAPI Actions use a separate, intentionally narrow credential. Never allow
 * that credential to reach profile, settings, file-download, mailbox, or legacy
 * dispatch routes through the generic API proxy.
 */
const OPENAPI_ACTION_METHODS: Record<string, readonly string[]> = {
  "/api/v1/tools/search-growth-signals": ["POST"],
  "/api/v1/tools/company-dossier": ["GET"],
  "/api/v1/tools/verify-contact": ["POST"],
  "/api/v1/tools/create-outreach-draft": ["POST"],
  "/api/v1/tools/pending-approvals": ["GET"],
  "/api/v1/tools/approve-outreach": ["POST"],
  "/api/v1/tools/send-approved-outreach": ["POST"],
};

function isOpenApiActionRequest(request: NextRequest): boolean {
  const { pathname } = request.nextUrl;
  const method = request.method.toUpperCase();

  if (OPENAPI_ACTION_METHODS[pathname]?.includes(method)) return true;
  return method === "GET" && /^\\/api\\/v1\\/tools\\/job-status\\/[^/]+$/.test(pathname);
}

export async function proxy(request: NextRequest) {
  const { pathname } = request.nextUrl;

  // These handlers perform their own independent authentication.
  if (
    pathname === "/login" ||
    pathname === "/api/auth/login" ||
    pathname === "/api/auth/logout" ||
    pathname === "/api/openapi.json" ||
    pathname === "/api/mcp"
  ) {
    return NextResponse.next();
  }

  const sessionOK = await verifySessionToken(
    request.cookies.get(SESSION_COOKIE_NAME)?.value
  );
  if (sessionOK) {
    if (["POST", "PUT", "PATCH", "DELETE"].includes(request.method)) {
      const origin = request.headers.get("origin");
      if (origin && origin !== request.nextUrl.origin) {
        return NextResponse.json(
          { error: "Cross-origin request blocked." },
          { status: 403 }
        );
      }
    }
    return NextResponse.next();
  }

  // The Actions key can call only the explicitly documented, versioned tools.
  if (isOpenApiActionRequest(request) && apiTokenMatches(request)) {
    return NextResponse.next();
  }

  if (pathname.startsWith("/api/")) {
    return NextResponse.json({ error: "Unauthorized." }, { status: 401 });
  }
  return NextResponse.redirect(new URL("/login", request.url));
}

export const config = {
  matcher: [
    "/((?!_next/static|_next/image|favicon.ico|.*\\.(?:svg|png|jpg|jpeg|gif|webp|ico|css|js)$).*)",
  ],
};
