"use client";

import { FormEvent, useCallback, useEffect, useState } from "react";
import { AlertCircle, CheckCircle2, ChevronDown, Clock3, FileText, Globe, LoaderCircle, RefreshCw, ShieldCheck, UploadCloud, WandSparkles } from "lucide-react";

type ToolStatus = {
  id: string;
  name: string;
  category: string;
  purpose: string;
  available: boolean;
  automatic: boolean;
  status: "ready" | "not_configured" | string;
  reason: string;
};
type CrawlResult = {
  provider: string;
  title: string;
  final_url: string;
  content_markdown: string;
  links?: { text: string; url: string }[];
  characters?: number;
  truncated?: boolean;
  duration_ms?: number;
  warnings?: string[];
};
type ApiResponse<T> = { result?: T; tools?: ToolStatus[]; detail?: string; error?: string; status?: string };

const strategies = [
  { id: "auto", label: "Automatic — recommended" },
  { id: "httpx", label: "Built-in HTTP / HTML" },
  { id: "crawl4ai", label: "Crawl4AI — JavaScript pages" },
  { id: "crawlee", label: "Crawlee — crawler framework" },
  { id: "scrapling", label: "Scrapling — adaptive extraction" },
  { id: "scrapy", label: "Scrapy — structured crawling" },
  { id: "firecrawl", label: "Firecrawl — remote extraction" },
  { id: "browser_use", label: "Browser Use — read-only agent" },
  { id: "autoscraper", label: "AutoScraper — sample-based extraction" },
  { id: "curl_impersonate", label: "curl-impersonate — allowlisted host only" },
];

function ErrorMessage({ children }: { children: string }) {
  return (
    <div role="alert" className="flex items-start gap-2 rounded-sm border border-rose-900/70 bg-rose-950/30 px-3 py-2.5 text-xs leading-relaxed text-rose-200">
      <AlertCircle className="mt-0.5 h-4 w-4 shrink-0" /> <span>{children}</span>
    </div>
  );
}

export default function CrawlingView() {
  const [tools, setTools] = useState<ToolStatus[]>([]);
  const [loadingTools, setLoadingTools] = useState(false);
  const [capabilityError, setCapabilityError] = useState("");
  const [url, setUrl] = useState("");
  const [strategy, setStrategy] = useState("auto");
  const [maxChars, setMaxChars] = useState("20000");
  const [wantedList, setWantedList] = useState("");
  const [browserInstruction, setBrowserInstruction] = useState("Extract the page title, company overview, and publicly announced expansion or hiring signals.");
  const [crawling, setCrawling] = useState(false);
  const [crawlError, setCrawlError] = useState("");
  const [crawlResult, setCrawlResult] = useState<CrawlResult | null>(null);
  const [document, setDocument] = useState<File | null>(null);
  const [converting, setConverting] = useState(false);
  const [conversionError, setConversionError] = useState("");
  const [convertedText, setConvertedText] = useState("");
  const [convertedFilename, setConvertedFilename] = useState("");

  const loadCapabilities = useCallback(async () => {
    setLoadingTools(true);
    setCapabilityError("");
    try {
      const response = await fetch("/api/v1/tools/crawl-capabilities", { cache: "no-store" });
      const payload = (await response.json()) as ApiResponse<never>;
      if (!response.ok) throw new Error(payload.detail || payload.error || `Capability request failed (${response.status}).`);
      setTools(payload.tools || []);
    } catch (error) {
      setCapabilityError(error instanceof Error ? error.message : "Unable to load integration status.");
    } finally {
      setLoadingTools(false);
    }
  }, []);

  useEffect(() => { void loadCapabilities(); }, [loadCapabilities]);

  const runCrawl = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setCrawling(true);
    setCrawlError("");
    setCrawlResult(null);
    try {
      const parsedUrl = new URL(url.trim());
      if (!["http:", "https:"].includes(parsedUrl.protocol)) throw new Error("Use a public HTTP or HTTPS URL.");
      const samples = wantedList.split("\n").map((item) => item.trim()).filter(Boolean).slice(0, 10);
      const response = await fetch("/api/v1/tools/crawl-web", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          url: parsedUrl.toString(),
          strategy,
          max_chars: Number(maxChars),
          ...(strategy === "autoscraper" ? { wanted_list: samples } : {}),
          ...(strategy === "browser_use" ? { browser_instruction: browserInstruction } : {}),
        }),
      });
      const payload = (await response.json()) as ApiResponse<CrawlResult>;
      if (!response.ok) throw new Error(payload.detail || payload.error || `Crawling failed (${response.status}).`);
      if (!payload.result) throw new Error("The API returned no extraction result.");
      setCrawlResult(payload.result);
    } catch (error) {
      setCrawlError(error instanceof Error ? error.message : "Crawling failed.");
    } finally {
      setCrawling(false);
    }
  };

  const convertDocument = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!document) {
      setConversionError("Choose a document first.");
      return;
    }
    setConverting(true);
    setConversionError("");
    setConvertedText("");
    setConvertedFilename("");
    try {
      const form = new FormData();
      form.append("file", document);
      const response = await fetch("/api/v1/tools/convert-document", { method: "POST", body: form });
      const payload = (await response.json()) as ApiResponse<{ content_markdown: string; filename: string }>;
      if (!response.ok) throw new Error(payload.detail || payload.error || `Conversion failed (${response.status}).`);
      if (!payload.result) throw new Error("The API returned no converted document.");
      setConvertedText(payload.result.content_markdown);
      setConvertedFilename(payload.result.filename);
    } catch (error) {
      setConversionError(error instanceof Error ? error.message : "Document conversion failed.");
    } finally {
      setConverting(false);
    }
  };

  const readyCount = tools.filter((tool) => tool.available).length;

  return (
    <div className="space-y-6">
      <section className="relative overflow-hidden rounded-sm border border-neutral-800 bg-neutral-900/60 p-5 md:p-7">
        <div className="pointer-events-none absolute inset-y-0 right-0 w-1/3 bg-gradient-to-l from-emerald-500/5 to-transparent" />
        <div className="relative flex flex-col gap-4 md:flex-row md:items-end md:justify-between">
          <div className="max-w-3xl">
            <div className="mb-3 flex items-center gap-2 text-[10px] font-bold uppercase tracking-[0.22em] text-emerald-300">
              <Globe className="h-4 w-4" /> Acquisition intelligence / extraction layer
            </div>
            <h1 className="text-2xl font-semibold tracking-tight text-neutral-50 md:text-3xl">Crawling toolkit</h1>
            <p className="mt-2 max-w-2xl text-sm leading-relaxed text-neutral-400">
              One interface for public-page extraction, tool readiness, source provenance, and document conversion.
              ACIOS selects an available adapter and returns a normalized result.
            </p>
          </div>
          <button onClick={() => void loadCapabilities()} disabled={loadingTools} className="inline-flex shrink-0 items-center justify-center gap-2 rounded-sm border border-neutral-700 bg-neutral-950 px-3 py-2 text-xs font-medium text-neutral-200 hover:border-neutral-500 disabled:opacity-50">
            <RefreshCw className={`h-3.5 w-3.5 ${loadingTools ? "animate-spin" : ""}`} /> Refresh integrations
          </button>
        </div>
        <div className="relative mt-6 grid grid-cols-2 gap-3 md:grid-cols-4">
          <div className="rounded-sm border border-neutral-800 bg-neutral-950/70 p-3">
            <div className="text-[10px] uppercase tracking-widest text-neutral-500">Available tools</div>
            <div className="mt-1 text-2xl font-semibold text-neutral-100">{loadingTools ? "…" : `${readyCount}/${tools.length || 11}`}</div>
          </div>
          <div className="rounded-sm border border-neutral-800 bg-neutral-950/70 p-3">
            <div className="text-[10px] uppercase tracking-widest text-neutral-500">Default mode</div>
            <div className="mt-2 text-sm font-semibold text-neutral-100">Local-first</div>
          </div>
          <div className="rounded-sm border border-neutral-800 bg-neutral-950/70 p-3">
            <div className="text-[10px] uppercase tracking-widest text-neutral-500">Page limit</div>
            <div className="mt-2 text-sm font-semibold text-neutral-100">50,000 chars</div>
          </div>
          <div className="rounded-sm border border-neutral-800 bg-neutral-950/70 p-3">
            <div className="text-[10px] uppercase tracking-widest text-neutral-500">Robots policy</div>
            <div className="mt-2 inline-flex items-center gap-1.5 text-sm font-semibold text-emerald-300"><ShieldCheck className="h-4 w-4" /> Checked</div>
          </div>
        </div>
      </section>

      <div className="grid items-start gap-5 xl:grid-cols-[minmax(0,1.15fr)_minmax(340px,0.85fr)]">
        <section className="rounded-sm border border-neutral-800 bg-neutral-900/35 p-5">
          <div className="mb-4 flex items-center gap-2">
            <WandSparkles className="h-4 w-4 text-emerald-300" />
            <h2 className="text-sm font-semibold text-neutral-100">Extract a public page</h2>
          </div>
          <form onSubmit={runCrawl} className="space-y-4">
            <label className="block">
              <span className="mb-1.5 block text-xs font-medium text-neutral-300">Website URL</span>
              <input type="url" required value={url} onChange={(event) => setUrl(event.target.value)} placeholder="https://example.com/newsroom" className="w-full rounded-sm border border-neutral-700 bg-neutral-950 px-3 py-2.5 text-sm text-neutral-100 outline-none placeholder:text-neutral-600 focus:border-emerald-500" />
            </label>
            <div className="grid gap-3 sm:grid-cols-[minmax(0,1fr)_140px]">
              <label className="block">
                <span className="mb-1.5 block text-xs font-medium text-neutral-300">Extraction strategy</span>
                <div className="relative">
                  <select value={strategy} onChange={(event) => setStrategy(event.target.value)} className="w-full appearance-none rounded-sm border border-neutral-700 bg-neutral-950 px-3 py-2.5 pr-9 text-sm text-neutral-100 outline-none focus:border-emerald-500">
                    {strategies.map((item) => <option key={item.id} value={item.id}>{item.label}</option>)}
                  </select>
                  <ChevronDown className="pointer-events-none absolute right-3 top-3 h-4 w-4 text-neutral-500" />
                </div>
              </label>
              <label className="block">
                <span className="mb-1.5 block text-xs font-medium text-neutral-300">Text limit</span>
                <select value={maxChars} onChange={(event) => setMaxChars(event.target.value)} className="w-full rounded-sm border border-neutral-700 bg-neutral-950 px-3 py-2.5 text-sm text-neutral-100 outline-none focus:border-emerald-500">
                  <option value="5000">5,000 chars</option>
                  <option value="10000">10,000 chars</option>
                  <option value="20000">20,000 chars</option>
                  <option value="50000">50,000 chars</option>
                </select>
              </label>
            </div>
            {strategy === "autoscraper" && (
              <label className="block">
                <span className="mb-1.5 block text-xs font-medium text-neutral-300">Sample values — one per line</span>
                <textarea required value={wantedList} onChange={(event) => setWantedList(event.target.value)} rows={3} placeholder={"Example company name\nExample headline"} className="w-full rounded-sm border border-neutral-700 bg-neutral-950 px-3 py-2.5 text-sm text-neutral-100 outline-none focus:border-emerald-500" />
              </label>
            )}
            {strategy === "browser_use" && (
              <label className="block">
                <span className="mb-1.5 block text-xs font-medium text-neutral-300">Read-only extraction instruction</span>
                <textarea required value={browserInstruction} onChange={(event) => setBrowserInstruction(event.target.value)} rows={3} maxLength={500} className="w-full rounded-sm border border-neutral-700 bg-neutral-950 px-3 py-2.5 text-sm text-neutral-100 outline-none focus:border-emerald-500" />
              </label>
            )}
            <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
              <p className="max-w-lg text-[11px] leading-relaxed text-neutral-500">Public pages only. Access restrictions, robots disallow rules, and unsafe destinations are rejected.</p>
              <button type="submit" disabled={crawling} className="inline-flex shrink-0 items-center justify-center gap-2 rounded-sm bg-emerald-400 px-4 py-2.5 text-xs font-bold text-neutral-950 transition hover:bg-emerald-300 disabled:cursor-not-allowed disabled:opacity-50">
                {crawling ? <LoaderCircle className="h-4 w-4 animate-spin" /> : <Globe className="h-4 w-4" />}
                {crawling ? "Extracting…" : "Run extraction"}
              </button>
            </div>
            {crawlError && <ErrorMessage>{crawlError}</ErrorMessage>}
          </form>
          {crawlResult && (
            <div className="mt-5 overflow-hidden rounded-sm border border-neutral-800 bg-neutral-950">
              <div className="flex flex-wrap items-start justify-between gap-3 border-b border-neutral-800 px-4 py-3">
                <div className="min-w-0">
                  <div className="flex items-center gap-2 text-xs font-semibold text-emerald-300"><CheckCircle2 className="h-4 w-4" /> Extraction complete</div>
                  <div className="mt-1 break-all text-sm font-medium text-neutral-100">{crawlResult.title || crawlResult.final_url}</div>
                  <div className="mt-1 break-all text-[10px] text-neutral-500">{crawlResult.final_url}</div>
                </div>
                <div className="flex items-center gap-1.5 text-[10px] text-neutral-400"><Clock3 className="h-3.5 w-3.5" /> {crawlResult.duration_ms ?? "—"} ms</div>
              </div>
              <div className="flex flex-wrap gap-2 px-4 py-3 text-[10px]">
                <span className="rounded-sm border border-neutral-700 px-2 py-1 text-neutral-300">Provider: {crawlResult.provider}</span>
                <span className="rounded-sm border border-neutral-700 px-2 py-1 text-neutral-300">{crawlResult.characters ?? crawlResult.content_markdown.length} characters</span>
                {crawlResult.truncated && <span className="rounded-sm border border-amber-800 px-2 py-1 text-amber-300">Output truncated</span>}
              </div>
              {crawlResult.warnings && crawlResult.warnings.length > 0 && <div className="px-4 pb-2 text-[11px] text-amber-300">Fallbacks: {crawlResult.warnings.join(" · ")}</div>}
              <pre className="max-h-[500px] overflow-auto whitespace-pre-wrap break-words border-t border-neutral-800 p-4 text-xs leading-relaxed text-neutral-300">{crawlResult.content_markdown}</pre>
              {crawlResult.links && crawlResult.links.length > 0 && (
                <div className="border-t border-neutral-800 px-4 py-3">
                  <div className="mb-2 text-[10px] font-bold uppercase tracking-widest text-neutral-500">Extracted links</div>
                  <div className="space-y-1.5">
                    {crawlResult.links.slice(0, 12).map((link, index) => (
                      <a key={`${link.url}-${index}`} href={link.url} target="_blank" rel="noreferrer noopener" className="block truncate text-xs text-sky-300 hover:text-sky-200">{link.text || link.url}</a>
                    ))}
                  </div>
                </div>
              )}
            </div>
          )}
        </section>

        <div className="space-y-5">
          <section className="rounded-sm border border-neutral-800 bg-neutral-900/35 p-5">
            <div className="mb-4 flex items-center gap-2">
              <FileText className="h-4 w-4 text-sky-300" />
              <h2 className="text-sm font-semibold text-neutral-100">Document to Markdown</h2>
            </div>
            <p className="mb-4 text-xs leading-relaxed text-neutral-400">Convert a supported PDF, Office file, CSV, HTML, or text document. Files are limited to 10 MB and plug-ins are disabled.</p>
            <form onSubmit={convertDocument} className="space-y-3">
              <label className="flex cursor-pointer flex-col items-center justify-center gap-2 rounded-sm border border-dashed border-neutral-700 bg-neutral-950/80 px-4 py-6 text-center hover:border-neutral-500">
                <UploadCloud className="h-5 w-5 text-neutral-400" />
                <span className="text-xs font-medium text-neutral-200">{document ? document.name : "Choose a document"}</span>
                <span className="text-[10px] text-neutral-500">Maximum 10 MB</span>
                <input type="file" className="sr-only" accept=".pdf,.docx,.pptx,.xlsx,.xls,.csv,.json,.xml,.html,.htm,.txt,.md,.rtf,.ppt,.doc,.epub" onChange={(event) => setDocument(event.target.files?.[0] || null)} />
              </label>
              <button type="submit" disabled={converting || !document} className="inline-flex w-full items-center justify-center gap-2 rounded-sm border border-neutral-700 bg-neutral-800 px-3 py-2.5 text-xs font-semibold text-neutral-100 hover:bg-neutral-700 disabled:cursor-not-allowed disabled:opacity-50">
                {converting ? <LoaderCircle className="h-4 w-4 animate-spin" /> : <FileText className="h-4 w-4" />}
                {converting ? "Converting…" : "Convert document"}
              </button>
              {conversionError && <ErrorMessage>{conversionError}</ErrorMessage>}
            </form>
            {convertedText && (
              <div className="mt-4 rounded-sm border border-neutral-800 bg-neutral-950">
                <div className="border-b border-neutral-800 px-3 py-2 text-xs font-medium text-emerald-300">{convertedFilename} · conversion complete</div>
                <pre className="max-h-72 overflow-auto whitespace-pre-wrap break-words p-3 text-[11px] leading-relaxed text-neutral-300">{convertedText}</pre>
              </div>
            )}
          </section>

          <section className="rounded-sm border border-neutral-800 bg-neutral-900/35 p-5">
            <div className="mb-3 flex items-center justify-between">
              <h2 className="text-sm font-semibold text-neutral-100">Integration readiness</h2>
              <span className="text-[10px] font-mono text-neutral-500">{readyCount} ready</span>
            </div>
            {capabilityError && <ErrorMessage>{capabilityError}</ErrorMessage>}
            {!capabilityError && tools.length === 0 ? (
              <div className="py-6 text-center text-xs text-neutral-500">{loadingTools ? "Checking tool availability…" : "No capability data returned yet."}</div>
            ) : (
              <div className="space-y-1.5">
                {tools.map((tool) => (
                  <div key={tool.id} className="flex items-start gap-2.5 rounded-sm border border-neutral-800/80 bg-neutral-950/50 px-3 py-2.5">
                    <span className={`mt-0.5 h-2 w-2 shrink-0 rounded-full ${tool.available ? "bg-emerald-400" : "bg-neutral-600"}`} />
                    <div className="min-w-0 flex-1">
                      <div className="flex flex-wrap items-center gap-2">
                        <span className="text-xs font-medium text-neutral-200">{tool.name}</span>
                        {tool.automatic && <span className="rounded-sm border border-neutral-700 px-1.5 py-0.5 text-[9px] uppercase tracking-wider text-neutral-500">Auto eligible</span>}
                      </div>
                      <div className="mt-0.5 text-[10px] leading-relaxed text-neutral-500">{tool.reason}</div>
                    </div>
                    <span className={`shrink-0 text-[9px] uppercase tracking-wider ${tool.available ? "text-emerald-300" : "text-neutral-600"}`}>{tool.available ? "Ready" : "Setup"}</span>
                  </div>
                ))}
              </div>
            )}
            <p className="mt-3 text-[10px] leading-relaxed text-neutral-600">Availability is based on installed packages and backend configuration; it is not a live uptime guarantee for external providers.</p>
          </section>
        </div>
      </div>
    </div>
  );
}
