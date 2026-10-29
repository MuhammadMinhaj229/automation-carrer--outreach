"""
Evidence-conscious organization and contact lookup.

This adapter deliberately does not guess company domains, scrape LinkedIn,
parse news headlines as a person's identity, or generate work-email candidates.
It returns stored records as leads needing revalidation and gives the operator
a manual profile-search URL when source-backed matches are unavailable.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional
from urllib.parse import urlencode, urlsplit

from acios.core.repository import CareerRepository


class LinkedInHunter:
    """Returns existing contact leads without promoting stale fields to verified facts."""

    def __init__(self, repo: Optional[CareerRepository] = None):
        self.repo = repo or CareerRepository()
        self.last_search_urls: Dict[str, str] = {}

    @staticmethod
    def _linkedin_search_url(org_name: str, intent: str = "people") -> str:
        query = f'"{org_name}" (founder OR director OR head OR lead OR recruiter)'
        route = "companies" if intent == "companies" else "people"
        return f"https://www.linkedin.com/search/results/{route}/?{urlencode({'keywords': query})}"

    @staticmethod
    def _stored_domain(website: Optional[str]) -> Optional[str]:
        """Extract a hostname from an explicitly stored URL; never derive it from a name."""
        if not website or not isinstance(website, str):
            return None
        candidate = website.strip()
        parts = urlsplit(candidate if "://" in candidate else f"https://{candidate}")
        if parts.scheme not in {"http", "https"} or not parts.hostname:
            return None
        return parts.hostname.lower()

    def audit_organization(self, org_name: str, headline: str = "") -> Dict[str, Any]:
        """Return stored organization metadata while marking it for source revalidation."""
        _ = headline
        self.last_search_urls = {
            "linkedin_company": self._linkedin_search_url(org_name, "companies"),
            "linkedin_people": self._linkedin_search_url(org_name, "people"),
        }
        existing = self.repo.get_organization(org_name)
        if existing:
            stored_website = existing.get("website")
            domain = self._stored_domain(stored_website)
            return {
                "organization_name": org_name,
                "verification_status": "STORED_RECORD_NEEDS_REVALIDATION",
                "trigger_confirmed": False,
                "evidence_tier": "Stored record; primary-source revalidation required",
                "audit_summary": (
                    "A matching local record exists, but this adapter has not "
                    "revalidated current identity, website ownership, or trigger status."
                ),
                "website": stored_website if domain else None,
                "domain": domain,
                "manual_company_search_url": self.last_search_urls["linkedin_company"],
                "manual_people_search_url": self.last_search_urls["linkedin_people"],
            }

        return {
            "organization_name": org_name,
            "verification_status": "UNVERIFIED_NO_SOURCE_BACKED_DOMAIN",
            "trigger_confirmed": False,
            "evidence_tier": "No supporting source record",
            "audit_summary": (
                "No source-backed organization record was found. No domain was guessed "
                "from the organization name."
            ),
            "website": None,
            "domain": None,
            "manual_company_search_url": self.last_search_urls["linkedin_company"],
            "manual_people_search_url": self.last_search_urls["linkedin_people"],
        }

    def hunt_decision_makers(
        self, org_name: str, country: str = "GCC", domain: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Return existing records as unverified review leads, never as verified contacts.

        Emails stored by legacy permutations are not exposed by this discovery adapter.
        No search snippets are treated as identity evidence and no contacts are created
        from unresolved search results.
        """
        _ = (country, domain)
        self.last_search_urls = {
            "linkedin_company": self._linkedin_search_url(org_name, "companies"),
            "linkedin_people": self._linkedin_search_url(org_name, "people"),
        }
        try:
            stored = self.repo.list_contacts(org_name=org_name)
        except Exception:
            stored = []

        leads: List[Dict[str, Any]] = []
        for contact in stored:
            linkedin_url = contact.get("linkedin_url")
            role = contact.get("role")
            name = contact.get("name")
            leads.append({
                "name": name,
                "role": role,
                "organization_name": contact.get("organization_name") or org_name,
                "linkedin_url": None,
                "stored_profile_url_needs_revalidation": linkedin_url,
                "email": None,
                "work_email": None,
                "stored_email_present": bool(contact.get("work_email")),
                "confidence": 0.0,
                "verified": False,
                "verification_status": "STORED_CONTACT_NEEDS_REVALIDATION",
                "verification_source": None,
                "manual_profile_search_url": self.last_search_urls["linkedin_people"],
                "notes": (
                    "Legacy contact metadata is not proof of a current role, identity, "
                    "or email. Revalidate it against an official company or profile source."
                ),
            })
        return leads

    def audit_and_hunt_multiple(self, org_names: List[str]) -> Dict[str, Dict[str, Any]]:
        """Return source-cautious records and manual review routes for each organization."""
        results: Dict[str, Dict[str, Any]] = {}
        for org in org_names:
            audit = self.audit_organization(org)
            decision_makers = self.hunt_decision_makers(org)
            results[org] = {"audit": audit, "decision_makers": decision_makers}
        return results
