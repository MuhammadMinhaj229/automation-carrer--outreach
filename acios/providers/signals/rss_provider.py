"""Legacy Google News RSS adapter.

RSS results are search leads. Neither a matching keyword nor a publication
timestamp proves a business event, an organization identity, or a primary source.
"""

import urllib.parse
from urllib.parse import urlsplit
from datetime import datetime, timezone
from typing import List, Optional

import feedparser

from acios.core.interfaces import SignalProvider, SignalItem

HIGH_VALUE_TRIGGER_WORDS = [
    "pilot", "expansion", "facility", "plant", "investment", "contract",
    "partnership", "launch", "solar", "biofuel", "camelina", "lithium",
    "carbon", "water", "hydrogen", "vision 2030", "vision 2040", "sohar",
]


class RSSSignalProvider(SignalProvider):
    """Discover unverified news leads; never promote an RSS hit to primary."""

    GOOGLE_NEWS_BASE = "https://news.google.com/rss/search?q={query}&hl=en-US&gl=US&ceid=US:en"

    def __init__(self, user_agent: Optional[str] = None):
        self.user_agent = user_agent or "ACIOS-SignalMonitor/1.0"

    def _score_headline(self, title: str, summary: str) -> int:
        text = f"{title} {summary}".lower()
        score = 40
        for kw in HIGH_VALUE_TRIGGER_WORDS:
            if kw in text:
                score += 10
        return min(score, 100)

    def fetch_signals(
        self,
        query: str,
        keywords: Optional[List[str]] = None,
        min_score: int = 50,
    ) -> List[SignalItem]:
        """Return only feed-backed leads with a title and a source URL.

        The feed publication timestamp is not an event date. Unknown publication
        dates stay unknown; the search query is not an organization identity.
        """
        encoded_q = urllib.parse.quote_plus(query)
        feed_url = self.GOOGLE_NEWS_BASE.format(query=encoded_q)
        try:
            feed = feedparser.parse(feed_url)
        except Exception as exc:
            print(f"[RSSSignalProvider] Error fetching feed: {type(exc).__name__}")
            return []

        results: List[SignalItem] = []
        for entry in getattr(feed, "entries", [])[:10]:
            title = str(entry.get("title") or "").strip()
            link = str(entry.get("link") or "").strip()
            if not title or not link:
                continue
            # A feed entry is untrusted input; never surface non-web or
            # credential-bearing links as reviewable source documents.
            try:
                parts = urlsplit(link)
                if parts.scheme not in {"http", "https"} or not parts.hostname:
                    continue
                if parts.username or parts.password:
                    continue
            except ValueError:
                continue

            title_clean = title.rsplit(" - ", 1)[0].strip() if " - " in title else title
            if not title_clean:
                continue

            published_at = None
            parsed = entry.get("published_parsed")
            if parsed:
                try:
                    published_at = datetime(*parsed[:6], tzinfo=timezone.utc).isoformat()
                except (TypeError, ValueError, OverflowError):
                    pass

            score = self._score_headline(title, str(entry.get("summary") or ""))
            if score < min_score:
                continue
            results.append(SignalItem(
                headline=title_clean,
                organization_name=None,
                signal_date=published_at,
                source_url=link,
                details=f"Unverified RSS discovery lead for topic '{query}': {title_clean}",
                score=score,
                evidence_tier="DISCOVERED_NEEDS_PRIMARY_VERIFICATION",
            ))
        return results
