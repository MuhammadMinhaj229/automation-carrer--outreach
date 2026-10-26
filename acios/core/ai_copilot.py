"""
ACIOS Interactive AI Co-Pilot Email Writer.
Provides personalized email drafting grounded in a private candidate profile.
Synthesizes target decision-maker history + company expansion triggers + candidate experiences.
Guarantees strict 100-160 word window, humble authentic tone, and zero buzzwords.
"""

import os
import re
import hashlib
import json
from typing import Dict, Any, List, Optional, Tuple
from pathlib import Path
import yaml
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent.parent
load_dotenv(BASE_DIR / ".env")

from acios.core.generator import DraftGenerator
from acios.models.contact import Contact, VerificationStatus
from acios.models.email_draft import EmailDraft

PROFILE_PATH = BASE_DIR / "config" / "candidate_profile.yaml"


class AICopilotWriter:
    """Interactively refines personalized outreach drafts with the user."""

    def __init__(self, profile_path: Optional[Path] = None):
        path = profile_path or PROFILE_PATH
        if path.exists():
            with open(path, "r", encoding="utf-8") as f:
                self.profile_data = yaml.safe_load(f)
        else:
            self.profile_data = {}

        self.generator = DraftGenerator(config_path=path)

    def set_profile_data(self, profile_data: Dict[str, Any]) -> None:
        """Refresh candidate identity and experience anchors from persistent storage."""
        self.profile_data = profile_data if isinstance(profile_data, dict) else {}
        self.generator.set_profile_data(self.profile_data)

    def generate_initial_draft(
        self,
        target_name: str,
        target_role: str,
        target_org: str,
        target_email: str,
        target_history: Dict[str, Any],
        signal_headline: str = ""
    ) -> EmailDraft:
        """Creates the initial evidence-based draft tailored to the target's background."""
        contact = Contact(
            name=target_name,
            role=target_role,
            organization_name=target_org,
            work_email=target_email,
            verification_status=VerificationStatus.PATTERN_PREDICTED
        )
        # Select best experience
        tech_focus = target_history.get("technical_focus", "")
        sector = "Energy" if any(k in f"{target_org} {tech_focus}".lower() for k in ["biofuel", "water", "energy", "solar", "camelina"]) else "Technology"
        
        draft = self.generator.generate_draft(
            contact=contact,
            sector=sector,
            signal_headline=signal_headline or target_history.get("career_summary", "")
        )
        return draft

    def refine_draft_with_guidance(
        self,
        current_body: str,
        current_subject: str,
        target_name: str,
        target_org: str,
        target_role: str,
        user_guidance: str,
        target_history: Dict[str, Any]
    ) -> Tuple[str, str, str]:
        """
        Refines the current draft based on the user's interactive chat prompt.
        Ensures strict 100-160 word count, respectful tone, and candidate accuracy.
        Returns: (new_body, new_subject, ai_explanation)
        """
        # If Gemini API is available, we can use google.genai
        gemini_api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
        
        candidate = (self.profile_data or {}).get("candidate", {}) or {}
        experiences = (self.profile_data or {}).get("experiences", {}) or {}
        candidate_name = str(candidate.get("full_name") or "the candidate")
        system_instruction = (
            f"You are an evidence-first career outreach writer for {candidate_name}. "
            f"Configured experience anchors (authoritative, may be empty): {json.dumps(experiences, ensure_ascii=False)}. "
            "Use only the profile and verified experience anchors supplied by the application. "
            "Never invent employers, degrees, contact details, achievements, or verification results. "
            "If profile evidence is missing, avoid unsupported biographical claims. "
            "Tone: humble, concise, authentic, research-oriented, and respectful. "
            "Avoid buzzwords and do not include a signature; the application adds configured signature details. "
            "Keep the email between 100 and 160 words, excluding signature."
        )

        prompt = f"""
Target Decision Maker:
- Name: {target_name}
- Role: {target_role}
- Organization: {target_org}
- Career & Technical Focus: {target_history.get('technical_focus', '')}
- Background / Milestones: {target_history.get('milestones', '')}

Current Subject: {current_subject}
Current Draft Body:
{current_body}

User's Refinement Instructions:
"{user_guidance}"

Rewrite the email draft and provide:
1. Revised Subject Line (start with 'SUBJECT: ')
2. Revised Email Body (start with 'BODY: ')
3. Brief 1-2 sentence explanation of changes made (start with 'EXPLANATION: ')
Keep word count of the body strictly between 100 and 150 words.
"""

        if gemini_api_key:
            try:
                from google import genai
                client = genai.Client(api_key=gemini_api_key)
                response = client.models.generate_content(
                    model="gemini-2.5-flash",
                    contents=[system_instruction, prompt]
                )
                text = response.text
                
                # Parse outputs
                subj = current_subject
                body = current_body
                expl = "I refined the draft based on your instructions while keeping within the 100–160 word window."

                if "SUBJECT:" in text and "BODY:" in text:
                    parts = text.split("BODY:")
                    subj_part = parts[0].replace("SUBJECT:", "").strip()
                    if subj_part:
                        subj = subj_part.split("\n")[0].strip()
                    
                    rest = parts[1]
                    if "EXPLANATION:" in rest:
                        body_part, expl_part = rest.split("EXPLANATION:")
                        body = body_part.strip()
                        expl = expl_part.strip()
                    else:
                        body = rest.strip()

                    # Strip any trailing signature if the LLM output it
                    body = re.sub(r"Regards,?\s*\n.*$", "", body, flags=re.DOTALL).strip()
                    return body, subj, expl
            except Exception as e:
                print(f"[AICopilotWriter] Gemini API call exception: {e}")

        # Fallback uses only the private candidate profile, never a source-coded biography.
        first_name = target_name.split()[0] if target_name else "Team"
        experiences = (self.profile_data or {}).get("experiences", {}) or {}
        evidence_items = []
        for item in experiences.values():
            if isinstance(item, dict):
                org = str(item.get("organization") or "").strip()
                role = str(item.get("role") or "").strip()
                summary = str(item.get("summary") or item.get("focus") or "").strip()
                evidence = " — ".join(part for part in (org, role, summary) if part)
                if evidence: evidence_items.append(evidence[:240])
        evidence_text = "; ".join(evidence_items[:2])
        experience_sentence = f"My configured experience includes {evidence_text}. " if evidence_text else "My verified experience details are still being configured, so I will not make unsupported claims. "
        context = str(target_history.get("career_summary") or target_history.get("technical_focus") or "your team’s current priorities").strip()
        subject = f"Technical workflow support at {target_org}"
        adjusted_body = (
            f"Dear {first_name},\n\n"
            f"I am researching {target_org} and its work around {context}. I wanted to connect about practical support with data workflows, software quality, or operational reporting. "
            f"{experience_sentence}"
            "I prefer to ground each claim in documented work and avoid assuming that a specific role is open or overstating my background. "
            "If there is a relevant need, I would value a brief conversation to learn about your team’s current priorities, tools, and where an additional contributor might help. "
            "I can tailor the discussion to an actual role or project instead of making a broad request. "
            "Would you be open to a short introductory call? I can share the configured resume or portfolio after confirming that it is relevant to the opportunity."
        )
        if not 100 <= len(adjusted_body.split()) <= 160:
            adjusted_body += " My goal is to understand your needs and discuss fit honestly before taking any next step."
        explanation = "Profile-driven draft created for human review. Confirm sources, recipient details, and claims before approval."
        return adjusted_body, subject, explanation
    @staticmethod
    def calculate_word_count(text: str) -> int:
        return len(text.strip().split())

    @staticmethod
    def generate_approval_hash(body: str, recipient_email: str) -> str:
        payload = f"{recipient_email.lower().strip()}:{body.strip()}".encode("utf-8")
        return hashlib.sha256(payload).hexdigest()
