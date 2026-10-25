"""
Unit tests for ACIOS Outreach State Machine and Evidence-Based Draft Generator.
"""

import sys
from pathlib import Path
import pytest

PACKAGE_ROOT = Path(__file__).resolve().parent.parent
if str(PACKAGE_ROOT) not in sys.path:
    sys.path.insert(0, str(PACKAGE_ROOT))

from acios.core.state_machine import OutreachStateMachine, ContactLifecycleState, StateTransitionError
from acios.core.generator import DraftGenerator
from acios.models.contact import Contact, VerificationStatus


def test_state_machine_valid_transitions():
    sm = OutreachStateMachine()

    # Valid forward path
    s1 = sm.transition(ContactLifecycleState.DISCOVERED, ContactLifecycleState.RESEARCHED)
    assert s1 == ContactLifecycleState.RESEARCHED

    s2 = sm.transition(s1, ContactLifecycleState.CONTACT_VERIFIED)
    assert s2 == ContactLifecycleState.CONTACT_VERIFIED

    s3 = sm.transition(
        s2, ContactLifecycleState.DRAFT_STAGED,
        is_suppressed=False,
        verification_status="Verified Primary (Direct Match)",
        word_count=135
    )
    assert s3 == ContactLifecycleState.DRAFT_STAGED

    s4 = sm.transition(s3, ContactLifecycleState.APPROVED)
    assert s4 == ContactLifecycleState.APPROVED

    s5 = sm.transition(s4, ContactLifecycleState.DISPATCHED)
    assert s5 == ContactLifecycleState.DISPATCHED

    s6 = sm.transition(s5, ContactLifecycleState.REPLIED)
    assert s6 == ContactLifecycleState.REPLIED


def test_state_machine_safety_violations():
    sm = OutreachStateMachine()

    # 1. Illegal transition skip
    with pytest.raises(StateTransitionError, match="Illegal lifecycle transition"):
        sm.transition(ContactLifecycleState.DISCOVERED, ContactLifecycleState.DISPATCHED)

    # 2. Blocked by suppression
    with pytest.raises(StateTransitionError, match="Safety Gate Violation"):
        sm.transition(
            ContactLifecycleState.CONTACT_VERIFIED, 
            ContactLifecycleState.DRAFT_STAGED, 
            is_suppressed=True
        )

    # 3. Blocked by word count
    with pytest.raises(StateTransitionError, match="Word Count Gate Violation"):
        sm.transition(
            ContactLifecycleState.CONTACT_VERIFIED,
            ContactLifecycleState.DRAFT_STAGED,
            verification_status="Verified Primary (Direct Match)",
            word_count=85
        )


def test_draft_generator_experience_selection():
    gen = DraftGenerator()

    # AgriTech / Biofuel -> PHFI
    exp_agri = gen.select_experience("Green Tech & Biofuels", "Lead Researcher")
    assert "Public Health Foundation of India" in exp_agri.get("organization", "")

    # AI / Software -> Ejada Labs
    exp_ai = gen.select_experience("Artificial Intelligence", "Senior Software Engineer")
    assert "Ejada Labs" in exp_ai.get("organization", "")

    # Operations -> Freelance
    exp_ops = gen.select_experience("Logistics & Supply Chain", "Operations Director")
    assert "Independent Client" in exp_ops.get("organization", "")


def test_draft_generator_full_compliance():
    gen = DraftGenerator()
    contact = Contact(
        name="Azzan Al Asmy",
        role="Group Managing Director",
        organization_name="Hema Energy",
        work_email="azzan@hema.om",
        verification_status=VerificationStatus.VERIFIED_PRIMARY
    )

    draft = gen.generate_draft(
        contact,
        sector="Energy & Clean Tech",
        signal_headline="expansion of camelina biofuel trial with treated wastewater"
    )

    assert draft.recipient_name == "Azzan Al Asmy"
    assert 100 <= draft.word_count <= 160
    assert len(draft.paragraphs) >= 3
    assert draft.approval_hash is not None
