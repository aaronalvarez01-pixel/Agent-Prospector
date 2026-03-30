"""
config.py — Centralized configuration for MySQL Prospect Finder.
Copy .env.example to .env and fill in your API keys.
"""

import os
from dotenv import load_dotenv

load_dotenv()

# ── Reddit API ─────────────────────────────────────────────────────────────────
REDDIT_CLIENT_ID = os.getenv("REDDIT_CLIENT_ID", "")
REDDIT_CLIENT_SECRET = os.getenv("REDDIT_CLIENT_SECRET", "")
REDDIT_USER_AGENT = os.getenv("REDDIT_USER_AGENT", "MySQLProspectFinder/1.0")

# ── Twitter/X API ──────────────────────────────────────────────────────────────
TWITTER_BEARER_TOKEN = os.getenv("TWITTER_BEARER_TOKEN", "")

# ── Scoring ────────────────────────────────────────────────────────────────────
MIN_SCORE_THRESHOLD = int(os.getenv("MIN_SCORE_THRESHOLD", "15"))
POSTS_PER_KEYWORD = int(os.getenv("POSTS_PER_KEYWORD", "50"))

# ── Subreddits to monitor ──────────────────────────────────────────────────────
REDDIT_SUBREDDITS = [
    "mysql",
    "Database",
    "SQL",
    "webdev",
    "devops",
    "sysadmin",
    "django",
    "PHP",
    "node",
    "rails",
    "aws",
    "selfhosted",
    "learnprogramming",
    "ProgrammerHumor",
    "ExperiencedDevs",
]

# ── Keywords for all scrapers ──────────────────────────────────────────────────
MYSQL_SEARCH_KEYWORDS = [
    "mysql slow queries",
    "mysql performance",
    "mysql crash",
    "mysql replication",
    "mysql migration",
    "mysql deadlock",
    "mysql out of memory",
    "mysql timeout",
    "mysql help",
    "mysql error",
    "mysql down",
    "mysql broken",
    "mysql scaling",
    "mysql upgrade",
    "mysql connection pool",
]

DB_SEARCH_KEYWORDS = [
    "database performance issues",
    "database scaling problems",
    "slow database queries",
    "database migration help",
    "database crash",
    "database down",
    "sql performance issues",
    "rds performance problems",
    "aurora mysql issues",
]

JOB_KEYWORDS = [
    "mysql dba",
    "database administrator mysql",
    "mysql database engineer",
    "database reliability engineer mysql",
    "mysql performance tuning",
    "database migration engineer",
]

# All keywords merged (deduplicated)
ALL_KEYWORDS = list(dict.fromkeys(MYSQL_SEARCH_KEYWORDS + DB_SEARCH_KEYWORDS))
