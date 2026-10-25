"""
ACIOS Stage 1: DNS & MX Record Verifier.
Validates RFC-5322 syntax and resolves mail exchanger (MX) records for the recipient domain.
"""

import re
import socket
from typing import List, Optional
try:
    import dns.resolver
    DNS_AVAILABLE = True
except ImportError:
    DNS_AVAILABLE = False

from acios.core.interfaces import VerifierProvider, VerificationResult
from acios.models.contact import VerificationStatus

EMAIL_REGEX = re.compile(
    r"^(?!\.)(?!.*\.\.)([A-Za-z0-9_'+\-\.]*)[A-Za-z0-9_+-]@([A-Za-z0-9][A-Za-z0-9\-]*\.)+[A-Za-z]{2,}$"
)


class DNSMXVerifier(VerifierProvider):
    """Stage 1: RFC Syntax & DNS MX lookup with fast in-memory caching."""

    def __init__(self, timeout: float = 2.0):
        self.timeout = timeout
        self._mx_cache: dict[str, List[str]] = {}

    def check_syntax(self, email: str) -> bool:
        """Validates format according to RFC 5322."""
        if not email or len(email) > 254:
            return False
        return bool(EMAIL_REGEX.match(email.strip()))

    def resolve_mx(self, domain: str) -> List[str]:
        """Queries DNS for MX records with memory caching."""
        clean_domain = (domain or "").strip().lower()
        if not clean_domain:
            return []
        if clean_domain in self._mx_cache:
            return self._mx_cache[clean_domain]

        mx_records = []
        if DNS_AVAILABLE:
            try:
                resolver = dns.resolver.Resolver()
                resolver.timeout = self.timeout
                resolver.lifetime = self.timeout
                answers = resolver.resolve(clean_domain, 'MX')
                # Sort by preference
                sorted_answers = sorted(answers, key=lambda r: r.preference)
                for rdata in sorted_answers:
                    mx_records.append(str(rdata.exchange).rstrip('.'))
                self._mx_cache[clean_domain] = mx_records
                return mx_records
            except (dns.resolver.NXDOMAIN, dns.resolver.NoAnswer, dns.resolver.NoNameservers, dns.exception.Timeout):
                pass
            except Exception:
                pass

        # Fallback to standard socket A/AAAA lookup if MX query fails or dnspython unavailable
        try:
            socket.gethostbyname(clean_domain)
            mx_records = [f"A-record-fallback:{clean_domain}"]
            self._mx_cache[clean_domain] = mx_records
            return mx_records
        except Exception:
            self._mx_cache[clean_domain] = []
            return []

    def verify(self, email: str) -> VerificationResult:
        clean_email = (email or "").strip().lower()
        if not self.check_syntax(clean_email):
            return VerificationResult(
                email=clean_email,
                status=VerificationStatus.UNVERIFIED,
                confidence_score=0.0,
                mx_valid=False,
                provider="DNSMXVerifier",
                details="Invalid RFC 5322 email syntax"
            )

        domain = clean_email.split("@")[1]
        mx_list = self.resolve_mx(domain)

        if not mx_list:
            return VerificationResult(
                email=clean_email,
                status=VerificationStatus.UNVERIFIED,
                confidence_score=0.1,
                mx_valid=False,
                provider="DNSMXVerifier",
                details=f"Domain '{domain}' has no valid MX or A DNS records"
            )

        return VerificationResult(
            email=clean_email,
            status=VerificationStatus.PATTERN_PREDICTED,
            confidence_score=0.6,
            mx_valid=True,
            mx_records=mx_list,
            provider="DNSMXVerifier",
            details=f"Valid MX exchange records found: {', '.join(mx_list[:2])}"
        )
