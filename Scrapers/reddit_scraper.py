"""
scrapers/reddit_scraper.py
Scrapes Reddit for MySQL/database pain signals using the official PRAW library.

Setup:
  1. Go to https://www.reddit.com/prefs/apps
  2. Click "Create App" → choose "script" type
  3. Copy client_id and client_secret into your .env file
"""

from datetime import datetime, timezone
from typing import List, Dict
import sys

from signal_engine import score_content, extract_company
from config import (
    REDDIT_CLIENT_ID,
    REDDIT_CLIENT_SECRET,
    REDDIT_USER_AGENT,
    REDDIT_SUBREDDITS,
    MYSQL_SEARCH_KEYWORDS,
    MIN_SCORE_THRESHOLD,
    POSTS_PER_KEYWORD,
)


def scrape_reddit() -> List[Dict]:
    if not REDDIT_CLIENT_ID or not REDDIT_CLIENT_SECRET:
        print("[Reddit] Skipping — no API credentials in .env (REDDIT_CLIENT_ID / REDDIT_CLIENT_SECRET)")
        return []

    try:
        import praw
    except ImportError:
        print("[Reddit] praw not installed. Run: pip install praw")
        return []

    try:
        reddit = praw.Reddit(
            client_id=REDDIT_CLIENT_ID,
            client_secret=REDDIT_CLIENT_SECRET,
            user_agent=REDDIT_USER_AGENT,
            read_only=True,
        )
        # Verify auth
        reddit.user.me()
    except Exception as e:
        # read_only mode raises 401 on user.me() — that's fine
        if "401" not in str(e) and "prawcore" not in str(e).lower():
            print(f"[Reddit] Auth error: {e}")

    prospects: List[Dict] = []
    seen_urls: set = set()

    def process_post(post, source_tag: str):
        url = f"https://reddit.com{post.permalink}"
        if url in seen_urls:
            return
        seen_urls.add(url)

        title = post.title or ""
        content = post.selftext or ""
        combined = f"{title} {content}"
        score, signals, tags = score_content(title, content, source_tag)

        if score >= MIN_SCORE_THRESHOLD:
            company = extract_company(combined)
            prospects.append({
                "title": title[:300],
                "content": content[:3000],
                "url": url,
                "source": "reddit",
                "author": str(post.author) if post.author else "unknown",
                "company": company,
                "score": score,
                "signals": signals,
                "created_at": datetime.fromtimestamp(
                    post.created_utc, tz=timezone.utc
                ).isoformat(),
                "tags": list(set(tags + [f"r/{post.subreddit.display_name}"])),
            })

    # ── 1. Browse key subreddits ───────────────────────────────────────────
    for sub_name in REDDIT_SUBREDDITS:
        try:
            subreddit = reddit.subreddit(sub_name)
            source_tag = f"reddit_{sub_name}" if sub_name == "mysql" else "reddit"
            for post in list(subreddit.hot(limit=30)) + list(subreddit.new(limit=30)):
                process_post(post, source_tag)
        except Exception as e:
            print(f"[Reddit] Error browsing r/{sub_name}: {e}")

    # ── 2. Keyword searches across top MySQL-relevant subreddits ──────────
    search_subs = ["mysql", "Database", "SQL", "devops", "sysadmin", "learnprogramming"]
    for keyword in MYSQL_SEARCH_KEYWORDS[:8]:      # limit to avoid rate limits
        for sub_name in search_subs:
            try:
                subreddit = reddit.subreddit(sub_name)
                results = subreddit.search(
                    keyword, sort="new", time_filter="month", limit=POSTS_PER_KEYWORD
                )
                for post in results:
                    process_post(post, "reddit")
            except Exception as e:
                print(f"[Reddit] Search error '{keyword}' in r/{sub_name}: {e}")

    print(f"[Reddit] Found {len(prospects)} prospects")
    return prospects
