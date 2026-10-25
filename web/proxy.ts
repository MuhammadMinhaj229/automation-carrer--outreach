import { NextRequest, NextResponse } from "next/server";
import { verifySessionToken, SESSION_COOKIE_NAME } from "@/lib/session";
function apiTokenMatches(request: NextRequest): boolean {
  const expected = process.env.ACIOS_API_KEY || "";
  if (expected.length < 32 || expected.startsWith("replace-with-")) return false;
  const match = /^Bearer\s+(.+)$/i.exec(request.headers.get("authorization") || "");
  if (!match || match[1].length !== expected.length) return false;
  let diff = 0;
  for (let i = 0; i < expected.length; i += 1) diff |= expected.charCodeAt(i) ^ match[1].charCodeAt(i);
  return diff === 0;
}
export async function proxy(request: NextRequest) {
  const { pathname } = request.nextUrl;
  if (pathname === "/login" || pathname === "/api/auth/login" || pathname === "/api/openapi.json" || pathname === "/api/mcp") return NextResponse.next();
  const sessionOK = await verifySessionToken(request.cookies.get(SESSION_COOKIE_NAME)?.value);
  if (sessionOK) {
    if (["POST", "PUT", "PATCH", "DELETE"].includes(request.method)) {
      const origin = request.headers.get("origin");
      if (origin && origin !== request.nextUrl.origin) return NextResponse.json({ error: "Cross-origin request blocked." }, { status: 403 });
    }
    return NextResponse.next();
  }
  if (pathname.startsWith("/api/") && apiTokenMatches(request)) return NextResponse.next();
  if (pathname.startsWith("/api/")) return NextResponse.json({ error: "Unauthorized." }, { status: 401 });
  return NextResponse.redirect(new URL("/login", request.url));
}
export const config = { matcher: ["/((?!_next/static|_next/image|favicon.ico|.*\\.(?:svg|png|jpg|jpeg|gif|webp|ico|css|js)$).*)"] };