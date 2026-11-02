"""Deterministic, private-data-free tests for the canonical SQLite exporters."""

import openpyxl
import pytest

from acios.core.database import get_db_connection, init_db
from acios.reports.export import export_excel, export_drafts_markdown


@pytest.fixture
def seeded_db(tmp_path):
    """Create only synthetic, explicitly staged records; never read data/acios.db."""
    db_path = tmp_path / "export-fixture.db"
    init_db(db_path)
    with get_db_connection(db_path) as conn:
        conn.execute(
            "INSERT INTO organizations (name, country, sector, created_at) VALUES (?, ?, ?, ?)",
            ("Example Research Lab", "OM", "Research", "2026-01-01T00:00:00+00:00"),
        )
        conn.execute(
            """INSERT INTO drafts (
                recipient_email, recipient_name, organization_name, recipient_role,
                subject_line, body_text, word_count, approval_hash, status, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                "reviewer@example.com",
                "Example Recipient",
                "Example Research Lab",
                "Researcher",
                "Synthetic draft for an isolated export test.",
                "This is synthetic test content and must not be sent.",
                10,
                "a" * 64,
                "PENDING_APPROVAL",
                "2026-01-01T00:00:00+00:00",
            ),
        )
    return db_path


def test_export_excel(tmp_path, seeded_db):
    output_excel = tmp_path / "Test_Master_Database.xlsx"
    export_excel(db_path=seeded_db, output_path=output_excel)

    assert output_excel.exists()
    wb = openpyxl.load_workbook(output_excel, data_only=True)
    assert {"Executive Summary", "All Organizations",
            "Decision Makers & Contacts", "Outreach Ledger"} <= set(wb.sheetnames)
    ws_orgs = wb["All Organizations"]
    assert ws_orgs.max_row == 2  # one header and exactly one synthetic organization
    assert ws_orgs["A2"].value == "Example Research Lab"
    assert ws_orgs["B2"].value == "OM"


def test_export_drafts_markdown(tmp_path, seeded_db):
    output_md = tmp_path / "Test_Drafts.md"
    export_drafts_markdown(db_path=seeded_db, output_path=output_md)

    assert output_md.exists()
    content = output_md.read_text(encoding="utf-8")
    assert "**Total Verified Staged Drafts:** 1" in content
    assert "### Draft #1: Example Research Lab — Example Recipient" in content
    assert "reviewer@example.com" in content
    assert "PENDING_APPROVAL" in content


def test_empty_database_exports_are_valid(tmp_path):
    """A clean installation has no seeded companies or fabricated draft entries."""
    db_path = tmp_path / "empty.db"
    init_db(db_path)
    excel_path = tmp_path / "empty.xlsx"
    markdown_path = tmp_path / "empty.md"
    export_excel(db_path=db_path, output_path=excel_path)
    export_drafts_markdown(db_path=db_path, output_path=markdown_path)

    wb = openpyxl.load_workbook(excel_path, data_only=True)
    assert wb["All Organizations"].max_row == 1
    content = markdown_path.read_text(encoding="utf-8")
    assert "**Total Verified Staged Drafts:** 0" in content
    assert "### Draft #" not in content
