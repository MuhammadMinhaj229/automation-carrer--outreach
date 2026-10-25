import { NextResponse } from "next/server";
import { timingSafeEqual } from "node:crypto";
import { createSessionToken, SESSION_COOKIE_NAME } from "@/lib/session";
function constantTimeEqual(actual: string, expected: string): boolean {
  const a = Buffer.from(actual); const b = Buffer.from(expected);
  const size = Math.max(a.length, b.length, 1); const aa = Buffer.alloc(size); const bb = Buffer.alloc(size);
  a.copy(aa); b.copy(bb);
  return timingSafeEqual(aa, bb) && a.length === b.length;
}
export async function POST(request: Request) {
  const expected = process.env.ACIOS_UI_PASSWORD || "";
  const sessionSecret = process.env.ACIOS_SESSION_SECRET || "";
  if (expected.length < 20 || expected.startsWith("replace-with-") || sessionSecret.length < 32 || sessionSecret.startsWith("replace-with-"))
    return NextResponse.json({ error: "UI authentication is not securely configured." }, { status: 503 });
  let body: { password?: unknown };
  try { body = await request.json(); } catch { return NextResponse.json({ error: "Invalid request body." }, { status: 400 }); }
  const supplied = typeof body.password === "string" ? body.password : "";
  if (!constantTimeEqual(supplied, expected)) return NextResponse.json({ error: "Incorrect password." }, { status: 401 });
  try {
    const { token, maxAge } = await createSessionToken();
    const response = NextResponse.json({ success: true });
    response.cookies.set(SESSION_COOKIE_NAME, token, { httpOnly: true, secure: process.env.NODE_ENV === "production", sameSite: "strict", path: "/", maxAge });
    return response;
  } catch { return NextResponse.json({ error: "Session signing is not configured." }, { status: 503 }); }
}