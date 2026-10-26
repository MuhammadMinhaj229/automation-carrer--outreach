"""Policy-aware orchestration over optional public-page extraction adapters.

The API deliberately exposes one-page extraction, not unbounded recursive crawling.
Optional dependencies are imported lazily to keep base app startup lean.
"""
from __future__ import annotations

import asyncio
import ipaddress
import json
import os
import shutil
import socket
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from urllib.parse import urljoin, urlsplit, urlunsplit
from urllib.robotparser import RobotFileParser
from typing import Any

import httpx
from bs4 import BeautifulSoup

from .catalog import _impersonate_binary, automatic_candidates, integration_status

MAX_URL_LENGTH = 2048
MAX_RESPONSE_BYTES = 2_000_000
MAX_DOCUMENT_BYTES = 10 * 1024 * 1024
MAX_OUTPUT_CHARS = 50_000
USER_AGENT = "ACIOSBot/2.0 (+https://github.com/MuhammadMinhaj229/automation-carrer--outreach)"
DOCUMENT_EXTENSIONS = {
    ".pdf", ".docx", ".pptx", ".xlsx", ".xls", ".csv", ".json", ".xml",
    ".html", ".htm", ".txt", ".md", ".rtf", ".ppt", ".doc", ".epub",
}

class CrawlSafetyError(ValueError):
    """Target, host, or robots policy rejected an operation."""

class ToolUnavailable(RuntimeError):
    """Explicitly selected optional adapter is not configured."""

class CrawlExecutionError(RuntimeError):
    """Provider failed without exposing secrets or upstream response bodies."""

def _host_matches(host: str, pattern: str) -> bool:
    pattern = pattern.strip().lower()
    if pattern.startswith("*."):
        suffix = pattern[2:].lstrip(".")
        return bool(suffix and host.endswith("." + suffix) and host != suffix)
    return host == pattern

def validate_url_syntax(url: str) -> str:
    candidate = (url or "").strip()
    if not candidate or len(candidate) > MAX_URL_LENGTH:
        raise CrawlSafetyError("A valid HTTP(S) URL of at most 2048 characters is required.")
    parsed = urlsplit(candidate)
    if parsed.scheme.lower() not in {"http", "https"}:
        raise CrawlSafetyError("Only HTTP and HTTPS URLs are supported.")
    if not parsed.hostname or parsed.username is not None or parsed.password is not None:
        raise CrawlSafetyError("URL must have a hostname and must not contain embedded credentials.")
    try:
        port = parsed.port
    except ValueError as exc:
        raise CrawlSafetyError("URL port is invalid.") from exc
    if port not in {None, 80, 443}:
        raise CrawlSafetyError("Only standard HTTP/HTTPS ports are permitted.")
    hostname = parsed.hostname.rstrip(".").lower()
    if hostname in {"localhost", "localhost.localdomain"} or hostname.endswith(".localhost"):
        raise CrawlSafetyError("Localhost is not a crawl target.")
    if hostname.endswith((".local", ".internal", ".lan", ".test", ".invalid")):
        raise CrawlSafetyError("Local or reserved hostnames are not crawl targets.")
    try:
        address = ipaddress.ip_address(hostname)
    except ValueError:
        address = None
    if address is not None and not address.is_global:
        raise CrawlSafetyError("Private, loopback, link-local, and reserved IP addresses are blocked.")
    allowed = [value.strip().lower() for value in os.getenv("ACIOS_CRAWLER_ALLOWED_HOSTS", "").split(",") if value.strip()]
    if allowed and not any(_host_matches(hostname, pattern) for pattern in allowed):
        raise CrawlSafetyError("The target host is outside ACIOS_CRAWLER_ALLOWED_HOSTS.")
    return urlunsplit((parsed.scheme.lower(), parsed.netloc, parsed.path or "/", parsed.query, ""))

def _resolve_public_host(host: str, port: int) -> list[str]:
    try:
        ipaddress.ip_address(host)
        addresses = [host]
    except ValueError:
        try:
            addresses = list({item[4][0] for item in socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)})
        except OSError as exc:
            raise CrawlSafetyError("Target host could not be resolved safely.") from exc
    if not addresses:
        raise CrawlSafetyError("Target DNS did not return an address.")
    for raw in addresses:
        try:
            address = ipaddress.ip_address(raw)
        except ValueError as exc:
            raise CrawlSafetyError("Invalid DNS response.") from exc
        if not address.is_global:
            raise CrawlSafetyError("Target DNS resolves to a private or reserved network.")
    return addresses

async def validate_public_url(url: str) -> str:
    normalized = validate_url_syntax(url)
    parsed = urlsplit(normalized)
    await asyncio.to_thread(_resolve_public_host, parsed.hostname or "", parsed.port or (443 if parsed.scheme == "https" else 80))
    return normalized

async def _check_robots(url: str) -> None:
    parsed = urlsplit(url)
    robots_url = urlunsplit((parsed.scheme, parsed.netloc, "/robots.txt", "", ""))
    await validate_public_url(robots_url)
    try:
        async with httpx.AsyncClient(timeout=5.0, follow_redirects=False, headers={"User-Agent": USER_AGENT}) as client:
            response = await client.get(robots_url)
    except httpx.HTTPError as exc:
        raise CrawlSafetyError("robots.txt could not be checked; stopped safely.") from exc
    if response.status_code in {404, 410}:
        return
    if response.status_code != 200:
        raise CrawlSafetyError("robots.txt policy could not be confirmed; stopped safely.")
    parser = RobotFileParser()
    parser.set_url(robots_url)
    parser.parse(response.text.splitlines())
    if not parser.can_fetch("ACIOSBot", url):
        raise CrawlSafetyError("Requested URL is disallowed by robots.txt.")

def _clean_html(provider: str, url: str, html: str) -> dict[str, Any]:
    soup = BeautifulSoup(html[:MAX_RESPONSE_BYTES], "html.parser")
    title = soup.title.get_text(" ", strip=True)[:300] if soup.title else ""
    for node in soup(["script", "style", "noscript", "svg", "canvas", "iframe", "nav", "footer"]):
        node.decompose()
    main = soup.find("main") or soup.find("article") or soup.body or soup
    links = []
    for anchor in main.find_all("a", href=True)[:100]:
        href = urljoin(url, str(anchor.get("href", "")))
        if urlsplit(href).scheme in {"http", "https"}:
            label = anchor.get_text(" ", strip=True)[:250]
            if label:
                links.append({"text": label, "url": href})
    return {"provider": provider, "title": title, "final_url": url, "content_markdown": main.get_text("\\n", strip=True), "links": links}

def _normalize_result(provider: str, url: str, markdown: str, title: str = "",
                     links: list[dict[str, str]] | None = None,
                     max_chars: int = 20_000, elapsed_ms: int = 0) -> dict[str, Any]:
    text = (markdown or "").strip()
    limit = max(500, min(int(max_chars), MAX_OUTPUT_CHARS))
    truncated = len(text) > limit
    text = text[:limit]
    return {
        "provider": provider, "title": (title or "")[:300], "final_url": url,
        "content_markdown": text, "links": (links or [])[:100],
        "characters": len(text), "truncated": truncated, "duration_ms": max(0, int(elapsed_ms)),
    }

async def _firecrawl(url: str, max_chars: int) -> dict[str, Any]:
    key = os.getenv("FIRECRAWL_API_KEY", "").strip()
    if not key:
        raise ToolUnavailable("Firecrawl is not configured.")
    async with httpx.AsyncClient(timeout=25.0, follow_redirects=False) as client:
        response = await client.post(
            "https://api.firecrawl.dev/v2/scrape",
            headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
            json={"url": url, "formats": ["markdown"], "onlyMainContent": True},
        )
    if response.status_code >= 400:
        raise CrawlExecutionError(f"Firecrawl returned HTTP {response.status_code}.")
    payload = response.json()
    data = payload.get("data") if isinstance(payload, dict) else None
    if not isinstance(data, dict):
        raise CrawlExecutionError("Firecrawl returned an unexpected response.")
    markdown = data.get("markdown") or data.get("content") or ""
    metadata = data.get("metadata") or {}
    if not markdown:
        raise CrawlExecutionError("Firecrawl returned no content.")
    final_url = str(metadata.get("sourceURL") or url)
    await validate_public_url(final_url)
    return _normalize_result("firecrawl", final_url, str(markdown), str(metadata.get("title") or ""), max_chars=max_chars)

async def _crawl4ai(url: str, max_chars: int) -> dict[str, Any]:
    try:
        from crawl4ai import AsyncWebCrawler
    except ImportError as exc:
        raise ToolUnavailable("Install the crawl4ai optional dependency and browser runtime.") from exc
    async with AsyncWebCrawler() as crawler:
        result = await asyncio.wait_for(crawler.arun(url=url), timeout=30.0)
    if getattr(result, "success", True) is False:
        raise CrawlExecutionError("Crawl4AI could not extract this page.")
    markdown = getattr(result, "markdown", "") or ""
    if not isinstance(markdown, str):
        markdown = getattr(markdown, "raw_markdown", None) or getattr(markdown, "fit_markdown", None) or str(markdown)
    final_url = str(getattr(result, "url", None) or url)
    await validate_public_url(final_url)
    metadata = getattr(result, "metadata", {}) or {}
    return _normalize_result("crawl4ai", final_url, markdown, str(metadata.get("title") or ""), max_chars=max_chars)

async def _crawlee(url: str, max_chars: int) -> dict[str, Any]:
    try:
        from crawlee.crawlers import BeautifulSoupCrawler, BeautifulSoupCrawlingContext
    except ImportError as exc:
        raise ToolUnavailable("Install crawlee[beautifulsoup].") from exc
    captured: list[dict[str, str]] = []
    crawler = BeautifulSoupCrawler(max_requests_per_crawl=1)
    @crawler.router.default_handler
    async def handle(context: BeautifulSoupCrawlingContext) -> None:
        soup = context.soup
        captured.append({
            "url": context.request.url,
            "title": soup.title.get_text(" ", strip=True) if soup.title else "",
            "text": soup.get_text("\\n", strip=True),
        })
    await asyncio.wait_for(crawler.run([url]), timeout=30.0)
    if not captured:
        raise CrawlExecutionError("Crawlee returned no page.")
    page = captured[0]
    await validate_public_url(page["url"])
    return _normalize_result("crawlee", page["url"], page["text"], page["title"], max_chars=max_chars)

async def _scrapling(url: str, max_chars: int) -> dict[str, Any]:
    try:
        from scrapling.fetchers import Fetcher
    except ImportError as exc:
        raise ToolUnavailable("Install scrapling[fetchers].") from exc
    def fetch() -> tuple[str, str, str]:
        page = Fetcher.get(url)
        title = " ".join(str(value) for value in page.css("title::text").getall())[:300]
        method = getattr(page, "get_all_text", None)
        text = method() if callable(method) else getattr(page, "text", "")
        return str(getattr(page, "url", "") or url), title, str(text or page)
    final_url, title, page_text = await asyncio.wait_for(asyncio.to_thread(fetch), timeout=20.0)
    await validate_public_url(final_url)
    return _normalize_result("scrapling", final_url, page_text, title, max_chars=max_chars)

async def _scrapy(url: str, max_chars: int) -> dict[str, Any]:
    try:
        import scrapy  # noqa: F401
    except ImportError as exc:
        raise ToolUnavailable("Install the Scrapy optional dependency.") from exc
    spider = (
        "import scrapy\n"
        "class ACIOSOnePageSpider(scrapy.Spider):\n"
        " name='acios_one_page'\n"
        " custom_settings={'LOG_ENABLED':False,'DOWNLOAD_TIMEOUT':12,'CLOSESPIDER_TIMEOUT':15,'ROBOTSTXT_OBEY':False,'REDIRECT_ENABLED':False}\n"
        " def __init__(self,target_url=None,*args,**kwargs):\n"
        "  super().__init__(*args,**kwargs); self.start_urls=[target_url] if target_url else []\n"
        " def parse(self,response):\n"
        "  yield {'url':response.url,'html':response.text[:1500000]}\n"
    )
    try:
        with tempfile.TemporaryDirectory(prefix="acios-scrapy-") as temp:
            base = Path(temp)
            spider_path, output_path = base / "spider.py", base / "out.json"
            spider_path.write_text(spider, encoding="utf-8")
            proc = await asyncio.create_subprocess_exec(
                sys.executable, "-m", "scrapy", "runspider", str(spider_path),
                "-a", f"target_url={url}", "-O", str(output_path), "-s", "LOG_ENABLED=False",
                "-s", "FEED_EXPORT_ENCODING=utf-8", cwd=temp,
                stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
            )
            try:
                await asyncio.wait_for(proc.communicate(), timeout=20.0)
            except asyncio.TimeoutError:
                proc.kill(); await proc.communicate()
                raise CrawlExecutionError("Scrapy exceeded the time limit.")
            if proc.returncode != 0 or not output_path.exists():
                raise CrawlExecutionError("Scrapy could not extract the page.")
            records = json.loads(output_path.read_text(encoding="utf-8"))
            if not isinstance(records, list) or not records or not records[0].get("html"):
                raise CrawlExecutionError("Scrapy returned no HTML.")
            record = records[0]
            await validate_public_url(record.get("url") or url)
            extracted = _clean_html("scrapy", record.get("url") or url, record["html"])
            return _normalize_result("scrapy", extracted["final_url"], extracted["content_markdown"], extracted["title"], extracted["links"], max_chars)
    except (ToolUnavailable, CrawlSafetyError, CrawlExecutionError):
        raise
    except Exception as exc:
        raise CrawlExecutionError("Scrapy execution failed.") from exc

async def _autoscraper(url: str, max_chars: int, wanted_list: list[str] | None) -> dict[str, Any]:
    if not wanted_list or len(wanted_list) > 10 or any(not isinstance(v, str) or not v.strip() or len(v) > 250 for v in wanted_list):
        raise CrawlSafetyError("AutoScraper requires 1–10 non-empty sample values, each at most 250 characters.")
    try:
        from autoscraper import AutoScraper
    except ImportError as exc:
        raise ToolUnavailable("Install autoscraper.") from exc
    def extract() -> list[str]:
        scraper = AutoScraper()
        scraper.build(url, wanted_list=wanted_list)
        return [str(value) for value in scraper.get_result_exact(url)[:100]]
    values = await asyncio.wait_for(asyncio.to_thread(extract), timeout=20.0)
    if not values:
        raise CrawlExecutionError("AutoScraper found no matching values.")
    return _normalize_result("autoscraper", url, "\\n".join(values), max_chars=max_chars)

async def _browser_use(url: str, max_chars: int, instruction: str | None) -> dict[str, Any]:
    if os.getenv("ACIOS_BROWSER_USE_ENABLED", "false").lower() != "true":
        raise ToolUnavailable("Browser Use is disabled; enable explicitly after review.")
    if not instruction or not instruction.strip():
        raise CrawlSafetyError("Browser Use requires a narrow read-only extraction instruction.")
    try:
        from browser_use import Agent, ChatBrowserUse, ChatGoogle
    except ImportError as exc:
        raise ToolUnavailable("Install browser-use and its browser runtime.") from exc
    if os.getenv("BROWSER_USE_API_KEY", "").strip():
        llm = ChatBrowserUse()
    elif os.getenv("GOOGLE_API_KEY", "").strip():
        llm = ChatGoogle(model=os.getenv("ACIOS_BROWSER_USE_MODEL", "gemini-2.5-flash"))
    else:
        raise ToolUnavailable("Configure BROWSER_USE_API_KEY or GOOGLE_API_KEY.")
    task = (
        f"Read publicly visible content from {url}. This is read-only. Never sign in, submit forms, "
        "click controls that change state, send messages, purchase items, accept legal terms, "
        "download executables, or bypass access controls. If access is restricted, stop. "
        f"Extract only: {instruction.strip()[:500]}"
    )
    agent = Agent(task=task, llm=llm)
    history = await asyncio.wait_for(agent.run(), timeout=30.0)
    result = getattr(history, "final_result", None)
    content = result() if callable(result) else str(history)
    return _normalize_result("browser_use", url, str(content), max_chars=max_chars)

async def _curl_impersonate(url: str, max_chars: int) -> dict[str, Any]:
    parsed = urlsplit(url)
    allowlist = [v.strip().lower() for v in os.getenv("ACIOS_CRAWLER_IMPERSONATE_HOSTS", "").split(",") if v.strip()]
    host = (parsed.hostname or "").lower()
    if not allowlist or not any(_host_matches(host, pattern) for pattern in allowlist):
        raise CrawlSafetyError("curl-impersonate is restricted to ACIOS_CRAWLER_IMPERSONATE_HOSTS.")
    binary = _impersonate_binary()
    if not binary:
        raise ToolUnavailable("Install the curl-impersonate executable.")
    proc = await asyncio.create_subprocess_exec(
        binary, "--silent", "--show-error", "--fail", "--max-time", "15",
        "--max-filesize", str(MAX_RESPONSE_BYTES), "--max-redirs", "0", url,
        stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
    )
    try:
        stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=18.0)
    except asyncio.TimeoutError:
        proc.kill(); await proc.communicate()
        raise CrawlExecutionError("curl-impersonate exceeded the time limit.")
    if proc.returncode != 0:
        raise CrawlExecutionError("curl-impersonate request failed.")
    page = _clean_html("curl_impersonate", url, stdout.decode("utf-8", errors="replace"))
    return _normalize_result("curl_impersonate", url, page["content_markdown"], page["title"], page["links"], max_chars)

async def _native_http(url: str, max_chars: int) -> dict[str, Any]:
    current = url
    for redirect_count in range(4):
        current = await validate_public_url(current)
        await _check_robots(current)
        async with httpx.AsyncClient(timeout=15.0, follow_redirects=False, headers={"User-Agent": USER_AGENT, "Accept": "text/html,application/xhtml+xml"}) as client:
            async with client.stream("GET", current) as response:
                if response.status_code in {301, 302, 303, 307, 308}:
                    location = response.headers.get("location")
                    if not location:
                        raise CrawlExecutionError("Redirect omitted its location.")
                    if redirect_count >= 3:
                        raise CrawlExecutionError("Redirect limit exceeded.")
                    current = urljoin(current, location)
                    continue
                if response.status_code >= 400:
                    raise CrawlExecutionError(f"Target returned HTTP {response.status_code}.")
                content_type = response.headers.get("content-type", "").lower()
                if "text/html" not in content_type and "application/xhtml+xml" not in content_type:
                    raise CrawlExecutionError("Target is not HTML; use the document converter for files.")
                body = bytearray()
                async for chunk in response.aiter_bytes():
                    body.extend(chunk)
                    if len(body) > MAX_RESPONSE_BYTES:
                        raise CrawlExecutionError("Page exceeds the 2 MB limit.")
                page = _clean_html("httpx", current, body.decode(response.encoding or "utf-8", errors="replace"))
                return _normalize_result("httpx", current, page["content_markdown"], page["title"], page["links"], max_chars)
    raise CrawlExecutionError("Redirect limit exceeded.")

async def crawl_url(url: str, strategy: str = "auto", max_chars: int = 20_000,
                    wanted_list: list[str] | None = None,
                    browser_instruction: str | None = None) -> dict[str, Any]:
    """Extract one public page via an explicit adapter or a safe local-first fallback chain."""
    allowed = {"auto","firecrawl","crawl4ai","browser_use","crawlee","scrapy","scrapling","curl_impersonate","autoscraper","httpx"}
    if strategy not in allowed:
        raise CrawlSafetyError("Unknown crawling strategy.")
    normalized = await validate_public_url(url)
    await _check_robots(normalized)
    if strategy == "auto":
        prefer_remote = os.getenv("ACIOS_CRAWLER_PREFER_FIRECRAWL", "false").lower() == "true"
        available = {item["id"]: item["available"] for item in integration_status()}
        candidates = [name for name in automatic_candidates(prefer_remote) if available.get(name, False)]
        if "httpx" not in candidates:
            candidates.append("httpx")
    else:
        candidates = [strategy]
    started = time.monotonic()
    warnings: list[str] = []
    for provider in candidates:
        try:
            if provider == "firecrawl": result = await _firecrawl(normalized, max_chars)
            elif provider == "crawl4ai": result = await _crawl4ai(normalized, max_chars)
            elif provider == "browser_use": result = await _browser_use(normalized, max_chars, browser_instruction)
            elif provider == "crawlee": result = await _crawlee(normalized, max_chars)
            elif provider == "scrapy": result = await _scrapy(normalized, max_chars)
            elif provider == "scrapling": result = await _scrapling(normalized, max_chars)
            elif provider == "curl_impersonate": result = await _curl_impersonate(normalized, max_chars)
            elif provider == "autoscraper": result = await _autoscraper(normalized, max_chars, wanted_list)
            else: result = await _native_http(normalized, max_chars)
            result["duration_ms"] = int((time.monotonic() - started) * 1000)
            result["warnings"] = warnings
            result["robots_policy_checked"] = True
            result["recursive_crawl"] = False
            return result
        except (CrawlSafetyError, ToolUnavailable):
            if strategy != "auto":
                raise
            warnings.append(f"{provider}: unavailable or blocked by policy")
        except Exception as exc:
            if strategy != "auto":
                raise CrawlExecutionError(f"{provider} failed ({type(exc).__name__}).") from exc
            warnings.append(f"{provider}: failed ({type(exc).__name__})")
    raise CrawlExecutionError("No adapter completed the request safely.")

def convert_document(data: bytes, filename: str, max_bytes: int = MAX_DOCUMENT_BYTES) -> dict[str, Any]:
    """Convert an uploaded local document with MarkItDown; do not allow plug-ins or arbitrary paths."""
    if not data or len(data) > max_bytes:
        raise CrawlSafetyError("Document must be non-empty and no larger than 10 MB.")
    extension = Path(filename or "").suffix.lower()
    if extension not in DOCUMENT_EXTENSIONS:
        raise CrawlSafetyError("Unsupported document extension.")
    try:
        from markitdown import MarkItDown
    except ImportError as exc:
        raise ToolUnavailable("Install the markitdown optional dependency.") from exc
    with tempfile.TemporaryDirectory(prefix="acios-markitdown-") as temp:
        path = Path(temp) / f"input{extension}"
        path.write_bytes(data)
        try:
            converted = MarkItDown(enable_plugins=False).convert(str(path))
        except Exception as exc:
            raise CrawlExecutionError("MarkItDown could not convert the document.") from exc
    markdown = str(getattr(converted, "markdown", "") or "")
    return {
        "provider":"markitdown", "filename":Path(filename).name[:255],
        "content_markdown":markdown[:MAX_OUTPUT_CHARS],
        "characters":min(len(markdown),MAX_OUTPUT_CHARS),
        "truncated":len(markdown)>MAX_OUTPUT_CHARS, "plugins_enabled":False,
    }
