"""
scrapers/blogs_scraper.py
Scrapes:
  1. Google News RSS — broad coverage of tech blogs, company engineering blogs, etc.
  2. Curated tech blog RSS feeds — Planet MySQL, Percona Blog, high-signal sources
  3. DBA StackExchange — for operational DBA pain signals

No API key required.
"""

import requests
import feedparser
from datetime import datetime, timezone
from typing import List, Dict
from email.utils import parsedate_to_datetime

from signal_engine import score_content, extract_company
from config import MYSQL_SEARCH_KEYWORDS, DB_SEARCH_KEYWORDS, MIN_SCORE_THRESHOLD

HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; MySQLProspectFinder/1.0; RSS reader)"}

# ── Curated high-signal RSS feeds ─────────────────────────────────────────────
CURATED_FEEDS = [
    # MySQL / DB focused blogs
    ("Percona Blog",     "https://www.percona.com/blog/feed/"),
    ("Planet MySQL",     "https://planet.mysql.com/rss20.xml"),
    ("Use The Index Luke", "https://use-the-index-luke.com/blog/rss"),
    ("DBA StackExchange", "https://dba.stackexchange.com/feeds/tag/mysql"),
    # Engineering blogs that discuss DB issues
    ("High Scalability", "http://feeds.feedburner.com/HighScalability"),
    ("Martin Fowler",    "https://martinfowler.com/feed.atom"),
]

# ── Google News search queries ─────────────────────────────────────────────────
GNEWS_QUERIES = [
    "mysql performance issues",
    "mysql database problems",
    "mysql migration problems",
    "mysql scaling issues",
    "mysql database outage",
    "database performance mysql",
    "mysql slow queries production",
]


def _parse_date(date_str: str) -> str:
    try:
        return parsedate_to_datetime(date_str).isoformat()
    except Exception:
        return datetime.now(tz=timezone.utc).isoformat()


def _entries_from_feed(url: str) -> List:
    try:
        resp = requests.get(url, headers=HEADERS, timeout=15)
        if resp.status_code == 200:
            return feedparser.parse(resp.content).entries
    except Exception as e:
        print(f"[Blogs] Feed error {url}: {e}")
    return []


def scrape_blogs() -> List[Dict]:
    prospects: List[Dict] = []
    seen_urls: set = set()

    def process_entry(entry: Dict, source_name: str, source_url: str = ""):
        url = entry.get("link", "") or source_url
        if not url or url in seen_urls:
            return
        seen_urls.add(url)

        title = entry.get("title", "") or ""
        content = (
            entry.get("summary", "")
            or entry.get("content", [{}])[0].get("value", "")
            or ""
        )[:3000]

        score, signals, tags = score_content(title, content, "blog_news")

        if score >= MIN_SCORE_THRESHOLD:
            prospects.append({
                "title": title[:300],
                "content": content,
                "url": url,
                "source": "blog_news",
                "author": source_name,
                "company": extract_company(f"{title} {content}"),
                "score": score,
                "signals": signals,
                "created_at": _parse_date(entry.get("published", entry.get("updated", ""))),
                "tags": tags + ["blog"],
            })

    # ── 1. Curated feeds ──────────────────────────────────────────────────
    for feed_name, feed_url in CURATED_FEEDS:
        for entry in _entries_from_feed(feed_url):
            process_entry(entry, feed_name)

    # ── 2. Google News RSS ────────────────────────────────────────────────
    import urllib.parse
    for query in GNEWS_QUERIES:
        encoded = urllib.parse.quote(query)
        gnews_url = f"https://news.google.com/rss/search?q={encoded}&hl=en-US&gl=US&ceid=US:en"
        for entry in _entries_from_feed(gnews_url):
            # Google News title includes "- Source Name" at end
            title_raw = entry.get("title", "") or ""
            source_name = "Blog/News"
            if " - " in title_raw:
                parts = title_raw.rsplit(" - ", 1)
                title_raw = parts[0].strip()
                source_name = parts[1].strip()
            process_entry({**entry, "title": title_raw}, source_name)

    print(f"[Blogs/News] Found {len(prospects)} prospects")
    return prospects
