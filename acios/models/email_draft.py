"""
Typed models for personalized email drafting and human approval gates.
"""

from datetime import datetime, timezone
from enum import Enum
from typing import List, Optional, Any
import hashlib
import json
from pydantic import BaseModel, Field, field_validator, model_validator


class PersonaType(str, Enum):
    DECISION_MAKER = "Decision Maker (Founder / CEO / VP)"
    PROJECT_LEAD = "Project / Technical Lead"
    RESEARCH_MENTOR = "Research Scientist / Academic Lead"
    OPERATIONS = "Operations / Project Controls"


class EmailDraft(BaseModel):
    """Enforces strict candidate tone, length constraints, and personalization."""
    recipient_name: str
    recipient_email: str
    recipient_role: str
    organization_name: str
    persona_type: PersonaType = PersonaType.DECISION_MAKER
    subject_line: str = Field(..., max_length=90)
    paragraphs: List[str] = Field(default_factory=list)
    cv_attached: bool = Field(default=False)
    attachment_sha256: Optional[str] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    @model_validator(mode="before")
    @classmethod
    def handle_body_text(cls, data: Any) -> Any:
        if isinstance(data, dict):
            if not data.get("paragraphs") and data.get("body_text"):
                raw = data["body_text"]
                paras = [p.strip() for p in raw.split("\n\n") if p.strip()]
                if not paras and raw.strip():
                    paras = [raw.strip()]
                data["paragraphs"] = paras
        return data

    @property
    def body_text(self) -> str:
        return "\n\n".join(self.paragraphs)

    @property
    def word_count(self) -> int:
        return len(self.body_text.split())

    @property
    def approval_hash(self) -> str:
        """Stable digest of every message field relevant to an approval decision.

        This is an integrity snapshot, not an authentication mechanism. Dispatch must
        compare it with the snapshot stored at the human-approval boundary.
        """
        payload = {
            "schema": 2,
            "recipient_email": self.recipient_email.strip().lower(),
            "recipient_name": self.recipient_name.strip(),
            "recipient_role": self.recipient_role.strip(),
            "organization_name": self.organization_name.strip(),
            "persona_type": self.persona_type.value,
            "subject_line": self.subject_line,
            "paragraphs": self.paragraphs,
            "cv_attached": bool(self.cv_attached),
            "attachment_sha256": self.attachment_sha256,
        }
        encoded = json.dumps(
            payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        ).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()

    @field_validator("paragraphs")
    @classmethod
    def validate_length_and_buzzwords(cls, paragraphs: List[str]) -> List[str]:
        text = " ".join(paragraphs)
        word_count = len(text.split())
        
        # The configured outreach rule is strict: 100–160 body words, excluding signature.
        if word_count < 100 or word_count > 160:
            raise ValueError(
                f"Draft word count {word_count} is outside the allowed 100-160 word window."
            )
        
        # Strict buzzword & agency jargon filter
        forbidden = [
            "synergy", "game-changer", "revolutionary", "disrupt", "delve", 
            "leverage our capabilities", "scale your business to the next level",
            "cutting-edge", "unleash", "skyrocket", "supercharge"
        ]
        text_lower = text.lower()
        for word in forbidden:
            if word in text_lower:
                raise ValueError(f"Draft contains forbidden sales/agency buzzword: '{word}'. Tone must be authentic and humble.")
                
        return paragraphs
