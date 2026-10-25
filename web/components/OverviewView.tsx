"use client";

import React, { useState, useEffect } from "react";
import { SystemOverviewData, api } from "@/lib/api";
import {
  Activity,
  Layers,
  Send,
  Mail,
  ShieldCheck,
  AlertTriangle,
  RefreshCw,
  FileText,
  Terminal,
  Cpu,
  CheckCircle2,
  ExternalLink,
  Clock,
  Inbox,
  Play,
  RotateCcw,
} from "lucide-react";

export default function OverviewView({ onNavigateToSettings }: { onNavigateToSettings: () => void }) {
  const [data, setData] = useState<SystemOverviewData | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [actionStatus, setActionStatus] = useState<string | null>(null);
  const [syncingImap, setSyncingImap] = useState(false);

  const fetchOverview = async () => {
    try {
      const overview = await api.getSystemOverview();
      setData(overview);
    } catch {
      // Offline fallback
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  };

  useEffect(() => {
    fetchOverview();
    const interval = setInterval(fetchOverview, 15000);
    return () => clearInterval(interval);
  }, []);

  const handleManualRefresh = () => {
    setRefreshing(true);
    fetchOverview();
  };

  const handleSyncDrafts = async () => {
    setActionStatus("Synchronizing approved drafts to Gmail...");
    try {
      const res = await api.triggerSyncDrafts();
      setActionStatus(res.message);
      await fetchOverview();
    } catch (err: unknown) {
      setActionStatus(err instanceof Error ? err.message : "Sync failed");
    }
  };

  const handleTriggerDispatch = async () => {
    setActionStatus("Initiating sequential dispatch queue (60s safety interval)...");
    try {
      const res = await api.triggerDispatchQueue(60);
      setActionStatus(res.message);
      await fetchOverview();
    } catch (err: unknown) {
      setActionStatus(err instanceof Error ? err.message : "Dispatch queue failed");
    }
  };

  const handleImapSync = () => {
    if (syncingImap) return;
    setSyncingImap(true);
    setActionStatus("Initiating bidirectional IMAP handshake...");
    const eventSource = new EventSource(api.getImapSyncStreamUrl());

    eventSource.onmessage = (event) => {
      try {
        const payload = JSON.parse(event.data);
        if (payload.type === "progress") {
          setActionStatus(`IMAP Scan: ${payload.message || "Scanning mailbox..."}`);
        } else if (payload.type === "done") {
          eventSource.close();
          setSyncingImap(false);
          const r = payload.result || {};
          setActionStatus(`IMAP Sync Complete: ${r.messages_examined || 0} examined, ${r.replies_found || 0} replies, ${r.bounces_found || 0} bounces recorded.`);
          fetchOverview();
        }
      } catch {
        // Fallback
      }
    };

    eventSource.onerror = () => {
      eventSource.close();
      setSyncingImap(false);
      setActionStatus("IMAP sync finished.");
      fetchOverview();
    };
  };

  if (loading && !data) {
    return (
      <div className="flex flex-col items-center justify-center h-96 text-neutral-400 space-y-3">
        <RefreshCw className="w-6 h-6 animate-spin text-neutral-200" />
        <span className="text-xs font-mono uppercase tracking-widest">Hydrating Executive Telemetry...</span>
      </div>
    );
  }

  const metrics = data?.metrics || {
    total_organizations: 0,
    total_contacts: 0,
    verified_contacts: 0,
    staged_drafts: 0,
    dispatched_emails: 0,
    replies_count: 0,
    bounces_caught: 0,
  };

  const modules = [
    { id: "M1", name: "Market Signal Scanner", purpose: "Expansion RSS & News", status: "READY", engine: "RSS/OSINT" },
    { id: "M2", name: "Executive Entity Extraction", purpose: "Target Decision Makers", status: "READY", engine: "Dorking & SERP" },
    { id: "M3", name: "Permutation Sieve", purpose: "Apollo/Hunter Alternative", status: "ONLINE", engine: "RFC Patterns" },
    { id: "M4", name: "Deliverability Shield", purpose: "Zero Bounce Socket Probe", status: "ACTIVE", engine: "DNS MX + Reacher" },
    { id: "M5", name: "Strategic Narrative AI", purpose: "100–160 Word Pitch", status: "CALIBRATED", engine: "SalesGPT / LLM" },
    { id: "M6", name: "MIME & PDF Staging", purpose: "Gmail Drafts + Resume", status: "STAGED", engine: "RFC822 + IMAP" },
    { id: "M7", name: "Sequential Dispatcher", purpose: "60s Cadence Throttling", status: "STANDBY", engine: "SMTP TLS" },
    { id: "M8", name: "Inbound Telemetry", purpose: "Replies & Bounce Ledger", status: "SYNCHRONIZED", engine: "IMAP Guard" },
  ];

  return (
    <div className="space-y-8 animate-fadeIn">
      {/* Top Identity & Status Banner */}
      <div className="bg-neutral-900/60 border border-neutral-800 rounded-sm p-6 relative overflow-hidden backdrop-blur-sm">
        <div className="absolute top-0 right-0 w-80 h-full bg-gradient-to-l from-emerald-500/5 to-transparent pointer-events-none" />
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 relative z-10">
          <div>
            <div className="flex items-center gap-2">
              <span className="px-2 py-0.5 rounded-xs text-[10px] font-mono uppercase tracking-widest bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 flex items-center gap-1.5">
                <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" />
                ACIOS AGENT_OPERATING_SYSTEM
              </span>
              <span className="text-neutral-600 text-xs font-mono">v2.5.0-ENTERPRISE</span>
            </div>
            <h1 className="text-xl md:text-2xl font-bold text-neutral-100 tracking-tight mt-2">
              Autonomous Career Intelligence &amp; Outreach System
            </h1>
            <p className="text-xs text-neutral-400 mt-1 max-w-3xl leading-relaxed">
              Decoupled 8-phase outreach pipeline designed for AI agents. Operates end-to-end entity discovery, corporate RFC permutation sieving, 4-tier deliverability verification, and rate-limited dispatch with zero domain degradation.
            </p>
          </div>

          <div className="flex flex-wrap items-center gap-2 shrink-0">
            <button
              onClick={handleManualRefresh}
              disabled={refreshing}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-sm bg-neutral-800 hover:bg-neutral-750 text-neutral-200 text-xs font-medium border border-neutral-700 transition-colors"
            >
              <RefreshCw className={`w-3.5 h-3.5 ${refreshing ? "animate-spin" : ""}`} />
              <span>Refresh</span>
            </button>
            <button
              onClick={handleImapSync}
              disabled={syncingImap}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-sm bg-neutral-800 hover:bg-neutral-750 text-neutral-200 text-xs font-medium border border-neutral-700 transition-colors"
            >
              <Inbox className={`w-3.5 h-3.5 ${syncingImap ? "animate-pulse text-amber-400" : ""}`} />
              <span>Sync IMAP</span>
            </button>
            <button
              onClick={onNavigateToSettings}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-sm bg-neutral-100 hover:bg-white text-neutral-950 text-xs font-medium shadow-xs transition-colors"
            >
              <span>Profile Settings</span>
              <ExternalLink className="w-3 h-3" />
            </button>
          </div>
        </div>

        {actionStatus && (
          <div className="mt-4 pt-3 border-t border-neutral-800/80 flex items-center justify-between text-xs font-mono text-neutral-300">
            <div className="flex items-center gap-2">
              <span className="w-1.5 h-1.5 rounded-full bg-blue-400 animate-ping" />
              <span>{actionStatus}</span>
            </div>
            <button
              onClick={() => setActionStatus(null)}
              className="text-neutral-500 hover:text-neutral-300 text-[11px]"
            >
              Dismiss
            </button>
          </div>
        )}
      </div>

      {/* Primary Telemetry Metric Cards */}
      <div>
        <div className="flex items-center justify-between mb-3">
          <h2 className="text-xs font-semibold text-neutral-300 uppercase tracking-wider flex items-center gap-2">
            <Activity className="w-3.5 h-3.5 text-neutral-400" />
            <span>Outreach Pipeline Telemetry</span>
          </h2>
          <span className="text-[11px] font-mono text-neutral-500">CANONICAL_DB: acios.db</span>
        </div>

        <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3">
          <div className="bg-neutral-900/40 border border-neutral-800 p-4 rounded-sm">
            <div className="text-[11px] text-neutral-400 uppercase tracking-wider font-mono">Organizations</div>
            <div className="text-2xl font-bold text-neutral-100 font-mono mt-1">
              {metrics.total_organizations}
            </div>
            <div className="text-[10px] text-neutral-500 mt-1">Market expansion targets</div>
          </div>

          <div className="bg-neutral-900/40 border border-neutral-800 p-4 rounded-sm">
            <div className="text-[11px] text-neutral-400 uppercase tracking-wider font-mono">Decision Makers</div>
            <div className="text-2xl font-bold text-neutral-100 font-mono mt-1">
              {metrics.total_contacts}
            </div>
            <div className="text-[10px] text-neutral-500 mt-1">Executive leadership</div>
          </div>

          <div className="bg-neutral-900/40 border border-neutral-800 p-4 rounded-sm">
            <div className="text-[11px] text-neutral-400 uppercase tracking-wider font-mono">Dispatched</div>
            <div className="text-2xl font-bold text-emerald-400 font-mono mt-1">
              {metrics.dispatched_emails}
            </div>
            <div className="text-[10px] text-emerald-500/80 mt-1">Sent via Gmail SMTP TLS</div>
          </div>

          <div className="bg-neutral-900/40 border border-neutral-800 p-4 rounded-sm">
            <div className="text-[11px] text-neutral-400 uppercase tracking-wider font-mono">Inbound Replies</div>
            <div className="text-2xl font-bold text-sky-400 font-mono mt-1">
              {metrics.replies_count}
            </div>
            <div className="text-[10px] text-sky-500/80 mt-1">Tracked via IMAP listener</div>
          </div>

          <div className="bg-neutral-900/40 border border-neutral-800 p-4 rounded-sm">
            <div className="text-[11px] text-neutral-400 uppercase tracking-wider font-mono">Bounces Caught</div>
            <div className="text-2xl font-bold text-amber-400 font-mono mt-1">
              {metrics.bounces_caught}
            </div>
            <div className="text-[10px] text-amber-500/80 mt-1">Suppressed &amp; insulated</div>
          </div>

          <div className="bg-neutral-900/40 border border-neutral-800 p-4 rounded-sm">
            <div className="text-[11px] text-neutral-400 uppercase tracking-wider font-mono">Active Resume</div>
            <div className="text-sm font-semibold text-neutral-200 mt-2 truncate" title={data?.resume.filename}>
              {data?.resume.is_ready ? "Attached" : "Missing"}
            </div>
            <div className="text-[10px] text-neutral-500 mt-1 font-mono">
              {data?.resume.size_kb ? `${data.resume.size_kb} KB PDF` : "No file"}
            </div>
          </div>
        </div>
      </div>

      {/* 8-Phase Decoupled Modular Architecture Grid */}
      <div>
        <div className="flex items-center justify-between mb-3">
          <h2 className="text-xs font-semibold text-neutral-300 uppercase tracking-wider flex items-center gap-2">
            <Layers className="w-3.5 h-3.5 text-neutral-400" />
            <span>Decoupled 8-Phase Architecture Pipeline</span>
          </h2>
          <span className="text-[11px] font-mono text-emerald-400">ALL_MODULES_INDEPENDENT</span>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-3">
          {modules.map((m) => (
            <div
              key={m.id}
              className="bg-neutral-900/30 border border-neutral-800/90 rounded-sm p-3.5 hover:border-neutral-700 transition-colors"
            >
              <div className="flex items-center justify-between">
                <span className="font-mono text-xs font-bold text-neutral-300 bg-neutral-800 px-1.5 py-0.5 rounded-xs">
                  {m.id}
                </span>
                <span className="text-[10px] font-mono font-medium text-emerald-400 bg-emerald-500/10 px-2 py-0.5 rounded-xs border border-emerald-500/20">
                  {m.status}
                </span>
              </div>
              <div className="text-xs font-semibold text-neutral-200 mt-2">
                {m.name}
              </div>
              <div className="text-[11px] text-neutral-400 mt-0.5">
                {m.purpose}
              </div>
              <div className="text-[10px] font-mono text-neutral-500 mt-2 pt-2 border-t border-neutral-800/60 flex items-center justify-between">
                <span>ENGINE:</span>
                <span className="text-neutral-300">{m.engine}</span>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Quick Agent Execution Controls */}
      <div className="bg-neutral-900/40 border border-neutral-800 rounded-sm p-5">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
          <div>
            <h3 className="text-xs font-semibold text-neutral-200 uppercase tracking-wider flex items-center gap-2">
              <Cpu className="w-3.5 h-3.5 text-neutral-400" />
              <span>Agent Operational Operations</span>
            </h3>
            <p className="text-[11px] text-neutral-400 mt-1">
              Direct pipeline execution triggers. The AI agent can also run these directly via CLI (`python -m acios.cli &lt;cmd&gt;`).
            </p>
          </div>

          <div className="flex items-center gap-3">
            <button
              onClick={handleSyncDrafts}
              className="flex items-center gap-2 px-3.5 py-2 rounded-sm bg-neutral-800 hover:bg-neutral-750 text-neutral-200 text-xs font-medium border border-neutral-700 transition-colors"
            >
              <RotateCcw className="w-3.5 h-3.5 text-neutral-300" />
              <span>Sync [Gmail]/Drafts</span>
            </button>
            <button
              onClick={handleTriggerDispatch}
              className="flex items-center gap-2 px-3.5 py-2 rounded-sm bg-emerald-500 hover:bg-emerald-400 text-neutral-950 text-xs font-medium shadow-xs transition-colors"
            >
              <Play className="w-3.5 h-3.5 fill-current" />
              <span>Dispatch Queue (60s Gap)</span>
            </button>
          </div>
        </div>
      </div>

      {/* Recent Outreach & Audit Ledger */}
      <div>
        <div className="flex items-center justify-between mb-3">
          <h2 className="text-xs font-semibold text-neutral-300 uppercase tracking-wider flex items-center gap-2">
            <Clock className="w-3.5 h-3.5 text-neutral-400" />
            <span>Recent Inbound / Outbound Audit Ledger</span>
          </h2>
          <span className="text-[11px] font-mono text-neutral-500">TABLE: outreach_events</span>
        </div>

        <div className="bg-neutral-900/30 border border-neutral-800 rounded-sm overflow-hidden">
          {data?.recent_events && data.recent_events.length > 0 ? (
            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs">
                <thead className="bg-neutral-900/80 border-b border-neutral-800 font-mono text-[11px] text-neutral-400">
                  <tr>
                    <th className="py-2.5 px-4 font-medium">EVENT TYPE</th>
                    <th className="py-2.5 px-4 font-medium">RECIPIENT EMAIL</th>
                    <th className="py-2.5 px-4 font-medium">TIMESTAMP</th>
                    <th className="py-2.5 px-4 font-medium">DIAGNOSTIC DETAILS</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-neutral-800/60 font-mono text-[11px]">
                  {data.recent_events.map((evt) => {
                    const isBounce = evt.event_type === "BOUNCED" || evt.event_type === "BLOCKED";
                    const isReply = evt.event_type.includes("REPLY");
                    const isSent = evt.event_type === "DISPATCHED" || evt.event_type === "SENT";

                    return (
                      <tr key={evt.id} className="hover:bg-neutral-900/50 transition-colors">
                        <td className="py-2.5 px-4">
                          <span
                            className={`px-2 py-0.5 rounded-xs text-[10px] font-medium border ${
                              isBounce
                                ? "bg-amber-500/10 text-amber-400 border-amber-500/20"
                                : isReply
                                ? "bg-sky-500/10 text-sky-400 border-sky-500/20"
                                : isSent
                                ? "bg-emerald-500/10 text-emerald-400 border-emerald-500/20"
                                : "bg-neutral-800 text-neutral-300 border-neutral-700"
                            }`}
                          >
                            {evt.event_type}
                          </span>
                        </td>
                        <td className="py-2.5 px-4 text-neutral-200">
                          {evt.recipient_email}
                        </td>
                        <td className="py-2.5 px-4 text-neutral-500">
                          {evt.timestamp}
                        </td>
                        <td className="py-2.5 px-4 text-neutral-400 truncate max-w-xs" title={evt.details}>
                          {evt.details}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          ) : (
            <div className="py-12 text-center text-neutral-500 text-xs">
              No recent outreach events recorded yet. Run `python -m acios.cli audit-mailbox` to synchronize.
            </div>
          )}
        </div>
      </div>

      {/* Agent Quick Reference Guide */}
      <div className="bg-neutral-900/20 border border-neutral-800/70 rounded-sm p-4 text-xs">
        <div className="flex items-center gap-2 text-neutral-300 font-mono font-semibold mb-2">
          <Terminal className="w-3.5 h-3.5 text-neutral-400" />
          <span>AI AGENT CLI QUICK REFERENCE (ACIOS_CLI)</span>
        </div>
        <p className="text-neutral-400 text-[11px] mb-3">
          As an autonomous AI agent, you can execute all pipeline operations directly via powershell terminal without human intervention:
        </p>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-2 font-mono text-[11px]">
          <div className="p-2 bg-neutral-950 border border-neutral-800/80 rounded-xs">
            <span className="text-emerald-400">python -m acios.cli audit-mailbox</span>
            <div className="text-neutral-500 text-[10px] mt-0.5">Scans Gmail IMAP for replies and bounces, auto-updating ledger</div>
          </div>
          <div className="p-2 bg-neutral-950 border border-neutral-800/80 rounded-xs">
            <span className="text-emerald-400">python -m acios.cli verify-drafts</span>
            <div className="text-neutral-500 text-[10px] mt-0.5">Sieves all draft recipients through 4-tier deliverability filter</div>
          </div>
          <div className="p-2 bg-neutral-950 border border-neutral-800/80 rounded-xs">
            <span className="text-emerald-400">python -m acios.cli sync-drafts</span>
            <div className="text-neutral-500 text-[10px] mt-0.5">Purges stale Gmail drafts and stages verified drafts with PDF resume</div>
          </div>
          <div className="p-2 bg-neutral-950 border border-neutral-800/80 rounded-xs">
            <span className="text-emerald-400">python -m acios.cli dispatch-queue --interval 60</span>
            <div className="text-neutral-500 text-[10px] mt-0.5">Dispatches staged drafts one by one with 60s human pacing gap</div>
          </div>
        </div>
      </div>
    </div>
  );
}
