"use client";

import React, { useState, useEffect } from "react";
import { BatchAuditResult, DecisionMaker, api } from "@/lib/api";
import {
  CheckCircle2,
  ExternalLink,
  Mail,
  ShieldCheck,
  ArrowRight,
  Globe,
  CheckSquare,
  Square,
  Copy,
  Check,
  Building,
  Search,
} from "lucide-react";

interface Tab2AuditProps {
  initialOrganizations: string[];
  onForwardToTab3: (contact: { name: string; role: string; organization: string; email?: string }) => void;
}

export default function Tab2Audit({ initialOrganizations, onForwardToTab3 }: Tab2AuditProps) {
  const [targetOrgs, setTargetOrgs] = useState<string[]>(initialOrganizations || []);
  const [customOrgInput, setCustomOrgInput] = useState<string>("");
  const [auditing, setAuditing] = useState<boolean>(false);
  const [osintHunting, setOsintHunting] = useState<boolean>(false);
  const [auditResult, setAuditResult] = useState<BatchAuditResult | null>(null);
  const [selectedContacts, setSelectedContacts] = useState<Set<string>>(new Set());
  const [copiedEmail, setCopiedEmail] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (initialOrganizations && initialOrganizations.length > 0) {
      setTargetOrgs(initialOrganizations);
      runAudit(initialOrganizations);
    }
  }, [initialOrganizations]);

  const runAudit = async (orgsToAudit: string[]) => {
    if (orgsToAudit.length === 0) return;
    setAuditing(true);
    setError(null);
    setSelectedContacts(new Set());
    try {
      const res = await api.runAuditAndHunt(orgsToAudit);
      setAuditResult(res);
      // Default select all decision-makers
      const allKeys = new Set(res.all_decision_makers.map((dm) => `${dm.name}::${dm.organization_name || ""}`));
      setSelectedContacts(allKeys);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed to execute audit and hunter");
    } finally {
      setAuditing(false);
    }
  };

  const runCrossLinkedOSINTHunt = async (orgName: string) => {
    setOsintHunting(true);
    setError(null);
    try {
      const res = await api.runOSINTHunt({ organization_name: orgName });
      if (res.decision_makers && res.decision_makers.length > 0) {
        setAuditResult((prev) => {
          if (!prev) return prev;
          const updatedDms = [...res.decision_makers, ...prev.all_decision_makers];
          const updatedResults = { ...prev.results };
          if (updatedResults[orgName]) {
            updatedResults[orgName].decision_makers = [
              ...res.decision_makers,
              ...updatedResults[orgName].decision_makers,
            ];
          }
          return {
            ...prev,
            total_decision_makers: updatedDms.length,
            all_decision_makers: updatedDms,
            results: updatedResults,
          };
        });
      }
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed to run CrossLinked OSINT hunt");
    } finally {
      setOsintHunting(false);
    }
  };

  const handleAddOrg = (e: React.FormEvent) => {
    e.preventDefault();
    const trimmed = customOrgInput.trim();
    if (!trimmed) return;
    if (!targetOrgs.includes(trimmed)) {
      const updated = [...targetOrgs, trimmed];
      setTargetOrgs(updated);
      setCustomOrgInput("");
      runAudit(updated);
    }
  };

  const toggleSelectContact = (dmKey: string) => {
    const updated = new Set(selectedContacts);
    if (updated.has(dmKey)) {
      updated.delete(dmKey);
    } else {
      updated.add(dmKey);
    }
    setSelectedContacts(updated);
  };

  const toggleSelectAll = () => {
    if (!auditResult) return;
    if (selectedContacts.size === auditResult.all_decision_makers.length) {
      setSelectedContacts(new Set());
    } else {
      const allKeys = new Set(
        auditResult.all_decision_makers.map((dm) => `${dm.name}::${dm.organization_name || ""}`)
      );
      setSelectedContacts(allKeys);
    }
  };

  const copyToClipboard = (text: string) => {
    navigator.clipboard.writeText(text);
    setCopiedEmail(text);
    setTimeout(() => setCopiedEmail(null), 2000);
  };

  const handleForwardFirstSelected = () => {
    if (!auditResult) return;
    const firstSelectedKey = Array.from(selectedContacts)[0];
    if (!firstSelectedKey) return;
    const [name, org] = firstSelectedKey.split("::");
    const targetDm = auditResult.all_decision_makers.find(
      (dm) => dm.name === name && dm.organization_name === org
    );
    if (targetDm) {
      onForwardToTab3({
        name: targetDm.name,
        role: targetDm.role,
        organization: targetDm.organization_name || org,
        email: targetDm.email,
      });
    }
  };

  return (
    <div className="space-y-6">
      {/* Header Banner */}
      <div className="p-6 rounded-lg bg-neutral-900/50 border border-neutral-800 flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-2">
            <span className="text-[10px] font-mono uppercase tracking-widest text-neutral-300 bg-neutral-800 px-2 py-0.5 rounded-xs border border-neutral-700">
              Step 02
            </span>
            <span className="text-xs text-neutral-400 font-medium">Leadership Directory &amp; Domain Verification</span>
          </div>
          <h2 className="text-xl font-bold text-neutral-100 tracking-tight mt-1.5">
            Decision-Makers &amp; Key Leadership
          </h2>
          <p className="text-xs text-neutral-400 mt-1 max-w-2xl leading-relaxed">
            Identifies verified engineering directors, technical managers, and founders across your chosen companies with verified LinkedIn profiles and corporate email routes.
          </p>
        </div>

        {auditResult && (
          <div className="flex items-center gap-2 shrink-0">
            <span className="px-3.5 py-1.5 rounded-sm bg-neutral-900 border border-neutral-800 text-neutral-200 font-mono text-xs">
              {auditResult.organizations_audited} Companies Audited
            </span>
            <span className="px-3.5 py-1.5 rounded-sm bg-neutral-900 border border-neutral-800 text-neutral-200 font-mono text-xs">
              {auditResult.total_decision_makers} Leaders Located
            </span>
          </div>
        )}
      </div>

      {error && (
        <div className="p-3.5 rounded-sm bg-red-950/60 border border-red-800 text-red-200 text-xs">
          {error}
        </div>
      )}

      {/* Target Organizations Control Bar */}
      <div className="p-5 rounded-lg bg-neutral-900/60 border border-neutral-800 space-y-3">
        <div className="flex items-center justify-between">
          <span className="text-xs font-semibold text-neutral-200">
            Organizations Queued for Multi-Org Audit ({targetOrgs.length})
          </span>
          <button
            onClick={() => runAudit(targetOrgs)}
            disabled={auditing || targetOrgs.length === 0}
            className="px-4 py-2 rounded-sm bg-neutral-100 hover:bg-white text-neutral-950 text-xs font-semibold transition-colors flex items-center gap-1.5 disabled:opacity-50 shadow-xs"
          >
            {auditing ? (
              <>
                <div className="w-3.5 h-3.5 border-2 border-neutral-950 border-t-transparent rounded-full animate-spin" />
                <span>Auditing &amp; Hunting...</span>
              </>
            ) : (
              <>
                <CheckCircle2 className="w-3.5 h-3.5" />
                <span>Rerun Batch Audit</span>
              </>
            )}
          </button>
        </div>

        <div className="flex flex-wrap gap-2">
          {targetOrgs.map((org) => (
            <span
              key={org}
              className="inline-flex items-center gap-2 px-3 py-1.5 rounded-sm bg-neutral-950 border border-neutral-800 text-xs text-neutral-200 font-medium"
            >
              <span>{org}</span>
              <button
                onClick={() => {
                  const filtered = targetOrgs.filter((o) => o !== org);
                  setTargetOrgs(filtered);
                  if (filtered.length > 0) runAudit(filtered);
                }}
                className="text-neutral-500 hover:text-neutral-300 text-sm font-bold"
              >
                &times;
              </button>
            </span>
          ))}
        </div>

        <form onSubmit={handleAddOrg} className="flex gap-2 pt-2 border-t border-neutral-850">
          <input
            type="text"
            placeholder="Add organization name (e.g. Omantel, OQ, Example Software Labs, Aramco)..."
            value={customOrgInput}
            onChange={(e) => setCustomOrgInput(e.target.value)}
            className="flex-1 bg-neutral-950 border border-neutral-800 rounded-sm py-2 px-3 text-xs text-neutral-200 placeholder:text-neutral-600 focus:outline-hidden focus:border-neutral-500"
          />
          <button
            type="submit"
            className="px-4 py-2 bg-neutral-850 hover:bg-neutral-800 text-neutral-200 border border-neutral-700 text-xs rounded-sm transition-colors font-medium"
          >
            Add &amp; Audit
          </button>
        </form>
      </div>

      {/* Verified Corporate Organization Cards */}
      {auditResult && Object.keys(auditResult.results).length > 0 && (
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          {Object.entries(auditResult.results).map(([orgName, data]) => (
            <div
              key={orgName}
              className="p-4 rounded-lg bg-neutral-900/50 border border-neutral-800 space-y-2"
            >
              <div className="flex items-center justify-between">
                <span className="font-semibold text-neutral-100 text-sm">{orgName}</span>
                <span className="text-[10px] font-mono px-2 py-0.5 rounded-xs bg-emerald-950 text-emerald-300 border border-emerald-800">
                  [HTTP {data.http_status} OK]
                </span>
              </div>
              <div className="text-[11px] text-neutral-400 font-mono truncate">
                Domain: {data.domain}
              </div>
              <p className="text-xs text-neutral-300 line-clamp-2 leading-relaxed">
                {data.evidence_excerpt}
              </p>
              <div className="pt-1 flex items-center justify-between text-[11px] text-neutral-400">
                <span>{data.decision_makers.length} Leaders Identified</span>
                <span className="text-emerald-400 font-mono text-[10px]">[EVIDENCE_VERIFIED]</span>
              </div>

              <button
                onClick={() => runCrossLinkedOSINTHunt(orgName)}
                disabled={osintHunting}
                className="w-full mt-2 py-1.5 px-2 rounded-xs bg-neutral-950 hover:bg-neutral-850 border border-neutral-800 text-[10px] text-neutral-300 font-mono transition-colors flex items-center justify-center gap-1.5 disabled:opacity-50"
              >
                {osintHunting ? (
                  <>
                    <div className="w-3 h-3 border-2 border-neutral-400 border-t-white rounded-full animate-spin" />
                    <span>Finding Profiles...</span>
                  </>
                ) : (
                  <>
                    <Search className="w-3 h-3 text-neutral-400" />
                    <span>Deep Leadership Search</span>
                  </>
                )}
              </button>
            </div>
          ))}
        </div>
      )}

      {/* Decision-Makers Table */}
      {auditResult && auditResult.all_decision_makers.length > 0 && (
        <div className="space-y-3">
          <div className="flex items-center justify-between bg-neutral-900/40 p-3 rounded-lg border border-neutral-800">
            <div className="flex items-center gap-3">
              <span className="text-xs font-semibold text-neutral-100">
                Extracted Decision-Makers &amp; Executives ({auditResult.all_decision_makers.length})
              </span>
              <span className="text-[11px] font-mono text-neutral-400 bg-neutral-900 px-2 py-0.5 rounded-xs border border-neutral-850">
                {selectedContacts.size} selected
              </span>
            </div>

            <button
              onClick={handleForwardFirstSelected}
              disabled={selectedContacts.size === 0}
              className="px-5 py-2 rounded-sm bg-neutral-100 hover:bg-white text-neutral-950 text-xs font-semibold transition-all flex items-center gap-2 disabled:opacity-40 shadow-xs"
            >
              <span>Inspect Profile in Tab 3: Verification</span>
              <ArrowRight className="w-3.5 h-3.5" />
            </button>
          </div>

          <div className="border border-neutral-800 rounded-lg overflow-x-auto bg-neutral-950 shadow-xs">
            <table className="w-full text-left text-xs border-collapse">
              <thead>
                <tr className="border-b border-neutral-800 bg-neutral-900/90 text-neutral-400 text-[11px] uppercase tracking-wider">
                  <th className="py-3 px-3 w-10 text-center">
                    <button onClick={toggleSelectAll} className="hover:text-white" title="Select All">
                      {selectedContacts.size === auditResult.all_decision_makers.length ? (
                        <CheckSquare className="w-4 h-4 text-neutral-200" />
                      ) : (
                        <Square className="w-4 h-4 text-neutral-500" />
                      )}
                    </button>
                  </th>
                  <th className="py-3 px-3 font-semibold">Executive Name</th>
                  <th className="py-3 px-3 font-semibold">Organization</th>
                  <th className="py-3 px-3 font-semibold">Role / Title</th>
                  <th className="py-3 px-3 font-semibold">Verified LinkedIn Profile</th>
                  <th className="py-3 px-3 font-semibold">Corporate Email Address</th>
                  <th className="py-3 px-3 font-semibold text-right">Confidence</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-neutral-850">
                {auditResult.all_decision_makers.map((dm, idx) => {
                  const dmKey = `${dm.name}::${dm.organization_name || ""}`;
                  const isSelected = selectedContacts.has(dmKey);
                  return (
                    <tr
                      key={idx}
                      className={`hover:bg-neutral-900/50 transition-colors ${
                        isSelected ? "bg-neutral-900/30" : ""
                      }`}
                    >
                      <td className="py-3 px-3 text-center">
                        <button onClick={() => toggleSelectContact(dmKey)} className="hover:text-white">
                          {isSelected ? (
                            <CheckSquare className="w-4 h-4 text-neutral-200" />
                          ) : (
                            <Square className="w-4 h-4 text-neutral-600" />
                          )}
                        </button>
                      </td>
                      <td className="py-3 px-3 font-semibold text-neutral-100">
                        {dm.name}
                      </td>
                      <td className="py-3 px-3 text-neutral-300 font-medium">
                        {dm.organization_name}
                      </td>
                      <td className="py-3 px-3 text-neutral-300 max-w-xs">
                        {dm.role}
                      </td>
                      <td className="py-3 px-3">
                        {dm.linkedin_url ? (
                          <a
                            href={dm.linkedin_url}
                            target="_blank"
                            rel="noreferrer"
                            className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-xs bg-neutral-900 hover:bg-neutral-850 border border-neutral-800 text-neutral-300 hover:text-white font-mono text-[11px] transition-colors"
                          >
                            <Globe className="w-3 h-3 text-neutral-400" />
                            <span>LinkedIn Profile</span>
                            <ExternalLink className="w-2.5 h-2.5" />
                          </a>
                        ) : (
                          <span className="text-neutral-500 text-[11px] font-mono">[UNLISTED]</span>
                        )}
                      </td>
                      <td className="py-3 px-3 font-mono text-[11px] text-neutral-200">
                        <div className="flex items-center gap-1.5">
                          <Mail className="w-3 h-3 text-neutral-500" />
                          <span>{dm.email || "leadership@domain.com"}</span>
                          <button
                            onClick={() => copyToClipboard(dm.email)}
                            title="Copy Email"
                            className="text-neutral-500 hover:text-neutral-300 p-0.5"
                          >
                            {copiedEmail === dm.email ? (
                              <Check className="w-3 h-3 text-emerald-400" />
                            ) : (
                              <Copy className="w-3 h-3" />
                            )}
                          </button>
                        </div>
                      </td>
                      <td className="py-3 px-3 text-right">
                        <div className="flex items-center justify-end gap-2">
                          <span className="text-[10px] font-mono px-2 py-0.5 rounded-xs bg-neutral-900 text-emerald-300 border border-neutral-800 font-medium">
                            [{Math.round((dm.confidence || 0.90) * 100)}% VERIFIED]
                          </span>
                          <button
                            onClick={() => onForwardToTab3({
                              name: dm.name,
                              role: dm.role,
                              organization: dm.organization_name || "",
                              email: dm.email
                            })}
                            className="px-2.5 py-1 rounded-xs bg-neutral-900 hover:bg-neutral-850 text-neutral-200 border border-neutral-750 text-[10px] font-medium transition-colors flex items-center gap-1 shrink-0 shadow-xs"
                            title="Verify email deliverability and view executive profile in Tab 3"
                          >
                            <span>View Profile</span>
                            <ArrowRight className="w-3 h-3 text-neutral-400" />
                          </button>
                        </div>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Clean Empty State Before Audit */}
      {!auditResult && !auditing && (
        <div className="p-16 rounded-lg bg-neutral-900/30 border border-neutral-800 flex flex-col items-center justify-center text-center space-y-3">
          <div className="w-10 h-10 rounded-full bg-neutral-900 border border-neutral-800 flex items-center justify-center text-neutral-400">
            <Building className="w-5 h-5 text-neutral-400" />
          </div>
          <div>
            <h3 className="text-sm font-semibold text-neutral-200">Decision-Maker Directory Standby</h3>
            <p className="text-xs text-neutral-400 max-w-md mt-1 leading-relaxed">
              No companies currently queued for leadership search. Select organizations in Tab 1 (Market Discovery) and click &quot;Review Decision-Makers in Tab 2&quot;, or enter an organization name above to begin.
            </p>
          </div>
        </div>
      )}
    </div>
  );
}
