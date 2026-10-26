"""
Stage 2 Organization Auditor & Decision-Maker Hunter.
Performs corporate domain checks and searches for decision-makers
without fabricating synthetic contacts or unverified statuses.
"""

import re
import urllib.parse
import urllib.request
from typing import Any, Dict, List, Optional
from bs4 import BeautifulSoup

from acios.core.permutator import EmailPermutator
from acios.core.repository import CareerRepository
from acios.models.contact import Contact, VerificationStatus
from acios.tools.discovery.firecrawl_client import FirecrawlProvider


class LinkedInHunter:
    """Audits organizations and retrieves sourced executive profiles."""

    def __init__(self, repo: Optional[CareerRepository] = None):
        self.repo = repo or CareerRepository()
        self.firecrawl = FirecrawlProvider()

    def audit_organization(self, org_name: str, headline: str = "") -> Dict[str, Any]:
        """
        Conducts web verification on the organization.
        Reports honest verification status based on actual database or HTTP evidence.
        """
        existing = self.repo.get_organization(org_name)
        if existing and existing.get("website"):
            dom = re.sub(r"^https?://(www\.)?", "", existing["website"]).split("/")[0]
            return {
                "organization_name": org_name,
                "verification_status": "Database Record Found",
                "trigger_confirmed": bool(existing.get("signals")),
                "evidence_tier": "Stored Organization Record",
                "audit_summary": f"Existing organization record: {existing.get('value_proposition') or 'Recorded entity'}",
                "website": existing["website"],
                "domain": dom,
            }

        clean_name = re.sub(r"[^a-zA-Z0-9]", "", org_name.lower())
        candidate_domains = [
            f"https://www.{clean_name}.com",
            f"https://{clean_name}.com",
            f"https://{clean_name}.om",
            f"https://{clean_name}.sa",
            f"https://{clean_name}.ae",
        ]

        found_website = None
        for dom in candidate_domains:
            try:
                req = urllib.request.Request(
                    dom,
                    headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"},
                )
                with urllib.request.urlopen(req, timeout=3) as resp:
                    if resp.status in [200, 301, 302]:
                        found_website = dom
                        break
            except Exception:
                continue

        if found_website:
            return {
                "organization_name": org_name,
                "verification_status": "HTTP Domain Reachable",
                "trigger_confirmed": bool(headline),
                "evidence_tier": "HTTP Probe",
                "audit_summary": f"Live domain responded at {found_website}.",
                "website": found_website,
                "domain": re.sub(r"^https?://(www\.)?", "", found_website).split("/")[0],
            }

        return {
            "organization_name": org_name,
            "verification_status": "Unverified Domain",
            "trigger_confirmed": False,
            "evidence_tier": "Unverified",
            "audit_summary": f"No live domain verified automatically for '{org_name}'.",
            "website": None,
            "domain": None,
        }

    def hunt_decision_makers(
        self, org_name: str, country: str = "GCC", domain: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Finds executive leadership and technical decision-makers for an organization.
        Never fabricates placeholder contacts when search yields no results.
        """
        decision_makers: List[Dict[str, Any]] = []
        clean_domain = (
            re.sub(r"^https?://(www\.)?", "", domain).split("/")[0] if domain else None
        )

        # 1. Check existing database contacts for this organization
        db_contacts = self.repo.list_contacts(org_name=org_name)
        if db_contacts:
            for c in db_contacts:
                work_email = c.get("work_email")
                ver_status = c.get("verification_status") or VerificationStatus.UNVERIFIED.value
                is_verified = ver_status in (
                    VerificationStatus.VERIFIED.value,
                    VerificationStatus.CONFIRMED_PAGE.value,
                )
                decision_makers.append(
                    {
                        "name": c["name"],
                        "role": c["role"],
                        "organization_name": org_name,
                        "linkedin_url": c.get("linkedin_url"),
                        "email": work_email,
                        "work_email": work_email,
                        "confidence": 0.90 if is_verified else 0.40,
                        "verified": is_verified,
                        "verification_status": ver_status,
                        "verification_source": "Database Record",
                    }
                )
            return decision_makers

        # 2. Search public RSS index for matching profiles
        query = (
            f'site:linkedin.com/in "{org_name}" '
            '("CEO" OR "Founder" OR "Managing Director" OR "Director" OR "Head of" OR "VP" OR "Engineer")'
        )
        google_news_rss = (
            f"https://news.google.com/rss/search?q={urllib.parse.quote(query)}&hl=en-US&gl=US&ceid=US:en"
        )

        try:
            req = urllib.request.Request(
                google_news_rss,
                headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"},
            )
            with urllib.request.urlopen(req, timeout=6) as response:
                content = response.read().decode("utf-8")
                soup = BeautifulSoup(content, "xml")
                for item in soup.find_all("item")[:5]:
                    title = item.find("title").get_text() if item.find("title") else ""
                    cleaned_title = re.sub(
                        r"\s*-\s*LinkedIn.*$", "", title, flags=re.IGNORECASE
                    )
                    parts = [p.strip() for p in cleaned_title.split(" - ") if p.strip()]

                    if len(parts) >= 2:
                        name_cand = parts[0]
                        role_cand = parts[1]
                    elif len(parts) == 1:
                        name_cand = parts[0]
                        role_cand = "Executive / Leadership"
                    else:
                        continue

                    if any(
                        bad in name_cand.lower()
                        for bad in ["jobs", "careers", "top", "trending", "working at", "home"]
                    ):
                        continue

                    email_cand = None
                    if clean_domain:
                        pats = EmailPermutator.generate_patterns(name_cand, clean_domain)
                        email_cand = pats[0] if pats else None

                    dm_record = {
                        "name": name_cand,
                        "role": role_cand,
                        "organization_name": org_name,
                        "linkedin_url": None,
                        "email": email_cand,
                        "work_email": email_cand,
                        "confidence": 0.35 if email_cand else 0.25,
                        "verified": False,
                        "verification_status": (
                            VerificationStatus.PATTERN_PREDICTED.value
                            if email_cand
                            else VerificationStatus.UNVERIFIED.value
                        ),
                        "verification_source": "Public Search Snippet (Unverified)",
                    }
                    decision_makers.append(dm_record)
        except Exception:
            pass

        for dm in decision_makers:
            try:
                ct = Contact(
                    name=dm["name"],
                    role=dm["role"],
                    organization_name=org_name,
                    work_email=dm.get("work_email"),
                    linkedin_url=dm.get("linkedin_url"),
                    verification_status=VerificationStatus.PATTERN_PREDICTED
                    if dm.get("work_email")
                    else VerificationStatus.UNVERIFIED,
                    notes=f"Discovered via Stage 2 Hunter: {dm.get('verification_source')}",
                )
                self.repo.upsert_contact(ct)
            except Exception:
                pass

        return decision_makers

    def audit_and_hunt_multiple(self, org_names: List[str]) -> Dict[str, Dict[str, Any]]:
        """Batch audit and hunt for multiple organizations."""
        results = {}
        for org in org_names:
            audit = self.audit_organization(org)
            dms = self.hunt_decision_makers(org, domain=audit.get("domain"))
            results[org] = {"audit": audit, "decision_makers": dms}
        return results
