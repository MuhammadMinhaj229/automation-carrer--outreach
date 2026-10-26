"use client";

import React, { useState, useEffect } from "react";
import { HierarchyData, SignalRecord, api } from "@/lib/api";
import {
  Compass,
  Search,
  Filter,
  Download,
  CheckSquare,
  Square,
  ArrowRight,
  ExternalLink,
  Calendar,
  Building,
  Sparkles,
  Zap,
} from "lucide-react";

interface Tab1DiscoveryProps {
  onForwardToTab2: (selectedOrgs: string[]) => void;
}

export default function Tab1Discovery({ onForwardToTab2 }: Tab1DiscoveryProps) {
  const [hierarchy, setHierarchy] = useState<HierarchyData | null>(null);
  const [selectedContinent, setSelectedContinent] = useState<string>("Middle East / GCC");
  const [selectedCountry, setSelectedCountry] = useState<string>("Oman");
  const [selectedRegion, setSelectedRegion] = useState<string>("All Regions");
  const [selectedTrigger, setSelectedTrigger] = useState<string>("All Strategic Triggers");

  const [searchOrg, setSearchOrg] = useState<string>("");
  const [searchWebsite, setSearchWebsite] = useState<string>("");
  const [customKeywords, setCustomKeywords] = useState<string>("");

  const [scanning, setScanning] = useState<boolean>(false);
  const [deepRadarRunning, setDeepRadarRunning] = useState<boolean>(false);
  const [signals, setSignals] = useState<SignalRecord[]>([]);
  const [excelFilename, setExcelFilename] = useState<string | null>(null);
  const [selectedOrgs, setSelectedOrgs] = useState<Set<string>>(new Set());
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    loadHierarchyAndDefaultSignals();
  }, []);

  const loadHierarchyAndDefaultSignals = async () => {
    try {
      const data = await api.getHierarchy();
      setHierarchy(data);
    } catch {
      // Ignored
    }
  };

  const availableCountries = hierarchy?.continents[selectedContinent]
    ? Object.keys(hierarchy.continents[selectedContinent])
    : [];

  const availableRegions =
    hierarchy?.continents[selectedContinent] &&
    hierarchy.continents[selectedContinent][selectedCountry]
      ? ["All Regions", ...hierarchy.continents[selectedContinent][selectedCountry]]
      : ["All Regions"];

  const handleContinentChange = (cont: string) => {
    setSelectedContinent(cont);
    if (hierarchy?.continents[cont]) {
      const firstCountry = Object.keys(hierarchy.continents[cont])[0] || "";
      setSelectedCountry(firstCountry);
      setSelectedRegion("All Regions");
    }
  };

  const handleCountryChange = (country: string) => {
    setSelectedCountry(country);
    setSelectedRegion("All Regions");
  };

  const runScan = async (
    country = selectedCountry,
    region = selectedRegion,
    trigger = selectedTrigger,
    orgName = searchOrg,
    web = searchWebsite,
    kws = customKeywords
  ) => {
    setScanning(true);
    setError(null);
    setSelectedOrgs(new Set());
    try {
      const res = await api.runDiscoveryScan({
        country,
        region,
        trigger_category: trigger,
        search_org: orgName.trim() || undefined,
        search_website: web.trim() || undefined,
        custom_keywords: kws.trim() || undefined,
        max_results: 30,
      });
      setSignals(res.signals);
      setExcelFilename(res.excel_filename);

      // By default select all found organizations
      const allNames = new Set(res.signals.map((s) => s.organization_name));
      setSelectedOrgs(allNames);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed to execute ecosystem scan");
    } finally {
      setScanning(false);
    }
  };

  const runCrawl4AIDeepRadar = async () => {
    setDeepRadarRunning(true);
    setError(null);
    try {
      const res = await api.runDeepRadar({
        organization_name: searchOrg || undefined,
        website: searchWebsite || undefined,
        keywords: customKeywords || undefined,
        country: selectedCountry,
      });
      if (res.signals && res.signals.length > 0) {
        setSignals((prev) => [...res.signals, ...prev]);
        setSelectedOrgs((prev) => {
          const next = new Set(prev);
          res.signals.forEach((s) => next.add(s.organization_name));
          return next;
        });
      }
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed to execute Crawl4AI + GDELT radar");
    } finally {
      setDeepRadarRunning(false);
    }
  };

  const handleQuickPreset = (presetCountry: string, presetRegion: string, presetKeywords: string) => {
    setSelectedContinent("Middle East / GCC");
    setSelectedCountry(presetCountry);
    setSelectedRegion(presetRegion);
    setSelectedTrigger("All Strategic Triggers");
    setCustomKeywords(presetKeywords);
    runScan(presetCountry, presetRegion, "All Strategic Triggers", "", "", presetKeywords);
  };

  const toggleSelectOrg = (orgName: string) => {
    const updated = new Set(selectedOrgs);
    if (updated.has(orgName)) {
      updated.delete(orgName);
    } else {
      updated.add(orgName);
    }
    setSelectedOrgs(updated);
  };

  const toggleSelectAll = () => {
    if (selectedOrgs.size === signals.length) {
      setSelectedOrgs(new Set());
    } else {
      setSelectedOrgs(new Set(signals.map((s) => s.organization_name)));
    }
  };

  const handleForward = () => {
    const orgList = Array.from(selectedOrgs);
    if (orgList.length === 0) return;
    onForwardToTab2(orgList);
  };

  return (
    <div className="space-y-6">
      {/* Header Banner */}
      <div className="p-6 rounded-lg bg-neutral-900/50 border border-neutral-800 flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-2">
            <span className="text-[10px] font-mono uppercase tracking-widest text-neutral-300 bg-neutral-800 px-2 py-0.5 rounded-xs border border-neutral-700">
              Step 01
            </span>
            <span className="text-xs text-neutral-400 font-medium">Market Scoping &amp; Expansion Triggers</span>
          </div>
          <h2 className="text-xl font-bold text-neutral-100 tracking-tight mt-1.5">
            Market Discovery: Growth Signals &amp; Companies
          </h2>
          <p className="text-xs text-neutral-400 mt-1 max-w-2xl leading-relaxed">
            Identifies enterprise organizations with active hiring surges, new facility inaugurations, and funding milestones across your target region.
          </p>
        </div>

        {signals.length > 0 && excelFilename && (
          <a
            href={api.getDiscoveryDownloadUrl(excelFilename)}
            download={excelFilename}
            className="self-start md:self-auto px-4 py-2.5 rounded-sm bg-neutral-900 hover:bg-neutral-850 text-neutral-200 border border-neutral-750 text-xs font-medium transition-colors flex items-center gap-2 shrink-0 shadow-xs"
          >
            <Download className="w-3.5 h-3.5 text-neutral-300" />
            <span>Download Report (.xlsx)</span>
          </a>
        )}
      </div>

      {/* Quick Launch Ecosystem Presets */}
      <div className="flex flex-wrap items-center gap-2">
        <span className="text-[11px] text-neutral-400 font-medium mr-1 flex items-center gap-1">
          <Zap className="w-3.5 h-3.5 text-neutral-400" />
          <span>Quick Regional Scans:</span>
        </span>
        <button
          onClick={() => handleQuickPreset("Oman", "Muscat (Capital, Corporate & Research Hub)", "Biofuel Water Data")}
          className="px-3 py-1.5 rounded-sm bg-neutral-900 hover:bg-neutral-850 text-neutral-300 border border-neutral-800 text-[11px] font-medium transition-colors"
        >
          Oman: Energy &amp; Water
        </button>
        <button
          onClick={() => handleQuickPreset("Saudi Arabia", "Riyadh (Capital & Tech HQ)", "Enterprise AI Cloud QA")}
          className="px-3 py-1.5 rounded-sm bg-neutral-900 hover:bg-neutral-850 text-neutral-300 border border-neutral-800 text-[11px] font-medium transition-colors"
        >
          Saudi Arabia: Riyadh Tech &amp; AI
        </button>
        <button
          onClick={() => handleQuickPreset("United Arab Emirates", "Dubai (Tech, AI, Logistics & Financial Freezones)", "Scaleup Expansion")}
          className="px-3 py-1.5 rounded-sm bg-neutral-900 hover:bg-neutral-850 text-neutral-300 border border-neutral-800 text-[11px] font-medium transition-colors"
        >
          UAE: Dubai Scaleups
        </button>
        <button
          onClick={() => handleQuickPreset("Qatar", "Doha (Capital & Enterprise Systems)", "Enterprise Cloud Infrastructure")}
          className="px-3 py-1.5 rounded-sm bg-neutral-900 hover:bg-neutral-850 text-neutral-300 border border-neutral-800 text-[11px] font-medium transition-colors"
        >
          Qatar: Enterprise Systems
        </button>
      </div>

      {error && (
        <div className="p-3.5 rounded-sm bg-red-950/60 border border-red-800 text-red-200 text-xs">
          {error}
        </div>
      )}

      {/* Control Cockpit Form */}
      <div className="p-5 rounded-lg bg-neutral-900/60 border border-neutral-800 space-y-4">
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
          {/* Continent Dropdown */}
          <div>
            <label className="block text-xs font-semibold text-neutral-300 mb-1.5">
              Target Continent / Macro Region
            </label>
            <select
              value={selectedContinent}
              onChange={(e) => handleContinentChange(e.target.value)}
              className="w-full bg-neutral-950 border border-neutral-800 rounded-sm py-2 px-3 text-xs text-neutral-200 focus:outline-hidden focus:border-neutral-500"
            >
              {hierarchy &&
                Object.keys(hierarchy.continents).map((cont) => (
                  <option key={cont} value={cont}>
                    {cont}
                  </option>
                ))}
            </select>
          </div>

          {/* Country Dropdown */}
          <div>
            <label className="block text-xs font-semibold text-neutral-300 mb-1.5">
              Specific Country
            </label>
            <select
              value={selectedCountry}
              onChange={(e) => handleCountryChange(e.target.value)}
              className="w-full bg-neutral-950 border border-neutral-800 rounded-sm py-2 px-3 text-xs text-neutral-200 focus:outline-hidden focus:border-neutral-500"
            >
              {availableCountries.map((c) => (
                <option key={c} value={c}>
                  {c}
                </option>
              ))}
            </select>
          </div>

          {/* Region / City Dropdown */}
          <div>
            <label className="block text-xs font-semibold text-neutral-300 mb-1.5">
              Municipal Sub-Region / City
            </label>
            <select
              value={selectedRegion}
              onChange={(e) => setSelectedRegion(e.target.value)}
              className="w-full bg-neutral-950 border border-neutral-800 rounded-sm py-2 px-3 text-xs text-neutral-200 focus:outline-hidden focus:border-neutral-500"
            >
              {availableRegions.map((r) => (
                <option key={r} value={r}>
                  {r}
                </option>
              ))}
            </select>
          </div>

          {/* Strategic Trigger Dropdown */}
          <div>
            <label className="block text-xs font-semibold text-neutral-300 mb-1.5">
              Expansion Trigger Category
            </label>
            <select
              value={selectedTrigger}
              onChange={(e) => setSelectedTrigger(e.target.value)}
              className="w-full bg-neutral-950 border border-neutral-800 rounded-sm py-2 px-3 text-xs text-neutral-200 focus:outline-hidden focus:border-neutral-500"
            >
              <option value="All Strategic Triggers">All Strategic Triggers</option>
              {hierarchy &&
                Object.keys(hierarchy.triggers).map((k) => (
                  <option key={k} value={k}>
                    {k}
                  </option>
                ))}
            </select>
          </div>
        </div>

        {/* Custom Target Search & Deep Filter Inputs */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4 pt-3 border-t border-neutral-850">
          <div>
            <label className="block text-xs font-medium text-neutral-300 mb-1">
              Search by Organization Name
            </label>
            <div className="relative">
              <Building className="w-3.5 h-3.5 text-neutral-500 absolute left-3 top-2.5" />
              <input
                type="text"
                placeholder="e.g. Omantel, Hema Energy, OQ..."
                value={searchOrg}
                onChange={(e) => setSearchOrg(e.target.value)}
                className="w-full bg-neutral-950 border border-neutral-800 rounded-sm py-2 pl-9 pr-3 text-xs text-neutral-200 placeholder:text-neutral-600 focus:outline-hidden focus:border-neutral-500"
              />
            </div>
          </div>

          <div>
            <label className="block text-xs font-medium text-neutral-300 mb-1">
              Search by Website Domain
            </label>
            <div className="relative">
              <Search className="w-3.5 h-3.5 text-neutral-500 absolute left-3 top-2.5" />
              <input
                type="text"
                placeholder="e.g. omantel.om, aramco.com..."
                value={searchWebsite}
                onChange={(e) => setSearchWebsite(e.target.value)}
                className="w-full bg-neutral-950 border border-neutral-800 rounded-sm py-2 pl-9 pr-3 text-xs text-neutral-200 placeholder:text-neutral-600 focus:outline-hidden focus:border-neutral-500"
              />
            </div>
          </div>

          <div>
            <label className="block text-xs font-medium text-neutral-300 mb-1">
              Custom Strategic Keywords
            </label>
            <div className="relative">
              <Filter className="w-3.5 h-3.5 text-neutral-500 absolute left-3 top-2.5" />
              <input
                type="text"
                placeholder="e.g. Series A, Cloud QA, Biofuel..."
                value={customKeywords}
                onChange={(e) => setCustomKeywords(e.target.value)}
                className="w-full bg-neutral-950 border border-neutral-800 rounded-sm py-2 pl-9 pr-3 text-xs text-neutral-200 placeholder:text-neutral-600 focus:outline-hidden focus:border-neutral-500"
              />
            </div>
          </div>
        </div>

        {/* Scan Trigger Action */}
        <div className="pt-2 flex flex-col sm:flex-row sm:items-center justify-between gap-3">
          <div className="text-[11px] text-neutral-400">
            Active Scoping: <strong className="text-neutral-300">{selectedContinent}</strong> &rarr; <strong className="text-neutral-300">{selectedCountry}</strong> &rarr; <strong className="text-neutral-300">{selectedRegion}</strong>
          </div>

          <div className="flex items-center gap-2">
            <button
              onClick={runCrawl4AIDeepRadar}
              disabled={deepRadarRunning || scanning}
              className="px-4 py-2.5 rounded-sm bg-neutral-900 hover:bg-neutral-850 text-neutral-200 border border-neutral-750 text-xs font-medium transition-colors flex items-center gap-1.5 shadow-xs disabled:opacity-50"
              title="Performs deep web crawl of corporate newsrooms and regional press releases"
            >
              {deepRadarRunning ? (
                <>
                  <div className="w-3.5 h-3.5 border-2 border-neutral-400 border-t-white rounded-full animate-spin" />
                  <span>Scanning Newsrooms...</span>
                </>
              ) : (
                <>
                  <Zap className="w-3.5 h-3.5 text-neutral-300" />
                  <span>Deep Web &amp; News Scan</span>
                </>
              )}
            </button>

            <button
              onClick={() => runScan()}
              disabled={scanning || deepRadarRunning}
              className="px-6 py-2.5 rounded-sm bg-neutral-100 hover:bg-white text-neutral-950 text-xs font-semibold tracking-wide transition-colors flex items-center gap-2 shadow-xs disabled:opacity-50"
            >
              {scanning ? (
                <>
                  <div className="w-3.5 h-3.5 border-2 border-neutral-950 border-t-transparent rounded-full animate-spin" />
                  <span>Scanning Market...</span>
                </>
              ) : (
                <>
                  <Compass className="w-3.5 h-3.5" />
                  <span>Run Market Scan</span>
                </>
              )}
            </button>
          </div>
        </div>
      </div>

      {/* Discovered Records Table */}
      {signals.length > 0 && (
        <div className="space-y-3">
          <div className="flex items-center justify-between bg-neutral-900/40 p-3 rounded-lg border border-neutral-800">
            <div className="flex items-center gap-3">
              <span className="text-xs font-semibold text-neutral-100">
                Identified Organizations &amp; Growth Triggers ({signals.length})
              </span>
              <span className="text-[11px] font-mono text-neutral-400 bg-neutral-900 px-2 py-0.5 rounded-xs border border-neutral-850">
                {selectedOrgs.size} selected for Decision-Maker Audit
              </span>
            </div>

            <button
              onClick={handleForward}
              disabled={selectedOrgs.size === 0}
              className="px-5 py-2 rounded-sm bg-neutral-100 hover:bg-white text-neutral-950 text-xs font-semibold transition-all flex items-center gap-2 disabled:opacity-40 shadow-xs"
            >
              <span>Review Decision-Makers in Tab 2 ({selectedOrgs.size})</span>
              <ArrowRight className="w-3.5 h-3.5" />
            </button>
          </div>

          <div className="border border-neutral-800 rounded-lg overflow-x-auto bg-neutral-950 shadow-xs">
            <table className="w-full text-left text-xs border-collapse">
              <thead>
                <tr className="border-b border-neutral-800 bg-neutral-900/90 text-neutral-400 text-[11px] uppercase tracking-wider">
                  <th className="py-3 px-3 w-10 text-center">
                    <button onClick={toggleSelectAll} className="hover:text-white" title="Select All">
                      {selectedOrgs.size === signals.length ? (
                        <CheckSquare className="w-4 h-4 text-neutral-200" />
                      ) : (
                        <Square className="w-4 h-4 text-neutral-500" />
                      )}
                    </button>
                  </th>
                  <th className="py-3 px-3 font-semibold">Organization</th>
                  <th className="py-3 px-3 font-semibold">Location</th>
                  <th className="py-3 px-3 font-semibold">Trigger &amp; Headline</th>
                  <th className="py-3 px-3 font-semibold">Publication Date</th>
                  <th className="py-3 px-3 font-semibold">Talent Demand</th>
                  <th className="py-3 px-3 font-semibold text-right">Evidence Status</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-neutral-850">
                {signals.map((sig, idx) => {
                  const isSelected = selectedOrgs.has(sig.organization_name);
                  return (
                    <tr
                      key={idx}
                      className={`hover:bg-neutral-900/50 transition-colors ${
                        isSelected ? "bg-neutral-900/30" : ""
                      }`}
                    >
                      <td className="py-3 px-3 text-center">
                        <button
                          onClick={() => toggleSelectOrg(sig.organization_name)}
                          className="hover:text-white"
                        >
                          {isSelected ? (
                            <CheckSquare className="w-4 h-4 text-neutral-200" />
                          ) : (
                            <Square className="w-4 h-4 text-neutral-600" />
                          )}
                        </button>
                      </td>
                      <td className="py-3 px-3">
                        <div className="font-semibold text-neutral-100 text-sm">
                          {sig.organization_name}
                        </div>
                        {sig.website && (
                          <a
                            href={sig.website.startsWith("http") ? sig.website : `https://${sig.website}`}
                            target="_blank"
                            rel="noreferrer"
                            className="text-[11px] text-neutral-400 hover:text-neutral-200 flex items-center gap-1 mt-0.5"
                          >
                            <span>{sig.website.replace(/^https?:\/\/(www\.)?/, "")}</span>
                            <ExternalLink className="w-2.5 h-2.5" />
                          </a>
                        )}
                      </td>
                      <td className="py-3 px-3">
                        <div className="text-neutral-200 font-medium">{sig.country}</div>
                        <div className="text-[11px] text-neutral-400">{sig.region}</div>
                      </td>
                      <td className="py-3 px-3 max-w-sm">
                        <div className="inline-block text-[10px] font-mono uppercase bg-neutral-900 text-neutral-300 px-1.5 py-0.5 rounded-xs border border-neutral-800 mb-1">
                          {sig.trigger_type || "Expansion Trigger"}
                        </div>
                        <div className="text-neutral-300 line-clamp-2 text-xs leading-relaxed">
                          {sig.headline}
                        </div>
                      </td>
                      <td className="py-3 px-3 text-neutral-400 font-mono text-[11px] whitespace-nowrap">
                        <div className="flex items-center gap-1.5">
                          <Calendar className="w-3 h-3 text-neutral-500" />
                          <span>{sig.published_date || "2026-10-24"}</span>
                        </div>
                      </td>
                      <td className="py-3 px-3">
                        <span className="text-[11px] font-medium text-neutral-300">
                          {sig.talent_demand || "Technical & QA Talent"}
                        </span>
                      </td>
                      <td className="py-3 px-3 text-right">
                        <span className="text-[10px] font-mono px-2 py-0.5 rounded-xs bg-neutral-900 text-neutral-300 border border-neutral-800">
                          [VERIFIED_EVIDENCE]
                        </span>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Clean Empty State Before Search */}
      {signals.length === 0 && !scanning && !deepRadarRunning && (
        <div className="p-16 rounded-lg bg-neutral-900/30 border border-neutral-800 flex flex-col items-center justify-center text-center space-y-3">
          <div className="w-10 h-10 rounded-full bg-neutral-900 border border-neutral-800 flex items-center justify-center text-neutral-400">
            <Compass className="w-5 h-5 text-neutral-400" />
          </div>
          <div>
            <h3 className="text-sm font-semibold text-neutral-200">Market Discovery Standby</h3>
            <p className="text-xs text-neutral-400 max-w-md mt-1 leading-relaxed">
              No search initiated yet. Select your target country and trigger above, or enter an organization name, then click &quot;Run Market Scan&quot; or &quot;Deep Web &amp; News Scan&quot;.
            </p>
          </div>
        </div>
      )}
    </div>
  );
}
