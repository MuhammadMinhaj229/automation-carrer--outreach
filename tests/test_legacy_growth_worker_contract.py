"""Offline contract tests for the legacy queued growth-scan adapter."""

from pathlib import Path

import pytest

from acios.core.job_queue import DurableJobQueue
from acios.tools.discovery.growth_scanner import GrowthSignalScanner


class _Repo:
    """Truthy stub; no database or external provider is touched."""


def test_queued_growth_scan_uses_maintained_discovery_api(monkeypatch):
    calls = []

    def fake_scan(self, **kwargs):
        calls.append((self.repo, kwargs))
        return [object(), object()], Path("data/discovery_runs/sample.xlsx"), Path(
            "data/discovery_runs/sample.csv"
        )

    monkeypatch.setattr(GrowthSignalScanner, "scan_ecosystem", fake_scan)
    repo = _Repo()
    queue = DurableJobQueue(repo=repo, redis_url="")
    result = queue._handlers["search_growth_signals"](
        {
            "country": "India",
            "city": "Hyderabad",
            "trigger": "Technical & Engineering Hiring Surges",
            "query": "research pilot",
            "limit": 250,
        }
    )

    assert calls == [
        (
            repo,
            {
                "country": "India",
                "region": "Hyderabad",
                "trigger_category": "Technical & Engineering Hiring Surges",
                "custom_keywords": "research pilot",
                "max_results": 100,
            },
        )
    ]
    assert result == {
        "discovered_count": 2,
        "verification_status": "DISCOVERED_NEEDS_PRIMARY_VERIFICATION",
        "export_csv": "data/discovery_runs/sample.csv",
        "export_excel": "data/discovery_runs/sample.xlsx",
    }
    assert "signals" not in result


def test_queued_growth_scan_defaults_and_minimum_limit(monkeypatch):
    calls = []

    def fake_scan(self, **kwargs):
        calls.append(kwargs)
        return [], Path("empty.xlsx"), Path("empty.csv")

    monkeypatch.setattr(GrowthSignalScanner, "scan_ecosystem", fake_scan)
    queue = DurableJobQueue(repo=_Repo(), redis_url="")
    result = queue._handlers["search_growth_signals"]({"limit": -9})
    assert result["discovered_count"] == 0
    assert calls == [{
        "country": "Oman",
        "region": "All Regions",
        "trigger_category": "All Strategic Triggers",
        "custom_keywords": None,
        "max_results": 1,
    }]


def test_queued_growth_scan_rejects_invalid_limit_before_provider(monkeypatch):
    def fail_if_called(self, **kwargs):
        pytest.fail("No provider should be called for malformed queue payload")

    monkeypatch.setattr(GrowthSignalScanner, "scan_ecosystem", fail_if_called)
    queue = DurableJobQueue(repo=_Repo(), redis_url="")
    with pytest.raises(ValueError):
        queue._handlers["search_growth_signals"]({"limit": "not-a-number"})
