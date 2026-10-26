"use client";

import React, { useState } from "react";
import OverviewView from "@/components/OverviewView";
import SettingsView from "@/components/SettingsView";
import { api } from "@/lib/api";
import {
  Activity,
  Settings,
  Layers,
  FileSpreadsheet,
  HardDrive,
  Inbox,
  RefreshCw,
} from "lucide-react";

export default function DashboardPage() {
  const [currentView, setCurrentView] = useState<"overview" | "settings">("overview");
  const [syncingImap, setSyncingImap] = useState(false);
  const [imapStatus, setImapStatus] = useState<string | null>(null);

  const navItems = [
    {
      id: "overview" as const,
      label: "01 System Overview & Telemetry",
      icon: Activity,
    },
    {
      id: "settings" as const,
      label: "02 Profile & Security Settings",
      icon: Settings,
    },
  ];

  const handleImapSync = () => {
    if (syncingImap) return;
    setSyncingImap(true);
    setImapStatus("Scanning inbox for replies and bounces...");

    const eventSource = new EventSource(api.getImapSyncStreamUrl());

    eventSource.onmessage = (event) => {
      try {
        const payload = JSON.parse(event.data);
        if (payload.type === "progress") {
          setImapStatus(payload.message || "Scanning mailbox...");
        } else if (payload.type === "done") {
          eventSource.close();
          setSyncingImap(false);
          const r = payload.result || {};
          setImapStatus(
            `Sync Complete: ${r.messages_examined || 0} examined, ${r.replies_found || 0} replies, ${r.bounces_found || 0} bounces recorded.`
          );
          setTimeout(() => setImapStatus(null), 6000);
        }
      } catch {
        // Fallback
      }
    };

    eventSource.onerror = () => {
      eventSource.close();
      setSyncingImap(false);
      setImapStatus("IMAP sync finished.");
      setTimeout(() => setImapStatus(null), 4000);
    };
  };

  return (
    <div className="min-h-screen w-full bg-neutral-950 text-neutral-100 font-sans antialiased flex flex-col">
      {/* Top Enterprise Navigation Header (No Sidebar) */}
      <header className="sticky top-0 z-50 px-6 py-3 border-b border-neutral-800 bg-neutral-950/90 backdrop-blur-md">
        <div className="max-w-7xl mx-auto flex flex-col md:flex-row md:items-center justify-between gap-3">
          {/* Brand Identity */}
          <div className="flex items-center gap-3">
            <div className="flex items-center gap-2 px-2.5 py-1 rounded-sm bg-neutral-900 border border-neutral-800">
              <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse" />
              <span className="text-xs font-bold text-neutral-100 font-mono tracking-wider">ACIOS</span>
            </div>
            <span className="text-neutral-700 hidden sm:inline">|</span>
            <div className="text-xs text-neutral-300 font-medium hidden sm:inline">
              Autonomous Career Intelligence &amp; Outbound System
            </div>
          </div>

          {/* Primary View Switcher Pills */}
          <div className="flex items-center space-x-1.5 bg-neutral-900/80 p-1 rounded-sm border border-neutral-800">
            {navItems.map((item) => {
              const isActive = currentView === item.id;
              const Icon = item.icon;

              return (
                <button
                  key={item.id}
                  onClick={() => setCurrentView(item.id)}
                  className={`flex items-center gap-2 px-3 py-1.5 rounded-sm text-xs font-medium transition-all ${
                    isActive
                      ? "bg-neutral-100 text-neutral-950 shadow-xs font-semibold"
                      : "text-neutral-400 hover:text-neutral-200 hover:bg-neutral-850"
                  }`}
                >
                  <Icon className={`w-3.5 h-3.5 ${isActive ? "text-neutral-950" : "text-neutral-400"}`} />
                  <span className="whitespace-nowrap">{item.label}</span>
                </button>
              );
            })}
          </div>

          {/* Quick Header Utility Actions */}
          <div className="flex items-center gap-2 shrink-0">
            <button
              onClick={handleImapSync}
              disabled={syncingImap}
              title="Scan Gmail IMAP for replies and bounces"
              className="flex items-center gap-1.5 px-2.5 py-1.5 rounded-sm bg-neutral-900 hover:bg-neutral-850 text-neutral-300 text-xs font-medium border border-neutral-800 transition-colors disabled:opacity-50"
            >
              <Inbox className={`w-3.5 h-3.5 ${syncingImap ? "animate-pulse text-amber-400" : "text-neutral-400"}`} />
              <span className="hidden lg:inline">{syncingImap ? "Scanning..." : "Sync IMAP"}</span>
            </button>

            <a
              href={api.getMasterExcelDownloadUrl()}
              download="Master_Career_Intelligence_Database.xlsx"
              title="Download Master Intelligence Spreadsheet"
              className="flex items-center gap-1.5 px-2.5 py-1.5 rounded-sm bg-neutral-900 hover:bg-neutral-850 text-neutral-300 text-xs font-medium border border-neutral-800 transition-colors"
            >
              <FileSpreadsheet className="w-3.5 h-3.5 text-neutral-400" />
              <span className="hidden lg:inline">Export XLSX</span>
            </a>

            <a
              href={api.getDbDownloadUrl()}
              download="acios.db"
              title="Download SQLite Database"
              className="flex items-center gap-1.5 px-2.5 py-1.5 rounded-sm bg-neutral-900 hover:bg-neutral-850 text-neutral-300 text-xs font-medium border border-neutral-800 transition-colors"
            >
              <HardDrive className="w-3.5 h-3.5 text-neutral-400" />
              <span className="hidden lg:inline">Export DB</span>
            </a>

            <div className="hidden xl:flex items-center gap-1.5 px-2.5 py-1.5 rounded-sm bg-neutral-900/60 border border-neutral-800 text-[11px] font-mono text-neutral-400">
              <span className="w-1.5 h-1.5 rounded-full bg-emerald-400" />
              <span>BFF Proxy Active</span>
            </div>
          </div>
        </div>

        {imapStatus && (
          <div className="max-w-7xl mx-auto mt-2 pt-2 border-t border-neutral-800/60 flex items-center justify-between text-xs font-mono text-neutral-300">
            <div className="flex items-center gap-2">
              <span className="w-1.5 h-1.5 rounded-full bg-blue-400 animate-ping" />
              <span>{imapStatus}</span>
            </div>
            <button
              onClick={() => setImapStatus(null)}
              className="text-neutral-500 hover:text-neutral-300 text-[11px]"
            >
              Dismiss
            </button>
          </div>
        )}
      </header>

      {/* Main Full-Width Content Viewport (No Sidebar) */}
      <main className="flex-1 w-full max-w-7xl mx-auto p-6 md:p-8">
        {currentView === "overview" && (
          <OverviewView onNavigateToSettings={() => setCurrentView("settings")} />
        )}

        {currentView === "settings" && <SettingsView />}
      </main>
    </div>
  );
}
