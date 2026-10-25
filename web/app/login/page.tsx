"use client";
import { FormEvent, useState } from "react";

export default function LoginPage() {
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); setBusy(true); setError("");
    try {
      const response = await fetch("/api/auth/login", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ password }), cache: "no-store" });
      const data = await response.json().catch(() => ({}));
      if (!response.ok) { setError(data.error || "Could not sign in."); return; }
      window.location.assign("/");
    } catch { setError("Unable to reach the sign-in service. Try again."); }
    finally { setBusy(false); }
  }
  return <main className="min-h-screen flex items-center justify-center bg-neutral-950 text-neutral-100 px-5">
    <form onSubmit={submit} className="w-full max-w-sm rounded-xl border border-neutral-800 bg-neutral-900 p-7 shadow-xl">
      <p className="text-xs uppercase tracking-[0.22em] text-neutral-400">Private workspace</p>
      <h1 className="mt-3 text-2xl font-semibold">Sign in to ACIOS</h1>
      <p className="mt-2 text-sm text-neutral-400">Enter the workspace password configured by the administrator.</p>
      <label htmlFor="password" className="mt-6 block text-sm text-neutral-300">Workspace password</label>
      <input id="password" autoComplete="current-password" type="password" required value={password} onChange={(event) => setPassword(event.target.value)} className="mt-2 w-full rounded-md border border-neutral-700 bg-neutral-950 px-3 py-2 text-sm outline-none focus:border-neutral-400" />
      {error ? <p role="alert" className="mt-3 text-sm text-red-400">{error}</p> : null}
      <button type="submit" disabled={busy} className="mt-5 w-full rounded-md bg-white px-4 py-2 text-sm font-semibold text-neutral-950 disabled:opacity-60">{busy ? "Signing in…" : "Sign in"}</button>
    </form>
  </main>;
}
