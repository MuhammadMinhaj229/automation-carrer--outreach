"""
Stage 1 Growth Signal & Organization Discovery Engine.
Conducts hierarchical continent, country, and regional intelligence scans,
supporting targeted organization and website search, enterprise triggers,
and source-aware discovery of possible expansion triggers.
RSS results are discovery leads only; the scanner does not verify claims or populate
fabricated organization domains, event dates, headcounts, or contact details.
"""

import os
import re
import hashlib
import urllib.parse
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple
import feedparser
import pandas as pd

from acios.core.repository import CareerRepository
from acios.models.organization import Organization, ExpansionSignal, SectorCategory

BASE_DIR = Path(__file__).resolve().parent.parent.parent.parent
DISCOVERY_RUNS_DIR = BASE_DIR / "data" / "discovery_runs"
DISCOVERY_RUNS_DIR.mkdir(parents=True, exist_ok=True)

# Hierarchical Continent -> Country -> Regions
CONTINENT_MAP: Dict[str, Dict[str, List[str]]] = {
    "Middle East / GCC": {
        "Saudi Arabia": [
            "All Regions",
            "Riyadh (Capital & Tech HQ)",
            "NEOM & Tabuk (Mega Projects & Clean Energy)",
            "Jeddah & Western Province (Commercial & Port)",
            "Dammam, Khobar & Eastern Province (Energy & Logistics)",
            "KAUST & Thuwal (DeepTech & Biotech Research)",
            "Jubail & Yanbu (Industrial & Petrochemical)",
            "Asir & Abha (Tourism & Agritech)",
            "Jazan (Economic City & Manufacturing)"
        ],
        "United Arab Emirates": [
            "All Regions",
            "Dubai (Tech, AI, Logistics & Financial Freezones)",
            "Abu Dhabi (Clean Tech, Sovereign Capital & Energy)",
            "Masdar City (Sustainability & Clean Tech R&D)",
            "Sharjah (Research & Advanced Manufacturing)",
            "Ras Al Khaimah (Heavy Industry & Mining)",
            "Fujairah (Bunkering & Energy Logistics)",
            "Ajman & Northern Emirates"
        ],
        "Oman": [
            "All Regions",
            "Muscat (Capital, Corporate & Research Hub)",
            "Sohar (Green Port, Biofuels, Agritech & Metals)",
            "Duqm (Special Economic Zone & Green Hydrogen)",
            "Salalah (Free Zone, Logistics & Agro-Pharma)",
            "Nizwa & Ad Dakhiliyah (Industrial & Heritage)",
            "Sur & Ash Sharqiyah (LNG & Fisheries)",
            "Al Buraimi (Border Logistics & Commerce)"
        ],
        "Qatar": [
            "All Regions",
            "Doha (Capital & Enterprise Systems)",
            "Lusail (Smart City & Tech)",
            "Qatar Science & Technology Park (QSTP)",
            "Ras Laffan (Industrial & Gas Processing)",
            "Mesaieed (Petrochemical & Heavy Industry)"
        ],
        "Bahrain": [
            "All Regions",
            "Manama (FinTech & Financial Center)",
            "Bahrain Bay & Sitra (Industrial & Maritime)",
            "Muharraq (Logistics & Airport Freezone)",
            "Riffa & Southern Governorate"
        ],
        "Kuwait": [
            "All Regions",
            "Kuwait City (Corporate & Finance)",
            "Shuaiba & Mina Al Ahmadi (Industrial & Energy)",
            "Sabah Al Salem & Capital Governorate",
            "Farwaniya & International Airport Logistics"
        ]
    },
    "Asia": {
        "India": [
            "All Regions",
            "Bengaluru (Technology & Research)",
            "Hyderabad (Biotech, AI & Software)",
            "Mumbai (Finance & Enterprise)",
            "Delhi NCR (Policy, Tech & Scaleups)",
            "Pune (Engineering & Automotive)",
            "Chennai (Manufacturing & SaaS)"
        ],
        "Singapore": [
            "All Regions",
            "Central Business District (FinTech & Corporate)",
            "One-North & Biopolis (Biotech & DeepTech)",
            "Jurong Innovation District (Advanced Manufacturing)",
            "Changi & Seletar (Aerospace & Logistics)"
        ],
        "Japan": [
            "All Regions",
            "Tokyo (Global HQ & Robotics)",
            "Osaka & Kansai (Bio & Industrial Tech)",
            "Yokohama (Engineering & Mobility)",
            "Fukuoka (Startup City & FinTech)"
        ],
        "Malaysia": [
            "All Regions",
            "Kuala Lumpur (Finance & Tech)",
            "Cyberjaya (Digital Hub)",
            "Penang (Semiconductors & Electronics)"
        ]
    },
    "Europe": {
        "United Kingdom": [
            "All Regions",
            "London (Tech, Finance & AI)",
            "Cambridge (Biotech & DeepTech)",
            "Oxford (Sciences & Quantum)",
            "Manchester & Leeds (Industrial Tech)"
        ],
        "Germany": [
            "All Regions",
            "Berlin (Startups & Software)",
            "Munich (Mobility, DeepTech & Engineering)",
            "Frankfurt (Finance & Cloud Hub)",
            "Stuttgart (Automotive & Automation)"
        ],
        "France": [
            "All Regions",
            "Paris (AI, FinTech & Research)",
            "Toulouse (Aerospace & Robotics)",
            "Lyon (Biotech & Chemistry)"
        ],
        "Switzerland": [
            "All Regions",
            "Zurich (AI, Robotics & FinTech)",
            "Geneva & Lausanne (Life Sciences & CleanTech)",
            "Basel (Pharma & Biotech)"
        ],
        "Netherlands": [
            "All Regions",
            "Amsterdam (FinTech & SaaS)",
            "Eindhoven (High-Tech & Semiconductors)",
            "Rotterdam (Maritime & Energy Transition)"
        ]
    },
    "North America": {
        "United States": [
            "All Regions",
            "San Francisco Bay Area / Silicon Valley",
            "New York City (Finance & Enterprise Tech)",
            "Boston & Cambridge (Biotech & Robotics)",
            "Austin (Tech & Clean Energy)",
            "Seattle (Cloud & AI Platforms)"
        ],
        "Canada": [
            "All Regions",
            "Toronto (AI & FinTech)",
            "Vancouver (CleanTech & Software)",
            "Montreal (AI Research & Aerospace)"
        ]
    }
}

# Backward compatible flat dictionary
COUNTRY_REGIONS: Dict[str, List[str]] = {}
for continent_countries in CONTINENT_MAP.values():
    for country_name, reg_list in continent_countries.items():
        COUNTRY_REGIONS[country_name] = reg_list

TRIGGER_CATEGORIES: Dict[str, List[str]] = {
    "All Strategic Triggers": [
        "startup", "fundraising", "expansion", "new facility", "pilot", "launch",
        "hiring", "biofuel", "camelina", "solar", "desalination", "hydrogen", "scaleup"
    ],
    "Seed, Venture & Series Funding": [
        "startup", "fundraising", "seed round", "series A", "series B", "venture capital",
        "incubator", "accelerator", "investment round", "equity financing"
    ],
    "Industrial Mega-Projects & Facility Expansion": [
        "expansion", "new facility", "pilot plant", "factory", "plant", "hub",
        "groundbreaking", "commissioned", "regional headquarters", "mega-project"
    ],
    "Biofuel, Sustainable Aviation Fuel & Agritech": [
        "biofuel", "camelina", "sustainable aviation fuel", "solar", "clean tech",
        "water treatment", "wastewater", "desalination", "carbon capture", "hydrogen"
    ],
    "Water Treatment, Desalination & Environmental Tech": [
        "water treatment", "treated wastewater", "desalination", "salinity monitoring",
        "circular economy", "water reuse", "environmental engineering", "waste-to-energy"
    ],
    "AI Platforms, Enterprise Software & Cloud Scaleup": [
        "enterprise AI", "platform launch", "data platform", "software expansion",
        "cloud infrastructure", "automation platform", "model deployment", "digital transformation"
    ],
    "Technical & Engineering Hiring Surges": [
        "expanding tech team", "hiring engineers", "data science team", "AI talent",
        "software development hub", "skilled technical personnel", "scaling engineering"
    ],
    "Joint Ventures, Sovereign Grants & Government Partnerships": [
        "joint venture", "sovereign wealth", "strategic partnership", "MOU",
        "government grant", "economic development", "consortium"
    ]
}

TRIGGER_KEYWORD_SCORES = {
    "pilot": 20,
    "expansion": 25,
    "facility": 20,
    "fundraising": 25,
    "seed round": 25,
    "series a": 25,
    "biofuel": 30,
    "camelina": 35,
    "plant": 15,
    "investment": 15,
    "hiring": 20,
    "partnership": 15,
    "launch": 15,
    "solar": 15,
    "hydrogen": 20,
    "sohar": 20,
    "neom": 25,
    "kaust": 20,
    "wastewater": 25,
    "desalination": 20
}


class GrowthSignalScanner:
    """Discovers, scores, and indexes hierarchical corporate expansion signals."""

    GOOGLE_NEWS_BASE = "https://news.google.com/rss/search?q={query}&hl=en-US&gl=US&ceid=US:en"

    def __init__(self, repo: Optional[CareerRepository] = None):
        self.repo = repo or CareerRepository()

    def _clean_region_name(self, region_str: str) -> str:
        if "(" in region_str:
            return region_str.split("(")[0].strip()
        return region_str.replace("All Regions", "").strip()

    def _extract_organization_name(self, headline: str, query: str) -> Optional[str]:
        raw_title = headline.rsplit(" - ", 1)[0] if " - " in headline else headline
        
        m_poss = re.search(r"(?:Saudi|Oman|UAE|Dubai|Qatar|Bahrain|Kuwait|India|UK|Germany|US)['’]s\s+([A-Z][A-Za-z0-9\s&]+?)\s+(?:plans|launches|secures|announces|expands|signs|raises|opens|is)", raw_title, re.IGNORECASE)
        if m_poss:
            return m_poss.group(1).strip()

        m_lead = re.match(r"^([A-Z][A-Za-z0-9\s&]{2,30}?)\s+(?:launches|secures|announces|expands|signs|raises|opens|plans|partners|unveils|commissions)", raw_title)
        if m_lead:
            cand = m_lead.group(1).strip()
            if cand.lower() not in ["startup", "report", "breaking", "new", "industry", "middle east", "global"]:
                return cand

        # Never turn the first words of an arbitrary headline into an entity.
        # If no supported name pattern matches, leave organization resolution unknown.
        return None

    def _score_item(self, title: str, summary: str) -> int:
        score = 45
        combined = f"{title} {summary}".lower()
        for kw, pts in TRIGGER_KEYWORD_SCORES.items():
            if kw in combined:
                score += pts
        return min(score, 100)

    def scan_ecosystem(
        self,
        country: str = "Oman",
        region: str = "All Regions",
        trigger_category: str = "All Strategic Triggers",
        search_org: Optional[str] = None,
        search_website: Optional[str] = None,
        custom_keywords: Optional[str] = None,
        max_results: int = 25
    ) -> Tuple[pd.DataFrame, Path, Path]:
        """Discover dated news articles without promoting aggregator hits to verified facts.

        Results are saved locally for review. An RSS hit is only a discovery lead:
        the source may be an aggregator, the event date may be absent, and organization
        resolution can remain unknown. Saved organization records are intentionally not
        added as if they were fresh expansion events.
        """
        limit = max(1, min(int(max_results), 100))
        clean_region = self._clean_region_name(region)
        keywords = TRIGGER_CATEGORIES.get(
            trigger_category, TRIGGER_CATEGORIES["All Strategic Triggers"]
        )

        if search_org and search_org.strip():
            org_term = search_org.strip()
            search_query = (
                f'"{org_term}" (expansion OR funding OR facility OR pilot OR project OR launch OR hiring)'
            )
        elif search_website and search_website.strip():
            dom_term = re.sub(
                r"^https?://(www\.)?", "", search_website.strip()
            ).split("/")[0]
            search_query = (
                f'"{dom_term}" (expansion OR funding OR facility OR pilot OR project OR hiring)'
            )
        else:
            query_parts = []
            if country.strip().lower() not in {"", "all", "worldwide", "all countries"}:
                query_parts.append(country.strip())
            if clean_region and clean_region.lower() != "all regions":
                query_parts.append(clean_region)
            if custom_keywords and custom_keywords.strip():
                query_parts.append(custom_keywords.strip())
            else:
                query_parts.append(f"({' OR '.join(keywords[:3])})")
            search_query = " ".join(query_parts)

        feed_url = self.GOOGLE_NEWS_BASE.format(query=urllib.parse.quote_plus(search_query))
        try:
            feed = feedparser.parse(feed_url)
        except Exception:
            feed = None

        records: List[Dict[str, Any]] = []
        retrieved_at = datetime.now(timezone.utc).isoformat()
        run_stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")

        continent = next(
            (
                continent_name
                for continent_name, countries in CONTINENT_MAP.items()
                if country in countries
            ),
            "Unclassified",
        )

        if feed and getattr(feed, "entries", None):
            for entry in feed.entries[:limit]:
                title = str(entry.get("title") or "").strip()
                source_url = str(entry.get("link") or "").strip()
                if not title or not source_url:
                    # A result without a title or retrievable source URL is not evidence.
                    continue

                raw_title = title
                outlet = ""
                if " - " in title:
                    possible_headline, possible_outlet = title.rsplit(" - ", 1)
                    if possible_headline.strip() and possible_outlet.strip():
                        title = possible_headline.strip()
                        outlet = possible_outlet.strip()

                summary = str(entry.get("summary") or "").strip()
                excerpt = re.sub(r"<[^>]+>", " ", summary)
                excerpt = re.sub(r"\s+", " ", excerpt).strip()[:2000]

                published_raw = str(entry.get("published") or "").strip()
                published_parsed = entry.get("published_parsed")
                published_at = None
                if published_parsed:
                    try:
                        published_at = datetime(
                            *published_parsed[:6], tzinfo=timezone.utc
                        ).isoformat()
                    except (TypeError, ValueError, OverflowError):
                        published_at = None

                if search_org and search_org.strip():
                    organization_name = search_org.strip()
                    entity_resolution_status = "USER_SUPPLIED_TARGET"
                else:
                    organization_name = self._extract_organization_name(raw_title, search_query)
                    entity_resolution_status = (
                        "HEADLINE_PATTERN_CANDIDATE"
                        if organization_name
                        else "UNRESOLVED"
                    )

                combined = f"{raw_title} {excerpt}".lower()
                explicit_hiring = any(
                    term in combined
                    for term in ("hiring", "we are hiring", "career opportunity", "job opening", "recruitment")
                )
                keyword_score = self._score_item(raw_title, excerpt)
                record_fingerprint = hashlib.sha256(
                    f"{source_url}\n{raw_title}\n{excerpt}".encode("utf-8")
                ).hexdigest()

                records.append({
                    "organization_name": organization_name,
                    "entity_resolution_status": entity_resolution_status,
                    "website": search_website.strip() if search_website and search_website.strip() else None,
                    "website_status": "USER_SUPPLIED_NEEDS_VERIFICATION" if search_website else "UNKNOWN",
                    "continent": continent,
                    "country": country,
                    "region": region,
                    "trigger_type": trigger_category,
                    "trigger_category": trigger_category,
                    "headline": title,
                    "source_outlet": outlet or "Not resolved from feed metadata",
                    "score": keyword_score,
                    "score_type": "HEURISTIC_KEYWORD_RELEVANCE_NOT_PROBABILITY",
                    "talent_demand": "EXPLICIT_HIRING_MENTION" if explicit_hiring else "NO_EXPLICIT_HIRING_MENTION",
                    "published_date": published_at[:10] if published_at else None,
                    "published_at": published_at,
                    "published_date_raw": published_raw or None,
                    "event_date": None,
                    "event_date_status": "NOT_EXTRACTED",
                    "source_url": source_url,
                    "source_type": "NEWS_AGGREGATOR_RESULT",
                    "evidence_excerpt": excerpt,
                    "discovery_record_sha256": record_fingerprint,
                    "verification_status": "DISCOVERED_NEEDS_PRIMARY_VERIFICATION",
                    "status": "DISCOVERED_NEEDS_PRIMARY_VERIFICATION",
                    "retrieved_at": retrieved_at,
                })

        df = pd.DataFrame(records) if records else pd.DataFrame(columns=[
            "organization_name", "entity_resolution_status", "website", "website_status",
            "continent", "country", "region", "trigger_category", "headline",
            "source_outlet", "score", "score_type", "talent_demand", "published_date",
            "published_at", "published_date_raw", "event_date", "event_date_status",
            "source_url", "source_type", "evidence_excerpt", "discovery_record_sha256",
            "verification_status", "status", "retrieved_at",
        ])

        country_slug = re.sub(r"[^a-zA-Z0-9]+", "_", country.lower())
        region_slug = re.sub(r"[^a-zA-Z0-9]+", "_", clean_region.lower()) if clean_region else "all"
        output_dir = BASE_DIR / "data" / "discovery_runs"
        output_dir.mkdir(parents=True, exist_ok=True)
        excel_path = output_dir / f"scan_{country_slug}_{region_slug}_{run_stamp}.xlsx"
        csv_path = output_dir / f"scan_{country_slug}_{region_slug}_{run_stamp}.csv"
        df.to_excel(excel_path, index=False, engine="openpyxl")
        df.to_csv(csv_path, index=False, encoding="utf-8")
        return df, excel_path, csv_path
