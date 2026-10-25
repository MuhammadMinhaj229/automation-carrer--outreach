"use client";

import React, { useState, useEffect } from "react";
import { DossierResponse, ContactRecord, api } from "@/lib/api";
import {
  PenTool,
  Send,
  Sparkles,
  CheckCircle,
  AlertCircle,
  ArrowRight,
  ShieldCheck,
  RefreshCw,
  MessageSquare,
  Zap,
  Users,
} from "lucide-react";

interface Tab4AICopilotProps {
  initialTarget?: {
    name: string;
    role: string;
    organization: string;
    email: string;
    history: DossierResponse["history"];
  } | null;
  onForwardToTab5: (recipientEmail: string) => void;
}

export default function Tab4AICopilot({ initialTarget, onForwardToTab5 }: Tab4AICopilotProps) {
  const [target, setTarget] = useState(initialTarget || null);
  const [availableContacts, setAvailableContacts] = useState<ContactRecord[]>([]);
  const [subjectLine, setSubjectLine] = useState("");
  const [bodyText, setBodyText] = useState("");
  const [wordCount, setWordCount] = useState(0);
  const [matchedExperience, setMatchedExperience] = useState<{
    organization: string;
    role: string;
    evidence_cite: string;
    headline: string;
  } | null>(null);

  // Chat conversation
  const [selectedStage, setSelectedStage] = useState<string>("Stage 1: First Touch Introduction");
  const [messages, setMessages] = useState<Array<{ sender: "user" | "copilot"; text: string }>>([
    {
      sender: "copilot",
      text: "Executive Outreach Co-Pilot ready. Select or forward an executive to start personalized drafting.",
    },
  ]);
  const [userInput, setUserInput] = useState("");
  const [refining, setRefining] = useState(false);
  const [generating, setGenerating] = useState(false);
  const [approving, setApproving] = useState(false);
  const [approvalHash, setApprovalHash] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api.listContacts().then(setAvailableContacts).catch(() => {});
  }, []);

  useEffect(() => {
    if (initialTarget) {
      setTarget(initialTarget);
      setMessages([
        {
          sender: "copilot",
          text: `Executive target loaded: ${initialTarget.name} (${initialTarget.role} at ${initialTarget.organization}). Verified background and candidate track record loaded. Select an outreach focus below or type custom guidance.`,
        },
      ]);
      generateInitial(initialTarget);
    }
  }, [initialTarget]);

  useEffect(() => {
    const words = bodyText.trim().split(/\s+/).filter(Boolean).length;
    setWordCount(words);
  }, [bodyText]);

  const generateInitial = async (tgt: typeof initialTarget) => {
    if (!tgt) return;
    setGenerating(true);
    setError(null);
    setApprovalHash(null);
    try {
      const res = await api.generateInitialDraft({
        target_name: tgt.name,
        target_role: tgt.role,
        target_org: tgt.organization,
        target_email: tgt.email || "contact@domain.com",
        target_history: (tgt.history || {}) as Record<string, unknown>,
      });
      setSubjectLine(res.subject_line);
      setBodyText(res.body_text);
      setMatchedExperience(res.auto_matched_experience);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed to generate initial draft");
    } finally {
      setGenerating(false);
    }
  };

  const handleSwitchTarget = async (compositeKey: string) => {
    const found = availableContacts.find((c) => `${c.organization_name}:::${c.contact_name}` === compositeKey);
    if (!found) return;
    setGenerating(true);
    try {
      const dossier = await api.getExecutiveDossier({
        name: found.contact_name,
        role: found.role_designation,
        organization: found.organization_name,
      });
      const newTgt = {
        name: dossier.name,
        role: dossier.role,
        organization: dossier.organization,
        email: dossier.email_info?.corporate_email || found.email_address,
        history: dossier.history,
      };
      setTarget(newTgt);
      setMessages([
        {
          sender: "copilot",
          text: `Switched target to ${newTgt.name} (${newTgt.role} at ${newTgt.organization}). Generated fresh baseline email draft aligned with their technical initiatives.`,
        },
      ]);
      await generateInitial(newTgt);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed to switch target");
    } finally {
      setGenerating(false);
    }
  };

  const handleRefine = async (prompt: string) => {
    if (!prompt.trim() || !target) return;

    setUserInput("");
    setMessages((prev) => [...prev, { sender: "user", text: prompt }]);
    setRefining(true);
    setError(null);

    try {
      const res = await api.refineDraft({
        current_body: bodyText,
        current_subject: subjectLine,
        target_name: target.name,
        target_org: target.organization,
        target_role: target.role,
        user_guidance: prompt,
        target_history: (target.history || {}) as Record<string, unknown>,
      });

      setBodyText(res.revised_body);
      setSubjectLine(res.revised_subject);
      setMessages((prev) => [
        ...prev,
        {
          sender: "copilot",
          text: `Revised draft (${res.word_count} words). ${res.explanation}`,
        },
      ]);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed to refine draft");
      setMessages((prev) => [
        ...prev,
        { sender: "copilot", text: "Encountered an issue processing that refinement instruction." },
      ]);
    } finally {
      setRefining(false);
    }
  };

  const handleStageSelect = async (stage: string) => {
    setSelectedStage(stage);
    if (!target) return;
    setRefining(true);
    setError(null);
    try {
      const res = await api.salesgptRefine({
        stage,
        target_name: target.name,
        target_org: target.organization,
        target_role: target.role,
        target_history: (target.history || {}) as Record<string, unknown>,
        user_guidance: userInput || undefined,
      });
      setBodyText(res.body_text);
      setSubjectLine(res.subject_line);
      setMessages((prev) => [
        ...prev,
        {
          sender: "copilot",
          text: `[Focus Updated] Calibrated draft (${res.word_count} words). ${res.explanation}`,
        },
      ]);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed to execute stage calibration");
    } finally {
      setRefining(false);
    }
  };

  const handleApprove = async () => {
    if (!target) return;
    if (wordCount < 100 || wordCount > 160) {
      setError(`Strict Quality Gate: Email body must be between 100 and 160 words. Current count is ${wordCount}. Use the quick chips on the left to calibrate.`);
      return;
    }

    setApproving(true);
    setError(null);
    try {
      const res = await api.approveDraft({
        recipient_email: target.email,
        recipient_name: target.name,
        organization_name: target.organization,
        recipient_role: target.role,
        subject_line: subjectLine,
        body_text: bodyText,
      });
      setApprovalHash(res.approval_hash);
      setTimeout(() => {
        onForwardToTab5(target.email);
      }, 700);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed to approve draft");
    } finally {
      setApproving(false);
    }
  };

  const isWordCountValid = wordCount >= 100 && wordCount <= 160;

  return (
    <div className="space-y-6">
      {/* Header Banner */}
      <div className="p-6 rounded-lg bg-neutral-900/50 border border-neutral-800 flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-2">
            <span className="text-[10px] font-mono uppercase tracking-widest text-neutral-300 bg-neutral-800 px-2 py-0.5 rounded-xs border border-neutral-700">
              Step 04
            </span>
            <span className="text-xs text-neutral-400 font-medium">Conversational AI Co-Pilot &amp; Quality Gate</span>
          </div>
          <h2 className="text-xl font-bold text-neutral-100 tracking-tight mt-1.5">
            AI Co-Pilot: Personalized Career Narrative
          </h2>
          <p className="text-xs text-neutral-400 mt-1 max-w-2xl leading-relaxed">
            Iterate directly with the co-pilot to craft high-conversion emails citing the candidate&apos;s real track record. Strictly enforces the 100&ndash;160 word window.
          </p>
        </div>

        {target && (
          <button
            onClick={() => generateInitial(target)}
            disabled={generating}
            className="self-start md:self-auto px-4 py-2.5 rounded-sm bg-neutral-900 hover:bg-neutral-850 text-neutral-200 border border-neutral-750 text-xs font-medium transition-colors flex items-center gap-1.5 shrink-0 shadow-xs"
          >
            <RefreshCw className={`w-3.5 h-3.5 text-neutral-300 ${generating ? "animate-spin" : ""}`} />
            <span>Reset to Base Draft</span>
          </button>
        )}
      </div>

      {error && (
        <div className="p-3.5 rounded-sm bg-red-950/60 border border-red-800 text-red-200 text-xs flex items-center gap-2">
          <AlertCircle className="w-4 h-4 shrink-0" />
          <span>{error}</span>
        </div>
      )}

      {!target ? (
        <div className="p-16 rounded-lg bg-neutral-900/30 border border-neutral-800 flex flex-col items-center justify-center text-center space-y-4">
          <div className="w-12 h-12 rounded-full bg-neutral-900 border border-neutral-800 flex items-center justify-center text-neutral-400">
            <PenTool className="w-5 h-5 text-neutral-400" />
          </div>
          <div>
            <h3 className="text-sm font-semibold text-neutral-200">AI Co-Pilot Writer Standby</h3>
            <p className="text-xs text-neutral-400 max-w-md mt-1 leading-relaxed">
              No target recipient selected. Forward an executive from Tab 3 (Executive Dossier), or choose a decision-maker from the directory below to begin personalized drafting.
            </p>
          </div>
          {availableContacts.length > 0 && (
            <div className="pt-2 flex items-center gap-2">
              <span className="text-xs text-neutral-400">Quick Select:</span>
              <select
                defaultValue=""
                onChange={(e) => {
                  if (e.target.value) handleSwitchTarget(e.target.value);
                }}
                className="bg-neutral-950 border border-neutral-800 rounded-sm py-1.5 px-3 text-xs text-neutral-200 focus:outline-hidden focus:border-neutral-500 max-w-xs"
              >
                <option value="">-- Choose an executive recipient --</option>
                {availableContacts.map((c) => (
                  <option key={`${c.organization_name}:::${c.contact_name}`} value={`${c.organization_name}:::${c.contact_name}`}>
                    {c.contact_name} ({c.organization_name} &bull; {c.role_designation})
                  </option>
                ))}
              </select>
            </div>
          )}
        </div>
      ) : (
        <>
          {/* Target & Matched Experience Context Bar */}
          <div className="p-4 rounded-lg bg-neutral-900/60 border border-neutral-800 flex flex-col md:flex-row md:items-center justify-between gap-3 text-xs">
            <div className="flex flex-col sm:flex-row sm:items-center gap-3">
              <div>
                <span className="text-neutral-400">Target Recipient:</span>{" "}
                <strong className="text-neutral-100 font-semibold">{target.name}</strong> ({target.role}) &bull;{" "}
                <span className="text-neutral-200 font-medium">{target.organization}</span>
              </div>
              {availableContacts.length > 0 && (
                <div className="flex items-center gap-1.5 shrink-0">
                  <Users className="w-3.5 h-3.5 text-neutral-400" />
                  <select
                    value={`${target.organization}:::${target.name}`}
                    onChange={(e) => handleSwitchTarget(e.target.value)}
                    disabled={generating}
                    className="bg-neutral-950 border border-neutral-800 rounded-sm py-1 px-2 text-[11px] text-neutral-300 focus:outline-hidden focus:border-neutral-500 max-w-[200px] truncate"
                    title="Switch Target Decision Maker"
                  >
                    {availableContacts.slice(0, 50).map((c) => (
                      <option key={`${c.organization_name}:::${c.contact_name}`} value={`${c.organization_name}:::${c.contact_name}`}>
                        {c.contact_name} ({c.organization_name})
                      </option>
                    ))}
                  </select>
                </div>
              )}
            </div>
            <div className="flex items-center gap-2">
              <span className="text-neutral-400">Matched Experience:</span>
              <span className="font-mono text-[11px] px-2.5 py-1 rounded-xs bg-neutral-950 border border-neutral-800 text-neutral-200">
                {matchedExperience?.organization || "Public Health Foundation of India (PHFI)"} &mdash;{" "}
                {matchedExperience?.headline || "Data Validation & Integrity"}
              </span>
            </div>
          </div>

          {/* Split-View Workspace */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Left Column: Interactive Chat Refinement */}
        <div className="p-5 rounded-lg bg-neutral-900/60 border border-neutral-800 flex flex-col h-[620px] justify-between">
          <div className="space-y-3">
            <div className="flex items-center justify-between pb-3 border-b border-neutral-800">
              <div className="flex items-center gap-2">
                <MessageSquare className="w-4 h-4 text-neutral-300" />
                <span className="text-xs font-semibold text-neutral-200">Co-Pilot Writer Dialogue</span>
              </div>
              <span className="text-[10px] font-mono text-emerald-400 bg-neutral-900 px-2 py-0.5 rounded-xs border border-neutral-800">
                [CO-PILOT_ONLINE]
              </span>
            </div>

            {/* Outreach Focus & Angle Selector */}
            <div className="space-y-1.5 pb-2">
              <div className="text-[10px] text-neutral-400 font-mono flex items-center justify-between">
                <span>Outreach Angle &amp; Experience Focus:</span>
                <span className="text-[10px] font-mono text-emerald-400">[Quality Gate: 100-160 Words]</span>
              </div>
              <div className="grid grid-cols-2 gap-1.5">
                {[
                  { key: "Stage 1: First Touch Introduction", label: "Initial Introduction" },
                  { key: "Stage 2: Technical QA & Platform Testing", label: "QA & Testing Focus" },
                  { key: "Stage 3: Automated ETL & Data Operations", label: "Data Pipelines & ETL" },
                  { key: "Stage 4: Executive Concise (2thepoint)", label: "Executive Brief (100W)" },
                ].map((item) => (
                  <button
                    key={item.key}
                    type="button"
                    onClick={() => handleStageSelect(item.key)}
                    disabled={refining}
                    className={`px-2.5 py-1.5 rounded-xs border text-[11px] font-medium text-left truncate transition-colors ${
                      selectedStage === item.key
                        ? "bg-neutral-100 text-neutral-950 border-white font-semibold shadow-xs"
                        : "bg-neutral-950 text-neutral-300 hover:bg-neutral-900 border-neutral-800"
                    }`}
                  >
                    {item.label}
                  </button>
                ))}
              </div>
            </div>

            {/* Quick Refinement Action Chips */}
            <div className="space-y-1.5 pb-2">
              <div className="text-[10px] text-neutral-400 font-mono flex items-center gap-1">
                <Zap className="w-3 h-3 text-neutral-400" />
                <span>Quick Refinements:</span>
              </div>
              <div className="flex flex-wrap gap-1.5">
                <button
                  type="button"
                  onClick={() => handleRefine("Make the email shorter and more concise (around 105 words) respecting 2thepoint")}
                  className="px-2.5 py-1 rounded-xs bg-neutral-950 hover:bg-neutral-850 border border-neutral-800 text-[11px] text-neutral-300 transition-colors"
                >
                  Make more concise
                </button>
                <button
                  type="button"
                  onClick={() => handleRefine("Emphasize my hands-on QA testing, API regression checks, and Sanad AI validation at Ejada Labs")}
                  className="px-2.5 py-1 rounded-xs bg-neutral-950 hover:bg-neutral-850 border border-neutral-800 text-[11px] text-neutral-300 transition-colors"
                >
                  Highlight Ejada Labs QA
                </button>
                <button
                  type="button"
                  onClick={() => handleRefine("Focus on my automated ETL pipelines and data cleaning scripts from client projects")}
                  className="px-2.5 py-1 rounded-xs bg-neutral-950 hover:bg-neutral-850 border border-neutral-800 text-[11px] text-neutral-300 transition-colors"
                >
                  Focus on ETL pipelines
                </button>
                <button
                  type="button"
                  onClick={() => handleRefine("Highlight Python validation scripts and large health dataset screening at PHFI")}
                  className="px-2.5 py-1 rounded-xs bg-neutral-950 hover:bg-neutral-850 border border-neutral-800 text-[11px] text-neutral-300 transition-colors"
                >
                  Emphasize PHFI data checks
                </button>
                <button
                  type="button"
                  onClick={() => handleRefine("Make the tone more formal and executive for senior corporate leadership")}
                  className="px-2.5 py-1 rounded-xs bg-neutral-950 hover:bg-neutral-850 border border-neutral-800 text-[11px] text-neutral-300 transition-colors"
                >
                  Formal executive tone
                </button>
              </div>
            </div>
          </div>

          {/* Messages Scroll Area */}
          <div className="flex-1 overflow-y-auto py-2 space-y-3 pr-1">
            {messages.map((m, idx) => (
              <div
                key={idx}
                className={`p-3 rounded-sm text-xs leading-relaxed max-w-[90%] ${
                  m.sender === "user"
                    ? "ml-auto bg-neutral-850 text-neutral-100 border border-neutral-750"
                    : "bg-neutral-950 text-neutral-300 border border-neutral-850"
                }`}
              >
                <div className="text-[10px] font-mono uppercase text-neutral-400 mb-1">
                  {m.sender === "user" ? "You (Guidance)" : "AI Co-Pilot Writer"}
                </div>
                <div>{m.text}</div>
              </div>
            ))}
            {refining && (
              <div className="p-3 rounded-sm text-xs bg-neutral-950 text-neutral-300 border border-neutral-850 flex items-center gap-2">
                <div className="w-3.5 h-3.5 border-2 border-neutral-400 border-t-white rounded-full animate-spin" />
                <span>Calibrating narrative to your instructions...</span>
              </div>
            )}
          </div>

          {/* Prompt Input Form */}
          <form
            onSubmit={(e) => {
              e.preventDefault();
              handleRefine(userInput);
            }}
            className="pt-3 border-t border-neutral-800 flex gap-2"
          >
            <input
              type="text"
              placeholder="Type any guidance (e.g. emphasize SQL validation, mention Tuesday call)..."
              value={userInput}
              onChange={(e) => setUserInput(e.target.value)}
              disabled={refining || !target}
              className="flex-1 bg-neutral-950 border border-neutral-800 rounded-sm py-2 px-3 text-xs text-neutral-200 placeholder:text-neutral-600 focus:outline-hidden focus:border-neutral-500 disabled:opacity-50"
            />
            <button
              type="submit"
              disabled={refining || !userInput.trim() || !target}
              className="px-4 py-2 bg-neutral-100 hover:bg-white text-neutral-950 text-xs font-semibold rounded-sm transition-colors flex items-center gap-1.5 disabled:opacity-40"
            >
              <Send className="w-3 h-3" />
              <span>Refine</span>
            </button>
          </form>
        </div>

        {/* Right Column: Live Draft Preview & Approval Gate */}
        <div className="p-5 rounded-lg bg-neutral-900/60 border border-neutral-800 flex flex-col h-[620px] justify-between">
          <div className="space-y-3">
            <div className="flex items-center justify-between pb-3 border-b border-neutral-800">
              <div className="flex items-center gap-2">
                <PenTool className="w-4 h-4 text-neutral-300" />
                <span className="text-xs font-semibold text-neutral-200">Live Draft Preview</span>
              </div>

              {/* Word Count Enforcement Indicator */}
              <div className="flex items-center gap-2">
                <span
                  className={`text-[10px] font-mono px-2.5 py-0.5 rounded-xs border font-medium ${
                    isWordCountValid
                      ? "bg-emerald-950 text-emerald-300 border-emerald-800"
                      : "bg-amber-950 text-amber-300 border-amber-800"
                  }`}
                >
                  [{wordCount} / 100-160 WORDS: {isWordCountValid ? "COMPLIANT" : "OUT OF BOUNDS"}]
                </span>
              </div>
            </div>

            {/* Subject Line Input */}
            <div>
              <label className="block text-[11px] text-neutral-400 mb-1 font-medium">Subject Line</label>
              <input
                type="text"
                value={subjectLine}
                onChange={(e) => setSubjectLine(e.target.value)}
                className="w-full bg-neutral-950 border border-neutral-800 rounded-sm py-2 px-3 text-xs text-neutral-100 font-mono focus:outline-hidden focus:border-neutral-500"
              />
            </div>

            {/* Email Body Text Area */}
            <div>
              <label className="block text-[11px] text-neutral-400 mb-1 font-medium">Email Body Text</label>
              <textarea
                rows={12}
                value={bodyText}
                onChange={(e) => setBodyText(e.target.value)}
                className="w-full bg-neutral-950 border border-neutral-800 rounded-sm p-3.5 text-xs text-neutral-200 leading-relaxed font-sans focus:outline-hidden focus:border-neutral-500 resize-none"
              />
            </div>
          </div>

          {/* Bottom Approval Action & Hash Preview */}
          <div className="pt-3 border-t border-neutral-800 space-y-2">
            {approvalHash && (
              <div className="p-2 rounded-sm bg-neutral-950 border border-neutral-800 text-[10px] font-mono text-neutral-300 flex items-center justify-between">
                <span>SHA-256 Approval Hash:</span>
                <span className="text-neutral-400 truncate max-w-[240px]">{approvalHash}</span>
              </div>
            )}

            <div className="flex items-center justify-between">
              <span className="text-[11px] text-neutral-400">
                Word Count Gate:{" "}
                <strong className={isWordCountValid ? "text-emerald-400" : "text-amber-400"}>
                  {isWordCountValid ? "100–160 Words Verified" : "Adjust length to 100-160 words"}
                </strong>
              </span>

              <button
                onClick={handleApprove}
                disabled={approving || !isWordCountValid || !target}
                className="px-6 py-2.5 rounded-sm bg-neutral-100 hover:bg-white text-neutral-950 text-xs font-semibold tracking-wide transition-colors flex items-center gap-2 disabled:opacity-40 shadow-xs"
              >
                {approving ? (
                  <>
                    <div className="w-3.5 h-3.5 border-2 border-neutral-950 border-t-transparent rounded-full animate-spin" />
                    <span>Signing &amp; Approving...</span>
                  </>
                ) : (
                  <>
                    <ShieldCheck className="w-3.5 h-3.5" />
                    <span>Approve Draft &amp; Proceed to Dispatch</span>
                    <ArrowRight className="w-3.5 h-3.5 ml-0.5" />
                  </>
                )}
              </button>
            </div>
          </div>
        </div>
      </div>
    </>
  )}
</div>
  );
}
