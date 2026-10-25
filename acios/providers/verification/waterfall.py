"""
ACIOS Multi-Stage Email Verification Waterfall Orchestrator.
Chains:
  - Gate 0: Master Suppression / Hard Bounce Registry Check
  - Gate 1: RFC-5322 Syntax & DNS MX Record Resolution
  - Gate 2: Disposable Domain & Role Account Screening
  - Gate 3: Hunter.io SMTP-Level Verification
Produces a consolidated deliverability determination with audit logs.
"""

from typing import Optional, List
from pathlib import Path

from acios.core.interfaces import VerificationResult
from acios.models.contact import VerificationStatus
from acios.core.suppression import SuppressionEngine
from acios.core.repository import CareerRepository
from acios.providers.verification.dns_verifier import DNSMXVerifier
from acios.providers.verification.disposable_verifier import DisposableRoleVerifier
from acios.providers.verification.hunter_provider import HunterVerifier


class EmailVerificationWaterfall:
    """Waterfall orchestrator executing multi-tier email verification."""

    def __init__(
        self,
        suppression_engine: Optional[SuppressionEngine] = None,
        dns_verifier: Optional[DNSMXVerifier] = None,
        disposable_verifier: Optional[DisposableRoleVerifier] = None,
        hunter_verifier: Optional[HunterVerifier] = None,
        repository: Optional[CareerRepository] = None
    ):
        self.suppression = suppression_engine or SuppressionEngine()
        self.dns = dns_verifier or DNSMXVerifier()
        self.disposable = disposable_verifier or DisposableRoleVerifier()
        self.hunter = hunter_verifier or HunterVerifier()
        self.repo = repository or CareerRepository()

    def verify_email(self, email: str, update_db: bool = False) -> VerificationResult:
        clean_email = (email or "").strip().lower()

        # Gate 0: Suppression Check
        if self.suppression.is_suppressed(clean_email):
            res = VerificationResult(
                email=clean_email,
                status=VerificationStatus.BOUNCED_SUPPRESSED,
                confidence_score=0.0,
                provider="SuppressionEngine",
                details="REJECTED: Recipient is listed on Master Suppression / Permanent Hard Bounce Registry"
            )
            if update_db:
                self._update_contact_record(clean_email, res, is_suppressed=True)
            return res

        # Gate 1: Syntax & DNS MX Check
        dns_res = self.dns.verify(clean_email)
        if not dns_res.mx_valid or dns_res.confidence_score == 0.0:
            res = VerificationResult(
                email=clean_email,
                status=VerificationStatus.UNVERIFIED,
                confidence_score=0.0,
                mx_valid=False,
                provider="DNSMXVerifier",
                details=f"REJECTED: {dns_res.details}"
            )
            if update_db:
                self._update_contact_record(clean_email, res, is_suppressed=False)
            return res

        # Gate 2: Disposable & Role Account Screening
        disp_res = self.disposable.verify(clean_email)
        if disp_res.is_disposable:
            res = VerificationResult(
                email=clean_email,
                status=VerificationStatus.UNVERIFIED,
                confidence_score=0.0,
                mx_valid=True,
                mx_records=dns_res.mx_records,
                is_disposable=True,
                provider="DisposableRoleVerifier",
                details="REJECTED: Temporary disposable domain detected"
            )
            if update_db:
                self._update_contact_record(clean_email, res, is_suppressed=False)
            return res

        # Gate 3: Hunter.io API Verification (if configured)
        if self.hunter.is_configured:
            hunter_res = self.hunter.verify(clean_email)
            composite_score = round((dns_res.confidence_score * 0.3) + (hunter_res.confidence_score * 0.7), 2)
            res = VerificationResult(
                email=clean_email,
                status=hunter_res.status,
                confidence_score=composite_score,
                mx_valid=True,
                mx_records=dns_res.mx_records,
                is_disposable=False,
                is_role_account=disp_res.is_role_account,
                provider="HunterVerifier+DNS",
                details=f"Waterfall verified. {hunter_res.details} (MX={len(dns_res.mx_records)})"
            )
        else:
            # Fallback when Hunter.io API is not active: DNS + Domain heuristics
            base_score = 0.4 if disp_res.is_role_account else 0.75
            status = VerificationStatus.PATTERN_PREDICTED
            res = VerificationResult(
                email=clean_email,
                status=status,
                confidence_score=base_score,
                mx_valid=True,
                mx_records=dns_res.mx_records,
                is_disposable=False,
                is_role_account=disp_res.is_role_account,
                provider="DNSMX+DomainHeuristics",
                details=f"DNS verified with {len(dns_res.mx_records)} MX records. RoleAccount={disp_res.is_role_account}"
            )

        if update_db:
            self._update_contact_record(clean_email, res, is_suppressed=False)
        return res

    def _update_contact_record(self, email: str, res: VerificationResult, is_suppressed: bool):
        try:
            with self.repo._conn() as conn:
                conn.execute("""
                    UPDATE contacts
                    SET verification_status = ?,
                        is_suppressed = ?,
                        notes = COALESCE(notes, '') || ' | ' || ?
                    WHERE LOWER(work_email) = ?
                """, (res.status.value, 1 if is_suppressed else 0, res.details, email))
                conn.commit()
        except Exception:
            pass
