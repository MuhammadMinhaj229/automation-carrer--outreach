"""Offline regressions for the legacy RSS/Prefect discovery boundary.

These tests must never fetch external sites or write the user's local database.
"""

from types import SimpleNamespace

import pytest

from acios.core.interfaces import SignalItem
from acios.core.repository import CareerRepository
from acios.flows import daily_signal_scan
from acios.providers.signals import rss_provider
from acios.flows.weekly_enrichment import identify_target_organizations


def _signal(url="https://news.google.com/rss/articles/example", **kwargs):
    return SignalItem(
        headline=kwargs.pop("headline", "Example pilot expansion"),
        source_url=url,
        details="A search lead, not an independently verified event",
        score=90,
        **kwargs,
    )


def test_signal_model_defaults_to_unverified_and_unknown_identity():
    signal = _signal()
    assert signal.organization_name is None
    assert signal.signal_date is None
    assert signal.evidence_tier == "DISCOVERED_NEEDS_PRIMARY_VERIFICATION"


def test_rss_missing_date_does_not_invent_today_or_verified_organization(monkeypatch):
    feed = SimpleNamespace(entries=[
        {"title": "Example company launches pilot - News Outlet",
         "link": "https://news.google.com/rss/articles/example",
         "summary": "pilot expansion"},
        {"title": "No source link", "summary": "pilot expansion"},
        {"title": "", "link": "https://news.google.com/rss/articles/empty"},
        {"title": "Another pilot", "link": "javascript:alert(1)", "summary": "pilot"},
        {"title": "Credentialed pilot", "link": "https://user:pass@example.org/a",
         "summary": "pilot"},
    ])
    monkeypatch.setattr(rss_provider.feedparser, "parse", lambda _url: feed)
    signals = rss_provider.RSSSignalProvider().fetch_signals("Example company", min_score=50)
    assert len(signals) == 1
    assert signals[0].headline == "Example company launches pilot"
    assert signals[0].organization_name is None
    assert signals[0].signal_date is None
    assert signals[0].evidence_tier == "DISCOVERED_NEEDS_PRIMARY_VERIFICATION"


def test_rss_uses_only_explicit_parsed_publication_timestamp(monkeypatch):
    feed = SimpleNamespace(entries=[{
        "title": "Example investment - Outlet",
        "link": "https://news.google.com/rss/articles/dated",
        "summary": "investment",
        "published_parsed": (2026, 10, 20, 9, 30, 0, 1, 293, 0),
    }])
    monkeypatch.setattr(rss_provider.feedparser, "parse", lambda _url: feed)
    result = rss_provider.RSSSignalProvider().fetch_signals("investment")
    assert len(result) == 1
    assert result[0].signal_date == "2026-10-20T09:30:00+00:00"


def test_empty_feeds_produce_zero_signals_not_five_fabricated_events(monkeypatch):
    class EmptyProvider:
        def fetch_signals(self, _topic, min_score=60):
            return []

    monkeypatch.setattr(daily_signal_scan, "RSSSignalProvider", EmptyProvider)
    assert daily_signal_scan.fetch_expansion_signals(["Green Tech"]) == []


def test_fetch_deduplicates_and_never_trusts_provider_verification(monkeypatch):
    class UnsafeProvider:
        def fetch_signals(self, _topic, min_score=60):
            return [_signal(
                organization_name="Unverified Corporation",
                evidence_tier="Verified Primary",
            )]

    monkeypatch.setattr(daily_signal_scan, "RSSSignalProvider", UnsafeProvider)
    results = daily_signal_scan.fetch_expansion_signals(["Green Tech"])
    assert len(results) == 1
    assert results[0].organization_name is None
    assert results[0].evidence_tier == "DISCOVERED_NEEDS_PRIMARY_VERIFICATION"


def test_legacy_flow_persists_only_unverified_leads_in_source_ledger(monkeypatch, tmp_path):
    repo = CareerRepository(db_path=tmp_path / "signals.db")
    monkeypatch.setattr(daily_signal_scan, "CareerRepository", lambda: repo)
    unsafe = _signal(
        organization_name="Claimed Corp",
        evidence_tier="Verified Primary",
        signal_date="2026-10-20T09:30:00+00:00",
    )
    assert daily_signal_scan.filter_and_persist_signals([unsafe]) == 1

    events = repo.list_discovery_events()
    assert len(events) == 1
    assert events[0]["organization_name"] is None
    assert events[0]["event_date"] is None
    assert events[0]["publication_date"] == "2026-10-20"
    assert events[0]["verification_status"] == "DISCOVERED_NEEDS_PRIMARY_VERIFICATION"
    assert events[0]["source_type"] == "NEWS_AGGREGATOR_RESULT"
    assert repo.list_organizations() == []
    with repo._conn() as conn:
        assert conn.execute("SELECT COUNT(*) FROM signals").fetchone()[0] == 0

    # The provenance ledger is idempotent for an identical feed item.
    assert daily_signal_scan.filter_and_persist_signals([unsafe]) == 1
    assert len(repo.list_discovery_events()) == 1


def test_legacy_flow_rejects_missing_or_non_http_source(monkeypatch, tmp_path):
    repo = CareerRepository(db_path=tmp_path / "signals.db")
    monkeypatch.setattr(daily_signal_scan, "CareerRepository", lambda: repo)
    bad = [
        _signal(url=None),
        _signal(url="javascript:alert(1)"),
        _signal(url="https://user:pass@example.org/event"),
    ]
    assert daily_signal_scan.filter_and_persist_signals(bad) == 0
    assert repo.list_discovery_events() == []


@pytest.mark.live_integration
def test_identify_target_organizations_task():
    # The weekly legacy workflow still uses external providers.
    orgs = identify_target_organizations(limit=3)
    assert isinstance(orgs, list)
    assert len(orgs) <= 3
