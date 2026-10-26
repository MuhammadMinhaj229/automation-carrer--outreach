"""
ACIOS Stage 3 Executive Email & History Intelligence Finder.
Performs:
1. Multi-Stage Email Permutation & Waterfall Verification (DNS MX, disposable check, confidence score).
2. Sourced Background & Role Profiling from stored organization and contact records.
"""

import re
from typing import Any, Dict, Optional

from acios.core.permutator import EmailPermutator
from acios.core.repository import CareerRepository
from acios.providers.verification.waterfall import EmailVerificationWaterfall


class ExecutiveIntelligenceFinder:
    """Finds candidate emails and role dossiers for decision-makers."""

    def __init__(
        self,
        repo: Optional[CareerRepository] = None,
        waterfall: Optional[EmailVerificationWaterfall] = None,
    ):
        self.repo = repo or CareerRepository()
        self.waterfall = waterfall or EmailVerificationWaterfall()

    def find_and_verify_email(
        self, name: str, org_name: str, domain: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Derives business domain, generates permutations, runs the verification waterfall,
        and returns evidence-backed confidence metadata.
        """
        if not domain:
            org = self.repo.get_organization(org_name)
            if org and org.get("website"):
                raw_web = org["website"]
                domain = re.sub(r"^https?://(www\.)?", "", raw_web).split("/")[0]
            else:
                clean_slug = re.sub(r"[^a-zA-Z0-9]", "", org_name.lower())
                domain = f"{clean_slug}.com"

        db_contacts = self.repo.list_contacts(org_name=org_name)
        for c in db_contacts:
            if c["name"].lower() == name.lower() and c.get("work_email"):
                ver = self.waterfall.verify_email(c["work_email"])
                return {
                    "email": c["work_email"],
                    "confidence_score": ver.confidence_score,
                    "determination": ver.status.value,
                    "mx_valid": ver.mx_valid,
                    "verified": ver.confidence_score >= 0.85,
                    "source": "Database Contact Record",
                    "details": ver.details,
                }

        permutations = EmailPermutator.generate_patterns(name, domain)
        if not permutations:
            permutations = [f"{re.sub(r'[^a-zA-Z0-9]', '', name.lower())}@{domain}"]

        best_email = permutations[0]
        best_ver = self.waterfall.verify_email(best_email)

        for candidate in permutations[:4]:
            ver = self.waterfall.verify_email(candidate)
            if ver.confidence_score > best_ver.confidence_score:
                best_email = candidate
                best_ver = ver
            if ver.confidence_score >= 0.8:
                break

        return {
            "email": best_email,
            "confidence_score": best_ver.confidence_score,
            "determination": best_ver.status.value,
            "mx_valid": best_ver.mx_valid,
            "verified": False,
            "source": f"Pattern Permutator ({domain})",
            "details": best_ver.details,
        }

    def extract_career_history(
        self, name: str, role: str, org_name: str
    ) -> Dict[str, Any]:
        """
        Builds a role summary anchored strictly in stored contact notes and organization signals.
        """
        org = self.repo.get_organization(org_name) or {}
        signals = org.get("signals") or []
        contacts = self.repo.list_contacts(org_name=org_name)
        matched_contact = next(
            (c for c in contacts if (c.get("name") or "").lower() == name.lower()),
            {},
        )

        milestones = [s.get("headline") for s in signals if s.get("headline")][:3]
        notes = matched_contact.get("notes")
        if notes and notes not in milestones:
            milestones.append(notes)

        role_lower = role.lower()
        if any(t in role_lower for t in ["ceo", "founder", "managing director", "president"]):
            focus = "Strategy, Capital Allocation, Regional Operations"
        elif any(t in role_lower for t in ["technology", "engineering", "cto", "developer", "software", "tech"]):
            focus = "Data Systems, Cloud Infrastructure, Platform Engineering, Automation"
        elif any(t in role_lower for t in ["project", "operations", "vp", "director"]):
            focus = "Operational Delivery, Quality Control, Program Execution"
        else:
            focus = "Business Operations, Technical Execution"

        return {
            "name": name,
            "role": role,
            "organization": org_name,
            "career_summary": (
                f"{role} at {org_name}. "
                + (org.get("value_proposition") or "Sourced organization profile.")
            ),
            "milestones": milestones,
            "academic_background": "Not specified in public record",
            "technical_focus": focus,
            "evidence_backed": bool(milestones),
        }
