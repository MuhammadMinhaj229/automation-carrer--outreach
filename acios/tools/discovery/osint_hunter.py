"""
ACIOS Executive OSINT Hunter.
Performs passive search dorking and corporate domain footprinting
without fabricating synthetic contacts or unverified statuses.
"""

import re
import socket
import urllib.parse
from typing import Any, Dict, List, Optional
import httpx
from bs4 import BeautifulSoup

from acios.core.repository import CareerRepository
from acios.models.contact import VerificationStatus


class OSINTHunter:
    """Executes passive LinkedIn dorking and corporate domain footprinting."""

    def __init__(self, repo: Optional[CareerRepository] = None):
        self.repo = repo or CareerRepository()
        self.headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36"
            )
        }

    async def crosslinked_dork(
        self, org_name: str, target_roles: Optional[List[str]] = None
    ) -> List[Dict[str, Any]]:
        """
        Passive search engine dorking to discover executive profiles.
        Never fabricates contacts when search returns no matches.
        """
        roles = target_roles or [
            "Managing Director",
            "CEO",
            "Founder",
            "Director",
            "VP",
            "Head of Engineering",
            "Project Lead",
            "Operations Manager",
        ]
        role_clause = " OR ".join([f'"{r}"' for r in roles[:4]])
        query = f'site:linkedin.com/in "{org_name}" ({role_clause})'

        discovered_executives: List[Dict[str, Any]] = []

        try:
            url = f"https://html.duckduckgo.com/html/?q={urllib.parse.quote_plus(query)}"
            async with httpx.AsyncClient(
                headers=self.headers, timeout=6.0, follow_redirects=True
            ) as client:
                resp = await client.get(url)
                if resp.status_code == 200:
                    soup = BeautifulSoup(resp.text, "html.parser")
                    for a in soup.find_all("a", class_="result__snippet"):
                        raw_text = a.get_text()
                        parent = a.find_parent("div", class_="result__body")
                        href = ""
                        if parent:
                            title_elem = parent.find("a", class_="result__title") or parent.find(
                                "a", class_="result__url"
                            )
                            if title_elem and "href" in title_elem.attrs:
                                href = title_elem["href"]

                        match = re.search(
                            r"([A-Z][a-z]+ [A-Z][a-z]+(?:\s[A-Z][a-z]+)?)\s*[-–|:]\s*([^–|-|]+)",
                            raw_text,
                        )
                        if match:
                            clean_name = match.group(1).strip()
                            clean_role = match.group(2).strip()
                            if clean_name and "linkedin.com" not in clean_name.lower():
                                linkedin_url = href
                                if "uddg=" in linkedin_url:
                                    parts = urllib.parse.parse_qs(
                                        urllib.parse.urlparse(linkedin_url).query
                                    )
                                    linkedin_url = parts.get("uddg", [linkedin_url])[0]

                                discovered_executives.append(
                                    {
                                        "name": clean_name,
                                        "role": clean_role or "Leadership / Executive",
                                        "organization_name": org_name,
                                        "linkedin_url": linkedin_url
                                        if "linkedin.com/in" in linkedin_url
                                        else None,
                                        "email": None,
                                        "confidence": 0.45,
                                        "verified": False,
                                        "source": "Passive Search Dorking (Unverified)",
                                    }
                                )
        except Exception:
            pass

        if not discovered_executives:
            db_contacts = self.repo.list_contacts(org_name=org_name)
            for c in db_contacts:
                ver_status = c.get("verification_status") or VerificationStatus.UNVERIFIED.value
                is_verified = ver_status in (
                    VerificationStatus.VERIFIED.value,
                    VerificationStatus.CONFIRMED_PAGE.value,
                )
                discovered_executives.append(
                    {
                        "name": c.get("name"),
                        "role": c.get("role"),
                        "organization_name": org_name,
                        "linkedin_url": c.get("linkedin_url"),
                        "email": c.get("work_email"),
                        "confidence": 0.90 if is_verified else 0.40,
                        "verified": is_verified,
                        "source": "Database Record",
                    }
                )

        return discovered_executives

    def theharvester_footprint(self, domain: str) -> Dict[str, Any]:
        """
        Passive corporate domain footprinting.
        Resolves active subdomains and primary domain IP without fabricating fallback IPs.
        """
        clean_domain = (
            re.sub(r"^https?://(www\.)?", "", domain).split("/")[0].strip().lower()
        )
        subdomains = [
            f"mail.{clean_domain}",
            f"webmail.{clean_domain}",
            f"portal.{clean_domain}",
            f"api.{clean_domain}",
            f"careers.{clean_domain}",
        ]

        active_subdomains = []
        for sub in subdomains:
            try:
                ip = socket.gethostbyname(sub)
                active_subdomains.append({"host": sub, "ip": ip})
            except Exception:
                continue

        primary_ip = None
        try:
            primary_ip = socket.gethostbyname(clean_domain)
        except Exception:
            primary_ip = None

        return {
            "domain": clean_domain,
            "primary_ip": primary_ip,
            "active_subdomains": active_subdomains,
            "subdomains_count": len(active_subdomains),
        }
