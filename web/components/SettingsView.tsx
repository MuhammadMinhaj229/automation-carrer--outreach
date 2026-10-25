"use client";

import React, { useState, useEffect } from "react";
import { SettingsData, SettingsUpdateRequest, api } from "@/lib/api";
import {
  ShieldCheck,
  User,
  Mail,
  Phone,
  Link2,
  Globe,
  GraduationCap,
  Key,
  Eye,
  EyeOff,
  Upload,
  FileText,
  CheckCircle2,
  AlertCircle,
  Save,
  RefreshCw,
  Briefcase,
  Lock,
} from "lucide-react";

export default function SettingsView() {
  const [settings, setSettings] = useState<SettingsData | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [saveSuccess, setSaveSuccess] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  // Form states
  const [fullName, setFullName] = useState("");
  const [email, setEmail] = useState("");
  const [phone, setPhone] = useState("");
  const [linkedinUrl, setLinkedinUrl] = useState("");
  const [portfolioUrl, setPortfolioUrl] = useState("");
  const [academicBackground, setAcademicBackground] = useState("");

  // Credential states
  const [gmailUser, setGmailUser] = useState("");
  const [gmailAppPassword, setGmailAppPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);

  // Resume upload state
  const [uploadingResume, setUploadingResume] = useState(false);
  const [resumeUploadMessage, setResumeUploadMessage] = useState<string | null>(null);

  const loadSettings = async () => {
    setLoading(true);
    setErrorMessage(null);
    try {
      const data = await api.getSettings();
      setSettings(data);
      if (data.profile) {
        setFullName(data.profile.full_name || "");
        setEmail(data.profile.email || "");
        setPhone(data.profile.phone || "");
        setLinkedinUrl(data.profile.linkedin_url || "");
        setPortfolioUrl(data.profile.portfolio_url || "");
        setAcademicBackground(data.profile.academic_background || "");
      }
      if (data.credentials) {
        setGmailUser(data.credentials.gmail_user || "");
        setGmailAppPassword(data.credentials.masked_password || "");
      }
    } catch (err: unknown) {
      setErrorMessage(err instanceof Error ? err.message : "Failed to load settings");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadSettings();
  }, []);

  const handleSave = async (e: React.FormEvent) => {
    e.preventDefault();
    setSaving(true);
    setSaveSuccess(false);
    setErrorMessage(null);

    const payload: SettingsUpdateRequest = {
      full_name: fullName,
      email: email,
      phone: phone,
      linkedin_url: linkedinUrl,
      portfolio_url: portfolioUrl,
      academic_background: academicBackground,
    };

    try {
      await api.updateSettings(payload);
      setSaveSuccess(true);
      setTimeout(() => setSaveSuccess(false), 4000);
      await loadSettings();
    } catch (err: unknown) {
      setErrorMessage(err instanceof Error ? err.message : "Failed to save settings");
    } finally {
      setSaving(false);
    }
  };

  const handleResumeUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    if (!file.name.toLowerCase().endsWith(".pdf")) {
      setErrorMessage("Only PDF resumes are supported.");
      return;
    }

    setUploadingResume(true);
    setResumeUploadMessage(null);
    setErrorMessage(null);

    try {
      const res = await api.uploadMasterResume(file);
      setResumeUploadMessage(`Master resume '${res.filename}' (${res.size_kb} KB) successfully uploaded and active.`);
      await loadSettings();
    } catch (err: unknown) {
      setErrorMessage(err instanceof Error ? err.message : "Resume upload failed");
    } finally {
      setUploadingResume(false);
    }
  };

  if (loading && !settings) {
    return (
      <div className="flex flex-col items-center justify-center h-96 text-neutral-400 space-y-3">
        <RefreshCw className="w-6 h-6 animate-spin text-neutral-200" />
        <span className="text-xs font-mono uppercase tracking-widest">Loading Candidate Profile &amp; Settings...</span>
      </div>
    );
  }

  return (
    <div className="space-y-8 animate-fadeIn max-w-4xl pb-16">
      {/* Header Banner */}
      <div className="bg-neutral-900/60 border border-neutral-800 rounded-sm p-6 backdrop-blur-sm">
        <div className="flex items-center gap-2">
          <span className="px-2 py-0.5 rounded-xs text-[10px] font-mono uppercase tracking-widest bg-blue-500/10 text-blue-400 border border-blue-500/20 flex items-center gap-1.5">
            <Lock className="w-3 h-3 text-blue-400" />
            SECURED_LOCAL_CONFIGURATION
          </span>
          <span className="text-neutral-500 text-xs font-mono">FILE: .env &amp; candidate_profile.yaml</span>
        </div>
        <h1 className="text-xl md:text-2xl font-bold text-neutral-100 tracking-tight mt-2">
          Candidate Identity &amp; System Configuration
        </h1>
        <p className="text-xs text-neutral-400 mt-1 leading-relaxed">
          Central management for your candidate credentials, outreach footer, master resume PDF, and Gmail TLS credentials. Changes are written directly to your local `.env` and `candidate_profile.yaml` without cloud telemetry exposure.
        </p>

        {saveSuccess && (
          <div className="mt-4 p-3 bg-emerald-500/10 border border-emerald-500/20 text-emerald-400 rounded-sm text-xs flex items-center gap-2 font-mono">
            <CheckCircle2 className="w-4 h-4 shrink-0" />
            <span>Profile settings and secure credentials successfully saved.</span>
          </div>
        )}

        {errorMessage && (
          <div className="mt-4 p-3 bg-rose-500/10 border border-rose-500/20 text-rose-400 rounded-sm text-xs flex items-center gap-2 font-mono">
            <AlertCircle className="w-4 h-4 shrink-0" />
            <span>{errorMessage}</span>
          </div>
        )}
      </div>

      <form onSubmit={handleSave} className="space-y-8">
        {/* Section 1: Candidate Identity */}
        <div className="bg-neutral-900/30 border border-neutral-800 rounded-sm p-6 space-y-5">
          <div className="border-b border-neutral-800 pb-3 flex items-center justify-between">
            <div>
              <h2 className="text-sm font-semibold text-neutral-200 flex items-center gap-2">
                <User className="w-4 h-4 text-neutral-400" />
                <span>1. Candidate Core Identity</span>
              </h2>
              <p className="text-[11px] text-neutral-400 mt-0.5">
                Included in cold emails, MIME headers, and AI pitch personalization.
              </p>
            </div>
            <span className="text-[10px] font-mono text-neutral-500">YAML_STORE</span>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <label className="block text-xs font-medium text-neutral-300 mb-1.5">
                Full Name
              </label>
              <input
                type="text"
                value={fullName}
                onChange={(e) => setFullName(e.target.value)}
                placeholder="e.g. "
                className="w-full px-3 py-2 bg-neutral-950 border border-neutral-800 rounded-sm text-xs text-neutral-100 focus:outline-none focus:border-neutral-500 transition-colors"
              />
            </div>

            <div>
              <label className="block text-xs font-medium text-neutral-300 mb-1.5">
                Outreach Email
              </label>
              <input
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="e.g. "
                className="w-full px-3 py-2 bg-neutral-950 border border-neutral-800 rounded-sm text-xs text-neutral-100 focus:outline-none focus:border-neutral-500 transition-colors font-mono"
                required
              />
            </div>

            <div>
              <label className="block text-xs font-medium text-neutral-300 mb-1.5">
                Phone Number (with Country Code)
              </label>
              <input
                type="text"
                value={phone}
                onChange={(e) => setPhone(e.target.value)}
                placeholder="e.g. "
                className="w-full px-3 py-2 bg-neutral-950 border border-neutral-800 rounded-sm text-xs text-neutral-100 focus:outline-none focus:border-neutral-500 transition-colors font-mono"
              />
            </div>

            <div>
              <label className="block text-xs font-medium text-neutral-300 mb-1.5">
                Academic Background / Specialization
              </label>
              <input
                type="text"
                value={academicBackground}
                onChange={(e) => setAcademicBackground(e.target.value)}
                placeholder="e.g. Computer Science & Data Science"
                className="w-full px-3 py-2 bg-neutral-950 border border-neutral-800 rounded-sm text-xs text-neutral-100 focus:outline-none focus:border-neutral-500 transition-colors"
              />
            </div>

            <div>
              <label className="block text-xs font-medium text-neutral-300 mb-1.5 flex items-center gap-1.5">
                <Link2 className="w-3.5 h-3.5 text-blue-400" />
                <span>LinkedIn Profile URL</span>
              </label>
              <input
                type="url"
                value={linkedinUrl}
                onChange={(e) => setLinkedinUrl(e.target.value)}
                placeholder="https://www.linkedin.com/in/"
                className="w-full px-3 py-2 bg-neutral-950 border border-neutral-800 rounded-sm text-xs text-neutral-100 focus:outline-none focus:border-neutral-500 transition-colors font-mono"
              />
            </div>

            <div>
              <label className="block text-xs font-medium text-neutral-300 mb-1.5 flex items-center gap-1.5">
                <Globe className="w-3.5 h-3.5 text-emerald-400" />
                <span>Portfolio Website URL</span>
              </label>
              <input
                type="url"
                value={portfolioUrl}
                onChange={(e) => setPortfolioUrl(e.target.value)}
                placeholder=""
                className="w-full px-3 py-2 bg-neutral-950 border border-neutral-800 rounded-sm text-xs text-neutral-100 focus:outline-none focus:border-neutral-500 transition-colors font-mono"
              />
            </div>
          </div>
        </div>

        {/* Section 2: Gmail TLS & Dispatch Credentials */}
        <div className="bg-neutral-900/30 border border-neutral-800 rounded-sm p-6 space-y-5">
          <div className="border-b border-neutral-800 pb-3 flex items-center justify-between">
            <div>
              <h2 className="text-sm font-semibold text-neutral-200 flex items-center gap-2">
                <Key className="w-4 h-4 text-amber-400" />
                <span>2. Gmail IMAP / SMTP Credentials</span>
              </h2>
              <p className="text-[11px] text-neutral-400 mt-0.5">
                Read-only connection status. Configure or rotate these values in your backend host secret manager; this page does not save credentials.
              </p>
            </div>
            <span className="text-[10px] font-mono text-emerald-400 bg-emerald-500/10 px-2 py-0.5 rounded-xs border border-emerald-500/20">
              {settings?.credentials.has_gmail_password ? "CONFIGURED" : "PENDING"}
            </span>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <label className="block text-xs font-medium text-neutral-300 mb-1.5">
                Gmail Sender Account (GMAIL_USER)
              </label>
              <input
                type="email"
                value={gmailUser}
                readOnly
                placeholder=""
                className="w-full px-3 py-2 bg-neutral-950 border border-neutral-800 rounded-sm text-xs text-neutral-100 focus:outline-none focus:border-neutral-500 transition-colors font-mono"
                required
              />
              <p className="text-[10px] text-neutral-500 mt-1">
                Used for SMTP dispatch and IMAP bounce/reply telemetry.
              </p>
            </div>

            <div>
              <label className="block text-xs font-medium text-neutral-300 mb-1.5 flex items-center justify-between">
                <span>16-Character App Password (GMAIL_APP_PASSWORD)</span>
                <button
                  type="button"
                  onClick={() => setShowPassword(!showPassword)}
                  className="text-[11px] text-neutral-400 hover:text-neutral-200 flex items-center gap-1"
                >
                  {showPassword ? <EyeOff className="w-3 h-3" /> : <Eye className="w-3 h-3" />}
                  <span>{showPassword ? "Hide" : "Show"}</span>
                </button>
              </label>
              <input
                type={showPassword ? "text" : "password"}
                value={gmailAppPassword}
                readOnly
                disabled
                placeholder="xxxx xxxx xxxx xxxx"
                className="w-full px-3 py-2 bg-neutral-950 border border-neutral-800 rounded-sm text-xs text-neutral-100 focus:outline-none focus:border-neutral-500 transition-colors font-mono tracking-wider"
              />
              <p className="text-[10px] text-neutral-500 mt-1">
                To change this credential, set GMAIL_APP_PASSWORD in the backend provider secret manager and redeploy.
              </p>
            </div>
          </div>
        </div>

        {/* Section 3: Master Resume PDF Manager */}
        <div className="bg-neutral-900/30 border border-neutral-800 rounded-sm p-6 space-y-4">
          <div className="border-b border-neutral-800 pb-3 flex items-center justify-between">
            <div>
              <h2 className="text-sm font-semibold text-neutral-200 flex items-center gap-2">
                <FileText className="w-4 h-4 text-emerald-400" />
                <span>3. Master PDF Resume Manager</span>
              </h2>
              <p className="text-[11px] text-neutral-400 mt-0.5">
                Automatically injected as an RFC822 attachment in all staged drafts and dispatched emails.
              </p>
            </div>
            <span className="text-[10px] font-mono text-neutral-400">
              LOCATION: data/resume/
            </span>
          </div>

          <div className="flex flex-col sm:flex-row sm:items-center justify-between p-4 bg-neutral-950 border border-neutral-800/80 rounded-sm gap-4">
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 rounded-sm bg-neutral-900 border border-neutral-800 flex items-center justify-center shrink-0">
                <FileText className="w-5 h-5 text-neutral-300" />
              </div>
              <div>
                <div className="text-xs font-medium text-neutral-200 truncate max-w-md">
                  {settings?.resume.filename || "No resume currently staged"}
                </div>
                <div className="text-[10px] font-mono text-neutral-500 mt-0.5">
                  Size: {settings?.resume.size_kb || 0} KB | Status:{" "}
                  <span className={settings?.resume.exists ? "text-emerald-400" : "text-amber-400"}>
                    {settings?.resume.exists ? "Verified on Disk" : "Missing"}
                  </span>
                </div>
              </div>
            </div>

            <div className="shrink-0">
              <label className="cursor-pointer inline-flex items-center gap-2 px-3 py-1.5 rounded-sm bg-neutral-800 hover:bg-neutral-750 text-neutral-200 text-xs font-medium border border-neutral-700 transition-colors">
                <Upload className="w-3.5 h-3.5" />
                <span>{uploadingResume ? "Uploading..." : "Upload New PDF"}</span>
                <input
                  type="file"
                  accept=".pdf"
                  onChange={handleResumeUpload}
                  disabled={uploadingResume}
                  className="hidden"
                />
              </label>
            </div>
          </div>

          {resumeUploadMessage && (
            <div className="p-2.5 bg-emerald-500/10 border border-emerald-500/20 text-emerald-400 rounded-sm text-xs font-mono flex items-center gap-2">
              <CheckCircle2 className="w-3.5 h-3.5 shrink-0" />
              <span>{resumeUploadMessage}</span>
            </div>
          )}
        </div>

        {/* Section 4: Email Signature Live Preview */}
        <div className="bg-neutral-900/30 border border-neutral-800 rounded-sm p-6 space-y-4">
          <div className="border-b border-neutral-800 pb-3">
            <h2 className="text-sm font-semibold text-neutral-200 flex items-center gap-2">
              <Mail className="w-4 h-4 text-sky-400" />
              <span>4. Standardized Email Footer &amp; Signature</span>
            </h2>
            <p className="text-[11px] text-neutral-400 mt-0.5">
              Dynamically compiled at the end of every cold outreach pitch.
            </p>
          </div>

          <div className="p-4 bg-neutral-950 border border-neutral-800 rounded-sm font-sans text-xs text-neutral-300 leading-relaxed">
            <div className="font-semibold text-neutral-100">{fullName || ""}</div>
            <div className="text-neutral-400 text-[11px]">Data &amp; Business Automation Analyst</div>
            <div className="text-[11px] text-neutral-500 mt-1">
              Mobile: {phone || ""} | Email: {email || ""}
            </div>
            <div className="text-[11px] text-sky-400/90 mt-0.5 flex flex-wrap gap-3 font-mono">
              {linkedinUrl && <span>LinkedIn: {linkedinUrl}</span>}
              {portfolioUrl && <span>Portfolio: {portfolioUrl}</span>}
            </div>
            <div className="text-[10px] text-neutral-500 mt-2 italic border-t border-neutral-900 pt-1.5">
              Master Resume attached: {settings?.resume.filename}
            </div>
          </div>
        </div>

        {/* Section 5: Grounded Experience Anchors */}
        <div className="bg-neutral-900/30 border border-neutral-800 rounded-sm p-6 space-y-4">
          <div className="border-b border-neutral-800 pb-3 flex items-center justify-between">
            <div>
              <h2 className="text-sm font-semibold text-neutral-200 flex items-center gap-2">
                <Briefcase className="w-4 h-4 text-purple-400" />
                <span>5. Grounded Experience Anchors (No-Hallucination Guard)</span>
              </h2>
              <p className="text-[11px] text-neutral-400 mt-0.5">
                The AI Writer is constrained to reference strictly these verified professional credentials.
              </p>
            </div>
            <span className="text-[10px] font-mono text-neutral-500">HARD_CONSTRAINTS</span>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
            {settings?.experiences &&
              Object.entries(settings.experiences).map(([key, exp]) => (
                <div key={key} className="p-3 bg-neutral-950 border border-neutral-800 rounded-sm text-xs">
                  <div className="font-semibold text-neutral-200">{exp.organization}</div>
                  <div className="text-neutral-400 text-[11px] mt-0.5">{exp.role}</div>
                  <div className="text-neutral-500 text-[10px] mt-2 line-clamp-3">
                    {exp.summary || exp.focus || exp.headline}
                  </div>
                </div>
              ))}
          </div>
        </div>

        {/* Form Actions Footer */}
        <div className="flex items-center justify-between pt-4 border-t border-neutral-800">
          <div className="text-xs text-neutral-500 font-mono">
            CONFIGURATION_STATUS: READY
          </div>
          <button
            type="submit"
            disabled={saving}
            className="flex items-center gap-2 px-5 py-2.5 rounded-sm bg-neutral-100 hover:bg-white text-neutral-950 text-xs font-semibold shadow-xs transition-colors"
          >
            <Save className={`w-3.5 h-3.5 ${saving ? "animate-spin" : ""}`} />
            <span>{saving ? "Saving Changes..." : "Save Settings & Credentials"}</span>
          </button>
        </div>
      </form>
    </div>
  );
}
