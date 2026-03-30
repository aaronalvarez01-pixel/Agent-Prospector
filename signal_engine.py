"""
signal_engine.py — Scores content for MySQL/database prospect value.

Scoring philosophy:
  - MySQL-specific pain words are worth the most (we want MySQL customers)
  - General DB pain adds moderate value
  - Job postings signal a company actively investing in DB
  - Urgency/complaint tone amplifies the base score
  - Score is capped at 100
"""

import re
from typing import Dict, List, Tuple


# ── MySQL-specific pain signals ────────────────────────────────────────────────
# Each maps a keyword → base score contribution (before amplifiers)
MYSQL_PAIN_SIGNALS: Dict[str, int] = {
    # Hard outages / data issues
    "mysql crash":          50,
    "mysql crashed":        50,
    "mysql down":           50,
    "mysql corrupt":        55,
    "mysql lost data":      60,
    "mysql data loss":      60,
    "mysql outage":         55,
    "mysql failed":         45,
    "mysql broken":         45,
    # Performance pain
    "mysql slow":           40,
    "mysql slowdown":       40,
    "mysql performance":    38,
    "mysql query slow":     42,
    "mysql high cpu":       42,
    "mysql memory":         38,
    "mysql out of memory":  50,
    "mysql timeout":        44,
    "mysql deadlock":       44,
    "mysql lock wait":      42,
    "mysql replication lag": 45,
    # Operational pain
    "mysql replication":    35,
    "mysql migration":      35,
    "mysql upgrade":        30,
    "mysql connection pool": 35,
    "mysql max connections": 38,
    "mysql scaling":        40,
    "mysql scale":          38,
    "mysql growing":        28,
    # General help-seeking
    "mysql problem":        44,
    "mysql issue":          42,
    "mysql help":           38,
    "mysql error":          42,
    "mysql troubleshoot":   38,
    "mysql fix":            40,
    # Tech identifiers (lower weight — signals stack but not pain)
    "mysql 5.7":            22,
    "mysql 8.0":            18,
    "mysql rds":            25,
    "aurora mysql":         25,
    "mysql innodb":         22,
    "innodb":               18,
    "percona":              20,
    "mariadb":              20,
}

# ── General DB pain signals ────────────────────────────────────────────────────
DB_PAIN_SIGNALS: Dict[str, int] = {
    "database slow":            22,
    "database performance":     22,
    "database crash":           28,
    "database down":            28,
    "database outage":          30,
    "database migration":       18,
    "database scaling":         22,
    "database timeout":         26,
    "database error":           22,
    "database problem":         22,
    "database help":            18,
    "slow queries":             26,
    "query optimization":       18,
    "sql performance":          22,
    "rds performance":          22,
    "switching database":       18,
    "database vendor":          14,
    "db migration":             18,
    "db issues":                22,
    "db crash":                 28,
    "db slow":                  22,
}

# ── Job posting signals ────────────────────────────────────────────────────────
JOB_SIGNALS: Dict[str, int] = {
    "mysql dba":                    35,
    "mysql database administrator": 35,
    "mysql engineer":               32,
    "database administrator":       25,
    "database reliability":         28,
    "dbre":                         28,
    "database performance engineer":32,
    "mysql performance tuning":     30,
    "database migration engineer":  28,
    "dba position":                 25,
    "seeking dba":                  30,
    "hiring dba":                   30,
    "database architect":           22,
}

# ── Urgency / complaint amplifier words ───────────────────────────────────────
URGENCY_WORDS = {
    "urgent", "critical", "down", "broken", "failed", "failing",
    "crashing", "corrupted", "lost data", "production down",
    "outage", "disaster", "emergency", "asap", "please help",
    "frustrated", "nightmare", "terrible", "awful", "horrible",
    "can't sleep", "panicking", "freaking out", "desperate",
    "going crazy", "pulling my hair", "last resort",
}

# ── Source quality multipliers ─────────────────────────────────────────────────
SOURCE_MULTIPLIERS: Dict[str, float] = {
    "reddit_mysql":     1.15,
    "stackoverflow":    1.10,
    "hackernews":       1.05,
    "devto":            1.00,
    "indeed":           1.00,
    "blog_news":        1.00,
    "reddit":           1.00,
}


def score_content(
    title: str,
    content: str,
    source: str = "",
) -> Tuple[int, List[str], List[str]]:
    """
    Analyse title + content and return (score, signals, tags).

    score   — integer 0–100
    signals — human-readable list of what triggered the score
    tags    — short lowercase label list (e.g. ["mysql", "urgent"])
    """
    text = f"{title} {content}".lower()

    score: int = 0
    signals: List[str] = []
    tags: List[str] = []

    # ── MySQL pain ──────────────────────────────────────────────────────────
    for kw, pts in MYSQL_PAIN_SIGNALS.items():
        if kw in text:
            score += pts
            if "mysql" not in tags:
                tags.append("mysql")
            label = f"MySQL: {kw.replace('mysql ', '').replace('mysql', '').strip().title()}"
            if label not in signals:
                signals.append(label)

    # ── General DB pain ─────────────────────────────────────────────────────
    db_pts = 0
    for kw, pts in DB_PAIN_SIGNALS.items():
        if kw in text:
            db_pts += pts
            if "database-issue" not in tags:
                tags.append("database-issue")
            label = f"DB Pain: {kw.title()}"
            if label not in signals:
                signals.append(label)
    score += min(db_pts, 40)   # cap general DB contribution

    # ── Job signals ─────────────────────────────────────────────────────────
    for kw, pts in JOB_SIGNALS.items():
        if kw in text:
            score += pts
            if "job-signal" not in tags:
                tags.append("job-signal")
            label = f"Hiring: {kw.title()}"
            if label not in signals:
                signals.append(label)

    # ── Urgency amplifier ────────────────────────────────────────────────────
    urgency_hits = sum(1 for w in URGENCY_WORDS if w in text)
    if urgency_hits >= 3:
        score = int(score * 1.35)
        tags.append("urgent")
        signals.append("🚨 High Urgency")
    elif urgency_hits >= 1:
        score = int(score * 1.12)

    # ── Source quality ───────────────────────────────────────────────────────
    multiplier = SOURCE_MULTIPLIERS.get(source, 1.0)
    score = int(score * multiplier)

    # ── Cap ──────────────────────────────────────────────────────────────────
    score = min(100, score)

    return score, signals[:12], list(dict.fromkeys(tags))  # dedupe tags


# ── Company extraction ────────────────────────────────────────────────────────

_COMPANY_PATTERNS = [
    r"\bat ([A-Z][A-Za-z0-9&]+(?: [A-Z][A-Za-z0-9&]+){0,3})\b",
    r"\bworking (?:for|with) ([A-Z][A-Za-z0-9&]+(?: [A-Z][A-Za-z0-9&]+){0,3})\b",
    r"\bour company[,\s]+([A-Z][A-Za-z0-9&]+(?: [A-Z][A-Za-z0-9&]+){0,2})\b",
    r"([A-Z][A-Za-z0-9&]+(?: [A-Z][A-Za-z0-9&]+){0,2})(?:'s)? (?:mysql|database)\b",
]

_COMPANY_BLACKLIST = {
    "MySQL", "Amazon", "Google", "Stack", "The", "Our", "This", "We",
    "Reddit", "Stack Overflow", "HackerNews", "Dev", "Indeed",
    "Monday", "Tuesday", "Wednesday", "Thursday", "Friday",
}


def extract_company(text: str) -> str:
    """Try to extract a company name from free text."""
    for pattern in _COMPANY_PATTERNS:
        m = re.search(pattern, text)
        if m:
            company = m.group(1).strip()
            if company not in _COMPANY_BLACKLIST and len(company) > 2:
                return company
    return ""
