"""
scrapers/devto_scraper.py
Uses the free Dev.to public API — no auth required for read access.

API docs: https://developers.forem.com/api
"""

import requests
from datetime import datetime, timezone
from typing import List, Dict

from signal_engine import score_content, extract_company
from config import MIN_SCORE_THRESHOLD, POSTS_PER_KEYWORD

DEVTO_API = "https://dev.to/api"

# Tags to fetch articles from (Dev.to uses tags heavily)
DEVTO_TAGS = [
    "mysql",
    "database",
    "sql",
    "postgres",          # mention for comparisons: "migrating from mysql to..."
    "devops",
    "backend",
    "webdev",
]

# Extra keyword searches
DEVTO_SEARCHES = [
    "mysql performance",
    "mysql migration",
    "mysql crash",
    "database scaling",
    "mysql slow",
]


def _fetch_by_tag(tag: str, per_page: int = 30) -> List[Dict]:
    try:
        resp = requests.get(
            f"{DEVTO_API}/articles",
            params={"tag": tag, "per_page": per_page, "state": "fresh"},
            timeout=12,
        )
        if resp.status_code == 200:
            return resp.json()
    except Exception as e:
        print(f"[Dev.to] Error fetching tag '{tag}': {e}")
    return []


def _fetch_by_search(query: str, per_page: int = 20) -> List[Dict]:
    try:
        # Dev.to doesn't have a native search endpoint in v1 API,
        # so we use the articles endpoint and filter locally
        resp = requests.get(
            f"{DEVTO_API}/articles",
            params={"per_page": per_page, "top": 1},
            timeout=12,
        )
        # Alternative: use published articles search if available
        if resp.status_code == 200:
            articles = resp.json()
            q_lower = query.lower()
            return [
                a for a in articles
                if q_lower in (a.get("title", "") + a.get("description", "")).lower()
            ]
    except Exception as e:
        print(f"[Dev.to] Search error for '{query}': {e}")
    return []


def scrape_devto() -> List[Dict]:
    prospects: List[Dict] = []
    seen_ids: set = set()

    def process_article(article: Dict):
        article_id = article.get("id")
        if article_id in seen_ids:
            return
        seen_ids.add(article_id)

        title = article.get("title", "") or ""
        description = article.get("description", "") or ""
        tag_list = article.get("tag_list", []) or []
        url = article.get("url", "") or ""
        user = article.get("user", {}) or {}

        content = f"{description} Tags: {', '.join(tag_list)}"
        score, signals, prospect_tags = score_content(title, content, "devto")

        if score >= MIN_SCORE_THRESHOLD:
            prospects.append({
                "title": title[:300],
                "content": content[:3000],
                "url": url,
                "source": "devto",
                "author": user.get("name", user.get("username", "unknown")),
                "company": extract_company(f"{title} {description}"),
                "score": score,
                "signals": signals,
                "created_at": article.get("published_at", datetime.now(tz=timezone.utc).isoformat()),
                "tags": list(dict.fromkeys(prospect_tags + tag_list)),
            })

    for tag in DEVTO_TAGS:
        for article in _fetch_by_tag(tag, per_page=POSTS_PER_KEYWORD):
            process_article(article)

    for query in DEVTO_SEARCHES:
        for article in _fetch_by_search(query):
            process_article(article)

    print(f"[Dev.to] Found {len(prospects)} prospects")
    return prospects
