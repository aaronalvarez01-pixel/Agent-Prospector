"""
main.py — FastAPI backend for MySQL Prospect Finder.

Run:
    uvicorn main:app --reload --port 8000

Then open: http://localhost:8000
"""

import threading
from datetime import datetime, timezone
from typing import Optional

from fastapi import BackgroundTasks, FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse

from database import (
    get_last_scrape,
    get_prospects,
    get_stats,
    init_db,
    log_scrape_run,
    save_prospect,
)
from scrapers.blogs_scraper import scrape_blogs
from scrapers.devto_scraper import scrape_devto
from scrapers.hackernews_scraper import scrape_hackernews
from scrapers.indeed_scraper import scrape_indeed
from scrapers.reddit_scraper import scrape_reddit
from scrapers.stackoverflow_scraper import scrape_stackoverflow

# ── Global scraping state ──────────────────────────────────────────────────────
_scrape_lock = threading.Lock()
scrape_status = {
    "running": False,
    "progress": "Idle",
    "last_count": 0,
    "started_at": None,
}

# ── App ────────────────────────────────────────────────────────────────────────
app = FastAPI(title="MySQL Prospect Finder", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

init_db()


# ── Scraping logic ─────────────────────────────────────────────────────────────

SCRAPERS = [
    ("Reddit",         scrape_reddit),
    ("Stack Overflow", scrape_stackoverflow),
    ("Hacker News",    scrape_hackernews),
    ("Dev.to",         scrape_devto),
    ("Indeed Jobs",    scrape_indeed),
    ("Blogs & News",   scrape_blogs),
]


def _run_scrape():
    global scrape_status
    with _scrape_lock:
        if scrape_status["running"]:
            return
        scrape_status["running"] = True
        scrape_status["started_at"] = datetime.now(tz=timezone.utc).isoformat()

    started_at = scrape_status["started_at"]
    total_new = 0
    sources_run = []

    for name, scraper_fn in SCRAPERS:
        scrape_status["progress"] = f"Scraping {name}…"
        try:
            prospects = scraper_fn()
            new = sum(1 for p in prospects if save_prospect(p))
            total_new += new
            sources_run.append(name)
            scrape_status["progress"] = f"{name} done ({new} new / {len(prospects)} found)"
        except Exception as e:
            print(f"[Scraper] {name} failed: {e}")
            scrape_status["progress"] = f"{name} error: {e}"

    completed_at = datetime.now(tz=timezone.utc).isoformat()
    log_scrape_run(started_at, completed_at, total_new, sources_run)

    scrape_status["running"] = False
    scrape_status["last_count"] = total_new
    scrape_status["progress"] = f"Complete — {total_new} new prospects added"


# ── API routes ─────────────────────────────────────────────────────────────────

@app.get("/", response_class=HTMLResponse, include_in_schema=False)
async def dashboard():
    return _dashboard_html()


@app.post("/api/scrape")
async def start_scrape(background_tasks: BackgroundTasks):
    if scrape_status["running"]:
        return JSONResponse({"message": "Already running", "status": "running"})
    background_tasks.add_task(_run_scrape)
    return JSONResponse({"message": "Scrape started", "status": "started"})


@app.get("/api/scrape/status")
async def get_scrape_status():
    return JSONResponse(scrape_status)


@app.get("/api/prospects")
async def list_prospects(
    limit: int = Query(100, le=500),
    offset: int = Query(0),
    source: Optional[str] = None,
    min_score: Optional[int] = None,
    search: Optional[str] = None,
    tag: Optional[str] = None,
):
    data = get_prospects(
        limit=limit,
        offset=offset,
        source=source,
        min_score=min_score,
        search=search,
        tag=tag,
    )
    return JSONResponse({"prospects": data, "count": len(data)})


@app.get("/api/stats")
async def stats():
    return JSONResponse(get_stats())


@app.get("/api/last-scrape")
async def last_scrape():
    return JSONResponse(get_last_scrape() or {})


# ── Dashboard HTML ─────────────────────────────────────────────────────────────

def _dashboard_html() -> str:
    return r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"/>
<meta name="viewport" content="width=device-width,initial-scale=1.0"/>
<title>MySQL Prospect Finder</title>
<script src="https://cdnjs.cloudflare.com/ajax/libs/Chart.js/4.4.1/chart.umd.min.js"></script>
<style>
  :root {
    --bg:       #0f1117;
    --surface:  #1a1d2e;
    --surface2: #242740;
    --border:   #2e3250;
    --text:      #e2e8f0;
    --muted:    #8892a4;
    --accent:   #6366f1;
    --accent2:  #818cf8;
    --green:    #22c55e;
    --yellow:   #eab308;
    --red:      #ef4444;
    --orange:   #f97316;
    --mysql:    #00758f;
  }
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body { background: var(--bg); color: var(--text); font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; font-size: 14px; min-height: 100vh; }

  /* ── Layout ── */
  .header { background: var(--surface); border-bottom: 1px solid var(--border); padding: 16px 24px; display: flex; align-items: center; justify-content: space-between; position: sticky; top: 0; z-index: 100; }
  .header-left { display: flex; align-items: center; gap: 12px; }
  .logo { width: 32px; height: 32px; background: var(--mysql); border-radius: 8px; display: flex; align-items: center; justify-content: center; font-size: 18px; }
  .header h1 { font-size: 18px; font-weight: 700; }
  .header .subtitle { color: var(--muted); font-size: 12px; }
  .main { max-width: 1400px; margin: 0 auto; padding: 24px; }

  /* ── Stat cards ── */
  .stats-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 16px; margin-bottom: 24px; }
  .stat-card { background: var(--surface); border: 1px solid var(--border); border-radius: 12px; padding: 20px; }
  .stat-card .label { color: var(--muted); font-size: 12px; text-transform: uppercase; letter-spacing: .5px; margin-bottom: 8px; }
  .stat-card .value { font-size: 32px; font-weight: 800; line-height: 1; }
  .stat-card .sub { color: var(--muted); font-size: 12px; margin-top: 6px; }
  .stat-card.accent .value { color: var(--accent2); }
  .stat-card.green .value  { color: var(--green); }
  .stat-card.yellow .value { color: var(--yellow); }
  .stat-card.mysql .value  { color: #29b6d2; }

  /* ── Charts row ── */
  .charts-row { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; margin-bottom: 24px; }
  .chart-card { background: var(--surface); border: 1px solid var(--border); border-radius: 12px; padding: 20px; }
  .chart-card h3 { font-size: 13px; font-weight: 600; color: var(--muted); text-transform: uppercase; letter-spacing: .5px; margin-bottom: 16px; }
  .chart-container { position: relative; height: 200px; }

  /* ── Controls ── */
  .controls { background: var(--surface); border: 1px solid var(--border); border-radius: 12px; padding: 16px 20px; margin-bottom: 20px; display: flex; gap: 12px; align-items: center; flex-wrap: wrap; }
  .controls input, .controls select { background: var(--surface2); border: 1px solid var(--border); border-radius: 8px; color: var(--text); padding: 8px 12px; font-size: 13px; outline: none; }
  .controls input { flex: 1; min-width: 200px; }
  .controls input:focus, .controls select:focus { border-color: var(--accent); }
  .controls select option { background: var(--surface2); }
  .btn { padding: 8px 18px; border-radius: 8px; border: none; cursor: pointer; font-size: 13px; font-weight: 600; transition: opacity .15s; }
  .btn:hover { opacity: .85; }
  .btn:disabled { opacity: .4; cursor: not-allowed; }
  .btn-primary { background: var(--accent); color: #fff; }
  .btn-outline { background: transparent; border: 1px solid var(--border); color: var(--text); }
  .spacer { flex: 1; }

  /* ── Scrape status bar ── */
  .status-bar { background: var(--surface2); border: 1px solid var(--border); border-radius: 8px; padding: 10px 16px; margin-bottom: 16px; display: flex; align-items: center; gap: 10px; font-size: 12px; color: var(--muted); }
  .spinner { width: 14px; height: 14px; border: 2px solid var(--border); border-top-color: var(--accent); border-radius: 50%; animation: spin .8s linear infinite; }
  @keyframes spin { to { transform: rotate(360deg); } }
  .pulse { width: 8px; height: 8px; background: var(--green); border-radius: 50%; }

  /* ── Prospects table ── */
  .table-card { background: var(--surface); border: 1px solid var(--border); border-radius: 12px; overflow: hidden; }
  .table-header { padding: 16px 20px; border-bottom: 1px solid var(--border); display: flex; align-items: center; justify-content: space-between; }
  .table-header h2 { font-size: 15px; font-weight: 700; }
  .count-badge { background: var(--surface2); border: 1px solid var(--border); border-radius: 20px; padding: 3px 12px; font-size: 12px; color: var(--muted); }
  table { width: 100%; border-collapse: collapse; }
  th { text-align: left; padding: 12px 16px; font-size: 11px; font-weight: 600; color: var(--muted); text-transform: uppercase; letter-spacing: .5px; border-bottom: 1px solid var(--border); background: var(--surface2); white-space: nowrap; }
  td { padding: 14px 16px; border-bottom: 1px solid var(--border); vertical-align: top; }
  tr:last-child td { border-bottom: none; }
  tr:hover td { background: rgba(99,102,241,.05); }

  /* ── Score badge ── */
  .score { display: inline-flex; align-items: center; justify-content: center; width: 44px; height: 44px; border-radius: 10px; font-size: 15px; font-weight: 800; }
  .score.high   { background: rgba(239,68,68,.15);   color: var(--red);    }
  .score.med    { background: rgba(234,179,8,.15);    color: var(--yellow); }
  .score.low    { background: rgba(99,102,241,.15);   color: var(--accent2);}

  /* ── Source badge ── */
  .source-badge { display: inline-block; padding: 3px 10px; border-radius: 20px; font-size: 11px; font-weight: 600; white-space: nowrap; }
  .src-reddit        { background: rgba(255,69,0,.15);   color: #ff8c69; }
  .src-stackoverflow { background: rgba(244,128,36,.15); color: #f48024; }
  .src-hackernews    { background: rgba(255,102,0,.15);  color: #ff6600; }
  .src-devto         { background: rgba(59,130,246,.15); color: #60a5fa; }
  .src-indeed        { background: rgba(34,197,94,.15);  color: var(--green); }
  .src-blog_news     { background: rgba(168,85,247,.15); color: #c084fc; }

  /* ── Tags / signals ── */
  .tags { display: flex; flex-wrap: wrap; gap: 4px; margin-top: 6px; }
  .tag { display: inline-block; padding: 2px 8px; border-radius: 4px; font-size: 10px; font-weight: 600; background: var(--surface2); color: var(--muted); border: 1px solid var(--border); }
  .tag.mysql   { background: rgba(0,117,143,.2); color: #29b6d2; border-color: rgba(0,117,143,.4); }
  .tag.urgent  { background: rgba(239,68,68,.15); color: var(--red); border-color: rgba(239,68,68,.3); }
  .tag.job     { background: rgba(34,197,94,.12); color: var(--green); border-color: rgba(34,197,94,.3); }

  /* ── Title / link ── */
  .prospect-title { font-weight: 600; line-height: 1.4; }
  .prospect-title a { color: var(--text); text-decoration: none; }
  .prospect-title a:hover { color: var(--accent2); }
  .prospect-meta { color: var(--muted); font-size: 12px; margin-top: 4px; }
  .signal-list { font-size: 11px; color: var(--muted); margin-top: 6px; line-height: 1.7; }

  /* ── Empty state ── */
  .empty { padding: 60px 20px; text-align: center; color: var(--muted); }
  .empty .icon { font-size: 48px; margin-bottom: 12px; }
  .empty p { font-size: 15px; margin-bottom: 8px; color: var(--text); }
  .empty small { font-size: 13px; }

  /* ── Loading skeleton ── */
  .skeleton { background: linear-gradient(90deg, var(--surface2) 25%, var(--border) 50%, var(--surface2) 75%); background-size: 200% 100%; animation: shimmer 1.5s infinite; border-radius: 4px; height: 14px; }
  @keyframes shimmer { 0% { background-position: -200% 0; } 100% { background-position: 200% 0; } }

  @media (max-width: 768px) {
    .charts-row { grid-template-columns: 1fr; }
    .stats-grid { grid-template-columns: repeat(2, 1fr); }
    table { font-size: 13px; }
  }
</style>
</head>
<body>

<!-- Header -->
<div class="header">
  <div class="header-left">
    <div class="logo">🐬</div>
    <div>
      <h1>MySQL Prospect Finder</h1>
      <div class="subtitle">Identifying companies with database pain signals</div>
    </div>
  </div>
  <div style="display:flex;gap:10px;align-items:center;">
    <span id="last-scrape-info" style="font-size:12px;color:var(--muted)"></span>
    <button class="btn btn-primary" id="scrape-btn" onclick="startScrape()">▶ Run Scrape</button>
  </div>
</div>

<div class="main">

  <!-- Stat cards -->
  <div class="stats-grid" id="stats-grid">
    <div class="stat-card accent"><div class="label">Total Prospects</div><div class="value" id="s-total">—</div><div class="sub">All sources combined</div></div>
    <div class="stat-card green"> <div class="label">High Priority</div><div class="value" id="s-high">—</div><div class="sub">Score ≥ 70</div></div>
    <div class="stat-card mysql"> <div class="label">MySQL Specific</div><div class="value" id="s-mysql">—</div><div class="sub">Direct MySQL signals</div></div>
    <div class="stat-card yellow"><div class="label">Avg Signal Score</div><div class="value" id="s-avg">—</div><div class="sub">Out of 100</div></div>
  </div>

  <!-- Charts -->
  <div class="charts-row">
    <div class="chart-card">
      <h3>Prospects by Source</h3>
      <div class="chart-container"><canvas id="sourceChart"></canvas></div>
    </div>
    <div class="chart-card">
      <h3>Score Distribution</h3>
      <div class="chart-container"><canvas id="scoreChart"></canvas></div>
    </div>
  </div>

  <!-- Status bar -->
  <div class="status-bar" id="status-bar" style="display:none">
    <div class="spinner" id="status-spinner"></div>
    <span id="status-text">Idle</span>
  </div>

  <!-- Controls -->
  <div class="controls">
    <input type="text" id="search-input" placeholder="🔍  Search prospects…" oninput="debounceLoad()"/>
    <select id="source-filter" onchange="loadProspects()">
      <option value="">All sources</option>
      <option value="reddit">Reddit</option>
      <option value="stackoverflow">Stack Overflow</option>
      <option value="hackernews">Hacker News</option>
      <option value="devto">Dev.to</option>
      <option value="indeed">Indeed</option>
      <option value="blog_news">Blogs & News</option>
    </select>
    <select id="score-filter" onchange="loadProspects()">
      <option value="">All scores</option>
      <option value="70">High priority (≥70)</option>
      <option value="40">Medium+ (≥40)</option>
      <option value="20">Low+ (≥20)</option>
    </select>
    <select id="tag-filter" onchange="loadProspects()">
      <option value="">All tags</option>
      <option value="mysql">MySQL</option>
      <option value="urgent">Urgent</option>
      <option value="job-posting">Job Posting</option>
      <option value="database-issue">DB Issue</option>
    </select>
    <div class="spacer"></div>
    <button class="btn btn-outline" onclick="resetFilters()">Reset</button>
    <span id="result-count" style="font-size:12px;color:var(--muted)"></span>
  </div>

  <!-- Table -->
  <div class="table-card">
    <div class="table-header">
      <h2>Prospects</h2>
      <span class="count-badge" id="table-count">0 results</span>
    </div>
    <div id="table-wrapper">
      <div class="empty">
        <div class="icon">🔍</div>
        <p>No prospects yet</p>
        <small>Click <strong>Run Scrape</strong> to start collecting data from all sources.</small>
      </div>
    </div>
  </div>

</div><!-- /main -->

<script>
let sourceChart, scoreChart;
let debounceTimer;
const PALETTE = ['#6366f1','#22c55e','#eab308','#ef4444','#f97316','#a855f7','#06b6d4'];

// ── Chart setup ────────────────────────────────────────────────────────────────
function initCharts() {
  const chartOpts = {
    responsive: true,
    maintainAspectRatio: false,
    plugins: { legend: { position: 'right', labels: { color: '#8892a4', font: { size: 11 }, padding: 12, boxWidth: 12 } } },
  };

  sourceChart = new Chart(document.getElementById('sourceChart'), {
    type: 'doughnut',
    data: { labels: [], datasets: [{ data: [], backgroundColor: PALETTE, borderWidth: 0, hoverOffset: 4 }] },
    options: { ...chartOpts, cutout: '65%' },
  });

  scoreChart = new Chart(document.getElementById('scoreChart'), {
    type: 'bar',
    data: {
      labels: ['High (70-100)', 'Medium (40-69)', 'Low (0-39)'],
      datasets: [{
        data: [0, 0, 0],
        backgroundColor: ['rgba(239,68,68,.6)', 'rgba(234,179,8,.6)', 'rgba(99,102,241,.6)'],
        borderRadius: 6,
      }]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: { legend: { display: false } },
      scales: {
        x: { grid: { color: 'rgba(255,255,255,.05)' }, ticks: { color: '#8892a4' } },
        y: { grid: { color: 'rgba(255,255,255,.05)' }, ticks: { color: '#8892a4' } },
      },
    },
  });
}

// ── Load stats ────────────────────────────────────────────────────────────────
async function loadStats() {
  try {
    const r = await fetch('/api/stats');
    const d = await r.json();

    document.getElementById('s-total').textContent = d.total ?? '—';
    document.getElementById('s-high').textContent  = d.high_priority ?? '—';
    document.getElementById('s-mysql').textContent = d.mysql_specific ?? '—';
    document.getElementById('s-avg').textContent   = d.avg_score ?? '—';

    // Source chart
    const src = d.by_source || [];
    sourceChart.data.labels = src.map(s => capitalize(s.source));
    sourceChart.data.datasets[0].data = src.map(s => s.count);
    sourceChart.update();

    // Score chart
    const bands = d.by_score_band || [];
    const bandMap = {};
    bands.forEach(b => bandMap[b.band] = b.count);
    scoreChart.data.datasets[0].data = [
      bandMap['High (70-100)'] || 0,
      bandMap['Medium (40-69)'] || 0,
      bandMap['Low (0-39)'] || 0,
    ];
    scoreChart.update();

    // Last scrape
    const ls = await fetch('/api/last-scrape').then(r => r.json());
    if (ls && ls.completed_at) {
      const dt = new Date(ls.completed_at);
      document.getElementById('last-scrape-info').textContent =
        `Last run: ${dt.toLocaleDateString()} ${dt.toLocaleTimeString([], {hour:'2-digit',minute:'2-digit'})} · +${ls.prospects_found} new`;
    }
  } catch(e) { console.error('Stats error', e); }
}

// ── Load prospects ────────────────────────────────────────────────────────────
async function loadProspects() {
  const search = document.getElementById('search-input').value.trim();
  const source = document.getElementById('source-filter').value;
  const minScore = document.getElementById('score-filter').value;
  const tag = document.getElementById('tag-filter').value;

  const params = new URLSearchParams({ limit: 200 });
  if (search)   params.set('search', search);
  if (source)   params.set('source', source);
  if (minScore) params.set('min_score', minScore);
  if (tag)      params.set('tag', tag);

  try {
    const r = await fetch(`/api/prospects?${params}`);
    const d = await r.json();
    renderTable(d.prospects || []);
  } catch(e) {
    console.error('Prospects error', e);
  }
}

function renderTable(prospects) {
  const wrapper = document.getElementById('table-wrapper');
  const count   = document.getElementById('table-count');

  count.textContent = `${prospects.length} result${prospects.length !== 1 ? 's' : ''}`;

  if (!prospects.length) {
    wrapper.innerHTML = `<div class="empty"><div class="icon">🔍</div><p>No prospects match your filters</p><small>Try adjusting the search or score threshold.</small></div>`;
    return;
  }

  const rows = prospects.map(p => {
    const scoreClass = p.score >= 70 ? 'high' : p.score >= 40 ? 'med' : 'low';
    const srcClass   = 'src-' + (p.source || 'blog_news');
    const srcLabel   = { reddit: 'Reddit', stackoverflow: 'Stack Overflow', hackernews: 'Hacker News', devto: 'Dev.to', indeed: 'Indeed', blog_news: 'Blog/News' }[p.source] || p.source;

    const tags = (p.tags || []).slice(0, 6).map(t => {
      const cls = t === 'mysql' ? 'mysql' : t === 'urgent' ? 'urgent' : t.includes('job') ? 'job' : '';
      return `<span class="tag ${cls}">${esc(t)}</span>`;
    }).join('');

    const signals = (p.signals || []).slice(0, 4).join(' · ');
    const date = p.created_at ? new Date(p.created_at).toLocaleDateString() : '';
    const author = p.author ? `@${esc(p.author.slice(0,30))}` : '';
    const company = p.company ? `<strong>${esc(p.company)}</strong> · ` : '';

    return `<tr>
      <td style="width:52px"><div class="score ${scoreClass}">${p.score}</div></td>
      <td>
        <div class="prospect-title"><a href="${esc(p.url)}" target="_blank" rel="noopener">${esc(p.title)}</a></div>
        <div class="prospect-meta">${company}${author} ${date ? '· ' + date : ''}</div>
        ${signals ? `<div class="signal-list">⚡ ${esc(signals)}</div>` : ''}
        <div class="tags">${tags}</div>
      </td>
      <td style="width:130px"><span class="source-badge ${srcClass}">${srcLabel}</span></td>
    </tr>`;
  }).join('');

  wrapper.innerHTML = `<table>
    <thead><tr>
      <th>Score</th>
      <th>Prospect</th>
      <th>Source</th>
    </tr></thead>
    <tbody>${rows}</tbody>
  </table>`;
}

// ── Scraping ──────────────────────────────────────────────────────────────────
async function startScrape() {
  const btn = document.getElementById('scrape-btn');
  btn.disabled = true;
  btn.textContent = '⏳ Running…';
  document.getElementById('status-bar').style.display = 'flex';

  try {
    await fetch('/api/scrape', { method: 'POST' });
    pollStatus();
  } catch(e) {
    btn.disabled = false;
    btn.textContent = '▶ Run Scrape';
  }
}

function pollStatus() {
  const interval = setInterval(async () => {
    try {
      const r = await fetch('/api/scrape/status');
      const d = await r.json();
      document.getElementById('status-text').textContent = d.progress || 'Working…';
      document.getElementById('status-spinner').style.display = d.running ? 'block' : 'none';

      if (!d.running) {
        clearInterval(interval);
        document.getElementById('scrape-btn').disabled = false;
        document.getElementById('scrape-btn').textContent = '▶ Run Scrape';
        await loadStats();
        await loadProspects();
        setTimeout(() => {
          document.getElementById('status-bar').style.display = 'none';
        }, 4000);
      }
    } catch(e) { clearInterval(interval); }
  }, 1500);
}

// ── Helpers ────────────────────────────────────────────────────────────────────
function esc(s) {
  return String(s || '').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
}
function capitalize(s) {
  const map = { reddit:'Reddit', stackoverflow:'Stack Overflow', hackernews:'Hacker News', devto:'Dev.to', indeed:'Indeed', blog_news:'Blog/News' };
  return map[s] || s;
}
function debounceLoad() {
  clearTimeout(debounceTimer);
  debounceTimer = setTimeout(loadProspects, 350);
}
function resetFilters() {
  document.getElementById('search-input').value = '';
  document.getElementById('source-filter').value = '';
  document.getElementById('score-filter').value = '';
  document.getElementById('tag-filter').value = '';
  loadProspects();
}

// ── Init ──────────────────────────────────────────────────────────────────────
initCharts();
loadStats();
loadProspects();

// Auto-refresh every 30 seconds if scraping is running
setInterval(async () => {
  const r = await fetch('/api/scrape/status').catch(() => null);
  if (!r) return;
  const d = await r.json();
  if (!d.running) {
    await loadStats();
    await loadProspects();
  }
}, 30000);
</script>
</body>
</html>"""


# ── Run directly ───────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
