"use client";

import React, { useState, useEffect } from "react";
import { SystemStats, SettingsData, api } from "@/lib/api";
import {
  Activity,
  Layers,
  Settings,
  ShieldCheck,
  FileSpreadsheet,
  HardDrive,
  RefreshCw,
  ArrowRight,
  Inbox,
  User,
  CheckCircle2,
} from "lucide-react";

interface SidebarProps {
  currentView: "overview" | "settings";
  onViewChange: (view: "overview" | "settings") => void;
  stats: SystemStats | null;
  onRefreshStats: () => void;
}

export default function Sidebar({
  currentView,
  onViewChange,
  stats,
  onRefreshStats,
}: SidebarProps) {
  const [settings, setSettings] = useState<SettingsData | null>(null);
  const [syncingImap, setSyncingImap] = useState(false);
  const [imapProgress, setImapProgress] = useState<{
    percent: number;
    message: string;
    elapsedSeconds: number;
  } | null>(null);
  const [syncResult, setSyncResult] = useState<string | null>(null);

  useEffect(() => {
    loadSettingsData();
  }, []);

  const loadSettingsData = async () => {
    try {
      const data = await api.getSettings();
      setSettings(data);
    } catch {
      // Offline fallback
    }
  };

  const handleImapSync = () => {
    if (syncingImap) return;
    setSyncingImap(true);
    setSyncResult(null);
    setImapProgress({
      percent: 5,
      message: "Initiating TLS connection to imap.gmail.com:993...",
      elapsedSeconds: 0,
    });

    const startTime = Date.now();
    const timerInterval = setInterval(() => {
      setImapProgress((prev) => {
        if (!prev) return null;
        return {
          ...prev,
          elapsedSeconds: Math.floor((Date.now() - startTime) / 1000),
        };
      });
    }, 1000);

    const eventSource = new EventSource(api.getImapSyncStreamUrl());

    eventSource.onmessage = (event) => {
      try {
        const payload = JSON.parse(event.data);
        if (payload.type === "progress") {
          setImapProgress((prev) => ({
            percent: Math.min(100, Math.max(prev?.percent || 0, payload.percent || 0)),
            message: payload.message || "Scanning mailbox...",
            elapsedSeconds: Math.floor((Date.now() - startTime) / 1000),
          }));
        } else if (payload.type === "done") {
          clearInterval(timerInterval);
          eventSource.close();
          setSyncingImap(false);
          const res = payload.result || {};
          setSyncResult(
            `Complete in ${Math.floor((Date.now() - startTime) / 1000)}s: ${res.messages_examined || 0} emails examined, ${res.replies_found || 0} replies recorded, ${res.bounces_found || 0} bounces suppressed.`
          );
          onRefreshStats();
        }
      } catch {
        // Fallback
      }
    };

    eventSource.onerror = () => {
      clearInterval(timerInterval);
      eventSource.close();
      setSyncingImap(false);
      setSyncResult("IMAP sync finished.");
      onRefreshStats();
    };
  };

  const navItems = [
    {
      id: "overview" as const,
      name: "System Overview",
      subtitle: "Telemetry, 8-phase grid & ledger",
      icon: Activity,
    },
    {
      id: "settings" as const,
      name: "Profile & Settings",
      subtitle: "Identity, credentials & master resume",
      icon: Settings,
    },
  ];

  return (
    <aside className="w-80 shrink-0 bg-neutral-950 border-r border-neutral-800 flex flex-col justify-between h-screen overflow-y-auto select-none font-sans">
      <div>
        {/* Brand Header */}
        <div className="p-5 border-b border-neutral-800 bg-neutral-900/40">
          <div className="flex items-center gap-2 text-xs font-semibold tracking-wider text-neutral-400 uppercase">
            <Layers className="w-4 h-4 text-neutral-200" />
            <span>Career Operating System</span>
          </div>
          <h1 className="text-sm font-bold text-neutral-100 tracking-tight mt-1">
            ACIOS Enterprise Agent Cockpit
          </h1>
          <p className="text-[11px] text-neutral-400 mt-1 leading-relaxed">
            Autonomous Outreach Telemetry &amp; Sieve Engine
          </p>
        </div>

        {/* 2-Page Primary Navigation */}
        <div className="p-4 border-b border-neutral-800">
          <div className="text-[10px] font-bold text-neutral-400 uppercase tracking-widest mb-2">
            Navigation
          </div>
          <div className="space-y-1">
            {navItems.map((item) => {
              const Icon = item.icon;
              const isActive = currentView === item.id;
              return (
                <button
                  key={item.id}
                  onClick={() => onViewChange(item.id)}
                  className={`w-full flex items-center justify-between p-2.5 rounded-sm text-left transition-colors ${
                    isActive
                      ? "bg-neutral-800 text-white font-medium border-l-2 border-neutral-200"
                      : "text-neutral-400 hover:text-neutral-200 hover:bg-neutral-900/80"
                  }`}
                >
                  <div className="flex items-center gap-3">
                    <Icon className={`w-4 h-4 ${isActive ? "text-neutral-100" : "text-neutral-400"}`} />
                    <div>
                      <div className="text-xs font-medium">{item.name}</div>
                      <div className="text-[10px] text-neutral-400 truncate max-w-[170px]">
                        {item.subtitle}
                      </div>
                    </div>
                  </div>
                </button>
              );
            })}
          </div>
        </div>

        {/* Database Metric Counters */}
        <div className="p-4 border-b border-neutral-800">
          <div className="flex items-center justify-between mb-2">
            <span className="text-[10px] font-bold text-neutral-400 uppercase tracking-widest">
              Live Pipeline Metrics
            </span>
            <button
              onClick={onRefreshStats}
              title="Refresh Stats"
              className="p-1 text-neutral-400 hover:text-neutral-200 rounded-sm hover:bg-neutral-900"
            >
              <RefreshCw className="w-3 h-3" />
            </button>
          </div>
          <div className="grid grid-cols-2 gap-2 text-xs">
            <div className="p-2 rounded-sm bg-neutral-900/60 border border-neutral-800">
              <div className="text-[10px] text-neutral-400">Organizations</div>
              <div className="text-sm font-bold text-neutral-100 font-mono mt-0.5">
                {stats?.total_organizations ?? "—"}
              </div>
            </div>
            <div className="p-2 rounded-sm bg-neutral-900/60 border border-neutral-800">
              <div className="text-[10px] text-neutral-400">Decision Makers</div>
              <div className="text-sm font-bold text-neutral-100 font-mono mt-0.5">
                {stats?.total_contacts ?? "—"}
              </div>
            </div>
            <div className="p-2 rounded-sm bg-neutral-900/60 border border-neutral-800">
              <div className="text-[10px] text-neutral-400">Market Signals</div>
              <div className="text-sm font-bold text-neutral-100 font-mono mt-0.5">
                {stats?.total_signals ?? "—"}
              </div>
            </div>
            <div className="p-2 rounded-sm bg-neutral-900/60 border border-neutral-800">
              <div className="text-[10px] text-neutral-400">Approved Drafts</div>
              <div className="text-sm font-bold text-neutral-100 font-mono mt-0.5">
                {stats?.total_staged_drafts ?? "—"}
              </div>
            </div>
          </div>
          <div className="mt-2 p-1.5 rounded-sm bg-neutral-900/40 border border-neutral-850 flex items-center justify-between text-[11px] text-neutral-400">
            <span>Suppressed Addresses</span>
            <span className="font-mono text-neutral-300 font-medium">
              {stats?.total_suppressed_emails ?? "—"}
            </span>
          </div>
        </div>

        {/* Database Direct Downloads */}
        <div className="p-4 border-b border-neutral-800">
          <div className="text-[10px] font-bold text-neutral-400 uppercase tracking-widest mb-2">
            Database Access
          </div>
          <div className="space-y-1.5">
            <a
              href={api.getMasterExcelDownloadUrl()}
              download="Master_Career_Intelligence_Database.xlsx"
              className="flex items-center justify-between p-2 rounded-sm bg-neutral-900/70 border border-neutral-800 hover:border-neutral-700 hover:bg-neutral-850 text-neutral-200 text-xs transition-colors"
            >
              <div className="flex items-center gap-2">
                <FileSpreadsheet className="w-3.5 h-3.5 text-neutral-400" />
                <span>Export Master Intelligence</span>
              </div>
              <span className="text-[10px] font-mono text-neutral-400">[XLSX]</span>
            </a>
            <a
              href={api.getDbDownloadUrl()}
              download="acios.db"
              className="flex items-center justify-between p-2 rounded-sm bg-neutral-900/70 border border-neutral-800 hover:border-neutral-700 hover:bg-neutral-850 text-neutral-200 text-xs transition-colors"
            >
              <div className="flex items-center gap-2">
                <HardDrive className="w-3.5 h-3.5 text-neutral-400" />
                <span>Export SQLite Database</span>
              </div>
              <span className="text-[10px] font-mono text-neutral-400">[SQLITE]</span>
            </a>
          </div>
        </div>

        {/* Candidate Identity Card */}
        <div className="p-4 border-b border-neutral-800">
          <div className="flex items-center justify-between mb-2">
            <span className="text-[10px] font-bold text-neutral-400 uppercase tracking-widest">
              Active Candidate
            </span>
            <span className="text-[10px] font-mono text-emerald-400 bg-emerald-500/10 px-1.5 py-0.5 rounded-xs border border-emerald-500/20">
              CONFIGURED
            </span>
          </div>
          <div className="p-2.5 rounded-sm bg-neutral-900/80 border border-neutral-800 space-y-1 text-xs">
            <div className="font-semibold text-neutral-200">
              {settings?.profile.full_name || "Mohammed Minhaj Mahmood"}
            </div>
            <div className="text-[11px] text-neutral-400 truncate font-mono">
              {settings?.profile.email || "minhajmuhammad229@gmail.com"}
            </div>
            <div className="text-[11px] text-neutral-400 font-mono">
              {settings?.profile.phone || "+91 9908597337"}
            </div>
            <button
              onClick={() => onViewChange("settings")}
              className="mt-2 w-full py-1.5 px-2 bg-neutral-800 hover:bg-neutral-750 text-neutral-200 rounded-sm text-[11px] font-medium transition-colors flex items-center justify-center gap-1.5"
            >
              <Settings className="w-3 h-3 text-neutral-400" />
              <span>Edit Profile &amp; Settings</span>
            </button>
          </div>
        </div>

        {/* Quick Operations: Real-Time IMAP Inbox Sync */}
        <div className="p-4">
          <div className="text-[10px] font-bold text-neutral-400 uppercase tracking-widest mb-2">
            Inbox Synchronization
          </div>
          <button
            onClick={handleImapSync}
            disabled={syncingImap}
            className="w-full p-2.5 rounded-sm bg-neutral-900 border border-neutral-800 hover:border-neutral-700 hover:bg-neutral-850 text-neutral-200 text-xs font-medium transition-colors flex items-center justify-between disabled:opacity-50"
          >
            <div className="flex items-center gap-2">
              <Inbox className={`w-3.5 h-3.5 ${syncingImap ? "animate-pulse text-amber-400" : "text-neutral-400"}`} />
              <span>{syncingImap ? "Scanning Inbox..." : "Check Inbox for Replies"}</span>
            </div>
            <ArrowRight className="w-3.5 h-3.5 text-neutral-500" />
          </button>

          {syncingImap && imapProgress && (
            <div className="mt-2 p-2.5 rounded-sm bg-neutral-900/90 border border-neutral-800 space-y-1.5">
              <div className="flex items-center justify-between text-[11px]">
                <span className="text-neutral-300 font-medium">Scanning IMAP Headers</span>
                <span className="font-mono text-neutral-400">{imapProgress.elapsedSeconds}s elapsed</span>
              </div>
              <div className="w-full bg-neutral-950 h-1.5 rounded-full overflow-hidden border border-neutral-800">
                <div
                  className="bg-neutral-200 h-full transition-all duration-300"
                  style={{ width: `${imapProgress.percent}%` }}
                />
              </div>
              <div className="text-[10px] text-neutral-400 font-mono truncate">
                {imapProgress.message}
              </div>
            </div>
          )}

          {syncResult && !syncingImap && (
            <div className="mt-2 p-2 rounded-sm bg-neutral-900/50 border border-neutral-800 text-[10px] text-neutral-300 font-mono">
              {syncResult}
            </div>
          )}
        </div>
      </div>

      {/* Footer System Status */}
      <div className="p-4 border-t border-neutral-800 bg-neutral-900/20 text-[10px] text-neutral-400 flex items-center justify-between">
        <div className="flex items-center gap-1.5">
          <Activity className="w-3 h-3 text-emerald-400" />
          <span>FastAPI Engine: 127.0.0.1:8000</span>
        </div>
        <span className="font-mono text-neutral-300">[ONLINE]</span>
      </div>
    </aside>
  );
}
