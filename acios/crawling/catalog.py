"""Capability registry for optional ACIOS crawling integrations."""
from __future__ import annotations

import importlib.util
import os
import shutil
from typing import Any

TOOL_CATALOG = (
    {"id":"firecrawl","name":"Firecrawl","category":"remote_web_extraction","purpose":"Remote page extraction; API usage may incur credits.","module":None,"automatic":True},
    {"id":"crawl4ai","name":"Crawl4AI","category":"javascript_rendering","purpose":"Local browser-backed extraction.","module":"crawl4ai","automatic":True},
    {"id":"browser_use","name":"Browser Use","category":"interactive_browser","purpose":"Explicit read-only browser-agent tasks; disabled by default.","module":"browser_use","automatic":False},
    {"id":"crawlee","name":"Crawlee","category":"crawler_framework","purpose":"Bounded programmable crawling through Python Crawlee.","module":"crawlee","automatic":True},
    {"id":"scrapy","name":"Scrapy","category":"crawler_framework","purpose":"Mature scraping framework for compatible public pages.","module":"scrapy","automatic":True},
    {"id":"markitdown","name":"MarkItDown","category":"document_conversion","purpose":"Local document-to-Markdown conversion; plug-ins disabled.","module":"markitdown","automatic":False},
    {"id":"scrapling","name":"Scrapling","category":"adaptive_extraction","purpose":"Adaptive extraction for authorized public websites.","module":"scrapling","automatic":True},
    {"id":"scrcpy","name":"scrcpy","category":"android_device","purpose":"Local Android display/control utility, not a web crawler.","module":None,"automatic":False},
    {"id":"autoscraper","name":"AutoScraper","category":"learned_extraction","purpose":"Learn extraction patterns from user-provided examples.","module":"autoscraper","automatic":False},
    {"id":"curl_impersonate","name":"curl-impersonate","category":"http_compatibility","purpose":"HTTP/TLS compatibility for explicitly authorized hosts only.","module":None,"automatic":False},
)

def _module_installed(name: str) -> bool:
    try:
        return importlib.util.find_spec(name) is not None
    except (ImportError, ValueError, ModuleNotFoundError):
        return False

def _impersonate_binary() -> str | None:
    configured = os.getenv("ACIOS_CURL_IMPERSONATE_BIN", "").strip()
    if configured:
        if any(char.isspace() for char in configured):
            return None
        return shutil.which(configured)
    for name in ("curl_chrome", "curl_chrome152", "curl_chrome131", "curl_chrome120", "curl-impersonate-chrome"):
        found = shutil.which(name)
        if found:
            return found
    return None

def _availability(item: dict[str, Any]) -> tuple[bool, str]:
    tool = item["id"]
    if tool == "firecrawl":
        enabled = bool(os.getenv("FIRECRAWL_API_KEY", "").strip())
        return enabled, "API key configured" if enabled else "FIRECRAWL_API_KEY not set; remote calls disabled"
    if tool == "browser_use":
        if os.getenv("ACIOS_BROWSER_USE_ENABLED", "false").lower() != "true":
            return False, "Disabled by default; explicitly enable after reviewing safety and cost"
        if not _module_installed("browser_use"):
            return False, "Install the browser-use optional dependency"
        if not any(os.getenv(key, "").strip() for key in ("BROWSER_USE_API_KEY", "GOOGLE_API_KEY")):
            return False, "Configure BROWSER_USE_API_KEY or GOOGLE_API_KEY"
        return True, "Enabled for explicit read-only browser tasks"
    if tool == "scrcpy":
        ready = shutil.which("scrcpy") is not None
        return ready, "Local executable found" if ready else "Local scrcpy executable is not installed"
    if tool == "curl_impersonate":
        ready = bool(_impersonate_binary())
        allowlist = bool(os.getenv("ACIOS_CRAWLER_IMPERSONATE_HOSTS", "").strip())
        return ready and allowlist, (
            "Executable and authorized-host allowlist found" if ready and allowlist
            else "Requires curl-impersonate executable and ACIOS_CRAWLER_IMPERSONATE_HOSTS"
        )
    module = item["module"]
    ready = bool(module and _module_installed(module))
    return ready, "Optional package installed" if ready else f"Optional package not installed: {module}"

def integration_status() -> list[dict[str, Any]]:
    """Non-secret readiness metadata for all ten integrations plus built-in HTTP fallback."""
    result = []
    for item in TOOL_CATALOG:
        available, reason = _availability(item)
        result.append({
            "id": item["id"], "name": item["name"], "category": item["category"],
            "purpose": item["purpose"], "available": available,
            "automatic": item["automatic"], "status": "ready" if available else "not_configured",
            "reason": reason,
        })
    http_ready = _module_installed("httpx") and _module_installed("bs4")
    result.append({
        "id":"httpx","name":"Built-in HTTP fallback","category":"basic_extraction",
        "purpose":"Bounded HTML extraction using base dependencies.","available":http_ready,
        "automatic":True,"status":"ready" if http_ready else "not_configured",
        "reason":"No API key or browser binary required",
    })
    return result

def automatic_candidates(prefer_firecrawl: bool = False) -> list[str]:
    """Deterministic priority; no browser agent, device tool, document converter, or impersonation by default."""
    if prefer_firecrawl:
        return ["firecrawl", "crawl4ai", "crawlee", "scrapling", "scrapy", "httpx"]
    return ["crawl4ai", "crawlee", "scrapling", "scrapy", "firecrawl", "httpx"]
