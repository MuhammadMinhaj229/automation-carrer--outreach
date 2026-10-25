/**
 * API client for interacting with the FastAPI backend.
 * Uses relative paths so Next.js proxy rewrites handle routing with zero CORS issues.
 */

const API_BASE = "";

export interface SystemOverviewData {
  metrics: {
    total_organizations: number;
    total_contacts: number;
    verified_contacts: number;
    staged_drafts: number;
    dispatched_emails: number;
    replies_count: number;
    bounces_caught: number;
  };
  candidate: {
    name: string;
    email_user: string;
  };
  resume: {
    filename: string;
    size_kb: number;
    is_ready: boolean;
  };
  recent_events: Array<{
    id: number;
    recipient_email: string;
    event_type: string;
    timestamp: string;
    details: string;
  }>;
  health: {
    database: string;
    reacher_sieve: string;
    apollo_hunter_alt: string;
    gmail_connected: boolean;
  };
}

export interface CandidateSettingsProfile {
  full_name: string;
  email: string;
  phone: string;
  linkedin_url: string;
  portfolio_url: string;
  academic_background: string;
}

export interface SettingsData {
  profile: CandidateSettingsProfile;
  credentials: {
    gmail_user: string;
    has_gmail_password: boolean;
    masked_password: string;
  };
  resume: {
    filename: string;
    size_kb: number;
    exists: boolean;
  };
  experiences: Record<string, {
    organization: string;
    role: string;
    focus?: string;
    summary?: string;
    evidence_cite?: string;
    headline?: string;
    tenure?: string;
  }>;
  rules: Record<string, unknown>;
}

export interface SettingsUpdateRequest {
  full_name?: string;
  email?: string;
  phone?: string;
  linkedin_url?: string;
  portfolio_url?: string;
  academic_background?: string;
  gmail_user?: string;
  gmail_app_password?: string;
  custom_footer?: string;
}

export interface SystemStats {
  total_organizations: number;
  total_contacts: number;
  total_signals: number;
  total_staged_drafts: number;
  total_suppressed_emails: number;
}

export interface HierarchyData {
  continents: Record<string, Record<string, string[]>>;
  triggers: Record<string, string>;
}

export interface CandidateProfile {
  full_name: string;
  email: string;
  phone: string;
  linkedin_url: string;
  location?: string;
  title?: string;
}

export interface ProfileResponse {
  candidate: CandidateProfile;
  signature_text: string;
  signature_html: string;
  last_updated: string | null;
  services: {
    imap_engine: string;
    smtp_engine: string;
    database: string;
    verification_waterfall: string;
  };
}

export interface SignalRecord {
  organization_name: string;
  website: string;
  continent: string;
  country: string;
  region: string;
  trigger_type: string;
  headline: string;
  published_date: string;
  talent_demand: string;
  status: string;
}

export interface DiscoveryScanResult {
  total_found: number;
  signals: SignalRecord[];
  excel_filename: string | null;
  csv_filename: string | null;
}

export interface DecisionMaker {
  name: string;
  role: string;
  linkedin_url: string;
  email: string;
  confidence: number;
  verified: boolean;
  source: string;
  organization_name?: string;
}

export interface AuditResult {
  domain: string;
  domain_accessible: boolean;
  http_status: number;
  trigger_verified: boolean;
  evidence_excerpt: string;
  decision_makers: DecisionMaker[];
}

export interface BatchAuditResult {
  organizations_audited: number;
  total_decision_makers: number;
  results: Record<string, AuditResult>;
  all_decision_makers: DecisionMaker[];
}

export interface ContactRecord {
  id: number;
  organization_name: string;
  contact_name: string;
  role_designation: string;
  email_address: string;
  linkedin_url: string;
  deliverability_status: string;
  confidence_score: number;
}

export interface DossierResponse {
  name: string;
  role: string;
  organization: string;
  email_info: {
    corporate_email: string;
    email_pattern: string;
    verification_waterfall: {
      gate_0_suppression: string;
      gate_1_mx_host: string;
      gate_2_disposable_check: string;
      gate_3_confidence_score: number;
    };
    deliverability_status: string;
  };
  history: {
    career_summary: string;
    technical_focus: string;
    past_roles: Array<{ role: string; organization: string; tenure: string }>;
    education: string;
    recent_initiatives: string;
  };
}

export interface InitialDraftResponse {
  subject_line: string;
  body_text: string;
  word_count: number;
  auto_matched_experience: {
    organization: string;
    role: string;
    evidence_cite: string;
    headline: string;
  };
}

export interface RefineDraftResponse {
  revised_body: string;
  revised_subject: string;
  word_count: number;
  explanation: string;
}

export interface ApprovedDraft {
  id: number;
  recipient_email: string;
  recipient_name: string;
  organization_name: string;
  recipient_role: string;
  subject_line: string;
  body_text: string;
  status: string;
  approval_hash?: string;
  updated_at?: string;
}

export interface OutreachEvent {
  id: number;
  recipient_email: string;
  action_type: string;
  status: string;
  status_message: string;
  timestamp: string;
}

export const api = {
  getSystemStats: async (): Promise<SystemStats> => {
    const res = await fetch(`${API_BASE}/api/system/stats`);
    if (!res.ok) throw new Error("Failed to fetch system stats");
    return res.json();
  },

  getHierarchy: async (): Promise<HierarchyData> => {
    const res = await fetch(`${API_BASE}/api/hierarchy`);
    if (!res.ok) throw new Error("Failed to fetch hierarchy");
    return res.json();
  },

  getProfile: async (): Promise<ProfileResponse> => {
    const res = await fetch(`${API_BASE}/api/profile`);
    if (!res.ok) throw new Error("Failed to fetch profile");
    return res.json();
  },

  updateProfile: async (data: CandidateProfile): Promise<{ status: string; message: string }> => {
    const res = await fetch(`${API_BASE}/api/profile`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(data),
    });
    if (!res.ok) throw new Error("Failed to update profile");
    return res.json();
  },

  runDiscoveryScan: async (payload: {
    country: string;
    region: string;
    trigger_category: string;
    search_org?: string;
    search_website?: string;
    custom_keywords?: string;
    max_results?: number;
  }): Promise<DiscoveryScanResult> => {
    const res = await fetch(`${API_BASE}/api/discovery/scan`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    if (!res.ok) throw new Error("Failed to execute discovery scan");
    return res.json();
  },

  runAuditAndHunt: async (organizations: string[]): Promise<BatchAuditResult> => {
    const res = await fetch(`${API_BASE}/api/audit/hunt`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ organizations }),
    });
    if (!res.ok) throw new Error("Failed to execute batch audit");
    return res.json();
  },

  listContacts: async (org?: string): Promise<ContactRecord[]> => {
    const url = org ? `${API_BASE}/api/contacts?org=${encodeURIComponent(org)}` : `${API_BASE}/api/contacts`;
    const res = await fetch(url);
    if (!res.ok) throw new Error("Failed to fetch contacts");
    return res.json();
  },

  getExecutiveDossier: async (payload: { name: string; role: string; organization: string }): Promise<DossierResponse> => {
    const res = await fetch(`${API_BASE}/api/executive/dossier`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    if (!res.ok) throw new Error("Failed to compile executive dossier");
    return res.json();
  },

  generateInitialDraft: async (payload: {
    target_name: string;
    target_role: string;
    target_org: string;
    target_email: string;
    target_history: Record<string, unknown>;
  }): Promise<InitialDraftResponse> => {
    const res = await fetch(`${API_BASE}/api/copilot/initial`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    if (!res.ok) throw new Error("Failed to generate initial draft");
    return res.json();
  },

  refineDraft: async (payload: {
    current_body: string;
    current_subject: string;
    target_name: string;
    target_org: string;
    target_role: string;
    user_guidance: string;
    target_history: Record<string, unknown>;
  }): Promise<RefineDraftResponse> => {
    const res = await fetch(`${API_BASE}/api/copilot/refine`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    if (!res.ok) throw new Error("Failed to refine draft");
    return res.json();
  },

  approveDraft: async (payload: {
    recipient_email: string;
    recipient_name: string;
    organization_name: string;
    recipient_role: string;
    subject_line: string;
    body_text: string;
  }): Promise<{ status: string; approval_hash: string; message: string }> => {
    const res = await fetch(`${API_BASE}/api/copilot/approve`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    if (!res.ok) throw new Error("Failed to approve draft");
    return res.json();
  },

  listApprovedDrafts: async (): Promise<ApprovedDraft[]> => {
    const res = await fetch(`${API_BASE}/api/drafts/approved`);
    if (!res.ok) throw new Error("Failed to list approved drafts");
    return res.json();
  },

  stageDraftInGmail: async (recipientEmail: string, file?: File): Promise<{ success: boolean; message: string }> => {
    const form = new FormData();
    form.append("recipient_email", recipientEmail);
    if (file) form.append("custom_resume", file);
    const res = await fetch(`${API_BASE}/api/dispatch/stage-gmail`, {
      method: "POST",
      body: form,
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: "Failed to stage draft" }));
      throw new Error(err.detail || "Failed to stage draft in Gmail");
    }
    return res.json();
  },

  sendDirectEmail: async (recipientEmail: string, file?: File): Promise<{ success: boolean; message: string }> => {
    const form = new FormData();
    form.append("recipient_email", recipientEmail);
    if (file) form.append("custom_resume", file);
    const res = await fetch(`${API_BASE}/api/dispatch/send-direct`, {
      method: "POST",
      body: form,
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: "Failed to send email" }));
      throw new Error(err.detail || "Failed to send email directly");
    }
    return res.json();
  },

  getOutreachLedger: async (limit = 20): Promise<OutreachEvent[]> => {
    const res = await fetch(`${API_BASE}/api/outreach/ledger?limit=${limit}`);
    if (!res.ok) throw new Error("Failed to fetch outreach ledger");
    return res.json();
  },

  runDeepRadar: async (payload: {
    organization_name?: string;
    website?: string;
    keywords?: string;
    country?: string;
  }): Promise<{
    engine: string;
    total_signals_discovered: number;
    signals: SignalRecord[];
  }> => {
    const res = await fetch(`${API_BASE}/api/discovery/deep-radar`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    if (!res.ok) throw new Error("Failed to execute Crawl4AI + GDELT deep radar scan");
    return res.json();
  },

  runOSINTHunt: async (payload: {
    organization_name: string;
    website?: string;
  }): Promise<{
    engine: string;
    organization: string;
    domain_footprint: {
      domain: string;
      primary_ip: string;
      active_subdomains_found: number;
      subdomains: Array<{ host: string; ip: string }>;
      engine: string;
    };
    decision_makers_found: number;
    decision_makers: DecisionMaker[];
  }> => {
    const res = await fetch(`${API_BASE}/api/audit/osint-hunt`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    if (!res.ok) throw new Error("Failed to execute CrossLinked OSINT hunt");
    return res.json();
  },

  checkReacherDeliverability: async (email: string): Promise<{
    valid: boolean;
    confidence: number;
    engine: string;
    status: string;
    mx_host?: string;
    is_catch_all?: boolean;
    smtp_code?: number;
    details: string;
  }> => {
    const res = await fetch(`${API_BASE}/api/verification/reacher-check`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email }),
    });
    if (!res.ok) throw new Error("Failed to execute Reacher SMTP check");
    return res.json();
  },

  salesgptRefine: async (payload: {
    stage: string;
    target_name: string;
    target_org: string;
    target_role: string;
    target_history: Record<string, unknown>;
    user_guidance?: string;
  }): Promise<{
    engine: string;
    stage: string;
    subject_line: string;
    body_text: string;
    word_count: number;
    explanation: string;
    compliant_100_160: boolean;
  }> => {
    const res = await fetch(`${API_BASE}/api/copilot/salesgpt-refine`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    if (!res.ok) throw new Error("Failed to execute SalesGPT stage refinement");
    return res.json();
  },

  getWebhookStatus: async (): Promise<{
    engine: string;
    status: string;
    webhook_path: string;
    bounce_guard: string;
    reply_guard: string;
  }> => {
    const res = await fetch(`${API_BASE}/api/webhooks/status`);
    if (!res.ok) throw new Error("Failed to fetch webhook status");
    return res.json();
  },

  getDbDownloadUrl: () => `${API_BASE}/api/download/db`,
  getMasterExcelDownloadUrl: () => `${API_BASE}/api/download/master-excel`,
  getDiscoveryDownloadUrl: (filename: string) => `${API_BASE}/api/discovery/download/${encodeURIComponent(filename)}`,
  getImapSyncStreamUrl: () => `${API_BASE}/api/imap/sync-stream`,

  getSystemOverview: async (): Promise<SystemOverviewData> => {
    const res = await fetch(`${API_BASE}/api/system/overview`);
    if (!res.ok) throw new Error("Failed to fetch system overview");
    return res.json();
  },

  getSettings: async (): Promise<SettingsData> => {
    const res = await fetch(`${API_BASE}/api/settings`);
    if (!res.ok) throw new Error("Failed to fetch settings");
    return res.json();
  },

  updateSettings: async (payload: SettingsUpdateRequest): Promise<{ status: string; message: string }> => {
    const res = await fetch(`${API_BASE}/api/settings`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    if (!res.ok) throw new Error("Failed to update settings");
    return res.json();
  },

  uploadMasterResume: async (file: File): Promise<{ status: string; filename: string; size_kb: number; message: string }> => {
    const formData = new FormData();
    formData.append("file", file);
    const res = await fetch(`${API_BASE}/api/settings/resume`, {
      method: "POST",
      body: formData,
    });
    if (!res.ok) throw new Error("Failed to upload master resume");
    return res.json();
  },

  triggerDispatchQueue: async (interval: number = 60): Promise<{ status: string; message: string }> => {
    const res = await fetch(`${API_BASE}/api/queue/dispatch?interval=${interval}`, {
      method: "POST",
    });
    if (!res.ok) throw new Error("Failed to trigger dispatch queue");
    return res.json();
  },

  triggerSyncDrafts: async (): Promise<{ status: string; message: string }> => {
    const res = await fetch(`${API_BASE}/api/drafts/sync-gmail`, {
      method: "POST",
    });
    if (!res.ok) throw new Error("Failed to trigger drafts synchronization");
    return res.json();
  },
};
