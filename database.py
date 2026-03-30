"""
database.py — SQLite persistence layer for MySQL Prospect Finder.
"""

import sqlite3
import json
from datetime import datetime, timezone
from typing import List, Dict, Optional

DB_PATH = "prospects.db"


def init_db():
    """Initialize the database schema."""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    c.execute("""
        CREATE TABLE IF NOT EXISTS prospects (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            title       TEXT    NOT NULL,
            content     TEXT,
            url         TEXT    UNIQUE NOT NULL,
            source      TEXT    NOT NULL,
            author      TEXT,
            company     TEXT,
            score       INTEGER DEFAULT 0,
            signals     TEXT    DEFAULT '[]',   -- JSON list
            tags        TEXT    DEFAULT '[]',   -- JSON list
            created_at  TEXT,
            scraped_at  TEXT    NOT NULL
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS scrape_runs (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            started_at      TEXT    NOT NULL,
            completed_at    TEXT,
            prospects_found INTEGER DEFAULT 0,
            sources_run     TEXT    DEFAULT '[]'    -- JSON list
        )
    """)

    c.execute("CREATE INDEX IF NOT EXISTS idx_score ON prospects(score DESC)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_source ON prospects(source)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_scraped ON prospects(scraped_at DESC)")

    conn.commit()
    conn.close()


def save_prospect(prospect: Dict) -> bool:
    """
    Upsert a prospect. Returns True if it was a new record, False if duplicate.
    """
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    try:
        c.execute("""
            INSERT OR IGNORE INTO prospects
                (title, content, url, source, author, company,
                 score, signals, tags, created_at, scraped_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            (prospect.get("title") or "")[:300],
            (prospect.get("content") or "")[:3000],
            prospect.get("url", ""),
            prospect.get("source", "unknown"),
            (prospect.get("author") or "")[:200],
            (prospect.get("company") or "")[:200],
            prospect.get("score", 0),
            json.dumps(prospect.get("signals", [])),
            json.dumps(prospect.get("tags", [])),
            prospect.get("created_at", datetime.now(tz=timezone.utc).isoformat()),
            datetime.now(tz=timezone.utc).isoformat(),
        ))
        new = c.rowcount > 0
        conn.commit()
        return new
    except Exception as e:
        print(f"[DB] Error saving prospect: {e}")
        return False
    finally:
        conn.close()


def get_prospects(
    limit: int = 100,
    offset: int = 0,
    source: Optional[str] = None,
    min_score: Optional[int] = None,
    search: Optional[str] = None,
    tag: Optional[str] = None,
) -> List[Dict]:
    """Fetch prospects with optional filtering."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()

    query = "SELECT * FROM prospects WHERE 1=1"
    params: list = []

    if source:
        query += " AND source = ?"
        params.append(source)
    if min_score is not None:
        query += " AND score >= ?"
        params.append(min_score)
    if search:
        term = f"%{search}%"
        query += " AND (title LIKE ? OR content LIKE ? OR author LIKE ? OR company LIKE ?)"
        params += [term, term, term, term]
    if tag:
        query += " AND tags LIKE ?"
        params.append(f"%{tag}%")

    query += " ORDER BY score DESC, scraped_at DESC LIMIT ? OFFSET ?"
    params += [limit, offset]

    c.execute(query, params)
    rows = c.fetchall()
    conn.close()

    result = []
    for row in rows:
        d = dict(row)
        try:
            d["signals"] = json.loads(d.get("signals") or "[]")
        except Exception:
            d["signals"] = []
        try:
            d["tags"] = json.loads(d.get("tags") or "[]")
        except Exception:
            d["tags"] = []
        result.append(d)
    return result


def get_stats() -> Dict:
    """Return aggregate statistics."""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    def q(sql, *args):
        c.execute(sql, args)
        return c.fetchone()

    total = q("SELECT COUNT(*) FROM prospects")[0]
    high_priority = q("SELECT COUNT(*) FROM prospects WHERE score >= 70")[0]
    mysql_specific = q("SELECT COUNT(*) FROM prospects WHERE tags LIKE '%mysql%'")[0]
    avg_score_raw = q("SELECT AVG(score) FROM prospects")[0]
    avg_score = round(avg_score_raw, 1) if avg_score_raw else 0

    c.execute("""
        SELECT source, COUNT(*) as cnt
        FROM prospects
        GROUP BY source
        ORDER BY cnt DESC
    """)
    by_source = [{"source": r[0], "count": r[1]} for r in c.fetchall()]

    c.execute("""
        SELECT score,
            CASE
                WHEN score >= 70 THEN 'High (70-100)'
                WHEN score >= 40 THEN 'Medium (40-69)'
                ELSE 'Low (0-39)'
            END as band
        FROM prospects
    """)
    rows = c.fetchall()
    bands: Dict[str, int] = {"High (70-100)": 0, "Medium (40-69)": 0, "Low (0-39)": 0}
    for _, band in rows:
        bands[band] = bands.get(band, 0) + 1

    conn.close()

    return {
        "total": total,
        "high_priority": high_priority,
        "mysql_specific": mysql_specific,
        "avg_score": avg_score,
        "by_source": by_source,
        "by_score_band": [{"band": k, "count": v} for k, v in bands.items()],
    }


def get_last_scrape() -> Optional[Dict]:
    """Return the most recent scrape run metadata."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute("SELECT * FROM scrape_runs ORDER BY started_at DESC LIMIT 1")
    row = c.fetchone()
    conn.close()
    if row:
        d = dict(row)
        try:
            d["sources_run"] = json.loads(d.get("sources_run") or "[]")
        except Exception:
            d["sources_run"] = []
        return d
    return None


def log_scrape_run(
    started_at: str,
    completed_at: str,
    prospects_found: int,
    sources_run: List[str],
):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
        INSERT INTO scrape_runs (started_at, completed_at, prospects_found, sources_run)
        VALUES (?, ?, ?, ?)
    """, (started_at, completed_at, prospects_found, json.dumps(sources_run)))
    conn.commit()
    conn.close()
