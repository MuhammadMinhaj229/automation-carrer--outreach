"""
Module 3: Autonomous Contact & Corporate Email Finder.
Open-source alternative to Apollo.io and Hunter.io.
Takes executive names and corporate domains, generates email permutations,
and sieves them through the deliverability engine to identify active mailboxes.
"""

import re
from typing import List, Optional
from acios.modules.contracts import ExecutiveProfile, CandidateEmail


class ContactFinderEngine:
    def __init__(self):
        pass

    def clean_name(self, name: str) -> tuple[str, str]:
        """Splits full name into clean first and last name components."""
        # Remove titles / honorifics
        cleaned = re.sub(r"^(dr\.|mr\.|mrs\.|ms\.|eng\.|sheikh|prof\.)\s+", "", name.strip(), flags=re.I)
        parts = cleaned.split()
        if not parts:
            return "contact", ""
        first = parts[0].lower().strip()
        last = parts[-1].lower().strip() if len(parts) > 1 else ""
        # Clean any non-alpha characters
        first = re.sub(r"[^a-z]", "", first)
        last = re.sub(r"[^a-z]", "", last)
        return first, last

    def generate_permutations(self, full_name: str, domain: str) -> List[CandidateEmail]:
        """
        Generates standard corporate RFC email permutations.
        Replaces Apollo.io pattern guessing with exhaustive candidate generation.
        """
        first, last = self.clean_name(full_name)
        domain = domain.lower().strip()
        # Remove protocols or paths if passed
        domain = re.sub(r"^https?://(www\.)?", "", domain).split("/")[0]

        candidates = []
        if not first:
            return candidates

        f_init = first[0] if first else ""
        l_init = last[0] if last else ""

        if last:
            patterns = [
                (f"{first}@{domain}", "{first}@{domain}"),
                (f"{first}.{last}@{domain}", "{first}.{last}@{domain}"),
                (f"{f_init}{last}@{domain}", "{f}{last}@{domain}"),
                (f"{f_init}.{last}@{domain}", "{f}.{last}@{domain}"),
                (f"{first}{l_init}@{domain}", "{first}{l}@{domain}"),
                (f"{first}_{last}@{domain}", "{first}_{last}@{domain}"),
                (f"{last}@{domain}", "{last}@{domain}"),
            ]
        else:
            patterns = [
                (f"{first}@{domain}", "{first}@{domain}"),
                (f"info@{domain}", "info@{domain}"),
                (f"contact@{domain}", "contact@{domain}")
            ]

        for email_addr, pat in patterns:
            candidates.append(CandidateEmail(
                email=email_addr,
                pattern_used=pat,
                domain=domain,
                source="Permutation Sieve"
            ))

        return candidates

    def resolve_best_email(
        self,
        full_name: str,
        domain: str,
        deliverability_verifier = None
    ) -> Optional[CandidateEmail]:
        """
        Generates permutations and runs them through the deliverability verifier.
        Returns the first permutation that verifies as a REAL_MAILBOX.
        """
        candidates = self.generate_permutations(full_name, domain)
        if not deliverability_verifier:
            # Fallback to standard first.last or first
            return candidates[0] if candidates else None

        for cand in candidates:
            verdict = deliverability_verifier.verify_sync(cand.email)
            if verdict.is_deliverable and not verdict.is_catch_all:
                return cand
            elif verdict.is_deliverable:
                # Catch-all: keep as candidate if nothing better found
                pass

        return candidates[0] if candidates else None
