import { NextRequest } from "next/server";
export const runtime = "nodejs";
export const dynamic = "force-dynamic";
type RouteContext = { params: Promise<{ path: string[] }> };
async function proxyToBackend(request: NextRequest, context: RouteContext) {
  const backendUrl = (process.env.ACIOS_BACKEND_URL || "").replace(/\/$/, "");
  const serviceKey = process.env.ACIOS_BACKEND_API_KEY || "";
  if (!backendUrl || serviceKey.length < 32 || serviceKey.startsWith("replace-with-")) return Response.json({ error: "Backend service is not securely configured." }, { status: 503 });
  let base: URL;
  try {
    base = new URL(backendUrl);
    if (process.env.NODE_ENV === "production" && base.protocol !== "https:" && base.hostname !== "backend") return Response.json({ error: "Production backend URL must use HTTPS, except the private Docker Compose service hostname." }, { status: 503 });
  } catch { return Response.json({ error: "Backend URL is invalid." }, { status: 503 }); }
  const { path } = await context.params;
  const incoming = new URL(request.url);
  const target = new URL(`/api/${path.map((part) => encodeURIComponent(part)).join("/")}${incoming.search}`, base);
  const headers = new Headers();
  const contentType = request.headers.get("content-type"); if (contentType) headers.set("content-type", contentType);
  const requestId = request.headers.get("x-request-id"); if (requestId) headers.set("x-request-id", requestId);
  headers.set("authorization", `Bearer ${serviceKey}`);
  const method = request.method.toUpperCase(); let body: ArrayBuffer | undefined;
  if (!["GET", "HEAD"].includes(method)) body = await request.arrayBuffer();
  try {
    const upstream = await fetch(target, { method, headers, body, cache: "no-store", redirect: "manual", signal: AbortSignal.timeout(30_000) });
    const responseHeaders = new Headers();
    for (const key of ["content-type", "content-disposition", "cache-control", "x-request-id"]) { const value = upstream.headers.get(key); if (value) responseHeaders.set(key, value); }
    responseHeaders.set("x-content-type-options", "nosniff");
    return new Response(upstream.body, { status: upstream.status, headers: responseHeaders });
  } catch { return Response.json({ error: "Backend is temporarily unavailable." }, { status: 502 }); }
}
export const GET = proxyToBackend;
export const HEAD = proxyToBackend;
export const POST = proxyToBackend;
export const PUT = proxyToBackend;
export const PATCH = proxyToBackend;
export const DELETE = proxyToBackend;
export const OPTIONS = proxyToBackend;