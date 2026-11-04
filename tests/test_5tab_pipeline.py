"""
ACIOS 5-Tab Pipeline Integration & Unit Test Suite.

Live website/provider coverage is opt-in. The normal CI suite uses isolated
SQLite fixtures and verifies local behavior without relying on private records.
"""

import pytest

from acios.core.ai_copilot import AICopilotWriter
from acios.core.repository import CareerRepository
from acios.core.smtp_dispatcher import SMTPDispatcher
from acios.core.suppression import SuppressionEngine
from acios.models.email_draft import EmailDraft
from acios.tools.discovery.executive_intelligence import ExecutiveIntelligenceFinder
from acios.tools.discovery.growth_scanner import (
    COUNTRY_REGIONS,
    GrowthSignalScanner,
)
from acios.tools.discovery.linkedin_hunter import LinkedInHunter


@pytest.fixture
def repo(tmp_path):
    """Give each test a fresh local database; never read the operator's data/acios.db."""
    return CareerRepository(db_path=tmp_path / "acios-test.sqlite3")


@pytest.mark.live_integration
def test_tab1_growth_scanner(repo):
    scanner = GrowthSignalScanner(repo=repo)
    assert "Saudi Arabia" in COUNTRY_REGIONS
    assert "Oman" in COUNTRY_REGIONS
    assert len(COUNTRY_REGIONS["Oman"]) >= 3

    frame, excel_path, csv_path = scanner.scan_ecosystem(
        country="Oman",
        region="Sohar (Green Port, Biofuels, Agritech & Metals)",
        trigger_category="Biofuel, Clean Tech & Agritech",
        max_results=2,
    )
    assert excel_path.exists()
    assert csv_path.exists()
    assert excel_path.suffix == ".xlsx"
    assert csv_path.suffix == ".csv"


def test_tab2_linkedin_hunter_does_not_invent_organization_identity(repo):
    hunter = LinkedInHunter(repo=repo)

    audit = hunter.audit_organization("Example Energy Ltd")

    assert audit["verification_status"] == "UNVERIFIED_NO_SOURCE_BACKED_DOMAIN"
    assert audit["trigger_confirmed"] is False
    assert audit["website"] is None
    assert audit["domain"] is None
    assert "linkedin.com/search/results/companies/" in audit["manual_company_search_url"]

    # No contacts are fabricated or promoted from a search URL.
    assert hunter.hunt_decision_makers("Example Energy Ltd") == []


def test_tab2_linkedin_hunter_keeps_stored_contacts_unverified(repo):
    connection = repo._conn()
    try:
        connection.execute(
            """
            INSERT INTO organizations (name, country, sector, website, created_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                "Example Energy Ltd",
                "United Arab Emirates",
                "Energy",
                "https://example.test",
                "2026-01-01T00:00:00+00:00",
            ),
        )
        connection.execute(
            """
            INSERT INTO contacts (
                organization_name, name, role, work_email, linkedin_url,
                verification_status, notes, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "Example Energy Ltd",
                "Test Contact",
                "Operations Director",
                "contact@example.test",
                "https://www.linkedin.com/in/example-test-contact",
                "Previously stored; needs review",
                "Synthetic fixture contact; not independently verified.",
                "2026-01-01T00:00:00+00:00",
            ),
        )
        connection.commit()
    finally:
        connection.close()

    hunter = LinkedInHunter(repo=repo)
    audit = hunter.audit_organization("Example Energy Ltd")
    leads = hunter.hunt_decision_makers("Example Energy Ltd")

    assert audit["verification_status"] == "STORED_RECORD_NEEDS_REVALIDATION"
    assert audit["trigger_confirmed"] is False
    assert len(leads) == 1
    assert leads[0]["name"] == "Test Contact"
    assert leads[0]["linkedin_url"] is None
    assert leads[0]["stored_profile_url_needs_revalidation"].endswith(
        "/example-test-contact"
    )
    assert leads[0]["email"] is None
    assert leads[0]["verified"] is False


def test_tab3_executive_intelligence_uses_isolated_source_records(repo):
    timestamp = "2026-01-01T00:00:00+00:00"
    connection = repo._conn()
    try:
        connection.execute(
            """
            INSERT INTO organizations (
                name, country, sector, value_proposition, created_at
            )
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                "Example Energy Ltd",
                "United Arab Emirates",
                "Renewable Energy",
                "Synthetic test organization.",
                timestamp,
            ),
        )
        connection.executemany(
            """
            INSERT INTO signals (
                organization_name, headline, signal_date, source_url,
                evidence_tier, details, created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    "Example Energy Ltd",
                    "Synthetic renewable fuels feasibility study",
                    "2026-01-01",
                    "https://example.test/news/renewable-fuels",
                    "DISCOVERED_NEEDS_PRIMARY_VERIFICATION",
                    "Test fixture only; not a real-world claim.",
                    timestamp,
                ),
                (
                    "Example Energy Ltd",
                    "Synthetic wastewater process evaluation",
                    "2026-01-02",
                    "https://example.test/news/wastewater",
                    "DISCOVERED_NEEDS_PRIMARY_VERIFICATION",
                    "Test fixture only; not a real-world claim.",
                    timestamp,
                ),
            ],
        )
        connection.execute(
            """
            INSERT INTO contacts (
                organization_name, name, role, notes, updated_at
            )
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                "Example Energy Ltd",
                "Test Executive",
                "Group Managing Director",
                "Synthetic note: technical areas include biofuels and wastewater reuse.",
                timestamp,
            ),
        )
        connection.commit()
    finally:
        connection.close()

    finder = ExecutiveIntelligenceFinder(repo=repo)
    history = finder.extract_career_history(
        "Test Executive",
        "Group Managing Director",
        "Example Energy Ltd",
    )

    assert history["organization"] == "Example Energy Ltd"
    assert history["name"] == "Test Executive"
    assert history["milestones"] == [
        "Synthetic renewable fuels feasibility study",
        "Synthetic wastewater process evaluation",
        "Synthetic note: technical areas include biofuels and wastewater reuse.",
    ]
    # The role-based focus is a heuristic; the method does not infer a verified
    # technical specialty from synthetic notes.
    assert history["technical_focus"] == (
        "Strategy, Capital Allocation, Regional Operations"
    )


def test_tab4_ai_copilot(repo):
    copilot = AICopilotWriter()
    history = {
        "technical_focus": "Biofuels, Wastewater Recycling",
        "career_summary": "Synthetic example: supporting a camelina trial.",
        "milestones": ["Synthetic national camelina trial", "Synthetic wastewater irrigation"],
    }
    draft = copilot.generate_initial_draft(
        target_name="Test Executive",
        target_role="Group Managing Director",
        target_org="Example Energy Ltd",
        target_email="test.executive@example.test",
        target_history=history,
    )
    assert 100 <= draft.word_count <= 160
    assert "Example Energy Ltd" in draft.subject_line

    revised_body, _revised_subject, explanation = copilot.refine_draft_with_guidance(
        current_body=draft.body_text,
        current_subject=draft.subject_line,
        target_name="Test Executive",
        target_org="Example Energy Ltd",
        target_role="Group Managing Director",
        user_guidance="Make it concise and technical",
        target_history=history,
    )
    word_count = copilot.calculate_word_count(revised_body)
    assert 100 <= word_count <= 160
    assert len(explanation) > 5


def test_tab5_smtp_and_attachment(repo):
    suppression = SuppressionEngine()
    dispatcher = SMTPDispatcher(repo=repo, supp=suppression)

    sample_body = (
        "Dear Director,\n\n"
        "I am reviewing the operational information published by your organization and the "
        "data controls that support reliable reporting across complex projects. "
        "Consistent validation can help teams identify missing variables, anomalies, and "
        "inconsistencies before records reach production dashboards.\n\n"
        "In a synthetic project example, I used Python validation scripts to check multi-source "
        "research datasets and flag issues for review. I also practiced structured feature "
        "quality assurance and regression testing to improve the reliability of application "
        "workflows.\n\n"
        "I would welcome the opportunity to understand whether data verification or workflow "
        "automation is relevant to any current operational priorities. I would be glad to share "
        "a short technical example for your team to assess."
    )

    draft = EmailDraft(
        recipient_email="test.recipient@example.test",
        recipient_name="Test Recipient",
        organization_name="Example Energy Ltd",
        recipient_role="Director",
        subject_line="Data quality and workflow automation",
        body_text=sample_body,
    )

    message = dispatcher.build_message(draft)
    assert message["To"] == "test.recipient@example.test"
    assert message.is_multipart()

    suppression.add_suppression("blocked.user@example.test")
    blocked_draft = EmailDraft(
        recipient_email="blocked.user@example.test",
        recipient_name="Blocked User",
        organization_name="Example Energy Ltd",
        recipient_role="CEO",
        subject_line="Data quality and workflow automation",
        body_text=sample_body,
    )
    with pytest.raises(PermissionError, match="Direct SMTP sending is disabled"):
        dispatcher.send_direct(blocked_draft)
