"""
Unit tests for ACIOS Multi-Stage Email Verification Waterfall.
"""

import sys
from pathlib import Path
import pytest

PACKAGE_ROOT = Path(__file__).resolve().parent.parent
if str(PACKAGE_ROOT) not in sys.path:
    sys.path.insert(0, str(PACKAGE_ROOT))

from acios.core.interfaces import VerificationResult
from acios.models.contact import VerificationStatus
from acios.providers.verification.dns_verifier import DNSMXVerifier
from acios.providers.verification.disposable_verifier import DisposableRoleVerifier
from acios.providers.verification.hunter_provider import HunterVerifier
from acios.providers.verification.waterfall import EmailVerificationWaterfall
from acios.core.repository import CareerRepository


def test_syntax_and_dns_verifier():
    verifier = DNSMXVerifier()

    # Syntax test
    assert verifier.check_syntax("valid.user@company.com") is True
    assert verifier.check_syntax("invalid..syntax@domain.com") is False
    assert verifier.check_syntax("no-at-sign.com") is False

    # MX verification for well-known domain
    res = verifier.verify("test@gmail.com")
    assert res.mx_valid is True
    assert len(res.mx_records) > 0

    # Non-existent domain
    res_fake = verifier.verify("fake@nonexistent-domain-9876543210-xyz.org")
    assert res_fake.confidence_score == 0.1
    assert res_fake.mx_valid is False


def test_disposable_and_role_verifier():
    verifier = DisposableRoleVerifier()

    # Disposable domain
    res_disp = verifier.verify("burner@mailinator.com")
    assert res_disp.is_disposable is True
    assert res_disp.confidence_score == 0.0

    # Role account
    res_role = verifier.verify("careers@uvera.co")
    assert res_role.is_role_account is True
    assert res_role.status == VerificationStatus.CORPORATE_ROUTE
    assert res_role.confidence_score == 0.4

    # Individual decision maker
    res_ind = verifier.verify("asrar@uvera.co")
    assert res_ind.is_role_account is False
    assert res_ind.is_disposable is False
    assert res_ind.confidence_score >= 0.7


def test_waterfall_suppression_gate(tmp_path):
    test_db = tmp_path / "test_waterfall.db"
    repo = CareerRepository(test_db)
    repo.add_suppression("hardbounce@blocked.com", reason="Hard bounce", source="Test")

    # Mock waterfall with temporary repo
    from acios.core.suppression import SuppressionEngine
    supp = SuppressionEngine()
    # Inject suppression directly
    supp.block("hardbounce@blocked.com")

    wf = EmailVerificationWaterfall(suppression_engine=supp, repository=repo)

    # 1. Blocked email
    res_blocked = wf.verify_email("hardbounce@blocked.com")
    assert res_blocked.status == VerificationStatus.BOUNCED_SUPPRESSED
    assert res_blocked.confidence_score == 0.0
    assert "REJECTED" in res_blocked.details

    # 2. Disposable email
    res_disp = wf.verify_email("user@guerrillamail.com")
    assert res_disp.status == VerificationStatus.UNVERIFIED
    assert res_disp.confidence_score == 0.0

    # 3. Valid corporate domain
    res_clean = wf.verify_email("asrar@uvera.co")
    assert res_clean.confidence_score >= 0.7
    assert res_clean.mx_valid is True
