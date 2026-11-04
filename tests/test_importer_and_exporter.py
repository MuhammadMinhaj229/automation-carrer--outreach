"""
Unit tests for the canonical exporters using isolated, synthetic SQLite data.

Tests must never depend on the operator's private data/acios.db or assume
that a CI runner contains a pre-populated prospect database.
"""

from pathlib import Path

import openpyxl

from acios.core.repository import CareerRepository
from acios.reports.export import export_drafts_markdown, export_excel


def _seed_export_database(db_path: Path) -> None:
    """Create a small deterministic database containing synthetic test records."""
    repo = CareerRepository(db_path=db_path)
    timestamp = "2026-01-01T00:00:00+00:00"
    connection = repo._conn()
    try:
        connection.executemany(
            """
            INSERT INTO organizations (
                name, country, sector, website, value_proposition, created_at
            )
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    "Example Energy Ltd",
                    "United Arab Emirates",
                    "Renewable Energy",
                    "https://example.test",
                    "Synthetic test organization.",
                    timestamp,
                ),
                (
                    "Example Water Services",
                    "Oman",
                    "Water",
                    "https://water.example.test",
                    "Synthetic test organization.",
                    timestamp,
                ),
            ],
        )
        connection.execute(
            """
            INSERT INTO signals (
                organization_name, headline, signal_date, source_url,
                evidence_tier, details, created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "Example Energy Ltd",
                "Synthetic renewable fuels feasibility study",
                "2026-01-01",
                "https://example.test/news/renewable-fuels",
                "DISCOVERED_NEEDS_PRIMARY_VERIFICATION",
                "Test fixture only; not a real-world claim.",
                timestamp,
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
                None,
                "UNVERIFIED",
                "Synthetic fixture only.",
                timestamp,
            ),
        )
        body = (
            "This is a synthetic test draft used only to validate the Markdown exporter. "
            * 12
        ).strip()
        connection.execute(
            """
            INSERT INTO drafts (
                recipient_email, recipient_name, organization_name, recipient_role,
                subject_line, body_text, word_count, approval_hash, status, created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "test.contact@example.test",
                "Test Contact",
                "Example Energy Ltd",
                "Operations Director",
                "Synthetic test subject",
                body,
                len(body.split()),
                "a" * 64,
                "PENDING_APPROVAL",
                timestamp,
            ),
        )
        connection.execute(
            """
            INSERT INTO outreach_events (recipient_email, event_type, timestamp, details)
            VALUES (?, ?, ?, ?)
            """,
            (
                "test.contact@example.test",
                "DRAFT_STAGED_FOR_REVIEW",
                timestamp,
                "Synthetic fixture event; no message was sent.",
            ),
        )
        connection.commit()
    finally:
        connection.close()


def test_export_excel_uses_only_supplied_database(tmp_path):
    db_path = tmp_path / "fixture.sqlite3"
    _seed_export_database(db_path)
    output_excel = tmp_path / "Test_Master_Database.xlsx"

    export_excel(db_path=db_path, output_path=output_excel)

    assert output_excel.exists()
    workbook = openpyxl.load_workbook(output_excel, data_only=True)
    assert "Executive Summary" in workbook.sheetnames
    assert "All Organizations" in workbook.sheetnames
    assert "Decision Makers & Contacts" in workbook.sheetnames
    assert "Outreach Ledger" in workbook.sheetnames

    organizations = workbook["All Organizations"]
    assert organizations.max_row == 3  # Header plus the two seeded organizations.
    assert organizations["A2"].value == "Example Water Services"
    assert organizations["A3"].value == "Example Energy Ltd"

    contacts = workbook["Decision Makers & Contacts"]
    assert contacts.max_row == 2
    assert contacts["A2"].value == "Test Contact"

    ledger = workbook["Outreach Ledger"]
    assert ledger.max_row == 2
    assert ledger["F2"].value == "DRAFT_STAGED_FOR_REVIEW"


def test_export_drafts_markdown_uses_only_supplied_database(tmp_path):
    db_path = tmp_path / "fixture.sqlite3"
    _seed_export_database(db_path)
    output_markdown = tmp_path / "Test_Drafts.md"

    export_drafts_markdown(db_path=db_path, output_path=output_markdown)

    assert output_markdown.exists()
    content = output_markdown.read_text(encoding="utf-8")
    assert "### Draft #1: Example Energy Ltd — Test Contact" in content
    assert "test.contact@example.test" in content
    assert "Synthetic test draft used only to validate the Markdown exporter" in content
    assert "**Total Verified Staged Drafts:** 1" in content


def test_exporters_handle_an_empty_database(tmp_path):
    db_path = tmp_path / "empty.sqlite3"
    CareerRepository(db_path=db_path)
    output_excel = tmp_path / "Empty_Master_Database.xlsx"
    output_markdown = tmp_path / "Empty_Drafts.md"

    export_excel(db_path=db_path, output_path=output_excel)
    export_drafts_markdown(db_path=db_path, output_path=output_markdown)

    workbook = openpyxl.load_workbook(output_excel, data_only=True)
    assert workbook["All Organizations"].max_row == 1
    assert "**Total Verified Staged Drafts:** 0" in output_markdown.read_text(
        encoding="utf-8"
    )
