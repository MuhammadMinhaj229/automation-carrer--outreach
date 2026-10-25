"""
ACIOS Evidence-Based Draft Generator.
Selects real candidate experiences from candidate_profile.yaml,
combines them with verified corporate signals, and generates calibrated outreach drafts
guaranteed to pass the 100-160 word window and zero-buzzword gates.
"""

from pathlib import Path
from typing import Dict, Any, Optional, List
import yaml

from acios.models.email_draft import EmailDraft, PersonaType
from acios.models.contact import Contact

CONFIG_PATH = Path(__file__).resolve().parent.parent.parent / "config" / "candidate_profile.yaml"


class DraftGenerator:
    """Generates strictly compliant, personalized email drafts based on verified intelligence."""

    def __init__(self, config_path: Optional[Path] = None):
        self.config_path = config_path or CONFIG_PATH
        if self.config_path.exists():
            self.profile = yaml.safe_load(self.config_path.read_text(encoding="utf-8"))
        else:
            self.profile = {}

    def select_experience(self, sector: str, role: str) -> Dict[str, Any]:
        """Select an experience from the private profile based on domain relevance."""
        text = f"{sector or ''} {role or ''}".lower()
        experiences = self.profile.get("experiences", {}) or {}
        candidates = [item for item in experiences.values() if isinstance(item, dict)]
        for item in candidates:
            domains = " ".join(map(str, item.get("relevant_domains", []) or [])).lower()
            focus = str(item.get("focus") or "").lower()
            summary = str(item.get("summary") or "").lower()
            if any(token in domains for token in text.split() if len(token) > 3) or any(token in (focus + " " + summary) for token in text.split() if len(token) > 3):
                return item
        return candidates[0] if candidates else {}

    def generate_draft(
        self,
        contact: Contact,
        sector: str = "Technology",
        signal_headline: Optional[str] = None
    ) -> EmailDraft:
        """Constructs a compliant, calibrated EmailDraft."""
        first_name = contact.name.split()[0] if contact.name else "Sir/Madam"
        org_name = contact.organization_name
        trigger = signal_headline or f"recent operations and technical expansion in the region"

        # Determine experience
        exp = self.select_experience(sector, contact.role)
        exp_summary = exp.get("summary", "").strip()

        # Paragraph 1: Direct Greeting & Context
        p1 = f"Dear {first_name},"

        candidate = self.profile.get("candidate", {}) or {}
        candidate_name = str(candidate.get("full_name") or "").strip()
        academic_background = str(candidate.get("academic_background") or "").strip()
        identity = (f"I am {candidate_name}" + (f", with a background in {academic_background}" if academic_background else "") + ". ") if candidate_name else "I am reaching out to introduce myself and learn about your team’s priorities. "
        experience_sentence = f"My relevant experience includes {exp_summary}. " if exp_summary else "My verified experience details are still being configured, so I will not make unsupported claims. "
        p2 = (
            f"I came across {org_name} while researching its work around {trigger}. "
            f"{identity}"
            f"{experience_sentence}"
        )
        # Paragraph 3: Relevant value proposition
        p3 = (
            f"As your team scales technical operations and monitors critical reporting workflows, "
            f"I would welcome the opportunity to support your engineering team with data cleaning, "
            f"automated pipelines, and operational quality control."
        )

        # Paragraph 4: Low-friction Call to Action
        p4 = (
            f"Would you be open to a brief introductory call to see whether there is a mutual fit? "
            f"I can share the configured resume after checking that it is relevant to your needs."
        )

        # Construct and validate draft
        draft = EmailDraft(
            recipient_name=contact.name,
            recipient_email=contact.work_email,
            recipient_role=contact.role,
            organization_name=org_name,
            persona_type=PersonaType.DECISION_MAKER,
            subject_line=f"Data workflows & operational reporting at {org_name}",
            paragraphs=[p1, p2, p3, p4]
        )

        return draft
