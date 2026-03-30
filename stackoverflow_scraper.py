"""
scrapers/stackoverflow_scraper.py
Uses the free Stack Exchange API (no API key required for read-only access,
though an API key raises the daily quota from 300 to 10,000 requests).

Docs: https://api.stackexchange.com/docs
"""

import requests
from datetime import datetime, timezone
from typing import List, Dict

from signal_engine import score_content, extract_company
from config import MYSQL_SEARCH_KEYWORDS, MIN_SCORE_THRESHOLD, POSTS_PER_KEYWORD

STACK_API = "https://api.stackexchange.com/2.3"

# Optional: set STACK_API_KEY in .env to raise quota
import os
STACK_KEY = os.getenv("STACK_API_KEY", "")


def _get_questions(intitle: str, tagged: str = "", page: int = 1) -> List[Dict]:
    params = {
        "order":    "desc",
        "sort":     "creation",
        "intitle":  intitle,
        "site":     "stackoverflow",
        "pagesize": min(POSTS_PER_KEYWORD, 100),
        "page":     page,
        "filter":   "withbody",
    }
    if tagged:
        params["tagged"] = tagged
    if STACK_KEY:
        params["key"] = STACK_KEY

    try:
        resp = requests.get(f"{STACK_API}/questions", params=params, timeout=12)
        if resp.status_code == 200:
            return resp.json().get("items", [])
    except Exception as e:
        print(f"[SO] Request error for '{intitle}': {e}")
    return []


def scrape_stackoverflow() -> List[Dict]:
    prospects: List[Dict] = []
    seen_ids: set = set()

    keyword_searches = MYSQL_SEARCH_KEYWORDS[:10]   # respect free quota

    # Also search by MySQL tag to catch questions that describe pain
    tag_searches = [
        ("performance", "mysql"),
        ("replication", "mysql"),
        ("migration", "mysql"),
        ("crash", "mysql"),
        ("slow queries", "mysql"),
        ("deadlock", "mysql"),
        ("timeout", "mysql"),
        ("out of memory", "mysql"),
    ]

    for keyword in keyword_searches:
        for item in _get_questions(intitle=keyword):
            q_id = item.get("question_id")
            if q_id in seen_ids:
                continue
            seen_ids.add(q_id)

            title = item.get("title", "")
            content = item.get("body", "")[:3000]
            tags = item.get("tags", [])
            url = item.get("link", "")

            score, signals, prospect_tags = score_content(
                title, f"{content} {' '.join(tags)}", "stackoverflow"
            )

            if score >= MIN_SCORE_THRESHOLD:
                prospects.append({
                    "title": title[:300],
                    "content": content,
                    "url": url,
                    "source": "stackoverflow",
                    "author": item.get("owner", {}).get("display_name", "unknown"),
                    "company": extract_company(f"{title} {content}"),
                    "score": score,
                    "signals": signals,
                    "created_at": datetime.fromtimestamp(
                        item.get("creation_date", 0), tz=timezone.utc
                    ).isoformat(),
                    "tags": list(dict.fromkeys(prospect_tags + tags)),
                })

    for intitle_kw, tag in tag_searches:
        for item in _get_questions(intitle=intitle_kw, tagged=tag):
            q_id = item.get("question_id")
            if q_id in seen_ids:
                continue
            seen_ids.add(q_id)

            title = item.get("title", "")
            content = item.get("body", "")[:3000]
            tags = item.get("tags", [])
            url = item.get("link", "")

            score, signals, prospect_tags = score_content(
                title, f"{content} {' '.join(tags)}", "stackoverflow"
            )

            if score >= MIN_SCORE_THRESHOLD:
                prospects.append({
                    "title": title[:300],
                    "content": content,
                    "url": url,
                    "source": "stackoverflow",
                    "author": item.get("owner", {}).get("display_name", "unknown"),
                    "company": extract_company(f"{title} {content}"),
                    "score": score,
                    "signals": signals,
                    "created_at": datetime.fromtimestamp(
                        item.get("creation_date", 0), tz=timezone.utc
                    ).isoformat(),
                    "tags": list(dict.fromkeys(prospect_tags + tags)),
                })

    print(f"[StackOverflow] Found {len(prospects)} prospects")
    return prospects
