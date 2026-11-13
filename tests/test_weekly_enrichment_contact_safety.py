"""Offline regressions: organization metadata cannot become invented contacts."""

from acios.flows import weekly_enrichment


def test_weekly_enrichment_never_fabricates_contacts(monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("No verification or network provider may run")

    # Legacy workflow must not call a provider, even with a plausible domain.
    monkeypatch.setattr(weekly_enrichment, "persist_enriched_contacts", forbidden)
    orgs = [
        {"name": "Example Research", "website": "https://example.org"},
        {"name": "Unknown Domain", "website": None},
        {"name": "Ambiguous Company", "website": "example.net"},
    ]
    task = weekly_enrichment.generate_and_verify_candidates
    assert getattr(task, "fn", task)(orgs) == []


def test_weekly_flow_does_not_persist_or_export_guesses(monkeypatch):
    monkeypatch.setattr(
        weekly_enrichment, "identify_target_organizations",
        lambda limit: [{"name": "Example Research", "website": "example.org"}],
    )

    def forbidden(*args, **kwargs):
        raise AssertionError("No contact writes or exports are allowed")

    monkeypatch.setattr(weekly_enrichment, "persist_enriched_contacts", forbidden)
    monkeypatch.setattr(weekly_enrichment, "export_all", forbidden)
    flow = weekly_enrichment.run_weekly_enrichment
    assert getattr(flow, "fn", flow)(batch_size=1) == 0
