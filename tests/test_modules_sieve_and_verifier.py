"""
Unit tests for ACIOS modular architecture: ContactFinderEngine and DeliverabilityShield.
"""

import sys
from pathlib import Path
import pytest

PACKAGE_ROOT = Path(__file__).resolve().parent.parent
if str(PACKAGE_ROOT) not in sys.path:
    sys.path.insert(0, str(PACKAGE_ROOT))

from acios.modules.contracts import CandidateEmail, DeliverabilityVerdict, DeliverabilityStatus
from acios.modules.m3_contact_finder.finder import ContactFinderEngine
from acios.modules.m4_deliverability.verifier import DeliverabilityShield


def test_contact_finder_permutations():
    finder = ContactFinderEngine()
    perms = finder.generate_permutations("Mohammed Minhaj", "example.com")
    
    emails = [p.email for p in perms]
    assert "mohammed@example.com" in emails
    assert "mohammed.minhaj@example.com" in emails
    assert "mminhaj@example.com" in emails
    assert "m.minhaj@example.com" in emails
    assert "mohammed_minhaj@example.com" in emails
    assert "minhaj@example.com" in emails


def test_deliverability_shield_syntax_gate():
    shield = DeliverabilityShield()
    
    # Invalid email
    v_invalid = shield.verify_sync("not-an-email")
    assert not v_invalid.is_deliverable
    assert v_invalid.status == DeliverabilityStatus.INVALID_SYNTAX
    assert "RFC 5322" in v_invalid.details


def test_deliverability_shield_master_suppression():
    shield = DeliverabilityShield()
    
    # Add a mock email to suppression
    suppressed_email = "bounced_test_address@suppressed.org"
    shield.supp.block(suppressed_email)
    
    verdict = shield.verify_sync(suppressed_email)
    assert not verdict.is_deliverable
    assert verdict.status == DeliverabilityStatus.CONFIRMED_BOUNCE
