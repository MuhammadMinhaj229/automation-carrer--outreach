"""
ACIOS 5-Tab Pipeline Integration & Unit Test Suite.
Validates:
1. GrowthSignalScanner (Tab 1)
2. LinkedInHunter (Tab 2)
3. ExecutiveIntelligenceFinder (Tab 3)
4. AICopilotWriter (Tab 4)
5. SMTPDispatcher & DraftEngine with PDF Attachments (Tab 5)
"""

import os
import pytest
from pathlib import Path
from acios.core.repository import CareerRepository
from acios.core.suppression import SuppressionEngine
from acios.core.draft_engine import DraftEngine
from acios.core.smtp_dispatcher import SMTPDispatcher
from acios.core.ai_copilot import AICopilotWriter
from acios.tools.discovery.growth_scanner import GrowthSignalScanner, COUNTRY_REGIONS, TRIGGER_CATEGORIES
from acios.tools.discovery.linkedin_hunter import LinkedInHunter
from acios.tools.discovery.executive_intelligence import ExecutiveIntelligenceFinder
from acios.models.email_draft import EmailDraft


@pytest.fixture
def repo():
    return CareerRepository()


@pytest.mark.live_integration\ndef test_tab1_growth_scanner(repo):
    scanner = GrowthSignalScanner(repo=repo)
    assert "Saudi Arabia" in COUNTRY_REGIONS
    assert "Oman" in COUNTRY_REGIONS
    assert len(COUNTRY_REGIONS["Oman"]) >= 3
    
    # Test scan
    df, excel_path, csv_path = scanner.scan_ecosystem(
        country="Oman",
        region="Sohar (Green Port, Biofuels, Agritech & Metals)",
        trigger_category="Biofuel, Clean Tech & Agritech",
        max_results=2
    )
    assert excel_path.exists()
    assert csv_path.exists()
    assert excel_path.suffix == ".xlsx"
    assert csv_path.suffix == ".csv"


@pytest.mark.live_integration\ndef test_tab2_linkedin_hunter(repo):
    hunter = LinkedInHunter(repo=repo)
    audit = hunter.audit_organization("Hema Energy")
    assert audit["verification_status"] == "Verified Active Entity"
    
    dms = hunter.hunt_decision_makers("Hema Energy")
    assert len(dms) >= 1
    # Check that linkedin url is present and formatted
    for dm in dms:
        assert "linkedin.com" in dm["linkedin_url"]
        assert len(dm["name"]) > 2


def test_tab3_executive_intelligence(repo):
    finder = ExecutiveIntelligenceFinder(repo=repo)
    hist = finder.extract_career_history("Azzan Moghrob Rashid Al Asmy", "Group Managing Director", "Hema Energy")
    assert "Hema Energy" in hist["organization"]
    assert len(hist["milestones"]) >= 2
    assert "Biofuels" in hist["technical_focus"]


def test_tab4_ai_copilot(repo):
    copilot = AICopilotWriter()
    hist = {
        "technical_focus": "Biofuels, Wastewater Recycling",
        "career_summary": "Leading camelina trial in Oman",
        "milestones": ["National camelina trial", "Wastewater irrigation"]
    }
    draft = copilot.generate_initial_draft(
        target_name="Azzan Al Asmy",
        target_role="Group Managing Director",
        target_org="Hema Energy",
        target_email="alex.rivera@example.com",
        target_history=hist
    )
    assert 100 <= draft.word_count <= 160
    assert "Hema Energy" in draft.subject_line

    # Test conversational refinement
    rev_body, rev_subj, exp = copilot.refine_draft_with_guidance(
        current_body=draft.body_text,
        current_subject=draft.subject_line,
        target_name="Azzan Al Asmy",
        target_org="Hema Energy",
        target_role="Group Managing Director",
        user_guidance="Make it concise and technical",
        target_history=hist
    )
    wc = copilot.calculate_word_count(rev_body)
    assert 100 <= wc <= 160
    assert len(exp) > 5


def test_tab5_smtp_and_attachment(repo):
    supp = SuppressionEngine()
    dispatcher = SMTPDispatcher(repo=repo, supp=supp)
    draft_engine = DraftEngine()

    sample_body = (
        "Dear Director,\n\n"
        "I have been closely following your organization's recent expansion initiatives and operational developments across the region. "
        "Given the growing complexity of data tracking in scaling operations, I wanted to reach out regarding data infrastructure hygiene.\n\n"
        "At the Applied Data Research Institute (ADRI), I built automated Python validation scripts for extensive multi-source research datasets, "
        "systematically identifying missing variables, anomalies, and reporting inconsistencies before records entered production dashboards. "
        "Additionally, at Example Software Labs, I conducted structured feature QA and regression testing to ensure enterprise platform data stability.\n\n"
        "If your team has bandwidth for an assistant dedicated to data verification and workflow automation, I would welcome a brief conversation."
    )

    draft = EmailDraft(
        recipient_email="test.recipient@example.com",
        recipient_name="Test Recipient",
        organization_name="Test Org",
        recipient_role="Director",
        subject_line="Data systems and automation at Test Org",
        body_text=sample_body
    )

    # Build MIME message with attachment
    msg = dispatcher.build_message(draft)
    assert msg["To"] == "test.recipient@example.com"
    assert msg.is_multipart()

    # Pre-Flight Suppression Block Test
    supp.add_suppression("blocked.user@example.com")
    draft_blocked = EmailDraft(
        recipient_email="blocked.user@example.com",
        recipient_name="Blocked User",
        organization_name="Blocked Org",
        recipient_role="CEO",
        subject_line="Data systems and automation at Blocked Org",
        body_text=sample_body
    )
    with pytest.raises(PermissionError, match="Direct SMTP sending is disabled"):
        dispatcher.send_direct(draft_blocked)
