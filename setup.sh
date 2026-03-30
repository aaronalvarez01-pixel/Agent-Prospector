#!/bin/bash
# ──────────────────────────────────────────────
#  MySQL Prospect Finder — Quick Setup Script
# ──────────────────────────────────────────────

set -e

echo ""
echo "🐬  MySQL Prospect Finder — Setup"
echo "────────────────────────────────────"

# 1. Create virtual environment
if [ ! -d ".venv" ]; then
  echo "▸ Creating virtual environment..."
  python3 -m venv .venv
fi

# 2. Activate it
source .venv/bin/activate

# 3. Install dependencies
echo "▸ Installing dependencies..."
pip install -q --upgrade pip
pip install -q -r requirements.txt

# 4. Create .env from example if not present
if [ ! -f ".env" ]; then
  cp .env.example .env
  echo ""
  echo "✅  Created .env from .env.example"
  echo ""
  echo "⚠️   IMPORTANT — Before running the app, add your Reddit API credentials:"
  echo "    1. Go to https://www.reddit.com/prefs/apps"
  echo "    2. Create a 'script' app"
  echo "    3. Paste the client_id and client_secret into .env"
  echo ""
  echo "    Reddit is the highest-signal source."
  echo "    All other sources (Stack Overflow, HN, Dev.to, Indeed, Blogs) work WITHOUT credentials."
fi

echo ""
echo "✅  Setup complete! Start the app with:"
echo ""
echo "    source .venv/bin/activate"
echo "    python main.py"
echo ""
echo "    Then open: http://localhost:8000"
echo ""
