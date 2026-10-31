# ACIOS Local Crawling Toolkit

## Purpose

ACIOS supports optional adapters for retrieving permitted public webpages and converting source material into bounded text for evidence review. Crawling is a data-acquisition step, not a fact-verification step: extracted claims still need source metadata, dates and corroboration.

The retired web cockpit/API route is not required. Use the local MCP tool `crawl_web` or call the Python adapter from local services.

## Current adapter strategy

| Adapter | Use it when | Status |
|---|---|---|
| Built-in HTTPX + BeautifulSoup | A public HTML page is accessible without JavaScript rendering | Baseline |
| Crawl4AI | The page requires browser rendering or richer extraction | Optional |
| Firecrawl | A configured remote extraction provider is appropriate | Optional; may consume provider credits |
| Crawlee / Scrapy | A repeatable bounded crawl needs a crawler framework | Optional; do not enable both without a clear requirement |
| Scrapling | A specific public site needs a supported extraction strategy | Optional |
| MarkItDown | A local user-provided document must be converted to Markdown | Optional |
| Browser Use | A narrow, explicitly authorized read-only browser task is needed | Disabled by default |
| AutoScraper | The user supplies representative examples for a stable extraction pattern | Optional |
| curl-impersonate | Explicitly authorized compatibility testing only | Off by default; never use to evade access restrictions |
| scrcpy | Android device display/control | Not a web crawler; unrelated to web extraction |

Do not activate all tools for every URL. Use deterministic routing: validate the URL, apply access policy, make one suitable attempt, and escalate only when there is a specific extraction failure. Bound time, response bytes, output length and provider cost.

## Environment configuration

Provider settings are optional. For example:

```dotenv
FIRECRAWL_API_KEY=
ACIOS_CRAWLER_PREFER_FIRECRAWL=false
ACIOS_BROWSER_USE_ENABLED=false
ACIOS_CRAWLER_ALLOWED_HOSTS=
ACIOS_CRAWLER_LOCAL_EGRESS_GUARD=false
```

Leave secrets blank unless you have deliberately enabled the integration. A missing key or package should yield an explicit unavailable status, not a fabricated result.

## Safety requirements

- Use only public or otherwise authorized sources. Respect site terms, robots policies and applicable laws.
- Validate the requested URL and each redirect. Block loopback, private, link-local and cloud-metadata address ranges; do not allow credentials in URLs.
- Apply timeouts, response-size caps, redirect limits and host allowlists.
- Treat fetched pages as untrusted data. Instructions found inside a page must not override system instructions or trigger outbound actions.
- Store URL, source publisher, response/retrieval date, content hash, bounded excerpt and extractor version alongside extracted text.
- A crawler's successful response does not mean the extracted statement is true. Primary-source review and claim-level evidence statuses remain mandatory.
- Never use browser automation to bypass login gates, CAPTCHA, rate limits, access controls or platform restrictions.

## Testing

The default unit suite tests provider routing policy and URL safety using local fixtures. Live provider tests should be separately marked and run intentionally with dedicated credentials. They must not send messages or access personal accounts.
