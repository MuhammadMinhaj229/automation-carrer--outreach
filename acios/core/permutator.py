"""
RFC-822 Email Permutator Engine.
Generates candidate email addresses based on person name and corporate domain.
"""

import re
from typing import List


class EmailPermutator:
    @staticmethod
    def clean_name(part: str) -> str:
        """Removes honorifics, titles, and non-alphanumeric characters."""
        part = re.sub(r"^(dr\.?|prof\.?|eng\.?|mr\.?|ms\.?|mrs\.?)\s+", "", part, flags=re.IGNORECASE)
        part = re.sub(r"[^a-zA-Z]", "", part)
        return part.lower()

    @classmethod
    def generate_patterns(cls, full_name: str, domain: str) -> List[str]:
        """
        Generates standard B2B email permutations:
        - first@domain
        - first.last@domain
        - flast@domain
        - firstlast@domain
        - f.last@domain
        - first_last@domain
        """
        clean_domain = domain.strip().lower().lstrip("@")
        name_parts = [cls.clean_name(p) for p in full_name.split() if cls.clean_name(p)]

        if not name_parts or not clean_domain:
            return []

        first = name_parts[0]
        last = name_parts[-1] if len(name_parts) > 1 else ""

        candidates = [f"{first}@{clean_domain}"]

        if last:
            f_initial = first[0]
            l_initial = last[0]
            candidates.extend([
                f"{first}.{last}@{clean_domain}",
                f"{first}{last}@{clean_domain}",
                f"{f_initial}{last}@{clean_domain}",
                f"{f_initial}.{last}@{clean_domain}",
                f"{first}_{last}@{clean_domain}",
                f"{first}{l_initial}@{clean_domain}",
            ])

        # Deduplicate while preserving pattern order
        seen = set()
        deduped = []
        for c in candidates:
            if c not in seen:
                seen.add(c)
                deduped.append(c)

        return deduped
