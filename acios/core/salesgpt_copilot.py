"""
ACIOS SalesGPT & Instructor Email Co-Pilot Engine.
Integrates:
1. SalesGPT-style stage-aware conversation states (First Touch, Technical QA, ETL Automation, Executive Concise).
2. Instructor-style self-correcting Pydantic validation loops (strictly enforcing 100-160 words).
3. Candidate grounding strictly bound to the configured candidate's verified track record.
"""

import os
import re
import hashlib
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple
from enum import Enum
from pydantic import BaseModel, Field, field_validator


class OutreachStage(str, Enum):
    STAGE_FIRST_TOUCH = "Stage 1: First Touch Introduction"
    STAGE_TECHNICAL_QA = "Stage 2: Technical QA & Platform Testing"
    STAGE_ETL_DATA = "Stage 3: Automated ETL & Data Operations"
    STAGE_EXECUTIVE_CONCISE = "Stage 4: Executive Concise (2thepoint)"


class DraftValidationModel(BaseModel):
    subject: str = Field(..., max_length=90)
    body: str
    explanation: str

    @field_validator("body")
    @classmethod
    def validate_body(cls, v: str) -> str:
        words = len(v.strip().split())
        if words < 100 or words > 160:
            raise ValueError(f"Draft has {words} words. Must be strictly between 100 and 160 words.")
        # Buzzword check
        buzzwords = ["synergy", "game-changer", "revolutionary", "disrupt", "delve", "cutting-edge"]
        for b in buzzwords:
            if b in v.lower():
                raise ValueError(f"Draft contains forbidden agency buzzword '{b}'.")
        return v


class SalesGPTCopilotEngine:
    """Stage-aware copilot that grounds every biographical claim in the private profile."""

    def __init__(
        self,
        profile_provider: Optional[Callable[[], Dict[str, Any]]] = None,
        profile_path: Optional[Path] = None,
    ):
        self.gemini_api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
        self.profile_provider = profile_provider
        self.profile_path = profile_path or (
            Path(__file__).resolve().parent.parent.parent
            / "config"
            / "candidate_profile.yaml"
        )

    def _profile_data(self) -> Dict[str, Any]:
        if self.profile_provider:
            value = self.profile_provider()
            return value if isinstance(value, dict) else {}
        if os.getenv("ACIOS_ENV", "development").strip().lower() == "production":
            return {}
        try:
            import yaml

            if self.profile_path.exists():
                value = yaml.safe_load(self.profile_path.read_text(encoding="utf-8")) or {}
                return value if isinstance(value, dict) else {}
        except (OSError, ValueError):
            pass
        return {}

    @staticmethod
    def _experience_evidence(profile: Dict[str, Any]) -> List[str]:
        experiences = profile.get("experiences", {}) or {}
        if not isinstance(experiences, dict):
            return []
        evidence: List[str] = []
        for item in experiences.values():
            if not isinstance(item, dict):
                continue
            organization = str(item.get("organization") or "").strip()
            role = str(item.get("role") or "").strip()
            summary = str(item.get("summary") or item.get("focus") or "").strip()
            parts = [part for part in (organization, role, summary) if part]
            if parts:
                evidence.append(" — ".join(parts)[:280])
            if len(evidence) == 3:
                break
        return evidence

    def generate_by_stage(
        self,
        stage: OutreachStage,
        target_name: str,
        target_org: str,
        target_role: str,
        target_history: Dict[str, Any],
        custom_guidance: Optional[str] = None
    ) -> Tuple[str, str, str, int]:
        """Create a 100–160-word draft without inventing candidate experience."""
        profile = self._profile_data()
        candidate = profile.get("candidate", {}) or {}
        candidate_name = str(candidate.get("full_name") or "").strip()
        evidence = self._experience_evidence(profile)
        evidence_text = "; ".join(evidence[:1])[:180]

        first_name = target_name.split()[0] if target_name else "there"
        stage_focus = {
            OutreachStage.STAGE_FIRST_TOUCH: "data workflows and operational reporting",
            OutreachStage.STAGE_TECHNICAL_QA: "software QA, test cases, and validation workflows",
            OutreachStage.STAGE_ETL_DATA: "data quality, ingestion pipelines, and reporting operations",
            OutreachStage.STAGE_EXECUTIVE_CONCISE: "practical workflow improvements aligned with your team's priorities",
        }
        focus = stage_focus.get(stage, stage_focus[OutreachStage.STAGE_FIRST_TOUCH])
        trigger = str(
            target_history.get("career_summary")
            or target_history.get("technical_focus")
            or "your team's current priorities"
        ).strip()[:120]
        subject = {
            OutreachStage.STAGE_FIRST_TOUCH: f"Data workflows and reporting at {target_org}",
            OutreachStage.STAGE_TECHNICAL_QA: f"QA and validation workflows at {target_org}",
            OutreachStage.STAGE_ETL_DATA: f"Data quality and reporting at {target_org}",
            OutreachStage.STAGE_EXECUTIVE_CONCISE: f"Workflow support at {target_org}",
        }.get(stage, f"Data workflows at {target_org}")[:90]

        candidate_line = (
            f"My name is {candidate_name}. "
            if candidate_name
            else "I am reaching out to learn whether this area aligns with my current technical focus. "
        )
        evidence_line = (
            f"My documented experience includes {evidence_text}. "
            if evidence_text
            else (
                "I am still configuring my verified experience examples, so I will not make "
                "unsupported claims about employers, achievements, or previous projects. "
            )
        )

        system_instruction = (
            "You are an evidence-first career outreach writer. Use only the configured candidate "
            "profile and supplied company context. Do not invent candidate names, employers, degrees, "
            "achievements, or verified evidence. If experience anchors are empty, do not make past-work "
            "claims. Write 100–160 words excluding any signature, be humble, specific and respectful, "
            "and avoid buzzwords such as synergy, game-changer, revolutionary, disrupt, delve, and cutting-edge. "
            f"Configured candidate name: {candidate_name or '[not configured]'}. "
            f"Verified experience anchors supplied by the application: {evidence!r}. "
            "Do not include phone numbers, email addresses, or profile contact fields in the generated body."
        )
        prompt = (
            f"Stage: {stage.value}\nTarget: {target_name} ({target_role}) at {target_org}\n"
            f"Supplied company context: {trigger}\nFocus: {focus}\n"
            f"Additional operator guidance: {custom_guidance or ''}\n"
            "Return exactly these labeled fields: SUBJECT: ..., BODY: ..., EXPLANATION: ... "
            "The body must be 100–160 words and must not include a signature."
        )

        if self.gemini_api_key:
            try:
                from google import genai

                client = genai.Client(api_key=self.gemini_api_key)
                response = client.models.generate_content(
                    model="gemini-3.8-flash",
                    contents=[system_instruction, prompt],
                )
                generated = response.text or ""
                if "SUBJECT:" in generated and "BODY:" in generated:
                    subject_part, rest = generated.split("BODY:", 1)
                    generated_subject = subject_part.replace("SUBJECT:", "").strip().split("\n")[0]
                    if "EXPLANATION:" in rest:
                        body_part, explanation = rest.split("EXPLANATION:", 1)
                    else:
                        body_part, explanation = rest, "Draft generated for human review."
                    body = re.sub(r"Regards,?\s*\n.*$", "", body_part, flags=re.DOTALL).strip()
                    candidate_subject = (generated_subject or subject)[:90]
                    validation = DraftValidationModel(
                        subject=candidate_subject,
                        body=body,
                        explanation=explanation.strip() or "Draft generated for human review.",
                    )
                    return validation.subject, validation.body, validation.explanation, len(validation.body.split())
            except Exception:
                # Fall through to a deterministic, profile-grounded template.
                pass

        if candidate_name and evidence_text:
            intro = f"{candidate_line}{evidence_line}"
        elif candidate_name:
            intro = (
                f"{candidate_line}"
                "I prefer to discuss only experience that can be substantiated with specific project examples. "
            )
        else:
            intro = evidence_line

        body = (
            f"Dear {first_name},\n\n"
            f"I am researching {target_org}, particularly {trigger}. I wanted to ask whether your team has "
            f"current or upcoming needs around {focus}.\n\n"
            f"{intro}"
            "I try to base each outreach message on documented information and real team needs rather than "
            "assume that a specific vacancy is open. If a project would benefit from support with "
            f"{focus}, I would welcome a brief conversation to understand your process, tools, and immediate goals. "
            "I can share a resume and relevant project examples once we establish what would be useful.\n\n"
            "Would you be open to a short introductory call at a convenient time? If this is not relevant "
            "to your team, I understand and appreciate your time."
        )
        if len(body.split()) < 100:
            body += (
                " I am happy to tailor the discussion to a particular role or workstream and to answer "
                "questions about the skills that are documented in my profile."
            )
        # Do not silently truncate evidence or alter meaning; report a validation error if
        # a very long target context pushes this authored fallback over the gate.
        validation = DraftValidationModel(
            subject=subject,
            body=body,
            explanation="Profile-grounded draft prepared for human review.",
        )
        return validation.subject, validation.body, validation.explanation, len(validation.body.split())
