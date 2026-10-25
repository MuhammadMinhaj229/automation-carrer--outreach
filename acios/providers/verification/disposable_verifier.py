"""
ACIOS Stage 2: Disposable Domain & Role-Based Inbox Detector.
Filters out temporary burner email providers and flags generic organizational mailboxes.
"""

from typing import Set, Optional
from acios.core.interfaces import VerifierProvider, VerificationResult
from acios.models.contact import VerificationStatus

COMMON_DISPOSABLE_DOMAINS: Set[str] = {
    "mailinator.com", "guerrillamail.com", "10minutemail.com", "tempmail.com",
    "throwawaymail.com", "fakeinbox.com", "yopmail.com", "dispostable.com",
    "trashmail.com", "sharklasers.com", "getairmail.com", "temp-mail.org",
    "maildrop.cc", "mohmal.com", "burnermail.io", "inboxkitten.com"
}

ROLE_BASED_PREFIXES: Set[str] = {
    "info", "support", "sales", "contact", "careers", "jobs", "hr", "admin",
    "marketing", "billing", "press", "media", "help", "office", "team",
    "hello", "general", "inquiry", "enquiries", "feedback", "recruitment"
}


class DisposableRoleVerifier(VerifierProvider):
    """Stage 2: Disposable and Role-Account Screening."""

    def __init__(self, custom_disposable: Optional[Set[str]] = None):
        self.disposable_domains = set(COMMON_DISPOSABLE_DOMAINS)
        if custom_disposable:
            self.disposable_domains.update(custom_disposable)

    def is_disposable(self, domain: str) -> bool:
        return domain.lower() in self.disposable_domains

    def is_role_account(self, local_part: str) -> bool:
        clean = local_part.lower().split("+")[0]
        return clean in ROLE_BASED_PREFIXES

    def verify(self, email: str) -> VerificationResult:
        clean_email = (email or "").strip().lower()
        if "@" not in clean_email:
            return VerificationResult(
                email=clean_email,
                status=VerificationStatus.UNVERIFIED,
                confidence_score=0.0,
                provider="DisposableRoleVerifier",
                details="Malformed address, missing @"
            )

        local_part, domain = clean_email.split("@", 1)
        disposable = self.is_disposable(domain)
        role_account = self.is_role_account(local_part)

        if disposable:
            return VerificationResult(
                email=clean_email,
                status=VerificationStatus.UNVERIFIED,
                confidence_score=0.0,
                is_disposable=True,
                is_role_account=role_account,
                provider="DisposableRoleVerifier",
                details="Disposable/burner domain detected"
            )

        if role_account:
            return VerificationResult(
                email=clean_email,
                status=VerificationStatus.CORPORATE_ROUTE,
                confidence_score=0.4,
                is_disposable=False,
                is_role_account=True,
                provider="DisposableRoleVerifier",
                details="Role-based generic mailbox (e.g. info@, careers@)"
            )

        return VerificationResult(
            email=clean_email,
            status=VerificationStatus.PATTERN_PREDICTED,
            confidence_score=0.7,
            is_disposable=False,
            is_role_account=False,
            provider="DisposableRoleVerifier",
            details="Individual decision-maker mailbox passed domain screening"
        )
