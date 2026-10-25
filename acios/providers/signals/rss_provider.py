"""
ACIOS Stage 2 Signal Provider: Google News & GCC RSS Feeds.
Monitors industrial expansions, pilot projects, and economic partnerships
across Oman, Saudi Arabia, the UAE, and the wider GCC region.
"""

import urllib.parse
from datetime import datetime, timezone
from typing import List, Optional
import feedparser

from acios.core.interfaces import SignalProvider, SignalItem

HIGH_VALUE_TRIGGER_WORDS = [
    "pilot", "expansion", "facility", "plant", "investment", "contract",
    "partnership", "launch", "solar", "biofuel", "camelina", "lithium",
    "carbon", "water", "hydrogen", "vision 2030", "vision 2040", "sohar"
]


class RSSSignalProvider(SignalProvider):
    """Monitors live RSS and Google News feeds for industrial signals."""

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
        min_score: int = 50
    ) -> List[SignalItem]:
        """Fetches and scores corporate signals for a query."""
        encoded_q = urllib.parse.quote_plus(query)
        feed_url = self.GOOGLE_NEWS_BASE.format(query=encoded_q)

        try:
            feed = feedparser.parse(feed_url)
        except Exception as e:
            print(f"[RSSSignalProvider] Error fetching feed: {e}")
            return []

        results: List[SignalItem] = []
        for entry in feed.entries[:10]:
            title = entry.get("title", "")
            link = entry.get("link", "")
            summary = entry.get("summary", "")
            published = entry.get("published", datetime.now(timezone.utc).strftime("%Y-%m-%d"))

            # Derive organization name from title if possible (e.g. "Title - Source")
            org_candidate = query
            if " - " in title:
                parts = title.rsplit(" - ", 1)
                title_clean = parts[0]
                source_outlet = parts[1]
            else:
                title_clean = title

            score = self._score_headline(title, summary)
            if score >= min_score:
                item = SignalItem(
                    headline=title_clean,
                    organization_name=org_candidate,
                    signal_date=published[:16] if len(published) > 16 else published,
                    source_url=link,
                    details=f"RSS Intelligence match for '{query}': {title_clean}",
                    score=score,
                    evidence_tier="Verified Primary (RSS Feed)"
                )
                results.append(item)

        return results
