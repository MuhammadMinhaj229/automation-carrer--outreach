const COOKIE_NAME = "acios_session";
const SESSION_TTL_SECONDS = 8 * 60 * 60;
function bytesToHex(bytes: Uint8Array): string {
  return Array.from(bytes, (byte) => byte.toString(16).padStart(2, "0")).join("");
}
function hexToBytes(hex: string): Uint8Array | null {
  if (!/^[a-f0-9]+$/i.test(hex) || hex.length % 2 !== 0) return null;
  const result = new Uint8Array(hex.length / 2);
  for (let i = 0; i < result.length; i += 1) result[i] = parseInt(hex.slice(i * 2, i * 2 + 2), 16);
  return result;
}
async function signingKey(): Promise<CryptoKey> {
  const secret = process.env.ACIOS_SESSION_SECRET || "";
  if (secret.length < 32 || secret.startsWith("replace-with-")) throw new Error("ACIOS_SESSION_SECRET must be a non-placeholder secret of at least 32 characters.");
  return crypto.subtle.importKey("raw", new TextEncoder().encode(secret), { name: "HMAC", hash: "SHA-256" }, false, ["sign", "verify"]);
}
export async function createSessionToken(nowMs = Date.now()): Promise<{ token: string; maxAge: number }> {
  const expiry = Math.floor(nowMs / 1000) + SESSION_TTL_SECONDS;
  const payload = String(expiry);
  const sig = await crypto.subtle.sign("HMAC", await signingKey(), new TextEncoder().encode(payload));
  return { token: `${payload}.${bytesToHex(new Uint8Array(sig))}`, maxAge: SESSION_TTL_SECONDS };
}
export async function verifySessionToken(token?: string, nowMs = Date.now()): Promise<boolean> {
  if (!token) return false;
  const [expiryText, signatureHex, extra] = token.split(".");
  if (!expiryText || !signatureHex || extra !== undefined) return false;
  const expiry = Number(expiryText);
  if (!Number.isSafeInteger(expiry) || expiry <= Math.floor(nowMs / 1000)) return false;
  const signature = hexToBytes(signatureHex);
  if (!signature) return false;
  try { return await crypto.subtle.verify("HMAC", await signingKey(), signature, new TextEncoder().encode(expiryText)); }
  catch { return false; }
}
export const SESSION_COOKIE_NAME = COOKIE_NAME;