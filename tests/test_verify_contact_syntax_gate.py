"""Offline regression checks for syntax-versus-suppression evidence semantics."""

import asyncio

from acios import api as api_module


def test_invalid_syntax_does_not_claim_suppression_match(monkeypatch):
    class UnexpectedLookup:
        def is_suppressed(self, _email):
            raise AssertionError("Invalid syntax must not query suppression storage")

    class UnexpectedVerifier:
        async def verify(self, _email):
            raise AssertionError("Invalid syntax must not perform DNS/network verification")

    monkeypatch.setattr(api_module, "repo", UnexpectedLookup())
    monkeypatch.setattr(api_module, "supp", UnexpectedLookup())
    monkeypatch.setattr(api_module, "reacher_verifier", UnexpectedVerifier())

    result = asyncio.run(
        api_module.tool_verify_contact(
            api_module.VerifyContactToolRequest(email=" invalid-syntax-email ")
        )
    )
    assert result["status"] == "INVALID_SYNTAX"
    assert result["evidence"] == ["rfc5322_syntax_failed"]
    assert result["valid"] is False
    assert result["verified"] is False
    assert result["is_suppressed"] is False
    assert result["confidence"] == 0.0


def test_valid_suppressed_address_preserves_registry_evidence(monkeypatch):
    class SuppressedRepo:
        def is_suppressed(self, email):
            return email == "blocked@example.org"

    class UnexpectedVerifier:
        async def verify(self, _email):
            raise AssertionError("Suppressed addresses must not be verified externally")

    monkeypatch.setattr(api_module, "repo", SuppressedRepo())
    monkeypatch.setattr(api_module, "reacher_verifier", UnexpectedVerifier())
    result = asyncio.run(
        api_module.tool_verify_contact(
            api_module.VerifyContactToolRequest(email="BLOCKED@example.org")
        )
    )
    assert result["status"] == "SUPPRESSED"
    assert result["evidence"] == ["master_suppression_match"]
    assert result["is_suppressed"] is True
