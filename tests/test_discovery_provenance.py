"""Deterministic tests for the discovery pipeline's evidence contract."""
from types import SimpleNamespace

import pytest

from acios.core.repository import CareerRepository
from acios.tools.discovery import growth_scanner


def test_unknown_headline_does_not_become_a_company_name():
    scanner = growth_scanner.GrowthSignalScanner(repo=object())
    assert scanner._extract_organization_name(
        "An outlook on regional renewable investment trends",
        "Worldwide renewable funding"
    ) is None


def test_rss_discovery_does_not_fabricate_website_or_event_date(monkeypatch, tmp_path):
    feed = SimpleNamespace(
        entries=[
            {
                "title": "A generic renewable projects headline with no entity - Wire Service",
                "link": "https://news.google.com/rss/articles/example",
                "summary": "<p>A new pilot is being discussed for renewable energy testing.</p>",
                "published": "October 20, 2026",
            }
        ]
    )
    monkeypatch.setattr(growth_scanner.feedparser, "parse", lambda _url: feed)
    monkeypatch.setattr(growth_scanner, "BASE_DIR", tmp_path)

    class RepositoryMustNotSupplyCurrentSignals:
        def list_organizations(self, *args, **kwargs):
            raise AssertionError("Historical database records must not be added as fresh signals.")

    scanner = growth_scanner.GrowthSignalScanner(repo=RepositoryMustNotSupplyCurrentSignals())
    frame, csv_path, excel_path = scanner.scan_ecosystem(
        country="Worldwide",
        region="All Regions",
        trigger_category="All Strategic Triggers",
        custom_keywords="renewable energy pilot",
        max_results=5,
    )

    assert len(frame) == 1
    record = frame.iloc[0].to_dict()
    assert record["organization_name"] is None
    assert record["entity_resolution_status"] == "UNRESOLVED"
    assert record["website"] is None
    assert record["event_date"] is None
    assert record["published_date"] is None
    assert record["published_date_raw"] == "October 20, 2026"
    assert record["source_type"] == "NEWS_AGGREGATOR_RESULT"
    assert record["status"] == "DISCOVERED_NEEDS_PRIMARY_VERIFICATION"
    assert record["score_type"] == "HEURISTIC_KEYWORD_RELEVANCE_NOT_PROBABILITY"
    assert csv_path.is_file()
    assert excel_path.is_file()


def test_user_supplied_organization_is_still_not_a_verified_trigger(monkeypatch, tmp_path):
    feed = SimpleNamespace(
        entries=[
            {
                "title": "Acme Renewables announces a pilot - Wire Service",
                "link": "https://news.google.com/rss/articles/acme",
                "summary": "<p>Company announced a pilot project.</p>",
            }
        ]
    )
    monkeypatch.setattr(growth_scanner.feedparser, "parse", lambda _url: feed)
    monkeypatch.setattr(growth_scanner, "BASE_DIR", tmp_path)
    scanner = growth_scanner.GrowthSignalScanner(repo=object())
    frame, _, _ = scanner.scan_ecosystem(
        country="Worldwide",
        search_org="Acme Renewables",
        max_results=3,
    )
    record = frame.iloc[0].to_dict()
    assert record["organization_name"] == "Acme Renewables"
    assert record["entity_resolution_status"] == "USER_SUPPLIED_TARGET"
    assert record["status"] == "DISCOVERED_NEEDS_PRIMARY_VERIFICATION"
    assert record["event_date"] is None
