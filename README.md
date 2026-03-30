# Agent-Prospector

# MySQL Prospect Finder

A web app that scrapes Reddit, Stack Overflow, Hacker News, Dev.to, Indeed, and tech blogs to identify companies and developers experiencing MySQL/database pain — ranked by signal score.

## Setup
```bash
bash setup.sh
```

Then edit `.env` and add your Reddit API credentials (free at reddit.com/prefs/apps).

## Run
```bash
source .venv/bin/activate
python main.py
```

Open http://localhost:8000

## Sources

| Source | Auth needed? |
|---|---|
| Reddit | Free API key |
| Stack Overflow | None |
| Hacker News | None |
| Dev.to | None |
| Indeed | None |
| Blogs & News | None |
