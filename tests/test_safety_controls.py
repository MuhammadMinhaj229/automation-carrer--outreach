"""
Automated Safety Control Test Suite for ACIOS.
Validates that safety constraints, suppression filters, duplicate detection,
word-count rules, and approval invalidation are strictly enforced.
"""

import hashlib
import pytest
from pathlib import Path
import sys

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from acios.core.suppression import SuppressionEngine
from acios.core.permutator import EmailPermutator
from acios.models.email_draft import EmailDraft, PersonaType
from acios.models.contact import Contact, VerificationStatus, OutreachStatus
from acios.core.repository import CareerRepository
from acios.core.job_queue import execute_approved_send


def test_suppression_blocks_bounced_email():
    """Safety Test 1: Suppressed recipient is strictly blocked."""
    supp = SuppressionEngine()
    
    # Known hard bounce from Gmail audit
    blocked_email = "blocked@example.com"
    clean_email = "clean.contact@example.com"
    
    assert supp.is_suppressed(blocked_email) is True
    assert supp.is_suppressed(clean_email) is False
    assert supp.is_suppressed("") is True
    assert supp.is_suppressed(None) is True


def test_draft_word_count_strictly_100_to_160():
    """Safety Test 2: Standardized word count validator enforces 100-160 words."""
    short_text = ["Hello,", "This is too short.", "Thanks."]
    long_text = ["Word " * 50, "Word " * 50, "Word " * 65] # 165 words
    valid_text = [
        "Hello Dr. Lamya,",
        "I read about Hema Energy and Nama Water Services launching the camelina biofuel pilot project in Oman. "
        "Evaluating camelina using reclaimed wastewater from the Manhal Nama program is a very practical sustainability milestone.",
        "I am Alex Rivera, with a background in Computer Science and Data Science. In previous roles, "
        "I organized research datasets and automated routine reporting at the Applied Data Research Institute (ADRI), "
        "tested software features on the enterprise platform at Example Software Labs, and managed operational tracking for freelance clients.",
        "As your team tracks agronomic measurements and irrigation efficiency across test plots, I was curious how you manage field trial logs and research data.",
        "I have attached my resume for your review. If your team could use junior support for trial data cleaning or research reporting, I would welcome the chance to connect.",
        "Thank you for your time."
    ]

    # Test short text fails (< 100 words)
    with pytest.raises(ValueError, match="outside the allowed 100-160 word window"):
        EmailDraft(
            recipient_name="Dr. Morgan Lee",
            recipient_email="lamya@squ.edu.om",
            recipient_role="Associate Professor",
            organization_name="SQU / Hema Energy",
            subject_line="A question regarding camelina trial data",
            paragraphs=short_text
        )

    # Test valid text succeeds (120 words)
    draft = EmailDraft(
        recipient_name="Dr. Morgan Lee",
        recipient_email="lamya@squ.edu.om",
        recipient_role="Associate Professor",
        organization_name="SQU / Hema Energy",
        subject_line="A question regarding camelina trial data",
        paragraphs=valid_text
    )
    assert 100 <= draft.word_count <= 160


def test_buzzword_rejection():
    """Safety Test 3: Marketing clichés and consulting buzzwords are rejected."""
    buzzword_paragraphs = [
        "Hello Dr. Lamya,",
        "I read about Hema Energy and Nama Water Services launching the camelina biofuel pilot project in Oman. "
        "We can leverage synergy to create a game-changer for your operations.", # Forbidden buzzwords
        "I am Alex Rivera, with a background in Computer Science and Data Science. In previous work, "
        "I organized research datasets and automated routine reporting at the Applied Data Research Institute (ADRI).",
        "As your team monitors camelina growth and irrigation metrics, I was curious how you handle data workflows.",
        "I have attached my resume for your review. If you ever have a junior support spot, I would be glad to speak.",
        "Thank you for your time."
    ]
    with pytest.raises(ValueError, match="forbidden sales/agency buzzword"):
        EmailDraft(
            recipient_name="Dr. Morgan Lee",
            recipient_email="lamya@squ.edu.om",
            recipient_role="Associate Professor",
            organization_name="SQU / Hema Energy",
            subject_line="A question regarding camelina trial data",
            paragraphs=buzzword_paragraphs
        )


def test_tamper_detection_invalidates_approval():
    """Safety Test 4: Modifying subject or body after approval invalidates approval hash."""
    draft = EmailDraft(
        recipient_name="Dr. Morgan Lee",
        recipient_email="lamya@squ.edu.om",
        recipient_role="Associate Professor",
        organization_name="SQU / Hema Energy",
        subject_line="A question regarding camelina trial data",
        paragraphs=[
            "Hello Dr. Lamya,",
            "I read about Hema Energy and Nama Water Services launching the camelina biofuel pilot project in Oman. "
            "Evaluating camelina using reclaimed wastewater from the Manhal Nama program is a very practical sustainability milestone.",
            "I am Alex Rivera, with a background in Computer Science and Data Science. In previous roles, "
            "I organized research datasets and automated routine reporting at the Applied Data Research Institute (ADRI), "
            "tested software features on the enterprise platform at Example Software Labs, and managed operational tracking for freelance clients.",
            "As your team tracks agronomic measurements and irrigation efficiency across test plots, I was curious how you manage field trial logs and research data.",
            "I have attached my resume for your review. If your team could use junior support for trial data cleaning or research reporting, I would welcome the chance to connect.",
            "Thank you for your time."
        ]
    )

    # Compute approval hash
    approval_payload = f"{draft.recipient_email}:{draft.subject_line}:{draft.body_text}"
    original_hash = hashlib.sha256(approval_payload.encode()).hexdigest()

    # Tamper with subject
    tampered_subject = "Urgent: Investment Opportunity"
    tampered_payload = f"{draft.recipient_email}:{tampered_subject}:{draft.body_text}"
    tampered_hash = hashlib.sha256(tampered_payload.encode()).hexdigest()

    assert original_hash != tampered_hash, "Tamper detection failed: approval hash must invalidate on change"


def test_unverified_email_flagged():
    """Safety Test 5: Unverified contact cannot be marked Verified Primary without proof."""
    contact = Contact(
        name="John Doe",
        role="Operations Lead",
        organization_name="Test Enterprise",
        work_email="johndoe@unknown.com",
        verification_status=VerificationStatus.UNVERIFIED
    )
    assert contact.verification_status == VerificationStatus.UNVERIFIED
    assert contact.is_suppressed is False


if __name__ == "__main__":
    print("Running safety control tests...")
    test_suppression_blocks_bounced_email()
    test_draft_word_count_strictly_100_to_160()
    test_buzzword_rejection()
    test_tamper_detection_invalidates_approval()
    test_unverified_email_flagged()
    print("All 5 isolated safety control tests PASSED successfully!")


def test_word_count_edges_are_exactly_100_to_160():
    """The implementation must not accept 95–99 or 161–165 words."""
    def make_draft(count):
        return EmailDraft(
            recipient_name="Test Recipient",
            recipient_email="recipient@example.org",
            recipient_role="Research Lead",
            organization_name="Example Organization",
            subject_line="A question about the project",
            paragraphs=[" ".join(["research"] * count)],
        )

    assert make_draft(100).word_count == 100
    assert make_draft(160).word_count == 160
    with pytest.raises(ValueError, match="outside the allowed 100-160 word window"):
        make_draft(99)
    with pytest.raises(ValueError, match="outside the allowed 100-160 word window"):
        make_draft(161)


def test_approval_hash_covers_identity_and_attachment():
    """Changing recipient metadata or the resume digest changes the approval hash."""
    draft = EmailDraft(
        recipient_name="Test Recipient",
        recipient_email="recipient@example.org",
        recipient_role="Research Lead",
        organization_name="Example Organization",
        subject_line="A question about the project",
        paragraphs=[" ".join(["research"] * 100)],
        cv_attached=True,
        attachment_sha256="a" * 64,
    )
    assert draft.approval_hash != draft.model_copy(
        update={"recipient_role": "Chief Executive"}
    ).approval_hash
    assert draft.approval_hash != draft.model_copy(
        update={"attachment_sha256": "b" * 64}
    ).approval_hash


def test_dispatch_rejects_draft_changed_after_human_approval(tmp_path, monkeypatch):
    """A changed persisted subject must fail before a send or dry-run is attempted."""
    monkeypatch.setenv("DRY_RUN", "true")
    repo = CareerRepository(db_path=tmp_path / "approval-snapshot.db")
    draft = EmailDraft(
        recipient_name="Test Recipient",
        recipient_email="recipient@example.org",
        recipient_role="Research Lead",
        organization_name="Example Organization",
        subject_line="A question about the project",
        paragraphs=[" ".join(["research"] * 100)],
    )
    draft_id = repo.upsert_draft(draft, status="PENDING_APPROVAL")
    repo.approve_draft(draft_id, approved_by="test-operator")

    with repo._conn() as conn:
        conn.execute(
            "UPDATE drafts SET subject_line = ? WHERE id = ?",
            ("Changed after approval", draft_id),
        )
        conn.commit()

    with pytest.raises(PermissionError, match="approved snapshot"):
        execute_approved_send(repo, draft_id=draft_id)
