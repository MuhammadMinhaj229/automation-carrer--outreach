"""Offline regressions for the no-evidence/no-write weekly flow boundary."""

from acios.flows import weekly_enrichment


def _underlying(callable_object):
    return getattr(callable_object, "fn", callable_object)


def test_no_generated_leads_never_open_persistence_or_export(monkeypatch):
    monkeypatch.setattr(
        weekly_enrichment,
        "identify_target_organizations",
        lambda limit: [{"name": "Synthetic Organization", "website": "example.org"}],
    )
    monkeypatch.setattr(weekly_enrichment, "generate_and_verify_candidates", lambda orgs: [])

    def forbidden(*args, **kwargs):
        raise AssertionError("Empty discovery must not write or export")

    monkeypatch.setattr(weekly_enrichment, "persist_enriched_contacts", forbidden)
    monkeypatch.setattr(weekly_enrichment, "export_all", forbidden)
    assert _underlying(weekly_enrichment.run_weekly_enrichment)(batch_size=1) == 0


def test_no_organizations_never_generate_persist_or_export(monkeypatch):
    monkeypatch.setattr(weekly_enrichment, "identify_target_organizations", lambda limit: [])

    def forbidden(*args, **kwargs):
        raise AssertionError("Empty target set must not perform enrichment side effects")

    monkeypatch.setattr(weekly_enrichment, "generate_and_verify_candidates", forbidden)
    monkeypatch.setattr(weekly_enrichment, "persist_enriched_contacts", forbidden)
    monkeypatch.setattr(weekly_enrichment, "export_all", forbidden)
    assert _underlying(weekly_enrichment.run_weekly_enrichment)(batch_size=5) == 0
