import ipaddress

import pytest

from acios.crawling.catalog import TOOL_CATALOG, automatic_candidates, integration_status
from acios.crawling.engine import (CrawlSafetyError, ToolUnavailable, _host_matches, _normalize_result, _require_adapter_egress_guard, validate_url_syntax)


def test_catalog_covers_all_ten_integrations():
    expected = {"firecrawl","crawl4ai","browser_use","crawlee","scrapy","markitdown","scrapling","scrcpy","autoscraper","curl_impersonate"}
    assert {item["id"] for item in TOOL_CATALOG} == expected
    status = integration_status()
    assert expected.issubset({item["id"] for item in status})
    assert all("available" in item and "reason" in item for item in status)


def test_automatic_candidates_keep_specialized_tools_opt_in():
    candidates = automatic_candidates()
    assert candidates[0] == "crawl4ai"
    assert "browser_use" not in candidates
    assert "autoscraper" not in candidates
    assert "scrcpy" not in candidates
    assert "markitdown" not in candidates
    assert "curl_impersonate" not in candidates
    assert automatic_candidates(prefer_firecrawl=True)[0] == "firecrawl"


@pytest.mark.parametrize("url", [
    "file:///etc/passwd", "ftp://example.com/", "http://localhost/",
    "http://127.0.0.1/", "http://169.254.169.254/latest/meta-data/",
    "http://user:password@example.com/", "http://example.com:8080/",
    "https://service.internal/",
])
def test_url_policy_rejects_unsafe_urls(url):
    with pytest.raises(CrawlSafetyError):
        validate_url_syntax(url)


def test_url_syntax_normalizes_safe_url():
    assert validate_url_syntax("HTTPS://example.com") == "https://example.com/"


def test_wildcard_host_policy_matches_subdomains_only():
    assert _host_matches("jobs.example.com", "*.example.com")
    assert not _host_matches("example.com", "*.example.com")
    assert _host_matches("example.com", "example.com")
    assert not _host_matches("other.example.net", "example.com")


def test_result_is_bounded_and_reports_truncation():
    result = _normalize_result("test", "https://example.com/", "x" * 2000, max_chars=500)
    assert len(result["content_markdown"]) == 500
    assert result["truncated"] is True
    assert result["characters"] == 500


def test_ip_classification():
    assert not ipaddress.ip_address("192.168.1.1").is_global
    assert ipaddress.ip_address("93.184.216.34").is_global

 
@pytest.mark.parametrize("provider", ["crawl4ai", "crawlee", "scrapy", "scrapling", "browser_use", "autoscraper", "curl_impersonate"])
def test_production_redirecting_adapters_require_egress_guard(monkeypatch, provider):
    monkeypatch.setenv("ACIOS_ENV", "production")
    monkeypatch.delenv("ACIOS_CRAWLER_LOCAL_EGRESS_GUARD", raising=False)
    with pytest.raises(ToolUnavailable, match="outbound egress protections"):
        _require_adapter_egress_guard(provider)


def test_development_does_not_require_production_egress_attestation(monkeypatch):
    monkeypatch.setenv("ACIOS_ENV", "development")
    monkeypatch.delenv("ACIOS_CRAWLER_LOCAL_EGRESS_GUARD", raising=False)
    _require_adapter_egress_guard("crawl4ai")


def test_configured_production_egress_guard_allows_local_adapter(monkeypatch):
    monkeypatch.setenv("ACIOS_ENV", "production")
    monkeypatch.setenv("ACIOS_CRAWLER_LOCAL_EGRESS_GUARD", "true")
    _require_adapter_egress_guard("crawl4ai")
