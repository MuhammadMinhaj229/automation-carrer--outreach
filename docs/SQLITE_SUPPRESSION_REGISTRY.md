# Opt-in local SQLite suppression registry (2026-11-05)

The legacy `SuppressionEngine` historically kept dynamic blocks in memory only.
A new process lost those blocks, so a successful bounce handler could not honestly
promise permanent suppression. This change adds an **opt-in** SQLite registry with
a normalized unique email key, original reason, UTC timestamp, and idempotent
`INSERT OR IGNORE`. Each check queries the database, so other processes can
observe committed blocks. The existing JSON list is still supported.

## Usage

```python
from pathlib import Path
from acios.core.suppression import SuppressionEngine

guard = SuppressionEngine(
    sqlite_path=Path.home() / ".local" / "share" / "acios" / "suppression.sqlite"
)
guard.block("example@example.org", reason="confirmed opt-out")
assert guard.is_suppressed("example@example.org")
```

Use a **private, persistent local path** excluded from Git and backups shared
with others. `suppression_files=[]` explicitly skips the default JSON file
for isolated tests. Without `sqlite_path`, the legacy in-memory behavior
remains; operators must not assume persistence. SQLite connection errors during
reads fail closed; errors during writes propagate rather than falsely reporting
a successful block. Corrupt JSON lists now raise instead of silently being
ignored. Records are intentionally not exposed via a network API.

**Not a complete dispatch safety guarantee.** Existing application call sites
must explicitly pass the same durable guard, and the final human-approved
dispatch boundary still requires an authoritative suppression check. The
repository also contains an optional MongoDB backend, which is not synchronized
with this local SQLite file. No sending, remote scraping, mailbox reads, or
webhook exposure is enabled. This PR deliberately does not change the separate
EmailEngine bounce PR (#10) or production configuration.

## Offline verification

Run `python -m pytest tests/test_sqlite_suppression_registry.py -q`
and `ruff check acios/core/suppression.py tests/test_sqlite_suppression_registry.py`.
Check the GitHub Actions Python 3.11/3.12 matrix before merging.

## Open-source fit assessment

| Project | License | Fit / caution |
| --- | --- | --- |
| [sqlite-utils](https://github.com/simonw/sqlite-utils) | Apache-2.0 | Useful migration and inspection reference; standard-library sqlite3 is sufficient here. |
| [MCP Python SDK](https://github.com/modelcontextprotocol/python-sdk) | MIT | Preserve local tool approval boundaries; no MCP changes required. |
| [Trafilatura](https://github.com/adbar/trafilatura) | Apache-2.0 | Authorized HTML extraction; not relevant to suppression writes. |
| [Scrapy](https://github.com/scrapy/scrapy) | BSD-3-Clause | Crawl orchestration only for permitted public sites; not part of this fix. |
| [Google API Python Client](https://github.com/googleapis/google-api-python-client) | Apache-2.0 | Draft staging with explicit review; never unattended sending. |
| [OpenTelemetry Python](https://github.com/open-telemetry/opentelemetry-python) | Apache-2.0 | Optional metrics without email addresses or candidate details. |

These are integration candidates, not imported dependencies. Licenses and
compatibility should be revalidated before any future code reuse. No
third-party code was copied.
