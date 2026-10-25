"""
Tests for ACIOS FastMCP Server.
Verifies tool registration, tool execution, resource access, and safety controls via MCP protocol.
"""

import asyncio
from pathlib import Path
import sys

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from acios.mcp_server import mcp


def test_fastmcp_tools_registered():
    """Verify all core tools are registered on the FastMCP instance."""
    async def _run():
        tools = await mcp.list_tools()
        tool_names = [t.name for t in tools]
        expected_tools = [
            "verify_suppression",
            "permute_email",
            "search_research_orgs",
            "search_wikidata_companies",
            "firecrawl_scrape_page",
            "firecrawl_map_domain",
            "validate_email_draft",
            "stage_draft_to_gmail"
        ]
        for et in expected_tools:
            assert et in tool_names, f"Tool '{et}' is missing from FastMCP registration"
    asyncio.run(_run())


def test_fastmcp_verify_suppression_tool():
    """Verify suppression tool catches blocked addresses and clears clean ones."""
    async def _run():
        # Test blocked address
        res_blocked = await mcp.call_tool("verify_suppression", {"email": "investors@metacon.se"})
        assert res_blocked.structured_content["is_suppressed"] is True
        assert res_blocked.structured_content["status"] == "BLOCKED"

        # Test clean address
        res_clean = await mcp.call_tool("verify_suppression", {"email": "layth@tathmeer.ai"})
        assert res_clean.structured_content["is_suppressed"] is False
        assert res_clean.structured_content["status"] == "CLEAN"
    asyncio.run(_run())


def test_fastmcp_permute_email_tool():
    """Verify email permutation tool generates candidates and marks suppression."""
    async def _run():
        res = await mcp.call_tool("permute_email", {"name": "Layth Dwairi", "domain": "tathmeer.ai"})
        candidates = res.structured_content["result"]
        assert len(candidates) >= 5
        emails = [c["candidate_email"] for c in candidates]
        assert "layth@tathmeer.ai" in emails
    asyncio.run(_run())


def test_fastmcp_validate_email_draft_tool():
    """Verify draft validation tool enforces length and buzzword safety."""
    async def _run():
        valid_paras = [
            "Hello Dr. Lamya,",
            "I read about Hema Energy and Nama Water Services launching the camelina biofuel pilot project in Oman. "
            "Evaluating camelina using reclaimed wastewater from the Manhal Nama program is a very practical sustainability milestone.",
            "I am Mohammed Minhaj, with a background in Computer Science and Data Science. In previous roles, "
            "I organized research datasets and automated routine reporting at the Public Health Foundation of India (PHFI), "
            "tested software features on Sanad AI at Ejada Labs, and managed operational tracking for freelance clients.",
            "As your team tracks agronomic measurements and irrigation efficiency across test plots, I was curious how you manage field trial logs and research data.",
            "I have attached my resume for your review. If your team could use junior support for trial data cleaning or research reporting, I would welcome the chance to connect.",
            "Thank you for your time."
        ]

        # Valid draft
        res_valid = await mcp.call_tool("validate_email_draft", {
            "recipient_name": "Dr. Lamya Al Haj",
            "recipient_email": "lamya@squ.edu.om",
            "recipient_role": "Associate Professor",
            "organization_name": "SQU",
            "subject_line": "A question regarding camelina trial data",
            "paragraphs": valid_paras
        })
        assert res_valid.structured_content["status"] == "APPROVED"
        assert 100 <= res_valid.structured_content["word_count"] <= 160

        # Blocked recipient
        res_blocked = await mcp.call_tool("validate_email_draft", {
            "recipient_name": "Blocked Contact",
            "recipient_email": "investors@metacon.se",
            "recipient_role": "Investor",
            "organization_name": "Metacon",
            "subject_line": "A question regarding data",
            "paragraphs": valid_paras
        })
        assert res_blocked.structured_content["status"] == "REJECTED"
    asyncio.run(_run())


def test_fastmcp_firecrawl_fallback():
    """Verify Firecrawl tool gracefully handles unconfigured state."""
    async def _run():
        res = await mcp.call_tool("firecrawl_scrape_page", {"url": "https://example.com"})
        assert res.structured_content["status"] in ["SUCCESS", "FALLBACK_SUCCESS", "ERROR"]
    asyncio.run(_run())


def test_fastmcp_metrics_and_draft_generation():
    """Verify metrics query and calibrated draft generation tools via FastMCP."""
    async def _run():
        # 1. Query metrics
        res_m = await mcp.call_tool("get_database_metrics", {})
        metrics = res_m.structured_content
        assert metrics["total_organizations"] >= 320
        assert metrics["total_contacts"] >= 230
        assert metrics["total_suppressed_emails"] >= 1600

        # 2. Generate calibrated draft
        res_d = await mcp.call_tool("generate_calibrated_draft", {
            "name": "Ibtihal Hassan",
            "work_email": "ibtihal@hema.om",
            "role": "Projects Engineer",
            "organization_name": "Hema Energy",
            "sector": "Energy & Sustainable Biofuels",
            "trigger_signal": "camelina pilot project with treated wastewater"
        })
        draft_data = res_d.structured_content
        assert draft_data["recipient_name"] == "Ibtihal Hassan"
        assert 100 <= draft_data["word_count"] <= 160
        assert "Public Health Foundation of India" in draft_data["body_text"]
    asyncio.run(_run())
