"""
Typed models for personalized email drafting and human approval gates.
"""

from datetime import datetime, timezone
from enum import Enum
from typing import List, Optional, Any
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
    cv_attached: bool = Field(default=True)
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
        import hashlib
        payload = f"{self.recipient_email}:{self.subject_line}:{self.body_text}"
        return hashlib.sha256(payload.encode()).hexdigest()

    @field_validator("paragraphs")
    @classmethod
    def validate_length_and_buzzwords(cls, paragraphs: List[str]) -> List[str]:
        text = " ".join(paragraphs)
        word_count = len(text.split())
        
        # Quality window guard (95 - 165 words allowing punctuation/whitespace variations)
        if word_count < 95 or word_count > 165:
            raise ValueError(f"Draft word count {word_count} is outside the allowed 100-160 word window.")
        
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
