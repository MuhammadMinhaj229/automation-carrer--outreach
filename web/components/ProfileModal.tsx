"use client";

import React, { useState, useEffect } from "react";
import { CandidateProfile, ProfileResponse, api } from "@/lib/api";
import { User, Mail, Phone, Globe, Check, AlertCircle, Save, X } from "lucide-react";

interface ProfileModalProps {
  isOpen: boolean;
  onClose: () => void;
  onProfileUpdated?: () => void;
}

export default function ProfileModal({ isOpen, onClose, onProfileUpdated }: ProfileModalProps) {
  const [profile, setProfile] = useState<ProfileResponse | null>(null);
  const [form, setForm] = useState<CandidateProfile>({
    full_name: "",
    email: "",
    phone: "",
    linkedin_url: "",
  });
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [saveSuccess, setSaveSuccess] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (isOpen) {
      loadProfile();
    }
  }, [isOpen]);

  const loadProfile = async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await api.getProfile();
      setProfile(data);
      setForm({
        full_name: data.candidate.full_name || "",
        email: data.candidate.email || "",
        phone: data.candidate.phone || "",
        linkedin_url: data.candidate.linkedin_url || "",
      });
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed to load candidate profile");
    } finally {
      setLoading(false);
    }
  };

  const handleSave = async (e: React.FormEvent) => {
    e.preventDefault();
    setSaving(true);
    setError(null);
    setSaveSuccess(false);
    try {
      await api.updateProfile(form);
      setSaveSuccess(true);
      if (onProfileUpdated) onProfileUpdated();
      await loadProfile();
      setTimeout(() => setSaveSuccess(false), 3000);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed to save profile");
    } finally {
      setSaving(false);
    }
  };

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-xs p-4">
      <div className="bg-neutral-900 border border-neutral-700 rounded-lg max-w-2xl w-full p-6 text-neutral-100 shadow-2xl overflow-y-auto max-h-[90vh]">
        <div className="flex items-center justify-between pb-4 border-b border-neutral-800">
          <div>
            <h2 className="text-lg font-semibold tracking-wide text-neutral-100">
              Candidate Identity & Profile Persistence
            </h2>
            <p className="text-xs text-neutral-400 mt-1">
              Stores the candidate profile in the configured application database; local YAML is only a development fallback.
            </p>
          </div>
          <button
            onClick={onClose}
            className="p-1 rounded-sm hover:bg-neutral-800 text-neutral-400 hover:text-white transition-colors"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {error && (
          <div className="mt-4 p-3 rounded-sm bg-red-950/60 border border-red-800 text-red-200 text-xs flex items-center gap-2">
            <AlertCircle className="w-4 h-4 shrink-0" />
            <span>{error}</span>
          </div>
        )}

        {saveSuccess && (
          <div className="mt-4 p-3 rounded-sm bg-emerald-950/60 border border-emerald-800 text-emerald-200 text-xs flex items-center gap-2">
            <Check className="w-4 h-4 shrink-0" />
            <span>Profile successfully saved to persistent storage.</span>
          </div>
        )}

        {loading ? (
          <div className="py-12 flex flex-col items-center justify-center space-y-2 text-neutral-400">
            <div className="w-6 h-6 border-2 border-neutral-500 border-t-white rounded-full animate-spin" />
            <p className="text-xs">Loading candidate profile...</p>
          </div>
        ) : (
          <form onSubmit={handleSave} className="mt-4 space-y-4">
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div>
                <label className="block text-xs font-medium text-neutral-300 mb-1">
                  Full Name
                </label>
                <div className="relative">
                  <User className="w-4 h-4 text-neutral-500 absolute left-3 top-2.5" />
                  <input
                    type="text"
                    value={form.full_name}
                    onChange={(e) => setForm({ ...form, full_name: e.target.value })}
                    required
                    className="w-full bg-neutral-950 border border-neutral-800 rounded-sm py-2 pl-9 pr-3 text-xs text-neutral-100 focus:outline-hidden focus:border-neutral-500"
                  />
                </div>
              </div>

              <div>
                <label className="block text-xs font-medium text-neutral-300 mb-1">
                  Corporate / Primary Email
                </label>
                <div className="relative">
                  <Mail className="w-4 h-4 text-neutral-500 absolute left-3 top-2.5" />
                  <input
                    type="email"
                    value={form.email}
                    onChange={(e) => setForm({ ...form, email: e.target.value })}
                    required
                    className="w-full bg-neutral-950 border border-neutral-800 rounded-sm py-2 pl-9 pr-3 text-xs text-neutral-100 focus:outline-hidden focus:border-neutral-500"
                  />
                </div>
              </div>

              <div>
                <label className="block text-xs font-medium text-neutral-300 mb-1">
                  Contact Phone / WhatsApp
                </label>
                <div className="relative">
                  <Phone className="w-4 h-4 text-neutral-500 absolute left-3 top-2.5" />
                  <input
                    type="text"
                    value={form.phone}
                    onChange={(e) => setForm({ ...form, phone: e.target.value })}
                    required
                    className="w-full bg-neutral-950 border border-neutral-800 rounded-sm py-2 pl-9 pr-3 text-xs text-neutral-100 focus:outline-hidden focus:border-neutral-500"
                  />
                </div>
              </div>

              <div>
                <label className="block text-xs font-medium text-neutral-300 mb-1">
                  LinkedIn Profile URL
                </label>
                <div className="relative">
                  <Globe className="w-4 h-4 text-neutral-500 absolute left-3 top-2.5" />
                  <input
                    type="url"
                    value={form.linkedin_url}
                    onChange={(e) => setForm({ ...form, linkedin_url: e.target.value })}
                    required
                    className="w-full bg-neutral-950 border border-neutral-800 rounded-sm py-2 pl-9 pr-3 text-xs text-neutral-100 focus:outline-hidden focus:border-neutral-500"
                  />
                </div>
              </div>
            </div>

            {/* Career Track Constraints */}
            <div className="p-3 bg-neutral-950/70 border border-neutral-800 rounded-sm text-xs space-y-1.5">
              <span className="font-semibold text-neutral-300">
                Verified Career Evidence Base:
              </span>
              <ul className="list-disc list-inside space-y-1 text-neutral-400">
                <li>
                  <strong className="text-neutral-300">Applied Data Research Institute (ADRI):</strong> Data validation, SQL integrity audits, reporting pipelines.
                </li>
                <li>
                  <strong className="text-neutral-300">Example Software Labs:</strong> QA automation, API regression testing, defect triage.
                </li>
                <li>
                  <strong className="text-neutral-300">Client Projects:</strong> High-throughput data extraction, ETL pipelines, Python data processing.
                </li>
              </ul>
            </div>

            {/* Dynamic Signature Preview */}
            {profile?.signature_text && (
              <div>
                <label className="block text-xs font-medium text-neutral-400 mb-1">
                  Dynamic Email Signature Preview
                </label>
                <pre className="p-3 bg-neutral-950 border border-neutral-800 rounded-sm text-[11px] text-neutral-300 font-mono whitespace-pre-wrap">
                  {profile.signature_text}
                </pre>
              </div>
            )}

            <div className="flex items-center justify-end gap-3 pt-3 border-t border-neutral-800">
              <button
                type="button"
                onClick={onClose}
                className="px-4 py-2 text-xs rounded-sm border border-neutral-700 hover:bg-neutral-800 text-neutral-300 transition-colors"
              >
                Close
              </button>
              <button
                type="submit"
                disabled={saving}
                className="px-4 py-2 text-xs rounded-sm bg-neutral-100 text-neutral-950 font-medium hover:bg-white transition-colors flex items-center gap-2 disabled:opacity-50"
              >
                {saving ? (
                  <>
                    <div className="w-3.5 h-3.5 border-2 border-neutral-900 border-t-transparent rounded-full animate-spin" />
                    <span>Saving...</span>
                  </>
                ) : (
                  <>
                    <Save className="w-3.5 h-3.5" />
                    <span>Save Changes</span>
                  </>
                )}
              </button>
            </div>
          </form>
        )}
      </div>
    </div>
  );
}
