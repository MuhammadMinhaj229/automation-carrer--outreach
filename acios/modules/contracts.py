"""
ACIOS 8-Phase Modular Contracts.
Defines strictly typed, decoupled data contracts exchanged between all 8 modules.
Modifying any module's internal tool or implementation will never break downstream modules
as long as these contracts are maintained.
"""

from typing import List, Optional, Dict, Any
from datetime import datetime, timezone
from enum import Enum
from pydantic import BaseModel, Field


# ==========================================
# Phase 1: Discovery Contracts
# ==========================================

class EvidenceTier(str, Enum):
    TIER_1_OFFICIAL = "Tier 1: Official Corporate/Gov Press Release"
    TIER_2_TRADE_MEDIA = "Tier 2: Verified Trade Media Publication"
    TIER_3_UNSTRUCTURED = "Tier 3: Unstructured Web/Social Signal"


class ExpansionSignal(BaseModel):
    organization_name: str
    headline: str
    signal_date: str
    source_url: str
    evidence_tier: EvidenceTier
    details: str
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


# ==========================================
# Phase 2: Decision Maker Contracts
# ==========================================

class ExecutiveProfile(BaseModel):
    organization_name: str
    full_name: str
    role_title: str
    linkedin_url: Optional[str] = None
    confidence_score: float = 1.0
    notes: Optional[str] = None


# ==========================================
# Phase 3: Contact Finder (Apollo/Hunter Alternative)
# ==========================================

class PermutationPattern(str, Enum):
    FIRST = "{first}@{domain}"
    FIRST_DOT_LAST = "{first}.{last}@{domain}"
    FIRST_INITIAL_LAST = "{f}{last}@{domain}"
    FIRST_INITIAL_DOT_LAST = "{f}.{last}@{domain}"
    LAST = "{last}@{domain}"
    FIRST_UNDERSCORE_LAST = "{first}_{last}@{domain}"


class CandidateEmail(BaseModel):
    email: str
    pattern_used: str
    domain: str
    source: str = "Permutation Sieve"


# ==========================================
# Phase 4: Deliverability Contracts
# ==========================================

class DeliverabilityStatus(str, Enum):
    REAL_MAILBOX = "REAL_MAILBOX"
    MX_BANNER_REACHABLE = "MX_BANNER_REACHABLE"
    MX_VALID_UNPROBED = "MX_VALID_UNPROBED"
    CATCH_ALL = "CATCH_ALL"
    DEAD_DOMAIN = "DEAD_DOMAIN"
    CONFIRMED_BOUNCE = "CONFIRMED_BOUNCE"
    INVALID_SYNTAX = "INVALID_SYNTAX"
    UNKNOWN = "UNKNOWN"


class DeliverabilityVerdict(BaseModel):
    email: str
    status: DeliverabilityStatus
    is_deliverable: bool
    confidence: float
    mx_host: Optional[str] = None
    is_catch_all: bool = False
    smtp_code: Optional[int] = None
    evidence: List[str] = Field(default_factory=list)
    details: str


# ==========================================
# Phase 5: Inbound Reply & Bounce Guard Contracts
# ==========================================

class InboundEventType(str, Enum):
    REPLY_RECEIVED = "REPLY_RECEIVED"
    BOUNCE_DETECTED = "BOUNCE_DETECTED"
    UNREAD_NOTIFICATION = "UNREAD_NOTIFICATION"


class InboundEvent(BaseModel):
    sender_email: str
    sender_name: Optional[str] = None
    subject: str
    event_type: InboundEventType
    timestamp: str
    body_snippet: Optional[str] = None


# ==========================================
# Phase 6: Narrative & Pitch Contracts
# ==========================================

class EmailDraftContract(BaseModel):
    recipient_email: str
    recipient_name: str
    organization_name: str
    recipient_role: str
    subject_line: str
    body_text: str
    word_count: int
    approval_hash: str
    status: str = "APPROVED"


# ==========================================
# Phase 7: Staging Contracts
# ==========================================

class StagedDraftResult(BaseModel):
    recipient_email: str
    staged: bool
    gmail_uid: Optional[str] = None
    attachment_name: str
    message: str


# ==========================================
# Phase 8: Paced Dispatch Contracts
# ==========================================

class DispatchRecord(BaseModel):
    recipient_email: str
    organization_name: str
    subject_line: str
    timestamp: str
    status: str  # DISPATCHED / FAILED
    error_message: Optional[str] = None
