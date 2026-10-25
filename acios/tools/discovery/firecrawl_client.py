"""
Firecrawl Client & Scraper Provider for ACIOS.
Supports both Firecrawl Cloud API and Self-Hosted Firecrawl instances (Docker/Fork),
with graceful fallback to standard HTTP extraction when Firecrawl is offline.
"""

import os
import urllib.request
import urllib.error
import json
from typing import Dict, Any, List, Optional
from firecrawl import FirecrawlApp


class FirecrawlProvider:
    def __init__(self, api_key: Optional[str] = None, api_url: Optional[str] = None):
        self.api_key = api_key or os.getenv("FIRECRAWL_API_KEY", "")
        self.api_url = api_url or os.getenv("FIRECRAWL_API_URL", "https://api.firecrawl.dev")
        self._app: Optional[FirecrawlApp] = None
        
        # Initialize FirecrawlApp if credentials or custom URL is present
        if self.api_key or (self.api_url and "api.firecrawl.dev" not in self.api_url):
            try:
                self._app = FirecrawlApp(api_key=self.api_key or "self-hosted", api_url=self.api_url)
            except Exception as e:
                print(f"[FirecrawlProvider Warning] Failed to initialize FirecrawlApp: {e}")

    def scrape(self, url: str) -> Dict[str, Any]:
        """
        Scrapes a single URL and converts it into LLM-ready clean Markdown.
        Uses Firecrawl if available; otherwise falls back to basic HTML reader.
        """
        if self._app:
            try:
                # Prefer v2 scrape method, fallback to scrape_url
                if hasattr(self._app, "scrape"):
                    res = self._app.scrape(url, formats=["markdown"])
                else:
                    res = self._app.scrape_url(url, params={"formats": ["markdown"]})

                # Check format of returned result
                if isinstance(res, dict):
                    markdown = res.get("markdown", "")
                    metadata = res.get("metadata", {})
                    return {
                        "status": "SUCCESS",
                        "provider": "firecrawl",
                        "url": url,
                        "markdown": markdown,
                        "metadata": metadata
                    }
                elif hasattr(res, "markdown"):
                    return {
                        "status": "SUCCESS",
                        "provider": "firecrawl",
                        "url": url,
                        "markdown": getattr(res, "markdown", ""),
                        "metadata": getattr(res, "metadata", {})
                    }
            except Exception as e:
                print(f"[FirecrawlProvider] Firecrawl scrape failed: {e}. Falling back to standard fetch.")

        # Fallback standard fetch
        return self._fallback_fetch(url)

    def search_and_scrape_top(self, query: str) -> Dict[str, Any]:
        """
        Searches the web via Firecrawl and immediately scrapes the top result.
        """
        if not self._app:
            return {"status": "ERROR", "message": "Firecrawl API key is required for web search."}

        try:
            search_res = self._app.search(query)
            items = []
            if hasattr(search_res, "data") and search_res.data:
                items = search_res.data
            elif hasattr(search_res, "web") and search_res.web:
                items = search_res.web

            if not items:
                return {"status": "NO_RESULTS", "query": query}

            top_item = items[0]
            top_url = getattr(top_item, "url", None) or (top_item.get("url") if isinstance(top_item, dict) else str(top_item))
            top_title = getattr(top_item, "title", None) or (top_item.get("title") if isinstance(top_item, dict) else "N/A")

            scrape_data = self.scrape(top_url)
            return {
                "status": "SUCCESS",
                "query": query,
                "top_title": top_title,
                "top_url": top_url,
                "scraped_markdown": scrape_data.get("markdown", "")
            }
        except Exception as e:
            return {"status": "ERROR", "error": str(e)}

    def map_urls(self, domain_url: str) -> Dict[str, Any]:
        """
        Discovers all subpages and paths for a target company domain (e.g. /news, /press, /team).
        """
        if self._app:
            try:
                res = self._app.map_url(domain_url)
                urls = []
                if isinstance(res, dict):
                    urls = res.get("links", [])
                elif hasattr(res, "links"):
                    urls = getattr(res, "links", [])
                elif isinstance(res, list):
                    urls = res
                return {
                    "status": "SUCCESS",
                    "provider": "firecrawl",
                    "domain": domain_url,
                    "discovered_urls": urls[:50]
                }
            except Exception as e:
                return {
                    "status": "ERROR",
                    "provider": "firecrawl",
                    "error": str(e),
                    "discovered_urls": []
                }
        
        return {
            "status": "UNAVAILABLE",
            "provider": "none",
            "message": "Firecrawl API key or self-hosted instance (http://localhost:3002) is required for domain URL mapping.",
            "discovered_urls": []
        }

    def _fallback_fetch(self, url: str) -> Dict[str, Any]:
        """Lightweight fallback using urllib if Firecrawl is not configured."""
        try:
            req = urllib.request.Request(
                url,
                headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
            )
            with urllib.request.urlopen(req, timeout=12) as response:
                html_bytes = response.read()
                # Basic text decodable
                text = html_bytes.decode("utf-8", errors="replace")
                # Strip raw scripts and styles
                import re
                text_clean = re.sub(r"<(script|style).*?>.*?</\1>", "", text, flags=re.DOTALL | re.IGNORECASE)
                text_clean = re.sub(r"<[^>]+>", " ", text_clean)
                text_clean = re.sub(r"\s+", " ", text_clean).strip()
                return {
                    "status": "FALLBACK_SUCCESS",
                    "provider": "urllib_fallback",
                    "url": url,
                    "markdown": text_clean[:3000],
                    "note": "Extracted via basic fallback. Connect Firecrawl for full JS rendering and Fit-Markdown."
                }
        except Exception as e:
            return {
                "status": "ERROR",
                "provider": "urllib_fallback",
                "url": url,
                "error": str(e)
            }
