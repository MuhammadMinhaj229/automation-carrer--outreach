"""Legacy Prefect-compatible RSS discovery workflow.

The workflow never invents corporate events, organization identities, or dates.
RSS search results are saved only as unverified local provenance-ledger leads.
"""

from datetime import datetime, timezone
from typing import List, Optional
from urllib.parse import urlsplit

try:
    from prefect import flow, task
except ImportError:
    # Local-first execution does not require Prefect.
    def task(name=None, **kwargs):
        def decorator(fn):
            return fn
        return decorator

    def flow(name=None, **kwargs):
        def decorator(fn):
            return fn
        return decorator

from acios.core.repository import CareerRepository
from acios.core.interfaces import SignalItem
from acios.providers.signals.rss_provider import RSSSignalProvider


@task(name="fetch_gcc_expansion_signals", retries=2, retry_delay_seconds=5)
def fetch_expansion_signals(target_sectors: List[str]) -> List[SignalItem]:
    """Fetch bounded RSS discovery leads, not fabricated registry-backed events."""
    topics = [
        "Oman camelina pilot",
        "Sohar Freezone lithium plant",
        "Oman Cables Plant 3",
        "44.01 carbon removal Oman",
        "HutanBio Wakud biofuel",
    ]
    # User-selected sectors add queries, not asserted events or identities.
    topics.extend(str(sector).strip()[:80] for sector in target_sectors[:8] if str(sector).strip())
    provider = RSSSignalProvider()
    discovered: List[SignalItem] = []
    seen = set()
    for topic in topics:
        for item in provider.fetch_signals(topic, min_score=60)[:2]:
            if not item.headline.strip() or not item.source_url:
                continue
            key = (item.source_url.strip(), item.headline.strip())
            if key in seen:
                continue
            seen.add(key)
            # A provider result is not evidence of verification, even if a
            # legacy/custom adapter supplied an unsafe evidence_tier value.
            discovered.append(item.model_copy(update={
                "organization_name": None,
                "evidence_tier": "DISCOVERED_NEEDS_PRIMARY_VERIFICATION",
            }))
    return discovered


@task(name="filter_and_persist_signals")
def filter_and_persist_signals(signals: List[SignalItem]) -> int:
    """Persist only sourced, unverified leads to the canonical SQLite ledger.

    Do not write the legacy organizations/signals tables: doing so would
    fabricate an organization and give downstream dossiers an unreviewed event.
    """
    repo = CareerRepository()
    persisted = 0
    retrieved_at = datetime.now(timezone.utc).isoformat()
    for item in signals:
        if item.score < 50 or not item.headline.strip() or not item.source_url:
            continue
        try:
            parts = urlsplit(item.source_url.strip())
            if parts.scheme not in {"http", "https"} or not parts.hostname:
                continue
            if parts.username or parts.password:
                continue
        except ValueError:
            continue

        repo.record_discovery_event({
            "organization_name": None,
            "entity_resolution_status": "UNRESOLVED",
            "headline": item.headline.strip(),
            "source_url": item.source_url.strip(),
            "source_outlet": "Google News RSS (aggregator)",
            "source_type": "NEWS_AGGREGATOR_RESULT",
            "published_at": item.signal_date,
            "published_date": item.signal_date[:10] if item.signal_date else None,
            "published_date_raw": None,
            "event_date": None,
            "event_date_status": "NOT_EXTRACTED",
            "evidence_excerpt": "",
            "discovery_note": item.details,
            "trigger_category": "UNCLASSIFIED",
            "score": item.score,
            "score_type": "HEURISTIC_KEYWORD_RELEVANCE_NOT_PROBABILITY",
            "verification_status": "DISCOVERED_NEEDS_PRIMARY_VERIFICATION",
            "retrieved_at": retrieved_at,
        })
        persisted += 1
    return persisted


@flow(name="daily_signal_scan_flow")
def run_daily_signal_scan(sectors: Optional[List[str]] = None) -> int:
    """Save unverified RSS leads locally; no outreach or verified export."""
    target_sectors = sectors or [
        "Green Tech", "Logistics", "Digital Infrastructure", "Water & AgriTech",
    ]
    signals = fetch_expansion_signals(target_sectors)
    count = filter_and_persist_signals(signals)
    print(f"[*] RSS discovery completed: {count} unverified leads stored/updated.")
    return count


if __name__ == "__main__":
    run_daily_signal_scan()
