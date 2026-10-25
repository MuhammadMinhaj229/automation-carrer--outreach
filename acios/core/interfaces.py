"""
ACIOS Pluggable Provider Interfaces.
Defines abstract base classes and typed contracts for discovery, scraping,
signal detection, email verification, and dossier generation.
"""

from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field

from acios.models.contact import VerificationStatus


class VerificationResult(BaseModel):
    """Result of an email verification check across waterfall stages."""
    email: str
    status: VerificationStatus
    confidence_score: float = Field(default=0.0, ge=0.0, le=1.0)
    mx_valid: bool = False
    mx_records: List[str] = Field(default_factory=list)
    is_disposable: bool = False
    is_role_account: bool = False
    provider: str = "Unknown"
    details: str = ""


class SignalItem(BaseModel):
    """A detected corporate expansion, pilot project, or funding event."""
    headline: str
    organization_name: str
    signal_date: Optional[str] = None
    source_url: Optional[str] = None
    details: str
    score: int = Field(default=50, ge=0, le=100)
    evidence_tier: str = "Verified Primary"


class ScrapedDocument(BaseModel):
    """Raw scraped web page content processed for LLM and agent consumption."""
    url: str
    title: Optional[str] = None
    markdown_content: str
    links: List[str] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class DiscoveryProvider(ABC):
    """Abstract interface for entity discovery and registry lookup."""

    @abstractmethod
    def search_organizations(self, query: str, country_code: Optional[str] = None) -> List[Dict[str, Any]]:
        """Searches for organizations by name and geographic criteria."""
        pass

    @abstractmethod
    def get_metadata(self, entity_id: str) -> Optional[Dict[str, Any]]:
        """Retrieves structured metadata for an identified organization."""
        pass


class SignalProvider(ABC):
    """Abstract interface for monitoring corporate growth signals."""

    @abstractmethod
    def fetch_signals(self, query: str, keywords: Optional[List[str]] = None, min_score: int = 50) -> List[SignalItem]:
        """Discovers verified expansion or hiring signals matching the criteria."""
        pass


class ScraperProvider(ABC):
    """Abstract interface for deep web crawling and page extraction."""

    @abstractmethod
    def scrape_page(self, url: str) -> ScrapedDocument:
        """Scrapes a single URL and converts it into clean markdown."""
        pass

    @abstractmethod
    def map_domain(self, domain: str, search_filter: Optional[str] = None) -> List[str]:
        """Discovers internal endpoints, subpages, and team links."""
        pass


class VerifierProvider(ABC):
    """Abstract interface for email address verification."""

    @abstractmethod
    def verify(self, email: str) -> VerificationResult:
        """Evaluates deliverability and safety for a target email address."""
        pass


class DossierProvider(ABC):
    """Abstract interface for compiling intelligence dossiers."""

    @abstractmethod
    def generate_dossier(self, org_name: str, contact_name: Optional[str] = None) -> Dict[str, Any]:
        """Synthesizes verified facts, expansion signals, and pitch angles."""
        pass
