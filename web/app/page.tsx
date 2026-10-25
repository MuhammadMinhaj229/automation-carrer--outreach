"use client";

import React, { useState, useEffect } from "react";
import Sidebar from "@/components/Sidebar";
import OverviewView from "@/components/OverviewView";
import SettingsView from "@/components/SettingsView";
import { SystemStats, api } from "@/lib/api";
import { Activity, Settings, Cpu } from "lucide-react";

export default function DashboardPage() {
  const [currentView, setCurrentView] = useState<"overview" | "settings">("overview");
  const [stats, setStats] = useState<SystemStats | null>(null);

  useEffect(() => {
    refreshStats();
  }, []);

  const refreshStats = async () => {
    try {
      const data = await api.getSystemStats();
      setStats(data);
    } catch {
      // Ignored if offline
    }
  };

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

  return (
    <div className="flex h-screen w-full bg-neutral-950 text-neutral-100 overflow-hidden font-sans antialiased">
      {/* Enterprise Fixed Sidebar */}
      <Sidebar
        currentView={currentView}
        onViewChange={(view) => setCurrentView(view)}
        stats={stats}
        onRefreshStats={refreshStats}
      />

      {/* Main Execution Viewport */}
      <main className="flex-1 flex flex-col h-screen overflow-hidden bg-neutral-950">
        {/* Top View Selector Header */}
        <header className="px-6 py-3.5 border-b border-neutral-800 bg-neutral-950/90 backdrop-blur-md shrink-0">
          <div className="max-w-6xl mx-auto flex items-center justify-between">
            <div className="flex items-center space-x-2">
              {navItems.map((item) => {
                const isActive = currentView === item.id;
                const Icon = item.icon;

                return (
                  <button
                    key={item.id}
                    onClick={() => setCurrentView(item.id)}
                    className={`flex items-center gap-2 px-3 py-1.5 rounded-sm text-xs font-medium transition-all ${
                      isActive
                        ? "bg-neutral-100 text-neutral-950 shadow-xs"
                        : "text-neutral-400 hover:text-neutral-200 hover:bg-neutral-900 border border-transparent"
                    }`}
                  >
                    <Icon className={`w-3.5 h-3.5 ${isActive ? "text-neutral-950" : "text-neutral-400"}`} />
                    <span className="whitespace-nowrap">{item.label}</span>
                  </button>
                );
              })}
            </div>

            <div className="hidden lg:flex items-center gap-2 font-mono text-[11px] text-neutral-400">
              <span className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse" />
              <span>AGENT_OPERATING_SYSTEM</span>
            </div>
          </div>
        </header>

        {/* Dynamic Viewport Container */}
        <div className="flex-1 overflow-y-auto p-6 md:p-8">
          <div className="max-w-6xl mx-auto">
            {currentView === "overview" && (
              <OverviewView onNavigateToSettings={() => setCurrentView("settings")} />
            )}

            {currentView === "settings" && <SettingsView />}
          </div>
        </div>
      </main>
    </div>
  );
}
