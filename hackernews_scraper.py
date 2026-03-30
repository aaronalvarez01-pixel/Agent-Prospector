"""
scrapers/hackernews_scraper.py
Uses the HackerNews Algolia search API — completely free, no auth needed.

API docs: https://hn.algolia.com/api
"""

import requests
from datetime import datetime, timezone
from typing import List, Dict

from signal_engine import score_content, extract_company
from config import MYSQL_SEARCH_KEYWORDS, DB_SEARCH_KEYWORDS, MIN_SCORE_THRESHOLD, POSTS_PER_KEYWORD

HN_ALGOLIA = "https://hn.algolia.com/api/v1"


def _search_hn(query: str, hits_per_page: int = 30, sort_by_date: bool = True) -> List[Dict]:
    endpoint = "search_by_date" if sort_by_date else "search"
    params = {
        "query":         query,
        "tags":          "(story,ask_hn,show_hn)",
        "hitsPerPage":   hits_per_page,
    }
    try:
        resp = requests.get(f"{HN_ALGOLIA}/{endpoint}", params=params, timeout=12)
        if resp.status_code == 200:
            return resp.json().get("hits", [])
    except Exception as e:
        print(f"[HN] Request error for '{query}': {e}")
    return []


def scrape_hackernews() -> List[Dict]:
    prospects: List[Dict] = []
    seen_ids: set = set()

    all_keywords = MYSQL_SEARCH_KEYWORDS + DB_SEARCH_KEYWORDS[:5]

    for keyword in all_keywords:
        for hit in _search_hn(keyword, hits_per_page=POSTS_PER_KEYWORD):
            item_id = hit.get("objectID")
            if item_id in seen_ids:
                continue
            seen_ids.add(item_id)

            title = hit.get("title", "") or ""
            # story_text is the body for Ask HN posts
            content = hit.get("story_text", "") or hit.get("comment_text", "") or ""
            url = hit.get("url", "") or f"https://news.ycombinator.com/item?id={item_id}"

            score, signals, tags = score_content(title, content, "hackernews")

            if score >= MIN_SCORE_THRESHOLD:
                prospects.append({
                    "title": title[:300],
                    "content": content[:3000],
                    "url": url,
                    "source": "hackernews",
                    "author": hit.get("author", "unknown"),
                    "company": extract_company(f"{title} {content}"),
                    "score": score,
                    "signals": signals,
                    "created_at": hit.get("created_at", datetime.now(tz=timezone.utc).isoformat()),
                    "tags": tags,
                })

    # Extra: "Ask HN" posts about database problems
    for query in ["Ask HN: MySQL", "Ask HN: database performance", "Ask HN: database migration"]:
        for hit in _search_hn(query, hits_per_page=20):
            item_id = hit.get("objectID")
            if item_id in seen_ids:
                continue
            seen_ids.add(item_id)
            title = hit.get("title", "") or ""
            content = hit.get("story_text", "") or ""
            url = f"https://news.ycombinator.com/item?id={item_id}"
            score, signals, tags = score_content(title, content, "hackernews")
            if score >= MIN_SCORE_THRESHOLD:
                prospects.append({
                    "title": title[:300],
                    "content": content[:3000],
                    "url": url,
                    "source": "hackernews",
                    "author": hit.get("author", "unknown"),
                    "company": extract_company(f"{title} {content}"),
                    "score": score,
                    "signals": signals,
                    "created_at": hit.get("created_at", datetime.now(tz=timezone.utc).isoformat()),
                    "tags": tags + ["ask-hn"],
                })

    print(f"[HackerNews] Found {len(prospects)} prospects")
    return prospects
