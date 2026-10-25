"use client";

import React, { useState, useEffect } from "react";
import { ApprovedDraft, OutreachEvent, api } from "@/lib/api";
import {
  Send,
  FileText,
  Mail,
  ShieldAlert,
  CheckCircle,
  AlertCircle,
  Upload,
  RefreshCw,
  Clock,
  Check,
  Building,
  User,
  Inbox,
  ArrowRight,
  Radio,
} from "lucide-react";

interface Tab5DispatchProps {
  initialRecipientEmail?: string | null;
  onRefreshStats: () => void;
}

export default function Tab5Dispatch({ initialRecipientEmail, onRefreshStats }: Tab5DispatchProps) {
  const [drafts, setDrafts] = useState<ApprovedDraft[]>([]);
  const [selectedEmail, setSelectedEmail] = useState<string>("");
  const [selectedDraft, setSelectedDraft] = useState<ApprovedDraft | null>(null);

  const [customFile, setCustomFile] = useState<File | null>(null);
  const [dispatchingDraft, setDispatchingDraft] = useState<boolean>(false);
  const [dispatchingDirect, setDispatchingDirect] = useState<boolean>(false);
  const [ledger, setLedger] = useState<OutreachEvent[]>([]);

  const [feedback, setFeedback] = useState<{ type: "success" | "error"; message: string } | null>(null);
  const [loadingDrafts, setLoadingDrafts] = useState<boolean>(false);

  useEffect(() => {
    loadApprovedDrafts();
    loadLedger();
  }, []);

  useEffect(() => {
    if (initialRecipientEmail) {
      loadApprovedDrafts();
      loadLedger();
    }
  }, [initialRecipientEmail]);

  const loadApprovedDrafts = async () => {
    setLoadingDrafts(true);
    try {
      const data = await api.listApprovedDrafts();
      setDrafts(data);
      if (initialRecipientEmail) {
        const found = data.find((d) => d.recipient_email === initialRecipientEmail);
        if (found) {
          setSelectedEmail(found.recipient_email);
          setSelectedDraft(found);
          return;
        }
      }
      // Keep empty by default unless forwarded or explicitly selected
      setSelectedEmail("");
      setSelectedDraft(null);
    } catch {
      // Ignored
    } finally {
      setLoadingDrafts(false);
    }
  };

  const loadLedger = async () => {
    try {
      const data = await api.getOutreachLedger(25);
      setLedger(data);
    } catch {
      // Ignored
    }
  };

  const handleSelectDraft = (email: string) => {
    setSelectedEmail(email);
    const d = drafts.find((item) => item.recipient_email === email) || null;
    setSelectedDraft(d);
    setFeedback(null);
  };

  const handleStageInGmail = async () => {
    if (!selectedDraft) return;
    setDispatchingDraft(true);
    setFeedback(null);
    try {
      const res = await api.stageDraftInGmail(selectedDraft.recipient_email, customFile || undefined);
      setFeedback({ type: "success", message: res.message });
      onRefreshStats();
      await loadLedger();
    } catch (err: unknown) {
      setFeedback({
        type: "error",
        message: err instanceof Error ? err.message : "Failed to stage draft in Gmail",
      });
    } finally {
      setDispatchingDraft(false);
    }
  };

  const handleSendDirect = async () => {
    if (!selectedDraft) return;
    setDispatchingDirect(true);
    setFeedback(null);
    try {
      const res = await api.sendDirectEmail(selectedDraft.recipient_email, customFile || undefined);
      setFeedback({ type: res.success ? "success" : "error", message: res.message });
      onRefreshStats();
      await loadLedger();
    } catch (err: unknown) {
      setFeedback({
        type: "error",
        message: err instanceof Error ? err.message : "Failed to send direct email",
      });
    } finally {
      setDispatchingDirect(false);
    }
  };

  return (
    <div className="space-y-6">
      {/* Header Banner */}
      <div className="p-6 rounded-lg bg-neutral-900/50 border border-neutral-800 flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-2">
            <span className="text-[10px] font-mono uppercase tracking-widest text-neutral-300 bg-neutral-800 px-2 py-0.5 rounded-xs border border-neutral-700">
              Step 05
            </span>
            <span className="text-xs text-neutral-400 font-medium">Review, Attachment &amp; Dispatch Control</span>
          </div>
          <h2 className="text-xl font-bold text-neutral-100 tracking-tight mt-1.5">
            Outreach Dispatch &amp; Tracking Ledger
          </h2>
          <p className="text-xs text-neutral-400 mt-1 max-w-2xl leading-relaxed">
            Review your approved message, attach your candidate resume PDF, and choose between staging as a draft in your Gmail account or sending directly.
          </p>
        </div>

        <button
          onClick={() => {
            loadApprovedDrafts();
            loadLedger();
          }}
          className="self-start md:self-auto px-4 py-2.5 rounded-sm bg-neutral-900 hover:bg-neutral-850 text-neutral-200 border border-neutral-750 text-xs font-medium transition-colors flex items-center gap-1.5 shrink-0 shadow-xs"
        >
          <RefreshCw className="w-3.5 h-3.5 text-neutral-300" />
          <span>Refresh Queue &amp; Ledger</span>
        </button>
      </div>

      {feedback && (
        <div
          className={`p-4 rounded-sm border text-xs flex items-center gap-2.5 ${
            feedback.type === "success"
              ? "bg-emerald-950/60 border-emerald-800 text-emerald-200"
              : "bg-red-950/60 border-red-800 text-red-200"
          }`}
        >
          {feedback.type === "success" ? (
            <Check className="w-4 h-4 shrink-0 text-emerald-400" />
          ) : (
            <AlertCircle className="w-4 h-4 shrink-0 text-red-400" />
          )}
          <span className="font-medium">{feedback.message}</span>
        </div>
      )}

      {/* Main Grid: Draft Details & Dispatch Controls */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Left Column: Draft Picker & PDF Attachment Config */}
        <div className="space-y-4">
          <div className="p-5 rounded-lg bg-neutral-900/60 border border-neutral-800 space-y-3">
            <span className="text-xs font-semibold text-neutral-200 block">
              Approved Staged Drafts ({drafts.length})
            </span>

            {loadingDrafts ? (
              <div className="py-6 text-center text-xs text-neutral-400">
                Loading approved drafts...
              </div>
            ) : drafts.length > 0 ? (
              <select
                value={selectedEmail}
                onChange={(e) => handleSelectDraft(e.target.value)}
                className="w-full bg-neutral-950 border border-neutral-800 rounded-sm py-2 px-3 text-xs text-neutral-200 focus:outline-hidden focus:border-neutral-500"
              >
                <option value="">-- Select an approved draft to stage --</option>
                {drafts.map((d) => (
                  <option key={d.recipient_email} value={d.recipient_email}>
                    {d.recipient_name} ({d.organization_name})
                  </option>
                ))}
              </select>
            ) : (
              <div className="p-4 rounded-sm bg-neutral-950 border border-neutral-850 text-xs text-neutral-400 text-center">
                No approved drafts in queue. Approve a draft in Tab 4 to stage it here.
              </div>
            )}
          </div>

          {/* Resume Attachment Manager */}
          <div className="p-5 rounded-lg bg-neutral-900/60 border border-neutral-800 space-y-3">
            <div className="flex items-center justify-between">
              <span className="text-xs font-semibold text-neutral-200 flex items-center gap-1.5">
                <FileText className="w-3.5 h-3.5 text-neutral-400" />
                <span>Resume PDF Manager</span>
              </span>
              <span className="text-[10px] font-mono px-2 py-0.5 rounded-xs bg-neutral-950 text-emerald-400 border border-neutral-800">
                [PDF_ATTACHED]
              </span>
            </div>

            <div className="p-3 rounded-sm bg-neutral-950 border border-neutral-850 space-y-1">
              <div className="text-[10px] text-neutral-400 font-mono">Active Resume Document:</div>
              <div className="text-xs font-mono font-semibold text-neutral-100 break-all">
                {customFile ? customFile.name : "Mohammed_Minhaj_Mahmood_CV.pdf"}
              </div>
              <div className="text-[10px] text-neutral-500">
                {customFile ? "Custom uploaded CV document" : "Canonical repository candidate resume"}
              </div>
            </div>

            <div>
              <label className="block text-[11px] text-neutral-400 mb-1 font-medium">
                Upload Alternate CV PDF (Optional)
              </label>
              <label className="flex items-center justify-center p-3 rounded-sm border border-dashed border-neutral-750 bg-neutral-950/60 hover:bg-neutral-900 cursor-pointer text-xs text-neutral-300 hover:text-white transition-colors">
                <Upload className="w-3.5 h-3.5 mr-2 text-neutral-400" />
                <span>{customFile ? "Change file..." : "Browse PDF from system"}</span>
                <input
                  type="file"
                  accept="application/pdf"
                  onChange={(e) => {
                    if (e.target.files && e.target.files[0]) {
                      setCustomFile(e.target.files[0]);
                    }
                  }}
                  className="hidden"
                />
              </label>
            </div>
          </div>

          {/* Pre-Flight Suppression Verification Notice */}
          <div className="p-5 rounded-lg bg-neutral-900/60 border border-neutral-800 space-y-2">
            <div className="flex items-center gap-2 text-xs font-semibold text-neutral-200">
              <ShieldAlert className="w-3.5 h-3.5 text-neutral-400" />
              <span>Pre-Flight Safety Shield</span>
            </div>
            <p className="text-[11px] text-neutral-400 leading-relaxed">
              Before transmission, every address is screened against the 1,655 suppressed domains and bounce records. Hard bounces or opt-outs are blocked immediately.
            </p>
          </div>

          {/* Automated Reply & Bounce Shield */}
          <div className="p-5 rounded-lg bg-neutral-900/60 border border-neutral-800 space-y-2 text-xs">
            <div className="flex items-center justify-between pb-2 border-b border-neutral-850">
              <div className="flex items-center gap-2 font-semibold text-neutral-200">
                <Radio className="w-3.5 h-3.5 text-emerald-400 animate-pulse" />
                <span>Automatic Reply &amp; Bounce Shield</span>
              </div>
              <span className="text-[10px] font-mono text-emerald-400 bg-neutral-950 px-2 py-0.5 rounded-xs border border-neutral-800">
                [ACTIVE_PROTECTION]
              </span>
            </div>
            <div className="space-y-1.5 text-[11px] text-neutral-400 leading-relaxed">
              <div className="flex items-start gap-1.5">
                <span className="text-emerald-400 font-mono text-xs">&bull;</span>
                <span><strong className="text-neutral-300">Reply Detection:</strong> Automatically pauses future outreach when an executive responds.</span>
              </div>
              <div className="flex items-start gap-1.5">
                <span className="text-emerald-400 font-mono text-xs">&bull;</span>
                <span><strong className="text-neutral-300">Bounce Shield:</strong> Permanently suppresses undeliverable addresses to protect sender score.</span>
              </div>
            </div>
          </div>
        </div>

        {/* Right Column: Draft Preview & Dual Execution Buttons */}
        <div className="lg:col-span-2 space-y-4">
          {selectedDraft ? (
            <div className="p-6 rounded-lg bg-neutral-900/60 border border-neutral-800 space-y-4">
              <div className="flex items-center justify-between pb-3 border-b border-neutral-800">
                <div>
                  <h3 className="text-base font-bold text-neutral-100">
                    {selectedDraft.recipient_name}
                  </h3>
                  <div className="text-xs text-neutral-400 mt-0.5">
                    {selectedDraft.recipient_role} &bull;{" "}
                    <strong className="text-neutral-200">{selectedDraft.organization_name}</strong>
                  </div>
                </div>
                <span className="text-[10px] font-mono px-2 py-0.5 rounded-xs bg-neutral-800 text-neutral-300 border border-neutral-700">
                  [{selectedDraft.status}]
                </span>
              </div>

              <div>
                <div className="text-[11px] text-neutral-400 font-medium mb-1">Subject:</div>
                <div className="p-2.5 rounded-sm bg-neutral-950 border border-neutral-850 font-mono text-xs text-neutral-100">
                  {selectedDraft.subject_line}
                </div>
              </div>

              <div>
                <div className="text-[11px] text-neutral-400 font-medium mb-1">Body Text:</div>
                <div className="p-4 rounded-sm bg-neutral-950 border border-neutral-850 text-xs text-neutral-200 whitespace-pre-wrap leading-relaxed">
                  {selectedDraft.body_text}
                </div>
              </div>

              {/* Dual Execution Cockpit Cards */}
              <div className="pt-3 border-t border-neutral-800 grid grid-cols-1 sm:grid-cols-2 gap-4">
                {/* Button 1: Make Draft in Gmail */}
                <div className="p-4 rounded-sm bg-neutral-950 border border-neutral-800 space-y-2">
                  <div className="flex items-center gap-2 text-xs font-semibold text-neutral-200">
                    <Inbox className="w-4 h-4 text-neutral-300" />
                    <span>Option A: Stage in Gmail Drafts</span>
                  </div>
                  <p className="text-[11px] text-neutral-400 leading-relaxed">
                    Uploads directly into your [Gmail]/Drafts folder so you can review on your phone or desktop before sending.
                  </p>
                  <button
                    onClick={handleStageInGmail}
                    disabled={dispatchingDraft || dispatchingDirect}
                    className="w-full py-2.5 px-3 rounded-sm bg-neutral-850 hover:bg-neutral-800 text-neutral-100 border border-neutral-700 text-xs font-semibold tracking-wide transition-colors flex items-center justify-center gap-2 disabled:opacity-50"
                  >
                    {dispatchingDraft ? (
                      <>
                        <div className="w-3.5 h-3.5 border-2 border-neutral-400 border-t-white rounded-full animate-spin" />
                        <span>Staging in Gmail...</span>
                      </>
                    ) : (
                      <>
                        <Mail className="w-3.5 h-3.5" />
                        <span>Stage Draft in Gmail</span>
                      </>
                    )}
                  </button>
                </div>

                {/* Button 2: Send Directly via SMTP */}
                <div className="p-4 rounded-sm bg-neutral-950 border border-neutral-800 space-y-2">
                  <div className="flex items-center gap-2 text-xs font-semibold text-neutral-200">
                    <Send className="w-4 h-4 text-neutral-300" />
                    <span>Option B: Send Directly Now</span>
                  </div>
                  <p className="text-[11px] text-neutral-400 leading-relaxed">
                    Transmits immediately through Gmail SMTP SSL (port 465) with your attached candidate resume PDF.
                  </p>
                  <button
                    onClick={handleSendDirect}
                    disabled={dispatchingDraft || dispatchingDirect}
                    className="w-full py-2.5 px-3 rounded-sm bg-neutral-100 hover:bg-white text-neutral-950 text-xs font-semibold tracking-wide transition-colors flex items-center justify-center gap-2 disabled:opacity-50 shadow-xs"
                  >
                    {dispatchingDirect ? (
                      <>
                        <div className="w-3.5 h-3.5 border-2 border-neutral-900 border-t-transparent rounded-full animate-spin" />
                        <span>Transmitting SMTP...</span>
                      </>
                    ) : (
                      <>
                        <Send className="w-3.5 h-3.5" />
                        <span>Send Directly via SMTP</span>
                      </>
                    )}
                  </button>
                </div>
              </div>
            </div>
          ) : (
            <div className="p-16 rounded-lg bg-neutral-900/30 border border-neutral-800 flex flex-col items-center justify-center text-center space-y-3">
              <div className="w-10 h-10 rounded-full bg-neutral-900 border border-neutral-800 flex items-center justify-center text-neutral-400">
                <Send className="w-5 h-5 text-neutral-400" />
              </div>
              <div>
                <h3 className="text-sm font-semibold text-neutral-200">Dispatch Queue Standby</h3>
                <p className="text-xs text-neutral-400 max-w-md mt-1 leading-relaxed">
                  No draft currently selected for dispatch. Complete approval in Tab 4 (AI Co-Pilot) to stage an email for dispatch, or select an approved draft from the queue on the left.
                </p>
              </div>
            </div>
          )}

          {/* Live Outreach Ledger Table */}
          <div className="p-5 rounded-lg bg-neutral-900/60 border border-neutral-800 space-y-3">
            <div className="flex items-center justify-between">
              <span className="text-xs font-semibold text-neutral-200">
                Outreach Ledger: Audit &amp; Event Log
              </span>
              <span className="text-[11px] font-mono text-neutral-400 bg-neutral-900 px-2 py-0.5 rounded-xs border border-neutral-850">
                {ledger.length} events recorded
              </span>
            </div>

            <div className="border border-neutral-800 rounded-sm overflow-x-auto bg-neutral-950">
              <table className="w-full text-left text-xs border-collapse">
                <thead>
                  <tr className="border-b border-neutral-800 bg-neutral-900/80 text-neutral-400 text-[11px] uppercase tracking-wider">
                    <th className="py-2.5 px-3 font-semibold">Timestamp</th>
                    <th className="py-2.5 px-3 font-semibold">Recipient</th>
                    <th className="py-2.5 px-3 font-semibold">Action</th>
                    <th className="py-2.5 px-3 font-semibold">Status</th>
                    <th className="py-2.5 px-3 font-semibold text-right">Details</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-neutral-850">
                  {ledger.map((evt) => (
                    <tr key={evt.id} className="hover:bg-neutral-900/40">
                      <td className="py-2.5 px-3 font-mono text-[11px] text-neutral-400 whitespace-nowrap">
                        {evt.timestamp ? evt.timestamp.split("T")[0] : "—"}
                      </td>
                      <td className="py-2.5 px-3 font-medium text-neutral-200">
                        {evt.recipient_email}
                      </td>
                      <td className="py-2.5 px-3 font-mono text-[11px] text-neutral-300">
                        {evt.action_type}
                      </td>
                      <td className="py-2.5 px-3">
                        <span
                          className={`text-[10px] font-mono px-2 py-0.5 rounded-xs border ${
                            evt.status === "DELIVERED" || evt.status === "SUCCESS"
                              ? "bg-emerald-950 text-emerald-300 border-emerald-800"
                              : evt.status === "STAGED_LOCAL" || evt.status === "STAGED"
                              ? "bg-blue-950 text-blue-300 border-blue-800"
                              : "bg-neutral-900 text-neutral-300 border-neutral-800"
                          }`}
                        >
                          [{evt.status}]
                        </span>
                      </td>
                      <td className="py-2.5 px-3 text-right text-[11px] text-neutral-400 truncate max-w-[200px]">
                        {evt.status_message}
                      </td>
                    </tr>
                  ))}
                  {ledger.length === 0 && (
                    <tr>
                      <td colSpan={5} className="py-6 text-center text-neutral-400">
                        No ledger actions recorded yet.
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
