"""
Tests for ACIOS FastMCP Server.
Verifies tool registration, narrow authorized MCP tool execution, and safety controls via MCP protocol.
"""

import asyncio
from pathlib import Path
import sys

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

import acios.mcp_server as mcp_module
from acios.mcp_server import mcp


def test_fastmcp_tools_registered():
    """Verify all core and narrow authorized tools are registered on the FastMCP instance."""
    async def _run():
        tools = await mcp.list_tools()
        tool_names = [t.name for t in tools]
        expected_tools = [
            "search_growth_signals",
            "get_company_dossier",
            "verify_contact",
            "create_outreach_draft",
            "list_pending_approvals",
            "send_approved_outreach",
            "get_job_status",
            "verify_suppression",
            "permute_email",
            "validate_email_draft",
        ]
        for et in expected_tools:
            assert et in tool_names, f"Tool '{et}' is missing from FastMCP registration"
        assert "approve_outreach" not in tool_names, "Machine-callable draft approval must remain disabled"
    asyncio.run(_run())


def test_fastmcp_permute_email_tool_is_disabled():
    """The compatibility tool must not manufacture contact-address guesses."""
    async def _run():
        res = await mcp.call_tool(
            "permute_email",
            {"name": "Synthetic Person", "domain": "example.org"},
        )
        payload = res.structured_content
        assert payload["status"] == "DISABLED_POLICY"
        assert payload["candidates"] == []
        assert "speculative contact enrichment" in payload["message"].lower()
    asyncio.run(_run())


def test_fastmcp_verify_suppression_checks_sqlite_and_compatibility_store(
    monkeypatch, tmp_path
):
    """Both local suppression stores must block the MCP status tool."""
    from acios.core.repository import CareerRepository
    from acios.core.suppression import SuppressionEngine

    repo = CareerRepository(db_path=tmp_path / "mcp-suppression.db")
    repo.add_suppression(
        "sqlite-blocked@example.org",
        reason="synthetic test opt-out",
        source="test fixture",
    )
    compatibility = SuppressionEngine(suppression_files=[])
    compatibility.block("memory-blocked@example.org")
    monkeypatch.setattr(mcp_module, "CareerRepository", lambda: repo)
    monkeypatch.setattr(mcp_module, "suppression_engine", compatibility)

    async def _run():
        for email in ("sqlite-blocked@example.org", "memory-blocked@example.org"):
            res = await mcp.call_tool("verify_suppression", {"email": email})
            payload = res.structured_content
            assert payload["is_suppressed"] is True
            assert payload["status"] == "BLOCKED"
            assert payload["check_status"] == "COMPLETE"
            assert payload["action_required"] == "DO NOT CONTACT"
    asyncio.run(_run())


def test_fastmcp_verify_suppression_fails_closed_on_repository_error(monkeypatch):
    """A failed SQLite suppression read must never be reported as clean."""
    from acios.core.suppression import SuppressionEngine

    class BrokenRepository:
        def is_suppressed(self, _email):
            raise RuntimeError("synthetic database failure")

    monkeypatch.setattr(mcp_module, "CareerRepository", BrokenRepository)
    monkeypatch.setattr(
        mcp_module, "suppression_engine", SuppressionEngine(suppression_files=[])
    )

    async def _run():
        res = await mcp.call_tool(
            "verify_suppression", {"email": "candidate@example.org"}
        )
        payload = res.structured_content
        assert payload["is_suppressed"] is True
        assert payload["status"] == "BLOCKED"
        assert payload["check_status"] == "FAILED_CLOSED"
        assert payload["error_type"] == "RuntimeError"
    asyncio.run(_run())




def test_fastmcp_email_waterfall_blocks_sqlite_suppression_before_provider(
    monkeypatch, tmp_path
):
    """A SQLite suppression match must stop verification before provider access."""
    from acios.core.repository import CareerRepository
    from acios.core.suppression import SuppressionEngine

    repo = CareerRepository(db_path=tmp_path / "mcp-waterfall-suppression.db")
    repo.add_suppression(
        "blocked-before-dns@example.org",
        reason="synthetic test opt-out",
        source="test fixture",
    )
    monkeypatch.setattr(mcp_module, "CareerRepository", lambda: repo)
    monkeypatch.setattr(
        mcp_module, "suppression_engine", SuppressionEngine(suppression_files=[])
    )

    def forbidden(*args, **kwargs):
        raise AssertionError("Verification providers must not run for suppressed input")

    monkeypatch.setattr(mcp_module, "EmailVerificationWaterfall", forbidden)

    async def _run():
        res = await mcp.call_tool(
            "verify_email_waterfall",
            {"email": "blocked-before-dns@example.org"},
        )
        payload = res.structured_content
        assert payload["status"] == "BOUNCED_SUPPRESSED"
        assert payload["is_suppressed"] is True
        assert payload["check_status"] == "COMPLETE"
        assert payload["provider"] == "LocalSuppressionPreflight"
    asyncio.run(_run())


def test_fastmcp_validate_email_draft_tool():
    """Verify draft validation tool enforces length and buzzword safety."""
    async def _run():
        valid_paras = [
            "Hello Dr. Morgan,",
            "I read about Acme Energy launching its sustainable industrial analytics pilot project this quarter. "
            "Evaluating operational telemetry across distributed sites is a practical engineering milestone.",
            "I am Alex Rivera, with a background in Computer Science and Data Science. In previous roles, "
            "I organized research datasets and automated routine reporting for an applied analytics lab, "
            "tested backend software features for an enterprise platform, and managed operational tracking for client projects.",
            "As your team tracks sensor measurements and operational efficiency across test sites, I was curious how you manage field trial logs and validation pipelines.",
            "I have attached my resume for your review. If your team could use support for data cleaning or engineering reporting, I would welcome the chance to connect.",
            "Thank you for your time."
        ]

        res_valid = await mcp.call_tool("validate_email_draft", {
            "recipient_name": "Dr. Morgan Lee",
            "recipient_email": "morgan.lee@example.org",
            "recipient_role": "Director of Engineering",
            "organization_name": "Acme Energy",
            "subject_line": "A question regarding pilot telemetry data",
            "paragraphs": valid_paras
        })
        assert res_valid.structured_content["status"] == "VALIDATED_PENDING_APPROVAL"
        assert 100 <= res_valid.structured_content["word_count"] <= 160
        assert "human approval" in res_valid.structured_content["note"].lower()
    asyncio.run(_run())


def test_fastmcp_metrics_and_draft_generation():
    """Verify metrics query and calibrated draft generation tools via FastMCP."""
    async def _run():
        res_m = await mcp.call_tool("get_database_metrics", {})
        metrics = res_m.structured_content
        assert "total_organizations" in metrics
        assert "total_contacts" in metrics

        res_d = await mcp.call_tool("generate_calibrated_draft", {
            "name": "Jordan Taylor",
            "work_email": "jordan.taylor@example.com",
            "role": "Projects Engineer",
            "organization_name": "Acme Energy",
            "sector": "Energy & Industrial Analytics",
            "trigger_signal": "industrial analytics pilot project"
        })
        draft_data = res_d.structured_content
        assert draft_data["recipient_name"] == "Jordan Taylor"
        assert 90 <= draft_data["word_count"] <= 170
    asyncio.run(_run())


def test_mcp_send_tool_disabled_in_local_first_mode():
    """MCP retains compatibility but cannot trigger a programmatic send."""
    async def _run():
        res = await mcp.call_tool(
            "send_approved_outreach",
            {"draft_id": 1, "idempotency_key": "compat-test-001"},
        )
        payload = res.structured_content
        assert payload["status"] == "DISABLED_LOCAL_FIRST"
        assert "manually" in payload["message"].lower()
    asyncio.run(_run())
