"""
Typed models for decision-makers, mentors, and contact verification.
"""

from datetime import datetime, timezone
from enum import Enum
from typing import Optional
from pydantic import BaseModel, EmailStr, Field


class VerificationStatus(str, Enum):
    VERIFIED_PRIMARY = "Verified Primary (Direct Match)"
    PATTERN_PREDICTED = "Pattern Predicted (Permutation)"
    CORPORATE_ROUTE = "Corporate / Departmental Route"
    UNVERIFIED = "Unverified"
    BOUNCED_SUPPRESSED = "Bounced / Suppressed"


class OutreachStatus(str, Enum):
    UNTOUCHED = "Untouched"
    STAGED_DRAFT = "Staged in Gmail Drafts"
    APPROVED = "Approved"
    DISPATCHED = "Dispatched via SMTP"
    REPLIED = "Replied (Protected)"
    SKIPPED = "Skipped"


class Contact(BaseModel):
    """Ground-truth model for a professional contact or decision-maker."""
    name: str = Field(..., description="Full name of the person or team title")
    role: str = Field(..., description="Exact title or function (e.g. Co-Founder & CEO, Head of R&D)")
    organization_name: str = Field(..., description="Parent company or institution")
    work_email: str = Field(..., description="Work email address or official department inbox")
    linkedin_url: Optional[str] = Field(default=None, description="Direct or searched LinkedIn profile URL")
    phone: Optional[str] = Field(default=None, description="Direct phone or official headquarters line")
    verification_status: VerificationStatus = Field(default=VerificationStatus.UNVERIFIED)
    outreach_status: OutreachStatus = Field(default=OutreachStatus.UNTOUCHED)
    is_suppressed: bool = Field(default=False, description="Flagged true if in suppression or bounce registry")
    notes: Optional[str] = Field(default=None, description="Contextual research notes or referral route")
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
