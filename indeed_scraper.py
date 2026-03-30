"""
scrapers/indeed_scraper.py
Scrapes Indeed's public RSS feeds for MySQL-related job postings.
Job postings are strong buying signals — a company actively hiring a DBA
or DB performance engineer is experiencing (or anticipating) database pain.

No API key required.
"""

import requests
import feedparser
from datetime import datetime, timezone
from typing import List, Dict
from email.utils import parsedate_to_datetime

from signal_engine import score_content, extract_company
from config import JOB_KEYWORDS, MIN_SCORE_THRESHOLD

HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; MySQLProspectFinder/1.0; RSS reader)"
}


def _parse_date(date_str: str) -> str:
    try:
        return parsedate_to_datetime(date_str).isoformat()
    except Exception:
        return datetime.now(tz=timezone.utc).isoformat()


def _fetch_indeed_rss(keyword: str) -> List[Dict]:
    """Fetch Indeed RSS feed for a keyword."""
    import urllib.parse
    encoded = urllib.parse.quote(keyword)
    url = f"https://www.indeed.com/rss?q={encoded}&sort=date&fromage=30"
    try:
        resp = requests.get(url, headers=HEADERS, timeout=15)
        if resp.status_code == 200:
            return feedparser.parse(resp.content).entries
    except Exception as e:
        print(f"[Indeed] Error for '{keyword}': {e}")
    return []


def scrape_indeed() -> List[Dict]:
    prospects: List[Dict] = []
    seen_urls: set = set()

    for keyword in JOB_KEYWORDS:
        entries = _fetch_indeed_rss(keyword)

        for entry in entries:
            url = entry.get("link", "")
            if not url or url in seen_urls:
                continue
            seen_urls.add(url)

            title = entry.get("title", "") or ""
            content = entry.get("summary", "") or ""

            # Job postings: append keyword context so signal engine picks it up
            augmented_content = f"{content} {keyword}"
            score, signals, tags = score_content(title, augmented_content, "indeed")

            # Jobs always get a minimum score boost — they're inherently interesting
            score = max(score, 30) if ("mysql" in title.lower() or "mysql" in content.lower()) else score
            score = max(score, 20) if score > 0 else score

            if score >= MIN_SCORE_THRESHOLD:
                # Try to extract company from Indeed title format: "Job Title - Company Name"
                company = ""
                if " - " in title:
                    parts = title.rsplit(" - ", 1)
                    if len(parts) == 2:
                        company = parts[1].strip()
                if not company:
                    company = extract_company(f"{title} {content}")

                prospects.append({
                    "title": title[:300],
                    "content": content[:3000],
                    "url": url,
                    "source": "indeed",
                    "author": "",
                    "company": company,
                    "score": score,
                    "signals": list(set(signals + ["📋 Job Posting"])),
                    "created_at": _parse_date(entry.get("published", "")),
                    "tags": list(set(tags + ["job-posting"])),
                })

    print(f"[Indeed] Found {len(prospects)} prospects")
    return prospects
