#!/usr/bin/env python3
"""Buzzsaw v3 Live Production Dashboard Server.

Run: python3 scripts/dashboard_server.py
Open: http://localhost:8787
"""

import json
import os
import re
import subprocess
import time
from http.server import HTTPServer, BaseHTTPRequestHandler
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
GAMES_DIR = ROOT / "apps" / "games-puzzles"
MANIFEST = ROOT / "apps" / "manifest.json"

def get_git_log():
    """Get recent commits with game info."""
    try:
        result = subprocess.run(
            ["git", "log", "--oneline", "-30", "--format=%h|%s|%ai"],
            capture_output=True, text=True, cwd=ROOT, timeout=5
        )
        waves = []
        for line in result.stdout.strip().split("\n"):
            if not line:
                continue
            parts = line.split("|", 2)
            if len(parts) == 3:
                sha, msg, date = parts
                if any(k in msg.lower() for k in ["wave", "feat:", "game", "buzzsaw"]):
                    waves.append({"sha": sha, "message": msg, "date": date[:19]})
        return waves
    except:
        return []

def scan_games():
    """Scan all game HTML files and score them."""
    games = []
    if not GAMES_DIR.exists():
        return games
    for f in sorted(GAMES_DIR.glob("*.html")):
        try:
            content = f.read_text(errors="ignore")
            lines = content.count("\n") + 1
            size = f.stat().st_size
            mtime = datetime.fromtimestamp(f.stat().st_mtime).strftime("%Y-%m-%d %H:%M")

            checks = {
                "doctype": "<!DOCTYPE" in content[:100].upper(),
                "localstorage": "localStorage" in content,
                "canvas": "canvas" in content.lower(),
                "audio": "AudioContext" in content or "webkitAudioContext" in content,
                "raf": "requestAnimationFrame" in content,
                "no_ext_deps": not re.search(r'(src|href)="https?:', content),
                "pause": "pause" in content.lower(),
                "gameover": "game over" in content.lower() or "gameover" in content.lower(),
            }
            score = 0
            if checks["doctype"]: score += 10
            if checks["localstorage"]: score += 10
            if checks["canvas"]: score += 10
            if checks["audio"]: score += 10
            if checks["raf"]: score += 10
            if checks["no_ext_deps"]: score += 10
            if checks["pause"]: score += 10
            if checks["gameover"]: score += 10
            if lines > 1500: score += 10
            elif lines > 500: score += 5
            if 50000 <= size <= 150000: score += 10
            elif 20000 <= size: score += 5

            games.append({
                "file": f.name,
                "title": f.stem.replace("-", " ").title(),
                "size": size,
                "lines": lines,
                "score": min(score, 100),
                "checks": checks,
                "modified": mtime,
            })
        except:
            pass
    return games

def get_running_agents():
    """Check for running Claude Code agent processes."""
    try:
        result = subprocess.run(
            ["ps", "aux"], capture_output=True, text=True, timeout=5
        )
        agents = []
        for line in result.stdout.split("\n"):
            if "claude" in line.lower() and "task" in line.lower():
                agents.append(line.strip()[-80:])
        return len(agents), agents
    except:
        return 0, []

def check_tmp_files():
    """Check /tmp for copilot and game generation artifacts."""
    artifacts = []
    for pattern in ["/tmp/copilot-*", "/tmp/game-prompt-*"]:
        import glob as g
        for f in g.glob(pattern):
            try:
                size = os.path.getsize(f)
                mtime = datetime.fromtimestamp(os.path.getmtime(f)).strftime("%H:%M:%S")
                artifacts.append({"file": os.path.basename(f), "size": size, "time": mtime})
            except:
                pass
    return artifacts

def build_stats():
    """Build complete stats payload."""
    games = scan_games()
    waves = get_git_log()
    agent_count, _ = get_running_agents()
    artifacts = check_tmp_files()

    total_lines = sum(g["lines"] for g in games)
    total_size = sum(g["size"] for g in games)
    avg_score = sum(g["score"] for g in games) / len(games) if games else 0
    scores = [g["score"] for g in games]

    # Estimate tokens
    est_copilot_tokens = total_lines * 4  # ~4 tokens per line of code
    est_claude_tokens = len(games) * 5000  # ~5K orchestration tokens per game

    return {
        "timestamp": datetime.now().isoformat(),
        "summary": {
            "total_games": len(games),
            "total_lines": total_lines,
            "total_size_mb": round(total_size / 1048576, 2),
            "avg_lines": round(total_lines / len(games)) if games else 0,
            "avg_size_kb": round(total_size / 1024 / len(games)) if games else 0,
            "avg_score": round(avg_score, 1),
            "max_score": max(scores) if scores else 0,
            "min_score": min(scores) if scores else 0,
            "est_claude_tokens": est_claude_tokens,
            "est_subagent_tokens": est_copilot_tokens,
            "delegation_pct": round(est_copilot_tokens / (est_copilot_tokens + est_claude_tokens) * 100, 1) if (est_copilot_tokens + est_claude_tokens) > 0 else 0,
            "active_agents": agent_count,
            "waves_committed": len(waves),
        },
        "games": games,
        "waves": waves,
        "artifacts": artifacts,
        "score_distribution": {
            "0-20": len([s for s in scores if s < 20]),
            "20-40": len([s for s in scores if 20 <= s < 40]),
            "40-60": len([s for s in scores if 40 <= s < 60]),
            "60-80": len([s for s in scores if 60 <= s < 80]),
            "80-100": len([s for s in scores if s >= 80]),
        }
    }

DASHBOARD_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Buzzsaw v3 — Live Dashboard</title>
<style>
* { margin:0; padding:0; box-sizing:border-box; }
body { background:#0a0a0f; color:#e0e0e0; font-family:'SF Mono',Monaco,monospace; overflow-x:hidden; }
.header { background:linear-gradient(135deg,#1a1a2e,#16213e); padding:16px 24px; display:flex; justify-content:space-between; align-items:center; border-bottom:2px solid #0ff3; }
.header h1 { font-size:20px; color:#0ff; text-shadow:0 0 20px #0ff5; letter-spacing:2px; }
.header .status { display:flex; gap:16px; align-items:center; font-size:13px; }
.live-dot { width:10px; height:10px; border-radius:50%; background:#0f0; box-shadow:0 0 8px #0f0; animation:pulse 1s infinite; }
@keyframes pulse { 0%,100%{opacity:1} 50%{opacity:0.4} }
.grid { display:grid; grid-template-columns:repeat(6,1fr); gap:12px; padding:16px; }
.card { background:#12121f; border:1px solid #ffffff15; border-radius:10px; padding:16px; text-align:center; }
.card .value { font-size:28px; font-weight:bold; color:#0ff; text-shadow:0 0 10px #0ff3; }
.card .label { font-size:11px; color:#888; margin-top:4px; text-transform:uppercase; letter-spacing:1px; }
.card.green .value { color:#0f0; text-shadow:0 0 10px #0f03; }
.card.gold .value { color:#ffd700; text-shadow:0 0 10px #ffd7003; }
.card.purple .value { color:#a855f7; text-shadow:0 0 10px #a855f73; }
.panels { display:grid; grid-template-columns:1fr 1fr; gap:12px; padding:0 16px 16px; }
.panel { background:#12121f; border:1px solid #ffffff15; border-radius:10px; padding:16px; }
.panel h2 { font-size:14px; color:#0ff; margin-bottom:12px; text-transform:uppercase; letter-spacing:1px; }
canvas { width:100%; border-radius:6px; }
.game-grid { display:grid; grid-template-columns:repeat(auto-fill,minmax(220px,1fr)); gap:8px; max-height:400px; overflow-y:auto; padding:0 16px 16px; }
.game-card { background:#12121f; border:1px solid #ffffff10; border-radius:8px; padding:12px; font-size:12px; }
.game-card .title { font-weight:bold; color:#fff; margin-bottom:4px; }
.game-card .meta { color:#666; }
.game-card .score-bar { height:4px; border-radius:2px; margin-top:6px; background:#333; }
.game-card .score-fill { height:100%; border-radius:2px; transition:width 0.5s; }
.checks { display:flex; gap:3px; margin-top:4px; }
.check { width:8px; height:8px; border-radius:50%; }
.check.pass { background:#0f0; box-shadow:0 0 4px #0f0; }
.check.fail { background:#f00; box-shadow:0 0 4px #f00; }
.wave-log { max-height:200px; overflow-y:auto; }
.wave-item { padding:6px 0; border-bottom:1px solid #ffffff08; font-size:12px; }
.wave-item .sha { color:#a855f7; }
.wave-item .msg { color:#ccc; }
.wave-item .date { color:#555; font-size:10px; }
.section-title { font-size:14px; color:#0ff; padding:0 16px 8px; text-transform:uppercase; letter-spacing:1px; }
</style>
</head>
<body>
<div class="header">
  <h1>BUZZSAW v3 — LIVE DASHBOARD</h1>
  <div class="status">
    <div class="live-dot"></div>
    <span id="refresh-status">Auto-refresh: 3s</span>
    <span id="timestamp" style="color:#555"></span>
  </div>
</div>

<div class="grid" id="metrics"></div>

<div class="panels">
  <div class="panel">
    <h2>Quality Distribution</h2>
    <canvas id="distChart" height="180"></canvas>
  </div>
  <div class="panel">
    <h2>Size vs Lines (Target Zone)</h2>
    <canvas id="scatterChart" height="180"></canvas>
  </div>
</div>

<div class="panels">
  <div class="panel">
    <h2>Token Delegation</h2>
    <canvas id="tokenChart" height="180"></canvas>
  </div>
  <div class="panel">
    <h2>Git Wave Log</h2>
    <div class="wave-log" id="waveLog"></div>
  </div>
</div>

<div class="section-title">All Games — Quality Grid</div>
<div class="game-grid" id="gameGrid"></div>

<script>
const API = '/api/stats';
let data = null;

async function fetchStats() {
  try {
    const r = await fetch(API);
    data = await r.json();
    render();
  } catch(e) { console.error('Fetch failed:', e); }
}

function render() {
  if (!data) return;
  const s = data.summary;
  document.getElementById('timestamp').textContent = new Date(data.timestamp).toLocaleTimeString();

  // Metrics cards
  document.getElementById('metrics').innerHTML = [
    {v: s.total_games, l: 'Total Games', c: ''},
    {v: s.total_lines.toLocaleString(), l: 'Total Lines', c: 'purple'},
    {v: s.total_size_mb + ' MB', l: 'Total Size', c: ''},
    {v: s.avg_score, l: 'Avg Quality', c: s.avg_score >= 70 ? 'green' : 'gold'},
    {v: s.delegation_pct + '%', l: 'Subagent Work', c: 'green'},
    {v: s.active_agents || '—', l: 'Active Agents', c: s.active_agents > 0 ? 'green' : ''},
  ].map(m => `<div class="card ${m.c}"><div class="value">${m.v}</div><div class="label">${m.l}</div></div>`).join('');

  drawDistribution();
  drawScatter();
  drawTokens();
  renderWaves();
  renderGameGrid();
}

function drawDistribution() {
  const c = document.getElementById('distChart');
  const ctx = c.getContext('2d');
  const W = c.width = c.offsetWidth * 2;
  const H = c.height = 360;
  ctx.scale(1,1);
  ctx.clearRect(0,0,W,H);
  const d = data.score_distribution;
  const buckets = ['0-20','20-40','40-60','60-80','80-100'];
  const colors = ['#f44','#f90','#ff0','#6f6','#0ff'];
  const vals = buckets.map(b => d[b] || 0);
  const max = Math.max(...vals, 1);
  const barW = W / buckets.length - 20;
  const pad = 40;

  buckets.forEach((b, i) => {
    const x = i * (barW + 20) + 10;
    const h = (vals[i] / max) * (H - pad*2);
    const y = H - pad - h;
    ctx.fillStyle = colors[i];
    ctx.shadowColor = colors[i];
    ctx.shadowBlur = 10;
    ctx.fillRect(x, y, barW, h);
    ctx.shadowBlur = 0;
    ctx.fillStyle = '#888';
    ctx.font = '20px monospace';
    ctx.textAlign = 'center';
    ctx.fillText(b, x + barW/2, H - 10);
    ctx.fillStyle = '#fff';
    ctx.fillText(vals[i], x + barW/2, y - 8);
  });

  // Target line at 80
  ctx.strokeStyle = '#0f04';
  ctx.lineWidth = 2;
  ctx.setLineDash([8,4]);
  const targetX = 3 * (barW + 20) + 10;
  ctx.beginPath();
  ctx.moveTo(targetX, 0);
  ctx.lineTo(targetX, H - pad);
  ctx.stroke();
  ctx.setLineDash([]);
}

function drawScatter() {
  const c = document.getElementById('scatterChart');
  const ctx = c.getContext('2d');
  const W = c.width = c.offsetWidth * 2;
  const H = c.height = 360;
  ctx.clearRect(0,0,W,H);
  const pad = 50;

  const games = data.games;
  if (!games.length) return;

  const maxSize = Math.max(...games.map(g => g.size), 150000);
  const maxLines = Math.max(...games.map(g => g.lines), 3000);

  // Target zone
  ctx.fillStyle = '#0ff08';
  const x1 = pad + (50000/maxSize) * (W-pad*2);
  const x2 = pad + (120000/maxSize) * (W-pad*2);
  const y1 = H - pad - (3000/maxLines) * (H-pad*2);
  const y2 = H - pad - (1500/maxLines) * (H-pad*2);
  ctx.fillRect(x1, y1, x2-x1, y2-y1);

  // Axes
  ctx.strokeStyle = '#333';
  ctx.lineWidth = 1;
  ctx.beginPath();
  ctx.moveTo(pad, pad);
  ctx.lineTo(pad, H-pad);
  ctx.lineTo(W-pad, H-pad);
  ctx.stroke();

  // Labels
  ctx.fillStyle = '#555';
  ctx.font = '18px monospace';
  ctx.textAlign = 'center';
  ctx.fillText('File Size (KB)', W/2, H - 5);
  ctx.save();
  ctx.translate(15, H/2);
  ctx.rotate(-Math.PI/2);
  ctx.fillText('Lines', 0, 0);
  ctx.restore();

  // Points
  games.forEach(g => {
    const x = pad + (g.size / maxSize) * (W - pad*2);
    const y = H - pad - (g.lines / maxLines) * (H - pad*2);
    const color = g.score >= 80 ? '#0ff' : g.score >= 60 ? '#ff0' : '#f44';
    ctx.fillStyle = color;
    ctx.shadowColor = color;
    ctx.shadowBlur = 8;
    ctx.beginPath();
    ctx.arc(x, y, 6, 0, Math.PI*2);
    ctx.fill();
    ctx.shadowBlur = 0;
  });
}

function drawTokens() {
  const c = document.getElementById('tokenChart');
  const ctx = c.getContext('2d');
  const W = c.width = c.offsetWidth * 2;
  const H = c.height = 360;
  ctx.clearRect(0,0,W,H);

  const claude = data.summary.est_claude_tokens;
  const sub = data.summary.est_subagent_tokens;
  const total = claude + sub || 1;
  const cx = W * 0.3, cy = H/2, r = Math.min(W*0.25, H*0.4);

  // Pie
  const slices = [
    {v: claude, c: '#a855f7', l: 'Claude Code (orchestration)'},
    {v: sub, c: '#0f0', l: 'Subagent (code generation)'},
  ];
  let angle = -Math.PI/2;
  slices.forEach(s => {
    const sweep = (s.v / total) * Math.PI * 2;
    ctx.beginPath();
    ctx.moveTo(cx, cy);
    ctx.arc(cx, cy, r, angle, angle + sweep);
    ctx.closePath();
    ctx.fillStyle = s.c;
    ctx.shadowColor = s.c;
    ctx.shadowBlur = 15;
    ctx.fill();
    ctx.shadowBlur = 0;
    angle += sweep;
  });

  // Center hole
  ctx.fillStyle = '#12121f';
  ctx.beginPath();
  ctx.arc(cx, cy, r * 0.5, 0, Math.PI*2);
  ctx.fill();

  // Center text
  ctx.fillStyle = '#fff';
  ctx.font = 'bold 28px monospace';
  ctx.textAlign = 'center';
  ctx.fillText(Math.round(total/1000) + 'K', cx, cy + 5);
  ctx.font = '16px monospace';
  ctx.fillStyle = '#888';
  ctx.fillText('tokens', cx, cy + 25);

  // Legend
  const lx = W * 0.6;
  slices.forEach((s, i) => {
    const ly = H * 0.3 + i * 50;
    ctx.fillStyle = s.c;
    ctx.fillRect(lx, ly, 16, 16);
    ctx.fillStyle = '#ccc';
    ctx.font = '18px monospace';
    ctx.textAlign = 'left';
    ctx.fillText(s.l, lx + 24, ly + 13);
    ctx.fillStyle = '#fff';
    ctx.font = 'bold 20px monospace';
    ctx.fillText(Math.round(s.v/1000) + 'K (' + Math.round(s.v/total*100) + '%)', lx + 24, ly + 38);
  });
}

function renderWaves() {
  const el = document.getElementById('waveLog');
  if (!data.waves.length) { el.innerHTML = '<div style="color:#555">No wave commits found</div>'; return; }
  el.innerHTML = data.waves.map(w =>
    `<div class="wave-item"><span class="sha">${w.sha}</span> <span class="msg">${w.message}</span><br><span class="date">${w.date}</span></div>`
  ).join('');
}

function renderGameGrid() {
  const el = document.getElementById('gameGrid');
  const games = [...data.games].sort((a,b) => b.score - a.score);
  el.innerHTML = games.map(g => {
    const color = g.score >= 80 ? '#0ff' : g.score >= 60 ? '#ff0' : '#f44';
    const checks = Object.entries(g.checks).map(([k,v]) =>
      `<div class="check ${v?'pass':'fail'}" title="${k}"></div>`
    ).join('');
    return `<div class="game-card">
      <div class="title">${g.title}</div>
      <div class="meta">${g.lines} lines · ${Math.round(g.size/1024)}KB · ${g.modified}</div>
      <div class="score-bar"><div class="score-fill" style="width:${g.score}%;background:${color}"></div></div>
      <div style="display:flex;justify-content:space-between;margin-top:4px">
        <div class="checks">${checks}</div>
        <span style="color:${color};font-weight:bold;font-size:14px">${g.score}</span>
      </div>
    </div>`;
  }).join('');
}

// Auto-refresh every 3 seconds
fetchStats();
setInterval(fetchStats, 3000);
</script>
</body>
</html>"""

class DashboardHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == '/api/stats':
            stats = build_stats()
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            self.wfile.write(json.dumps(stats).encode())
        elif self.path == '/' or self.path == '/dashboard':
            self.send_response(200)
            self.send_header('Content-Type', 'text/html')
            self.end_headers()
            self.wfile.write(DASHBOARD_HTML.encode())
        else:
            self.send_response(404)
            self.end_headers()

    def log_message(self, format, *args):
        # Quiet logging - only show errors
        if '404' in str(args):
            super().log_message(format, *args)

def main():
    port = 8787
    server = HTTPServer(('0.0.0.0', port), DashboardHandler)
    print(f"""
╔══════════════════════════════════════════════╗
║   BUZZSAW v3 LIVE DASHBOARD                  ║
║                                              ║
║   Open: http://localhost:{port}               ║
║                                              ║
║   Auto-refreshes every 3 seconds             ║
║   Scans: apps/games-puzzles/*.html           ║
║   Tracks: quality scores, token estimates,   ║
║           git waves, active agents           ║
║                                              ║
║   Press Ctrl+C to stop                       ║
╚══════════════════════════════════════════════╝
""")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nDashboard stopped.")
        server.server_close()

if __name__ == '__main__':
    main()
