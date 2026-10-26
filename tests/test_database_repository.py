"""
Unit and integration tests for ACIOS SQLite database engine and CareerRepository.
"""

import sys
from pathlib import Path
import pytest
import sqlite3

PACKAGE_ROOT = Path(__file__).resolve().parent.parent
if str(PACKAGE_ROOT) not in sys.path:
    sys.path.insert(0, str(PACKAGE_ROOT))

from acios.core.database import get_db_connection, init_db
from acios.core.repository import CareerRepository
from acios.models.organization import Organization, ExpansionSignal, SectorCategory
from acios.models.contact import Contact, VerificationStatus, OutreachStatus
from acios.models.email_draft import EmailDraft


@pytest.fixture
def temp_db(tmp_path):
    test_db_path = tmp_path / "test_acios.db"
    init_db(test_db_path)
    return test_db_path


def test_init_db_creates_all_tables(temp_db):
    conn = get_db_connection(temp_db)
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = {row[0] for row in cursor.fetchall()}
    conn.close()

    expected_tables = {"organizations", "signals", "contacts", "drafts", "suppression", "outreach_events"}
    assert expected_tables.issubset(tables)


def test_organization_and_signal_upsert(temp_db):
    repo = CareerRepository(temp_db)
    org = Organization(
        name="Test AgTech",
        country="Saudi Arabia",
        city="Riyadh",
        sector=SectorCategory.AGRITECH,
        website="https://test-agtech.sa",
        signals=[
            ExpansionSignal(
                headline="KSA Vision 2030 Pilot Launch",
                source_url="https://vision2030.gov.sa/agtech",
                details="Government research contract for hydroponics",
                signal_date="2026-10-24"
            )
        ]
    )
    repo.upsert_organization(org)

    saved = repo.get_organization("Test AgTech")
    assert saved is not None
    assert saved["country"] == "Saudi Arabia"
    assert len(saved["signals"]) == 1
    assert saved["signals"][0]["headline"] == "KSA Vision 2030 Pilot Launch"


def test_contact_upsert_and_suppression_check(temp_db):
    repo = CareerRepository(temp_db)
    
    # 1. Add suppression
    repo.add_suppression("blocked@example.com", reason="Hard bounce test", source="Unit Test")
    assert repo.is_suppressed("blocked@example.com") is True
    assert repo.is_suppressed("clean@example.com") is False

    # 2. Add contact
    contact = Contact(
        name="Omar Al-Hassan",
        role="Chief Technology Officer",
        organization_name="Test AgTech",
        work_email="omar@test-agtech.sa",
        verification_status=VerificationStatus.VERIFIED_PRIMARY
    )
    repo.upsert_contact(contact)

    contacts = repo.list_contacts("Test AgTech")
    assert len(contacts) == 1
    assert contacts[0]["name"] == "Omar Al-Hassan"
    assert contacts[0]["role"] == "Chief Technology Officer"


def test_draft_upsert_and_hash_integrity(temp_db):
    repo = CareerRepository(temp_db)
    p1 = "Dear Omar,"
    p2 = "I came across your recent telemetry expansion in the region. At the Applied Data Research Institute (ADRI), I built automated Python validation pipelines for large health datasets, systematically detecting missing variables and cleaning inconsistencies across field reports. At Example Software Labs, I conducted rigorous QA and end-to-end regression testing on enterprise AI systems to guarantee reliable data ingestion."
    p3 = "During independent client projects, I also developed continuous data cleaning scripts that prevented malformed records from propagating into production reporting dashboards. Given your focus on operational data integrity, I would welcome the opportunity to support your engineering team with data cleaning and automation workflows."
    p4 = "Would you be open to a brief 10-minute conversation next week to explore where I could add value?"
    draft = EmailDraft(
        recipient_email="omar@test-agtech.sa",
        recipient_name="Omar",
        organization_name="Test AgTech",
        recipient_role="Chief Technology Officer",
        subject_line="Research data workflows & telemetry at Test AgTech",
        paragraphs=[p1, p2, p3, p4]
    )
    repo.upsert_draft(draft)

    drafts = repo.list_drafts()
    assert len(drafts) == 1
    assert drafts[0]["recipient_email"] == "omar@test-agtech.sa"
    assert drafts[0]["approval_hash"] == draft.approval_hash
    assert 100 <= drafts[0]["word_count"] <= 160
