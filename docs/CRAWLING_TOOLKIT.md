# ACIOS Modular Crawling and Extraction Toolkit

## Overview

The toolkit integrates the ten requested projects through small adapters and a shared result schema. It does not copy or vendor their code. Optional dependencies load lazily so the core API does not have to install every browser stack.

The first release extracts **one public page per API request**. It does not claim to perform an unlimited recursive website crawl. A future durable crawling worker can add sitemap discovery, per-host concurrency, job checkpoints, and a bounded URL queue.

## Integrations and intended roles

| Project | ACIOS role | Availability/activation |
| --- | --- | --- |
| Firecrawl | Remote web-to-Markdown extraction | Set backend-only `FIRECRAWL_API_KEY`; remote API use may consume credits. |
| Crawl4AI | Local browser-backed/JavaScript-rendered extraction | Install the `crawl4ai` extra and required browser runtime. |
| Browser Use | Explicit, read-only agent browser tasks | Install `browser-use`, configure `BROWSER_USE_API_KEY` or `GOOGLE_API_KEY`, then set `ACIOS_BROWSER_USE_ENABLED=true`. Disabled by default. |
| Crawlee | Bounded, programmable one-page crawling | Install `crawlee[beautifulsoup]`. |
| Scrapy | Mature framework for compatible HTML extraction | Install the `scrapy` extra. |
| MarkItDown | Uploaded document to Markdown conversion | Install `markitdown[all]`; conversion plug-ins are disabled. |
| Scrapling | Adaptive public-page extraction | Install `scrapling[fetchers]`. |
| scrcpy | Local Android device display/control | Install the executable and ADB on a trusted local machine. It is not a web crawler and is not invoked by the hosted API. |
| AutoScraper | Learn extraction from sample values | Install `autoscraper`; explicitly provide a `wanted_list`. |
| curl-impersonate | HTTP/TLS compatibility for approved targets | Install the binary and set an explicit `ACIOS_CRAWLER_IMPERSONATE_HOSTS` allowlist. Never use it to evade authorization or access controls. |

The built-in `httpx` + BeautifulSoup adapter remains a lightweight fallback; it is not one of the ten named integrations.

## Cockpit interface\n\nThe signed-in web cockpit includes a Crawling Toolkit view with capability status, a single-page extraction form, provider strategy selection, and a bounded document-to-Markdown upload form. The view reports the selected provider and fallback warnings; it does not expose credentials.\n\n## API contracts

- `GET /api/v1/tools/crawl-capabilities` — reports readiness for all ten tools plus the built-in HTTP adapter. It never returns secret values.
- `POST /api/v1/tools/crawl-web` — extracts one public page using a chosen strategy or the local-first automatic fallback.
- `POST /api/v1/tools/convert-document` — converts an uploaded document up to 4 MB. This route is session-authenticated through the web cockpit and is not exposed to OpenAPI Actions.

Crawling output includes provider name, title, URL, normalized Markdown text, extracted links where supported, output length/truncation, duration, fallback warnings, and a flag confirming that robots policy was checked.

### Example crawl request

```json
{
  "url": "https://example.com/",
  "strategy": "auto",
  "max_chars": 20000
}
```

Supported strategies: `auto`, `firecrawl`, `crawl4ai`, `browser_use`, `crawlee`, `scrapy`, `scrapling`, `curl_impersonate`, `autoscraper`, `httpx`.

For AutoScraper supply `wanted_list`. For Browser Use supply a narrow `browser_instruction`; the tool will be asked to read publicly visible data only. MarkItDown is accessed only through the document-conversion route.

## Tool selection and fallback

Automatic mode selects the first configured provider in this order by default: Crawl4AI, Crawlee, Scrapling, Scrapy, Firecrawl (only when a key is configured), and the built-in HTTP adapter. Set `ACIOS_CRAWLER_PREFER_FIRECRAWL=true` only if remote processing and possible API cost are intentional.

Browser Use, AutoScraper, MarkItDown, scrcpy, and curl-impersonate remain purpose-specific rather than being run on every URL. AutoScraper needs examples, MarkItDown needs an uploaded document, scrcpy needs a local attached device, and curl-impersonate requires an explicit host allowlist. Running every tool on every page would duplicate work, waste cost, increase the attack surface, and produce inconsistent extraction.

## Security policy

1. Only HTTP/HTTPS targets on standard ports are accepted; URL credentials, local hostnames, localhost, private/reserved IP literals, and non-public DNS resolutions are rejected.
2. Optional `ACIOS_CRAWLER_ALLOWED_HOSTS` limits targets to exact hostnames and wildcard subdomains such as `*.example.com`.
3. Before extraction, the adapter checks `robots.txt`. If policy denies access or cannot be confirmed, the request stops. HTTP 404/410 for robots.txt means no policy file was published.
4. Redirects in the native adapter are checked individually and capped. Browser-backed libraries and third-party fetch APIs have library/provider-specific network behavior; production deployment should enforce outbound network/metadata IP restrictions at infrastructure level to mitigate DNS rebinding and redirect-based SSRF.
5. Per-page response bodies are capped at 2 MB; result text is capped at 50,000 characters. Adapter operations have deadlines.
6. In production, redirect-capable local adapters (Crawl4AI, Browser Use, Crawlee, Scrapy, Scrapling, AutoScraper, and curl-impersonate) stay disabled unless the deployment's outbound network policy blocks private, loopback, link-local, and cloud-metadata IP ranges. Only after confirming that network policy is enforced, set `ACIOS_CRAWLER_LOCAL_EGRESS_GUARD=true`. This flag is an operator attestation, not a firewall; setting it alone does not secure the network.
6. No recursive crawl or unrestricted URL queue is exposed by this API.
7. No CAPTCHA, login wall, paywall, access-control, or anti-bot bypass is performed. curl-impersonate is not an evasion mode.
8. Browser Use is disabled by default and restricted by instruction to read-only extraction. Do not supply instructions to send messages, submit forms, purchase, or change remote state.
9. Uploaded documents are size/extension checked, stored in a generated temporary path, and converted with MarkItDown plug-ins disabled. Never accept an arbitrary local path from the client.
10. scrcpy is local-only. Never expose an ADB/scrcpy server or personal device control endpoint to the public internet.
11. These API routes inherit ACIOS backend service authentication. OpenAPI Actions may call only the two explicitly allowlisted endpoints; document conversion remains web-session-only.

## Installation

Use the smallest dependency set that serves the target. From repository root:

```bash
pip install -e '.[crawl4ai]'
pip install -e '.[crawlee]'
pip install -e '.[scrapy]'
pip install -e '.[scrapling]'
pip install -e '.[markitdown]'
pip install -e '.[browser-use]'
pip install -e '.[autoscraper]'
```

These extras are optional, so the standard production API stays lightweight. A complete local development install is possible with `pip install -e '.[crawl-all]`, but browser engines can significantly increase install size and memory use. The CI pipeline deliberately tests the core toolkit without downloading every browser. curl-impersonate and scrcpy are separately installed native executables, not Python extras.

For production at scale, run browser-dependent work in a dedicated crawling worker/container with controlled egress rather than loading every browser engine into the API web process. Before enabling larger crawls add durable job records, concurrency limits, per-host rate limits, cancellation, retries, tenant quotas, and observability.

## Environment variables

All credentials below belong on the backend/crawler worker, never in browser-visible `NEXT_PUBLIC_*` variables:

- `FIRECRAWL_API_KEY` — optional remote provider token.
- `ACIOS_CRAWLER_ALLOWED_HOSTS` — optional comma-separated exact hosts or wildcard subdomains; empty allows any public host.
- `ACIOS_CRAWLER_PREFER_FIRECRAWL` — `false` by default.
- `ACIOS_BROWSER_USE_ENABLED` — `false` by default.
- `BROWSER_USE_API_KEY` or `GOOGLE_API_KEY` — credentials for explicit Browser Use tasks.
- `ACIOS_BROWSER_USE_MODEL` — optional model name.
- `ACIOS_CRAWLER_IMPERSONATE_HOSTS` — explicit authorized host list for curl-impersonate.
- `ACIOS_CURL_IMPERSONATE_BIN` — optional executable name/path (not command-line arguments).

## Verification and rollout checklist

1. Run the CI test suite and the new URL policy/catalog tests.
2. Check `GET /api/v1/tools/crawl-capabilities` with valid backend credentials.
3. Test `POST /api/v1/tools/crawl-web` against a public page that you control.
4. Confirm localhost, private IPs, invalid schemes, unsupported ports, disallowed robots paths, and out-of-allowlist hosts are rejected.
5. Install one optional adapter at a time in staging, then verify runtime/binary dependencies and memory requirements.
6. Test a remote provider only after reviewing cost and data handling.
7. Keep real outreach sending isolated from the crawler. Extracting a contact must never itself trigger outreach dispatch.
8. Generate an SBOM/license report for exact versions before distribution and include required notices.
