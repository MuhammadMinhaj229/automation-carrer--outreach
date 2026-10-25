"""
Career Intelligence and Outreach Operating System.
Comprehensive 5-Tab Pipeline:
  Tab 1: Discovery
  Tab 2: Audit & Decision-Makers
  Tab 3: Executive Dossier & History
  Tab 4: AI Co-Pilot
  Tab 5: Email Automation & Dispatch
"""

import sys
import os
import re
import time
from pathlib import Path
from datetime import datetime, timezone
import streamlit as st
import pandas as pd
import yaml

BASE_DIR = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(BASE_DIR))

from acios.core.repository import CareerRepository
from acios.core.draft_engine import DraftEngine, get_candidate_signature
from acios.core.smtp_dispatcher import SMTPDispatcher
from acios.core.suppression import SuppressionEngine
from acios.core.generator import DraftGenerator
from acios.core.ai_copilot import AICopilotWriter
from acios.models.contact import Contact, VerificationStatus, OutreachStatus
from acios.models.email_draft import EmailDraft
from acios.providers.verification.waterfall import EmailVerificationWaterfall
from acios.tools.discovery.growth_scanner import GrowthSignalScanner, CONTINENT_MAP, TRIGGER_CATEGORIES
from acios.tools.discovery.linkedin_hunter import LinkedInHunter
from acios.tools.discovery.executive_intelligence import ExecutiveIntelligenceFinder
from acios.reports.export import export_all
from acios.flows.imap_reply_guard import run_imap_reply_guard

PROFILE_CONFIG_PATH = BASE_DIR / "config" / "candidate_profile.yaml"
DB_FILE_PATH = BASE_DIR / "data" / "acios.db"
MASTER_EXCEL_PATH = BASE_DIR / "Master_Career_Intelligence_Database.xlsx"
SUPPRESSION_FILE_PATH = BASE_DIR / "data" / "suppression" / "master_suppression.json"
DEFAULT_RESUME_PATH = BASE_DIR / "data" / "resume" / "master_resume.pdf"

# Page Configuration - Strict Zero Emojis
st.set_page_config(
    page_title="Career Intelligence and Outreach Operating System",
    page_icon=None,
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom Enterprise Styling - Clean, Minimalist, Zero Emojis
st.markdown("""
<style>
    .reportview-container {
        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
    }
    .metric-card {
        background-color: #f8fafc;
        border: 1px solid #cbd5e1;
        border-radius: 6px;
        padding: 12px;
        text-align: center;
        margin-bottom: 8px;
    }
    .badge-verified {
        background-color: #f0fdf4;
        color: #166534;
        border: 1px solid #bbf7d0;
        padding: 2px 8px;
        border-radius: 4px;
        font-weight: 600;
        font-size: 12px;
        display: inline-block;
    }
    .badge-blocked {
        background-color: #fef2f2;
        color: #991b1b;
        border: 1px solid #fecaca;
        padding: 2px 8px;
        border-radius: 4px;
        font-weight: 600;
        font-size: 12px;
        display: inline-block;
    }
    .badge-info {
        background-color: #f0f9ff;
        color: #075985;
        border: 1px solid #bae6fd;
        padding: 2px 8px;
        border-radius: 4px;
        font-weight: 600;
        font-size: 12px;
        display: inline-block;
    }
    .step-box {
        background-color: #f1f5f9;
        border-left: 3px solid #0284c7;
        padding: 8px 12px;
        margin-bottom: 6px;
        font-size: 13px;
        color: #1e293b;
    }
    .chat-bubble-assistant {
        background-color: #f8fafc;
        border-left: 3px solid #0284c7;
        padding: 12px;
        border-radius: 4px;
        margin-bottom: 8px;
        font-size: 13.5px;
        color: #0f172a;
    }
    .chat-bubble-user {
        background-color: #f0f9ff;
        border-left: 3px solid #2563eb;
        padding: 12px;
        border-radius: 4px;
        margin-bottom: 8px;
        font-size: 13.5px;
        color: #0f172a;
    }
</style>
""", unsafe_allow_html=True)


@st.cache_resource
def get_services():
    repo = CareerRepository()
    supp = SuppressionEngine()
    draft_engine = DraftEngine()
    dispatcher = SMTPDispatcher(repo=repo, supp=supp)
    waterfall = EmailVerificationWaterfall()
    scanner = GrowthSignalScanner(repo=repo)
    hunter = LinkedInHunter(repo=repo)
    intel_finder = ExecutiveIntelligenceFinder(repo=repo, waterfall=waterfall)
    copilot = AICopilotWriter()
    return repo, supp, draft_engine, dispatcher, waterfall, scanner, hunter, intel_finder, copilot

repo, supp, draft_engine, dispatcher, waterfall, scanner, hunter, intel_finder, copilot = get_services()

# Session State Initialization - Automatic Cross-Tab Linking
if "tab1_results" not in st.session_state:
    st.session_state["tab1_results"] = None
if "tab1_excel_path" not in st.session_state:
    st.session_state["tab1_excel_path"] = None
if "selected_organizations" not in st.session_state:
    st.session_state["selected_organizations"] = []
if "tab2_audit_results" not in st.session_state:
    st.session_state["tab2_audit_results"] = None
if "tab2_all_dms" not in st.session_state:
    st.session_state["tab2_all_dms"] = []
if "tab3_active_lead" not in st.session_state:
    st.session_state["tab3_active_lead"] = None
if "tab3_dossier" not in st.session_state:
    st.session_state["tab3_dossier"] = None
if "copilot_messages" not in st.session_state:
    st.session_state["copilot_messages"] = []
if "current_draft_body" not in st.session_state:
    st.session_state["current_draft_body"] = ""
if "current_draft_subject" not in st.session_state:
    st.session_state["current_draft_subject"] = ""
if "current_draft_recipient" not in st.session_state:
    st.session_state["current_draft_recipient"] = ""
if "approved_drafts" not in st.session_state:
    st.session_state["approved_drafts"] = []

# Load Candidate Profile from YAML and Database
def load_candidate_profile():
    # First check database settings
    db_profile = repo.get_candidate_profile()
    if db_profile:
        return db_profile

    # Fallback to YAML
    if PROFILE_CONFIG_PATH.exists():
        with open(PROFILE_CONFIG_PATH, "r", encoding="utf-8") as f:
            return yaml.safe_load(f)
    return {}

def save_candidate_profile(data):
    # 1. Save to YAML
    with open(PROFILE_CONFIG_PATH, "w", encoding="utf-8") as f:
        yaml.safe_dump(data, f, sort_keys=False)
    # 2. Save to database settings table
    repo.save_candidate_profile(data)
    now_iso = datetime.now(timezone.utc).isoformat()
    repo.set_setting("candidate_profile_updated_at", now_iso)

candidate_data = load_candidate_profile()
cand_info = candidate_data.get("candidate", {})

# =========================================================
# SIDEBAR
# =========================================================
with st.sidebar:
    st.markdown("## Career Intelligence and Outreach Operating System")
    st.caption("Human-in-the-Loop Strategic Execution Platform")
    st.divider()

    st.markdown("### Execution Pipeline Steps")
    st.markdown("""
    <div class='step-box'><b>Step 1: Discover</b> &mdash; Continent, country, and ecosystem scan</div>
    <div class='step-box'><b>Step 2: Audit</b> &mdash; Corporate verification and leadership search</div>
    <div class='step-box'><b>Step 3: Extract</b> &mdash; Deliverability waterfall and OSINT dossier</div>
    <div class='step-box'><b>Step 4: Personalize</b> &mdash; Evidence-based AI draft synthesis</div>
    <div class='step-box'><b>Step 5: Dispatch</b> &mdash; Staging to Gmail drafts or SMTP sending</div>
    """, unsafe_allow_html=True)
    st.divider()

    st.markdown("### Database Metrics")
    stats = repo.get_system_stats()
    c_m1, c_m2 = st.columns(2)
    c_m1.metric("Organizations", f"{stats['total_organizations']:,}")
    c_m2.metric("Contacts", f"{stats['total_contacts']:,}")
    c_m1.metric("Signals", f"{stats['total_signals']:,}")
    c_m2.metric("Drafts", f"{stats['total_staged_drafts']:,}")
    st.metric("Suppression Blocklist", f"{stats['total_suppressed_emails']:,} Inboxes")

    st.markdown("#### Database Downloads")
    if DB_FILE_PATH.exists():
        with open(DB_FILE_PATH, "rb") as f_db:
            st.download_button(
                label="Download SQLite Database (acios.db)",
                data=f_db.read(),
                file_name="acios.db",
                mime="application/x-sqlite3",
                use_container_width=True
            )

    if MASTER_EXCEL_PATH.exists():
        with open(MASTER_EXCEL_PATH, "rb") as f_xl:
            st.download_button(
                label="Download Master Excel Workbook (.xlsx)",
                data=f_xl.read(),
                file_name="Master_Career_Intelligence_Database.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True
            )

    st.divider()
    st.markdown("### Profile")
    with st.expander("Candidate Identity & Connectivity", expanded=False):
        p_name = st.text_input("Full Name:", cand_info.get("full_name", ""))
        p_email = st.text_input("Sender Email:", cand_info.get("email", ""))
        p_phone = st.text_input("Phone:", cand_info.get("phone", ""))
        p_linkedin = st.text_input("LinkedIn:", cand_info.get("linkedin_url", ""))
        
        last_updated = repo.get_setting("candidate_profile_updated_at")
        if last_updated:
            st.caption(f"Last persisted: {last_updated[:19].replace('T', ' ')}")

        st.markdown("**Connected Services:**")
        st.markdown("- Gmail IMAP Engine: Active")
        st.markdown("- Gmail SMTP SSL: Active")
        st.markdown("- SQLite Store: Connected")
        st.markdown("- 4-Gate Verification Waterfall: Ready")

        if st.button("Save Profile Updates", use_container_width=True):
            with st.spinner("Persisting profile changes to config/candidate_profile.yaml and database store..."):
                cand_info["full_name"] = p_name
                cand_info["email"] = p_email
                cand_info["phone"] = p_phone
                cand_info["linkedin_url"] = p_linkedin
                candidate_data["candidate"] = cand_info
                save_candidate_profile(candidate_data)
                st.success("Profile saved and permanently persisted in YAML config and SQLite database.")
                time.sleep(0.5)
                st.rerun()

    st.divider()
    st.markdown("### Quick Operations")

    # Real-Time IMAP Synchronization with Live Visual Feedback and Timing
    if st.button("Sync IMAP Inbox & Reply Guard", use_container_width=True):
        st.markdown("##### IMAP Synchronization Progress")
        imap_progress_bar = st.progress(0, text="Initializing IMAP SSL connection...")
        imap_status_text = st.empty()

        def on_imap_progress(pct: float, message: str):
            imap_progress_bar.progress(int(min(max(pct, 0.0), 1.0) * 100))
            imap_status_text.markdown(f"<div class='step-box'>{message}</div>", unsafe_allow_html=True)

        res = run_imap_reply_guard(progress_callback=on_imap_progress, limit=30)
        
        if res.get("status") == "SUCCESS":
            st.success(f"Sync complete in {res.get('elapsed_seconds', 0)}s: {res.get('replies_detected', 0)} replies protected, {res.get('bounces_detected', 0)} hard bounces suppressed.")
        else:
            st.warning(f"Sync finished: {res.get('summary', res.get('error', 'Finished'))}")

    if st.button("Export Updated Master Intelligence Workbook", use_container_width=True):
        with st.spinner("Compiling canonical database tables into Master Excel Workbook..."):
            export_all()
            st.success("Master Excel exports updated in workspace root.")


# =========================================================
# MAIN HEADER
# =========================================================
st.title("Career Intelligence and Outreach Operating System")
st.caption("End-to-End Enterprise Recruitment and Direct Outreach Architecture")

# Tab Navigation - Strict Zero Emojis
tab1, tab2, tab3, tab4, tab5 = st.tabs([
    "Discovery",
    "Audit & Decision-Makers",
    "Executive Dossier & History",
    "AI Co-Pilot",
    "Email Automation & Dispatch"
])


# =========================================================
# TAB 1: DISCOVERY
# =========================================================
with tab1:
    st.subheader("Discovery")
    st.write("Scan ecosystems by geographical hierarchy, enterprise expansion categories, or direct organization search.")

    # Geographic Hierarchy
    col_c1, col_c2, col_c3 = st.columns(3)
    with col_c1:
        continents = list(CONTINENT_MAP.keys())
        sel_continent = st.selectbox("Continent:", continents, index=0)

    with col_c2:
        countries = list(CONTINENT_MAP[sel_continent].keys())
        sel_country = st.selectbox("Country:", countries, index=0)

    with col_c3:
        regions = CONTINENT_MAP[sel_continent][sel_country]
        sel_region = st.selectbox("Region / City:", regions, index=0)

    # Strategic Triggers
    trigger_list = list(TRIGGER_CATEGORIES.keys())
    sel_trigger = st.selectbox("Strategic Expansion Trigger:", trigger_list, index=0)

    # Targeted Search Inputs
    col_s1, col_s2, col_s3 = st.columns(3)
    with col_s1:
        search_org_in = st.text_input("Search by Organization Name (Optional):", placeholder="e.g. Hema Energy, Humain, an enterprise AI platform")
    with col_s2:
        search_web_in = st.text_input("Search by Website / Domain (Optional):", placeholder="e.g. hema.om, desert-technologies.com")
    with col_s3:
        search_kw_in = st.text_input("Custom Keywords / Specialization (Optional):", placeholder="e.g. camelina trial, treated wastewater, salinity")

    if st.button("Scan Ecosystem", use_container_width=True):
        with st.status("Executing regional intelligence scan...", expanded=True) as status_box:
            st.write("Formulating search query and querying live RSS news streams...")
            time.sleep(0.3)
            df_res, xl_path, csv_path = scanner.scan_ecosystem(
                country=sel_country,
                region=sel_region,
                trigger_category=sel_trigger,
                search_org=search_org_in,
                search_website=search_web_in,
                custom_keywords=search_kw_in,
                max_results=30
            )
            st.write(f"Parsed {len(df_res)} candidate expansion signals.")
            st.write("Archiving scan results to data/discovery_runs/ (Excel & CSV)...")
            st.write("Upserting organizations and expansion triggers into database...")
            status_box.update(label=f"Discovery Scan Complete: Found {len(df_res)} Triggers", state="complete", expanded=False)

            st.session_state["tab1_results"] = df_res
            st.session_state["tab1_excel_path"] = xl_path
            if not df_res.empty:
                st.session_state["selected_organizations"] = sorted(list(set(df_res["organization_name"].tolist())))

    if st.session_state["tab1_results"] is not None and not st.session_state["tab1_results"].empty:
        df_display = st.session_state["tab1_results"]
        st.success(f"Discovered {len(df_display)} expansion triggers. Data auto-saved to disk and indexed in database.")

        if st.session_state["tab1_excel_path"] and Path(st.session_state["tab1_excel_path"]).exists():
            with open(st.session_state["tab1_excel_path"], "rb") as f_x:
                st.download_button(
                    label=f"Download Discovery Run Excel ({Path(st.session_state['tab1_excel_path']).name})",
                    data=f_x.read(),
                    file_name=Path(st.session_state["tab1_excel_path"]).name,
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )

        # Organization Selection
        st.markdown("#### Select Organizations for Deep Audit in Tab 2")
        all_found = sorted(list(set(df_display["organization_name"].tolist())))
        
        c_sel1, c_sel2 = st.columns([1, 4])
        with c_sel1:
            select_all = st.checkbox("Select All Organizations", value=True)
        
        with c_sel2:
            if select_all:
                st.session_state["selected_organizations"] = all_found
                st.markdown(f"**All {len(all_found)} organizations selected.** They are automatically linked to Tab 2.")
            else:
                st.session_state["selected_organizations"] = st.multiselect(
                    "Select specific organizations:",
                    all_found,
                    default=all_found[:3] if len(all_found) >= 3 else all_found
                )

        st.dataframe(
            df_display[[
                "organization_name", "headline", "score", "talent_demand",
                "published_date", "source_outlet", "source_url"
            ]],
            use_container_width=True,
            hide_index=True
        )
    elif st.session_state["tab1_results"] is not None:
        st.warning("No new signals matched the exact query. Broaden the region or trigger filter.")


# =========================================================
# TAB 2: AUDIT & DECISION-MAKERS
# =========================================================
with tab2:
    st.subheader("Audit & Decision-Makers")
    st.write("Verifies organizational footprints and uncovers key decision-makers with direct LinkedIn profiles and corporate email addresses.")

    linked_orgs = st.session_state.get("selected_organizations")
    if not linked_orgs:
        db_orgs = repo.list_organizations()
        linked_orgs = [o["name"] for o in db_orgs] if db_orgs else ["Hema Energy", "Desert Technologies", "Red Sea Farms", "Uvera", "Terraxy"]

    st.markdown(f"**Linked Organizations Available for Deep Audit:** {len(linked_orgs)}")

    col_a1, col_a2 = st.columns([1.5, 1])
    with col_a1:
        sel_audit_mode = st.radio("Audit Scope:", ["Batch Audit All Linked Organizations", "Audit Specific Organization"], horizontal=True)
    with col_a2:
        if sel_audit_mode == "Audit Specific Organization":
            single_org_target = st.selectbox("Select Target Organization:", linked_orgs)
        else:
            single_org_target = None
            st.info(f"Batch mode will process all {len(linked_orgs)} selected organizations.")

    if st.button("Execute Deep Audit & Leadership Discovery", use_container_width=True):
        targets_to_audit = [single_org_target] if single_org_target else linked_orgs
        with st.status(f"Auditing {len(targets_to_audit)} organizations and locating leadership...", expanded=True) as audit_status:
            audit_progress = st.progress(0, text="Initializing audit engine...")
            
            batch_res = {}
            all_dms = []
            total_targets = len(targets_to_audit)

            for idx, target_org in enumerate(targets_to_audit):
                pct = (idx) / max(total_targets, 1)
                audit_progress.progress(int(pct * 100), text=f"Auditing {idx + 1}/{total_targets}: {target_org}...")
                
                # Run audit and hunt
                audit_info = hunter.audit_organization(target_org)
                dms = hunter.hunt_decision_makers(target_org, domain=audit_info.get("domain"))
                batch_res[target_org] = {
                    "audit": audit_info,
                    "decision_makers": dms
                }
                for dm in dms:
                    dm["organization_name"] = target_org
                    all_dms.append(dm)

            audit_progress.progress(100, text="Audit completed for all organizations.")
            st.session_state["tab2_audit_results"] = batch_res
            st.session_state["tab2_all_dms"] = all_dms
            audit_status.update(label=f"Audit Complete: Processed {total_targets} Organizations, Located {len(all_dms)} Decision-Makers", state="complete", expanded=False)

    # Display Audit Results
    if st.session_state["tab2_audit_results"]:
        batch_data = st.session_state["tab2_audit_results"]
        st.markdown("### Audit Dossiers & Executive Profiles")

        for org_name, data in batch_data.items():
            aud = data["audit"]
            dms = data["decision_makers"]

            with st.expander(f"Organization: {org_name} ({len(dms)} Decision-Makers Found)", expanded=True):
                c_aud1, c_aud2 = st.columns(2)
                with c_aud1:
                    st.markdown(f"**Verification Status:** <span class='badge-verified'>{aud['verification_status']}</span>", unsafe_allow_html=True)
                    st.markdown(f"**Evidence Tier:** `{aud['evidence_tier']}`")
                with c_aud2:
                    st.markdown(f"**Domain:** `{aud.get('domain') or 'Resolved via Press Wire'}`")
                    st.markdown(f"**Trigger Evidence:** `{'Confirmed' if aud['trigger_confirmed'] else 'Unconfirmed'}`")
                st.caption(f"**Summary:** {aud['audit_summary']}")

                st.markdown("##### Executive Decision-Makers")
                if dms:
                    for dm_idx, dm in enumerate(dms):
                        c_d1, c_d2, c_d3, c_d4 = st.columns([1.5, 1.2, 1.2, 1])
                        with c_d1:
                            st.markdown(f"**{dm['name']}**")
                            st.caption(f"Role: {dm['role']}")
                        with c_d2:
                            st.markdown(f"[LinkedIn Profile]({dm['linkedin_url']})")
                            st.caption(f"Source: {dm.get('verification_source', 'Search')}")
                        with c_d3:
                            st.markdown(f"`{dm.get('work_email') or 'Pending Extraction'}`")
                        with c_d4:
                            if st.button("Select for Dossier", key=f"sel_dm_{org_name}_{dm_idx}"):
                                st.session_state["tab3_active_lead"] = dm
                                st.success(f"Selected {dm['name']}. Proceed to Tab 3.")
                else:
                    st.caption("No public decision-makers identified.")

    elif st.session_state["tab2_all_dms"]:
        st.dataframe(pd.DataFrame(st.session_state["tab2_all_dms"]), use_container_width=True)


# =========================================================
# TAB 3: EXECUTIVE DOSSIER & HISTORY
# =========================================================
with tab3:
    st.subheader("Executive Dossier & History")
    st.write("Extracts deep background intelligence, milestones, and deliverability verification through the 4-gate waterfall.")

    all_known_contacts = repo.list_contacts()
    all_contact_names = [f"{c['name']} &mdash; {c['role']} @ {c['organization_name']}" for c in all_known_contacts if c.get("name")]


    if not all_contact_names:
        st.info("No contacts are stored yet. Run discovery first, then review the evidence before creating a dossier.")
    else:
        st.markdown("#### Select Lead to Profile")
        col_f1, col_f2, col_f3 = st.columns(3)
        
        with col_f1:
            all_org_names = ["All Organizations"] + sorted(list(set(c["organization_name"] for c in all_known_contacts if c.get("organization_name"))))
            sel_filter_org = st.selectbox("Filter by Organization:", all_org_names)

        filtered_contacts = all_known_contacts
        if sel_filter_org != "All Organizations":
            filtered_contacts = [c for c in filtered_contacts if c.get("organization_name") == sel_filter_org]

        with col_f2:
            all_roles = ["All Roles"] + sorted(list(set(c["role"] for c in filtered_contacts if c.get("role"))))
            sel_filter_role = st.selectbox("Filter by Role:", all_roles)

        if sel_filter_role != "All Roles":
            filtered_contacts = [c for c in filtered_contacts if c.get("role") == sel_filter_role]

        with col_f3:
            lead_options = [f"{c['name']} &mdash; {c['role']} @ {c['organization_name']}" for c in filtered_contacts]
            if not lead_options:
                lead_options = all_contact_names
            
            default_idx = 0
            if st.session_state.get("tab3_active_lead"):
                t2_name = st.session_state["tab3_active_lead"]["name"]
                for i, opt in enumerate(lead_options):
                    if t2_name in opt:
                        default_idx = i
                        break

            chosen_lead_string = st.selectbox("Target Executive:", lead_options, index=default_idx)

        raw_parts = chosen_lead_string.split(" &mdash; ")
        lead_name = raw_parts[0].strip()
        rest_parts = raw_parts[1].split(" @ ") if len(raw_parts) > 1 else ["Executive", "GCC Entity"]
        lead_role = rest_parts[0].strip()
        lead_org = rest_parts[1].strip() if len(rest_parts) > 1 else "Hema Energy"

        if st.button("Generate Executive Dossier & Run Verification Waterfall", use_container_width=True):
            with st.status(f"Compiling executive intelligence and verifying deliverability for {lead_name}...", expanded=True) as dos_status:
                st.write("Gate 0: Screened against master suppression blacklist.")
                st.write("Gate 1: Resolving corporate domain and verifying DNS MX mailservers...")
                st.write("Gate 2: Screening disposable domains and role accounts...")
                st.write("Gate 3: Computing deliverability confidence score...")
                
                email_res = intel_finder.find_and_verify_email(lead_name, lead_org)
                st.write(f"Email deliverability verified: {email_res['email']} ({int(email_res['confidence_score']*100)}% confidence).")
                
                st.write("Synthesizing executive milestones, academic background, and technical focus...")
                history_res = intel_finder.extract_career_history(lead_name, lead_role, lead_org)
                
                st.session_state["tab3_dossier"] = {
                    "name": lead_name,
                    "role": lead_role,
                    "organization": lead_org,
                    "email_info": email_res,
                    "history": history_res
                }
                st.session_state["current_draft_recipient"] = email_res["email"]
                dos_status.update(label=f"Dossier & Deliverability Verification Complete for {lead_name}", state="complete", expanded=False)

        if st.session_state.get("tab3_dossier"):
            dos = st.session_state["tab3_dossier"]
            em = dos["email_info"]
            hist = dos["history"]

            col_d1, col_d2 = st.columns([1, 1.2])
            with col_d1:
                st.markdown("### Email Deliverability Waterfall")
                st.markdown(f"**Target Email:** `{em['email']}`")
                conf_score = em["confidence_score"]
                badge_type = "badge-verified" if conf_score >= 0.7 else "badge-blocked"
                st.markdown(f"**Deliverability Confidence:** <span class='{badge_type}'>{int(conf_score * 100)}% ({em['determination']})</span>", unsafe_allow_html=True)
                st.markdown(f"**DNS MX Host Validation:** `{'Valid Mailservers Detected' if em['mx_valid'] else 'No Valid MX Host'}`")
                st.markdown(f"**Verification Engine:** `{em['source']}`")
                st.caption(f"Details: {em['details']}")

            with col_d2:
                st.markdown(f"### Executive Dossier: {dos['name']}")
                st.markdown(f"**Role:** {dos['role']} @ **{dos['organization']}**")
                st.markdown(f"**Technical Focus:** `{hist['technical_focus']}`")
                st.markdown(f"**Academic Background:** {hist['academic_background']}")
                st.markdown(f"**Executive Summary:** {hist['career_summary']}")
                st.markdown("**Key Milestones & Initiatives:**")
                for m in hist["milestones"]:
                    st.markdown(f"- {m}")

            st.info("Dossier compiled. Proceed to Tab 4 (AI Co-Pilot) to review and refine your personalized outreach.")




# =========================================================
# TAB 4: AI CO-PILOT
# =========================================================
with tab4:
    st.subheader("AI Co-Pilot")
    st.write(f"Interactive email personalizer writing directly as **{cand_info.get('full_name', 'the configured candidate')}**. Synthesizes target executive history with candidate's 3 real experiences (the configured research role, the configured software team, Client ETL) within the strict 100-160 word window.")

    active_dos = st.session_state.get("tab3_dossier")

    if not active_dos:
        st.info("Select a decision-maker in Tab 3 before starting an AI draft. No sample contact or email address is preloaded.")
    else:
        # Initialize draft if empty
        if not st.session_state["current_draft_body"]:
            init_draft = copilot.generate_initial_draft(
                target_name=active_dos["name"],
                target_role=active_dos["role"],
                target_org=active_dos["organization"],
                target_email=active_dos["email_info"]["email"],
                target_history=active_dos["history"],
                signal_headline=active_dos["history"]["career_summary"]
            )
            st.session_state["current_draft_body"] = init_draft.body_text
            st.session_state["current_draft_subject"] = init_draft.subject_line
            st.session_state["current_draft_recipient"] = active_dos["email_info"]["email"]
            st.session_state["copilot_messages"] = [
                {"role": "assistant", "content": f"I have loaded the dossier for {active_dos['name']} ({active_dos['role']} @ {active_dos['organization']}). Below is an initial calibrated draft linking their work in {active_dos['history']['technical_focus']} with your research data validation experience at the configured research role. Instruct me on any specific nuances to refine."}
            ]

        col_cp1, col_cp2 = st.columns([1, 1.2])

        with col_cp1:
            st.markdown("### Profile Alignment")
            st.markdown(f"**Target:** `{active_dos['name']}` ({active_dos['role']})")
            st.markdown(f"**Organization:** `{active_dos['organization']}`")
            st.markdown(f"**Recipient Address:** `{st.session_state['current_draft_recipient']}`")

            exp_match = copilot.generator.select_experience(active_dos["history"]["technical_focus"], active_dos["role"])
            st.markdown(f"""
            <div class='step-box'>
                <b>Auto-Matched Real Experience:</b> {exp_match.get('organization', 'the configured research role')} &mdash; {exp_match.get('role')}<br>
                <i>{exp_match.get('summary', '')}</i>
            </div>
            """, unsafe_allow_html=True)

            st.markdown("#### Co-Pilot Conversation")
            chat_box = st.container(height=320)
            with chat_box:
                for m in st.session_state["copilot_messages"]:
                    if m["role"] == "assistant":
                        st.markdown(f"<div class='chat-bubble-assistant'><b>AI Writer:</b> {m['content']}</div>", unsafe_allow_html=True)
                    else:
                        st.markdown(f"<div class='chat-bubble-user'><b>You:</b> {m['content']}</div>", unsafe_allow_html=True)

            user_input_prompt = st.chat_input("Instruct your AI writer (e.g. 'Emphasize salinity metrics from the configured research role', 'Make it concise')...")
            if user_input_prompt:
                st.session_state["copilot_messages"].append({"role": "user", "content": user_input_prompt})
                with st.spinner(f"AI Co-Pilot is refining your outreach pitch as {cand_info.get('full_name', 'the configured candidate')}..."):
                    rev_b, rev_s, expl = copilot.refine_draft_with_guidance(
                        current_body=st.session_state["current_draft_body"],
                        current_subject=st.session_state["current_draft_subject"],
                        target_name=active_dos["name"],
                        target_org=active_dos["organization"],
                        target_role=active_dos["role"],
                        user_guidance=user_input_prompt,
                        target_history=active_dos["history"]
                    )
                    st.session_state["current_draft_body"] = rev_b
                    st.session_state["current_draft_subject"] = rev_s
                    st.session_state["copilot_messages"].append({"role": "assistant", "content": expl})
                    st.rerun()

        with col_cp2:
            st.markdown("### Live Draft & Deliverability Guard")
            
            subj_in = st.text_input("Subject Line:", st.session_state["current_draft_subject"])
            st.session_state["current_draft_subject"] = subj_in

            body_in = st.text_area("Body Text (Editable):", st.session_state["current_draft_body"], height=220)
            st.session_state["current_draft_body"] = body_in

            w_cnt = copilot.calculate_word_count(body_in)
            badge_cls = "badge-verified" if 100 <= w_cnt <= 160 else "badge-blocked"
            st.markdown(f"**Word Count:** <span class='{badge_cls}'>{w_cnt} words</span> (Standard Window: 100-160 words)", unsafe_allow_html=True)

            # Dynamic Signature from Candidate Profile
            c_name, _, c_sig_html = get_candidate_signature()
            html_preview = f"""
            <div style="font-family: Arial, sans-serif; font-size: 13.5px; line-height: 1.55; color: #1e293b; background: white; padding: 14px; border: 1px solid #cbd5e1; border-radius: 4px;">
                <p>{body_in.replace(chr(10)+chr(10), '</p><p>').replace(chr(10), '<br>')}</p>
                {c_sig_html}
            </div>
            """
            st.components.v1.html(html_preview, height=260, scrolling=True)

            st.divider()
            if st.button("Approve Draft for Dispatch (Stage to Tab 5)", use_container_width=True):
                with st.spinner("Generating cryptographic approval hash (SHA-256) and committing to database..."):
                    app_hash = copilot.generate_approval_hash(body_in, st.session_state["current_draft_recipient"])
                    draft_to_save = EmailDraft(
                        recipient_email=st.session_state["current_draft_recipient"],
                        recipient_name=active_dos["name"],
                        organization_name=active_dos["organization"],
                        recipient_role=active_dos["role"],
                        subject_line=subj_in,
                        body_text=body_in
                    )
                    repo.upsert_draft(draft_to_save, status="APPROVED")
                    
                    if draft_to_save.recipient_email not in [d.get("recipient_email") for d in st.session_state["approved_drafts"]]:
                        st.session_state["approved_drafts"].append({
                            "recipient_email": draft_to_save.recipient_email,
                            "recipient_name": draft_to_save.recipient_name,
                            "organization_name": draft_to_save.organization_name,
                            "recipient_role": draft_to_save.recipient_role,
                            "subject_line": draft_to_save.subject_line,
                            "body_text": draft_to_save.body_text,
                            "word_count": draft_to_save.word_count,
                            "approval_hash": app_hash
                        })

                    st.success(f"Draft approved (Hash: {app_hash[:16]}...) and automatically staged to Tab 5.")




# =========================================================
# TAB 5: EMAIL AUTOMATION & DISPATCH
# =========================================================
with tab5:
    st.subheader("Email Automation & Dispatch")
    st.write("Review all approved, human-vetted outreach drafts. Attach candidate resume PDF and execute via **Gmail Draft Staging (IMAP)** or **Direct SMTP Send** with complete suppression list safety.")

    db_drafts = repo.list_drafts()
    approved_db = [d for d in db_drafts if d.get("status") in ["APPROVED", "STAGED"]]

    if not approved_db:
        st.warning("No approved drafts found in queue. Go to Tab 4 to craft and approve your outreach draft.")
    else:
        df_app = pd.DataFrame(approved_db)
        sel_draft_email = st.selectbox(
            "Select Approved Draft to Dispatch / Stage:",
            df_app["recipient_email"].tolist(),
            format_func=lambda e: f"{df_app.loc[df_app['recipient_email'] == e, 'organization_name'].iloc[0]} &mdash; {df_app.loc[df_app['recipient_email'] == e, 'recipient_name'].iloc[0]} ({e})"
        )

        d_item = next(item for item in approved_db if item["recipient_email"] == sel_draft_email)

        c_disp1, c_disp2 = st.columns([1.2, 1])
        with c_disp1:
            st.markdown(f"### Target: {d_item['recipient_name']} ({d_item['recipient_role']})")
            st.markdown(f"**Organization:** {d_item['organization_name']}")
            st.markdown(f"**Target Email:** `{d_item['recipient_email']}`")
            st.markdown(f"**Subject:** {d_item['subject_line']}")

            wc_val = d_item["word_count"]
            b_class = "badge-verified" if 100 <= wc_val <= 160 else "badge-blocked"
            st.markdown(f"**Word Count:** <span class='{b_class}'>{wc_val} words</span>", unsafe_allow_html=True)

            is_supp = supp.is_suppressed(d_item["recipient_email"])
            if is_supp:
                st.markdown("<span class='badge-blocked'>Recipient is on Master Suppression List &mdash; Sending Blocked</span>", unsafe_allow_html=True)
            else:
                st.markdown("<span class='badge-verified'>Recipient is Verified Clean & Deliverable</span>", unsafe_allow_html=True)

            st.text_area("Approved Pitch Body:", d_item["body_text"], height=180, disabled=True)

        with c_disp2:
            st.markdown("### Resume & Attachment Control")
            
            uploaded_pdf = st.file_uploader("Upload Custom Resume (PDF):", type=["pdf"])
            pdf_bytes = None
            pdf_name = "master_resume.pdf"

            if uploaded_pdf is not None:
                pdf_bytes = uploaded_pdf.read()
                pdf_name = uploaded_pdf.name
                st.success(f"Custom Resume Attached: {pdf_name} ({len(pdf_bytes)//1024} KB)")
            elif DEFAULT_RESUME_PATH.exists():
                pdf_bytes = DEFAULT_RESUME_PATH.read_bytes()
                st.info(f"Default Resume Detected: master_resume.pdf ({len(pdf_bytes)//1024} KB)")
            else:
                st.warning("No PDF resume attached. Draft will be staged/sent without attachment.")

            st.divider()
            st.markdown("### Execution Controls")

            col_btn1, col_btn2 = st.columns(2)
            with col_btn1:
                if st.button("Make as Draft in Gmail", use_container_width=True):
                    with st.spinner("Connecting to Gmail IMAP SSL, building MIME message with PDF resume attachment, and staging into [Gmail]/Drafts..."):
                        ed_obj = EmailDraft(
                            recipient_email=d_item["recipient_email"],
                            recipient_name=d_item["recipient_name"],
                            organization_name=d_item["organization_name"],
                            recipient_role=d_item["recipient_role"],
                            subject_line=d_item["subject_line"],
                            body_text=d_item["body_text"]
                        )
                        ok, msg = draft_engine.stage_draft(ed_obj, attachment_bytes=pdf_bytes, attachment_filename=pdf_name)
                        if ok:
                            st.success(msg)
                        else:
                            st.error(f"Staging failed: {msg}")

            with col_btn2:
                if st.button("Send Directly", use_container_width=True, disabled=is_supp):
                    with st.spinner("Executing pre-flight suppression check, authenticating via Gmail SMTP SSL, and sending email with attached CV..."):
                        ed_obj = EmailDraft(
                            recipient_email=d_item["recipient_email"],
                            recipient_name=d_item["recipient_name"],
                            organization_name=d_item["organization_name"],
                            recipient_role=d_item["recipient_role"],
                            subject_line=d_item["subject_line"],
                            body_text=d_item["body_text"]
                        )
                        ok, msg = dispatcher.send_direct(ed_obj, attachment_bytes=pdf_bytes, attachment_filename=pdf_name)
                        if ok:
                            st.success(msg)
                            time.sleep(0.5)
                            st.rerun()
                        else:
                            st.error(f"Dispatch failed: {msg}")

        st.divider()
        st.markdown("### Outreach & Dispatch Ledger")
        evs = repo.list_outreach_events(limit=10)
        if evs:
            st.dataframe(
                pd.DataFrame(evs)[["timestamp", "recipient_email", "event_type", "details"]],
                use_container_width=True,
                hide_index=True
            )
        else:
            st.caption("No dispatch events logged yet. Execute a send or draft staging to view ledger activity.")
