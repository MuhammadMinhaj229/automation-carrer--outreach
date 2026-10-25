"""
Typed models for organizations, signals, and research metadata.
"""

from datetime import datetime, timezone
from enum import Enum
from typing import List, Optional
from pydantic import BaseModel, Field, HttpUrl


class SectorCategory(str, Enum):
    AGRITECH = "AgriTech & Controlled Environment"
    CLEANTECH = "CleanTech & Waste Valorization"
    ENERGY = "Renewable Energy & Storage"
    MATERIALS = "Advanced Materials & Circular Economy"
    HEALTH = "Digital Health & Life Sciences"
    AI_DATA = "AI, Software & Data Infrastructure"
    RESEARCH = "Academic & Research Institute"
    OTHER = "Other"


class ExpansionSignal(BaseModel):
    """Specific event triggering outreach (funding, contract award, new facility, pilot launch)."""
    headline: str = Field(..., description="Summary of the breakthrough or trigger event")
    signal_date: str = Field(..., description="Date of the signal (YYYY-MM-DD)")
    source_url: str = Field(..., description="Verified primary source link (WAM, Zawya, press release)")
    evidence_tier: str = Field(default="Verified Primary", description="Source quality tier")
    details: Optional[str] = Field(default=None, description="Technical parameters (e.g. 40 kg/day, $5M round)")


class Organization(BaseModel):
    """Ground-truth model for a tracked enterprise or research entity."""
    name: str = Field(..., description="Official enterprise or institution name")
    country: str = Field(..., description="GCC State or international host country")
    city: Optional[str] = Field(default=None, description="City or Emirate")
    sector: SectorCategory = Field(default=SectorCategory.OTHER)
    website: Optional[str] = Field(default=None, description="Official domain or landing page")
    signals: List[ExpansionSignal] = Field(default_factory=list)
    value_proposition: Optional[str] = Field(default=None, description="Specific candidate capability match")
    prototype_concept: Optional[str] = Field(default=None, description="Relevant mock-up or data workflow demo")
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
