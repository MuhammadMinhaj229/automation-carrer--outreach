"""Offline safety regressions for the legacy weekly contact persistence boundary."""

import pytest

from acios.flows import weekly_enrichment


def _fn(task):
    return getattr(task, "fn", task)


def test_nonempty_unreviewed_contacts_fail_before_repository_initialization(monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("No repository, database, or network access allowed")

    monkeypatch.setattr(weekly_enrichment, "CareerRepository", forbidden)
    lead = {
        "organization_name": "Synthetic Example",
        "name": "Unverified Person",
        "role": "Engineer",
        "work_email": "synthetic@example.invalid",
        "verification_status": "Verified",
        "notes": "Untrusted caller label",
    }
    with pytest.raises(RuntimeError, match="human approval"):
        _fn(weekly_enrichment.persist_enriched_contacts)([lead])


def test_empty_contact_batch_has_no_side_effects(monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("Empty batch must not initialize repository")

    monkeypatch.setattr(weekly_enrichment, "CareerRepository", forbidden)
    assert _fn(weekly_enrichment.persist_enriched_contacts)([]) == 0


def test_claimed_provenance_cannot_bypass_review(monkeypatch):
    monkeypatch.setattr(
        weekly_enrichment,
        "CareerRepository",
        lambda: (_ for _ in ()).throw(AssertionError("Repository opened")),
    )
    with pytest.raises(RuntimeError, match="human approval"):
        _fn(weekly_enrichment.persist_enriched_contacts)([
            {
                "organization_name": "Synthetic Example",
                "name": "Unverified Person",
                "work_email": "synthetic@example.invalid",
                "verification_status": "Verified",
                "source_url": "https://example.org",
                "approved": True,
            }
        ])
