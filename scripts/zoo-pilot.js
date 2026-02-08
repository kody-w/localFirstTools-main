#!/usr/bin/env node
/**
 * zoo-pilot.js — Data-Slosh Driven Autonomous UI Pilot
 *
 * Drives the RappterZoo gallery via Playwright with a visible cursor,
 * using LLM intelligence (gh copilot / Claude Opus 4.6) to read the data
 * mesh and decide what to do next. No templates — pure data sloshing.
 *
 * Usage:
 *   node scripts/zoo-pilot.js                    # Launch browser + REPL
 *   node scripts/zoo-pilot.js --auto             # Autonomous data-slosh mode
 *   node scripts/zoo-pilot.js --auto --duration 120
 *   node scripts/zoo-pilot.js --headless         # No visible browser
 *   node scripts/zoo-pilot.js --port 9999        # Custom port
 *
 * REPL Commands:
 *   search <query>     Type in search box
 *   category <name>    Click sidebar category
 *   sort <mode>        Click sort tab (hot|new|rising|top|name)
 *   open <n>           Click nth post in feed
 *   play <n>           Open nth app in new tab
 *   rate <stars>       Rate current modal app (1-5)
 *   comment <text>     Post comment on current app
 *   back               Close modal/overlay
 *   scroll [n]         Scroll feed (default 400px)
 *   click <x> <y>      Click at coordinates
 *   hover <x> <y>      Move cursor to coordinates
 *   type <text>        Type text at current focus
 *   key <key>          Press key (Enter, Escape, ArrowDown, etc.)
 *   auto [seconds]     Autonomous LLM-driven browsing
 *   stop               Stop autonomous mode
 *   screenshot [name]  Save screenshot to ./screenshots/
 *   data               Show data mesh summary
 *   apps [category]    List apps from manifest
 *   status             Current page state (URL, modal open, etc.)
 *   slosh              One-shot: LLM reads page state + data, decides + executes
 *   molt <stem>        Trigger molt on an app (shells out to scripts/molt.py)
 *   rank               Trigger ranking (shells out to scripts/rank_games.py)
 *   quit               Exit
 */

const { chromium } = require('playwright');
const http = require('http');
const fs = require('fs');
const path = require('path');
const readline = require('readline');
const { execSync, spawn } = require('child_process');

const ROOT = path.resolve(__dirname, '..');
const APPS_DIR = path.join(ROOT, 'apps');
const MODEL = 'claude-opus-4.6';

// ─── Data Mesh ───────────────────────────────────────────────────────────────

function loadJSON(filePath) {
  try { return JSON.parse(fs.readFileSync(filePath, 'utf8')); }
  catch { return null; }
}

function loadDataMesh() {
  return {
    manifest: loadJSON(path.join(APPS_DIR, 'manifest.json')),
    rankings: loadJSON(path.join(APPS_DIR, 'rankings.json')),
    community: loadJSON(path.join(APPS_DIR, 'community.json')),
    contentGraph: loadJSON(path.join(APPS_DIR, 'content-graph.json')),
    contentIdentities: loadJSON(path.join(APPS_DIR, 'content-identities.json')),
    molterState: loadJSON(path.join(APPS_DIR, 'molter-state.json')),
    dataMoltState: loadJSON(path.join(APPS_DIR, 'data-molt-state.json')),
    agentHistory: loadJSON(path.join(APPS_DIR, 'agent-history.json')),
  };
}

function meshSummary(mesh) {
  const m = mesh.manifest;
  if (!m) return 'manifest not loaded';
  const cats = m.categories || {};
  let totalApps = 0;
  const catSummary = {};
  for (const [key, cat] of Object.entries(cats)) {
    catSummary[key] = { title: cat.title, count: (cat.apps || []).length };
    totalApps += (cat.apps || []).length;
  }

  const r = mesh.rankings;
  let avgScore = 0, lowApps = [], highApps = [];
  if (r && r.rankings) {
    const scores = r.rankings.map(a => a.score || a.total || 0);
    avgScore = scores.length ? (scores.reduce((a, b) => a + b, 0) / scores.length).toFixed(1) : 0;
    lowApps = r.rankings.filter(a => (a.score || a.total || 0) < 30).slice(0, 5).map(a => ({ file: a.file, score: a.score || a.total, grade: a.grade }));
    highApps = r.rankings.filter(a => (a.score || a.total || 0) >= 70).slice(0, 5).map(a => ({ file: a.file, score: a.score || a.total, grade: a.grade }));
  }

  const c = mesh.community;
  const playerCount = c && c.players ? c.players.length : 0;
  const commentKeys = c && c.comments ? Object.keys(c.comments).length : 0;

  return {
    totalApps, categories: catSummary, avgScore,
    lowScoringApps: lowApps, highScoringApps: highApps,
    playerCount, appsWithComments: commentKeys,
    molterFrame: mesh.molterState ? mesh.molterState.frame : null,
  };
}

function getAppList(mesh, category) {
  const m = mesh.manifest;
  if (!m || !m.categories) return [];
  const apps = [];
  for (const [key, cat] of Object.entries(m.categories)) {
    if (category && key !== category && cat.folder !== category) continue;
    for (const a of (cat.apps || [])) {
      apps.push({ ...a, category: key, folder: cat.folder });
    }
  }
  return apps;
}

// ─── Copilot CLI (LLM) ──────────────────────────────────────────────────────

function copilotCall(prompt, timeout = 120000) {
  try {
    const result = execSync(
      `gh copilot --model ${MODEL} -p ${JSON.stringify(prompt)} --no-ask-user`,
      { timeout, encoding: 'utf8', stdio: ['pipe', 'pipe', 'pipe'], maxBuffer: 10 * 1024 * 1024 }
    );
    return stripCopilotWrapper(result.trim());
  } catch (e) {
    console.error('  ⚠ LLM call failed:', e.message?.substring(0, 120));
    return null;
  }
}

function stripCopilotWrapper(text) {
  // Strip ANSI escape codes
  text = text.replace(/\x1b\[[0-9;]*[a-zA-Z]/g, '');
  text = text.replace(/\x1b[^a-zA-Z]*[a-zA-Z]/g, '');
  for (const marker of ['Task complete', 'Total usage est:', 'Total session time:']) {
    const idx = text.indexOf(marker);
    if (idx > 0) text = text.substring(0, idx);
  }
  return text.trim();
}

function parseLLMJson(raw) {
  if (!raw) return null;
  try { return JSON.parse(raw); } catch {}
  const fenced = raw.match(/```(?:json)?\s*\n?([\s\S]*?)\n?```/);
  if (fenced) try { return JSON.parse(fenced[1]); } catch {}
  // Try to find JSON object/array
  const objMatch = raw.match(/\{[\s\S]*\}/);
  if (objMatch) try { return JSON.parse(objMatch[0]); } catch {}
  const arrMatch = raw.match(/\[[\s\S]*\]/);
  if (arrMatch) try { return JSON.parse(arrMatch[0]); } catch {}
  return null;
}

// ─── Static File Server ──────────────────────────────────────────────────────

const MIME = {
  '.html': 'text/html', '.js': 'application/javascript', '.css': 'text/css',
  '.json': 'application/json', '.png': 'image/png', '.jpg': 'image/jpeg',
  '.svg': 'image/svg+xml', '.wav': 'audio/wav', '.ico': 'image/x-icon',
};

function startServer(port) {
  return new Promise((resolve) => {
    const server = http.createServer((req, res) => {
      let urlPath = decodeURIComponent(req.url.split('?')[0].split('#')[0]);
      if (urlPath === '/') urlPath = '/index.html';
      const filePath = path.join(ROOT, urlPath);
      // Security: must be under ROOT
      if (!filePath.startsWith(ROOT)) { res.writeHead(403); res.end(); return; }
      fs.readFile(filePath, (err, data) => {
        if (err) { res.writeHead(404); res.end('Not found'); return; }
        const ext = path.extname(filePath);
        res.writeHead(200, { 'Content-Type': MIME[ext] || 'application/octet-stream' });
        res.end(data);
      });
    });
    server.listen(port, () => {
      console.log(`  🌐 Serving at http://localhost:${port}`);
      resolve(server);
    });
  });
}

// ─── Visible Cursor Injection ────────────────────────────────────────────────

const CURSOR_INJECT = `
(function() {
  if (document.getElementById('zoo-pilot-cursor')) return;
  const cursor = document.createElement('div');
  cursor.id = 'zoo-pilot-cursor';
  cursor.innerHTML = '<svg width="28" height="28" viewBox="0 0 28 28"><path d="M2 2L12 26L15 16L26 14Z" fill="#ff4500" stroke="#fff" stroke-width="1.5"/></svg>';
  Object.assign(cursor.style, {
    position: 'fixed', top: '0', left: '0', zIndex: '999999',
    pointerEvents: 'none', transition: 'transform 0.35s cubic-bezier(.22,.68,.36,1.0)',
    filter: 'drop-shadow(0 0 6px rgba(255,69,0,.6))', transformOrigin: '2px 2px',
  });
  document.body.appendChild(cursor);

  const trail = document.createElement('div');
  trail.id = 'zoo-pilot-trail';
  Object.assign(trail.style, {
    position: 'fixed', top: '0', left: '0', width: '12px', height: '12px',
    borderRadius: '50%', background: 'rgba(255,69,0,0.3)', zIndex: '999998',
    pointerEvents: 'none', transition: 'transform 0.5s ease-out, opacity 0.5s',
    transformOrigin: 'center',
  });
  document.body.appendChild(trail);

  // Click ripple effect
  const ripple = document.createElement('div');
  ripple.id = 'zoo-pilot-ripple';
  Object.assign(ripple.style, {
    position: 'fixed', top: '0', left: '0', width: '40px', height: '40px',
    borderRadius: '50%', border: '2px solid #ff4500', zIndex: '999997',
    pointerEvents: 'none', opacity: '0', transform: 'translate(-50%,-50%) scale(0)',
    transition: 'none',
  });
  document.body.appendChild(ripple);

  // Status bar
  const bar = document.createElement('div');
  bar.id = 'zoo-pilot-status';
  Object.assign(bar.style, {
    position: 'fixed', bottom: '0', left: '0', right: '0', height: '28px',
    background: 'linear-gradient(90deg, #1a1a2e, #16213e)', color: '#ff4500',
    fontFamily: 'monospace', fontSize: '12px', lineHeight: '28px',
    padding: '0 12px', zIndex: '999999', display: 'flex',
    justifyContent: 'space-between', alignItems: 'center',
    borderTop: '1px solid #ff450040',
  });
  bar.innerHTML = '<span>🦎 zoo-pilot: watching</span><span id="zoo-pilot-action">idle</span>';
  document.body.appendChild(bar);

  window.__zooPilot = {
    moveTo(x, y) {
      cursor.style.transform = 'translate(' + x + 'px,' + y + 'px)';
      trail.style.transform = 'translate(' + (x + 2) + 'px,' + (y + 2) + 'px)';
    },
    clickAt(x, y) {
      ripple.style.transition = 'none';
      ripple.style.opacity = '1';
      ripple.style.transform = 'translate(' + (x - 20) + 'px,' + (y - 20) + 'px) scale(0)';
      ripple.offsetHeight; // force reflow
      ripple.style.transition = 'transform 0.4s ease-out, opacity 0.4s ease-out';
      ripple.style.transform = 'translate(' + (x - 20) + 'px,' + (y - 20) + 'px) scale(1.5)';
      ripple.style.opacity = '0';
    },
    setStatus(text) {
      const el = document.getElementById('zoo-pilot-action');
      if (el) el.textContent = text;
    },
    getPageState() {
      const modalOpen = !!document.querySelector('.modal-bg.open');
      const profileOpen = !!document.querySelector('.profile-overlay.open');
      const joinOpen = !!document.querySelector('.join-overlay.open');
      const searchVal = (document.getElementById('q') || {}).value || '';
      const activeSort = (document.querySelector('.sort-tab.active') || {}).dataset?.s || '';
      const activeCat = (document.querySelector('.sub-link.active') || {}).dataset?.c || '';
      const postCount = document.querySelectorAll('.post').length;
      const modalTitle = modalOpen ? (document.querySelector('.modal-post h2') || {}).textContent || '' : '';
      return { modalOpen, profileOpen, joinOpen, searchVal, activeSort, activeCat, postCount, modalTitle };
    }
  };
})();
`;

// ─── Smooth Mouse Movement ───────────────────────────────────────────────────

async function smoothMove(page, x, y, steps = 15) {
  // Get current cursor position from the page
  const current = await page.evaluate(() => {
    const c = document.getElementById('zoo-pilot-cursor');
    if (!c) return { x: 0, y: 0 };
    const t = c.style.transform;
    const m = t.match(/translate\((\d+(?:\.\d+)?)px,\s*(\d+(?:\.\d+)?)px\)/);
    return m ? { x: parseFloat(m[1]), y: parseFloat(m[2]) } : { x: 0, y: 0 };
  });
  // The CSS transition handles the smooth animation — just set the target
  await page.evaluate(({ x, y }) => window.__zooPilot.moveTo(x, y), { x, y });
  // Wait for the CSS transition to complete
  await page.waitForTimeout(400);
}

async function pilotClick(page, x, y) {
  await smoothMove(page, x, y);
  await page.evaluate(({ x, y }) => window.__zooPilot.clickAt(x, y), { x, y });
  await page.waitForTimeout(100);
  await page.mouse.click(x, y);
  await page.waitForTimeout(200);
}

async function pilotClickSelector(page, selector, label) {
  const el = await page.$(selector);
  if (!el) { console.log(`  ✗ Not found: ${selector}`); return false; }
  const box = await el.boundingBox();
  if (!box) { console.log(`  ✗ Not visible: ${selector}`); return false; }
  const x = box.x + box.width / 2;
  const y = box.y + box.height / 2;
  if (label) await setStatus(page, label);
  await pilotClick(page, x, y);
  return true;
}

async function pilotType(page, selector, text) {
  const el = await page.$(selector);
  if (!el) return false;
  const box = await el.boundingBox();
  if (box) await smoothMove(page, box.x + box.width / 2, box.y + box.height / 2);
  await el.click();
  await page.waitForTimeout(100);
  // Clear existing text
  await el.evaluate(e => e.value = '');
  // Type character by character for visible effect
  for (const ch of text) {
    await page.keyboard.type(ch, { delay: 40 + Math.random() * 60 });
  }
  return true;
}

async function setStatus(page, text) {
  await page.evaluate(t => {
    if (window.__zooPilot) window.__zooPilot.setStatus(t);
  }, text);
}

async function getPageState(page) {
  return page.evaluate(() => window.__zooPilot ? window.__zooPilot.getPageState() : {});
}

// ─── REPL Command Handlers ───────────────────────────────────────────────────

const COMMANDS = {};

COMMANDS.search = async (page, mesh, args) => {
  const q = args.join(' ');
  await setStatus(page, `searching: ${q}`);
  await pilotType(page, '#q', q);
  // Trigger the input event
  await page.evaluate(() => document.getElementById('q').dispatchEvent(new Event('input')));
  await page.waitForTimeout(500);
  const count = await page.$$eval('.post', posts => posts.length);
  console.log(`  🔍 Search "${q}" → ${count} results`);
};

COMMANDS.category = async (page, mesh, args) => {
  const name = args[0] || 'all';
  const sel = `.sub-link[data-c="${name}"]`;
  await setStatus(page, `category: ${name}`);
  const ok = await pilotClickSelector(page, sel, `category: ${name}`);
  if (ok) {
    await page.waitForTimeout(600);
    const count = await page.$$eval('.post', posts => posts.length);
    console.log(`  📂 Category "${name}" → ${count} apps`);
  }
};

COMMANDS.sort = async (page, mesh, args) => {
  const mode = args[0] || 'hot';
  const sel = `.sort-tab[data-s="${mode}"]`;
  await setStatus(page, `sort: ${mode}`);
  await pilotClickSelector(page, sel, `sort: ${mode}`);
  await page.waitForTimeout(400);
  console.log(`  📊 Sorted by ${mode}`);
};

COMMANDS.open = async (page, mesh, args) => {
  const n = parseInt(args[0]) || 1;
  const posts = await page.$$('.post-title');
  if (n < 1 || n > posts.length) { console.log(`  ✗ Post ${n} not found (${posts.length} visible)`); return; }
  const el = posts[n - 1];
  const text = await el.textContent();
  const box = await el.boundingBox();
  if (box) {
    await setStatus(page, `opening: ${text.substring(0, 30)}`);
    await pilotClick(page, box.x + box.width / 2, box.y + box.height / 2);
    await page.waitForTimeout(800);
    console.log(`  📖 Opened: ${text}`);
  }
};

COMMANDS.play = async (page, mesh, args) => {
  const n = parseInt(args[0]) || 1;
  const posts = await page.$$('.post [data-action="open"]');
  if (n < 1 || n > posts.length) { console.log(`  ✗ Post ${n} not found`); return; }
  const el = posts[n - 1];
  const box = await el.boundingBox();
  if (box) {
    await setStatus(page, `playing app #${n}`);
    await pilotClick(page, box.x + box.width / 2, box.y + box.height / 2);
    console.log(`  ▶ Launched app #${n}`);
  }
};

COMMANDS.rate = async (page, mesh, args) => {
  const stars = parseInt(args[0]) || 5;
  const sel = `#modal-stars .star[data-star="${Math.min(5, Math.max(1, stars))}"]`;
  await setStatus(page, `rating: ${'★'.repeat(stars)}`);
  await pilotClickSelector(page, sel, `rating: ${stars} stars`);
  console.log(`  ⭐ Rated ${stars} stars`);
};

COMMANDS.comment = async (page, mesh, args) => {
  const text = args.join(' ');
  if (!text) { console.log('  ✗ Usage: comment <text>'); return; }
  await setStatus(page, 'commenting...');
  const typed = await pilotType(page, '#root-textarea', text);
  if (!typed) { console.log('  ✗ Comment box not found (open an app first)'); return; }
  await page.waitForTimeout(200);
  await pilotClickSelector(page, '#root-submit', 'posting comment');
  await page.waitForTimeout(400);
  console.log(`  💬 Commented: ${text.substring(0, 50)}...`);
};

COMMANDS.back = async (page) => {
  await setStatus(page, 'closing modal');
  const state = await getPageState(page);
  if (state.joinOpen) {
    await pilotClickSelector(page, '[data-action="skip"]', 'skipping join');
  } else if (state.profileOpen) {
    await pilotClickSelector(page, '#profile-close', 'closing profile');
  } else if (state.modalOpen) {
    await pilotClickSelector(page, '#modal-close', 'closing modal');
  } else {
    await page.keyboard.press('Escape');
  }
  await page.waitForTimeout(300);
  console.log('  ← Back');
};

COMMANDS.scroll = async (page, mesh, args) => {
  const px = parseInt(args[0]) || 400;
  await setStatus(page, `scrolling ${px}px`);
  await page.evaluate(px => window.scrollBy({ top: px, behavior: 'smooth' }), px);
  await page.waitForTimeout(400);
  console.log(`  ↕ Scrolled ${px}px`);
};

COMMANDS.click = async (page, mesh, args) => {
  const x = parseInt(args[0]) || 0;
  const y = parseInt(args[1]) || 0;
  await setStatus(page, `click (${x}, ${y})`);
  await pilotClick(page, x, y);
  console.log(`  🖱 Clicked (${x}, ${y})`);
};

COMMANDS.hover = async (page, mesh, args) => {
  const x = parseInt(args[0]) || 0;
  const y = parseInt(args[1]) || 0;
  await smoothMove(page, x, y);
  console.log(`  → Moved to (${x}, ${y})`);
};

COMMANDS.type = async (page, mesh, args) => {
  const text = args.join(' ');
  await page.keyboard.type(text, { delay: 50 });
  console.log(`  ⌨ Typed: ${text}`);
};

COMMANDS.key = async (page, mesh, args) => {
  const key = args[0] || 'Enter';
  await page.keyboard.press(key);
  console.log(`  ⌨ Pressed: ${key}`);
};

COMMANDS.screenshot = async (page, mesh, args) => {
  const name = args[0] || `zoo-pilot-${Date.now()}`;
  const dir = path.join(ROOT, 'screenshots');
  if (!fs.existsSync(dir)) fs.mkdirSync(dir, { recursive: true });
  const file = path.join(dir, `${name}.png`);
  await page.screenshot({ path: file, fullPage: false });
  console.log(`  📸 Screenshot: ${file}`);
};

COMMANDS.data = async (page, mesh) => {
  const fresh = loadDataMesh();
  const summary = meshSummary(fresh);
  console.log('  📊 Data Mesh Summary:');
  console.log(`     Apps: ${summary.totalApps} | Players: ${summary.playerCount} | Avg Score: ${summary.avgScore}`);
  console.log(`     Apps w/ Comments: ${summary.appsWithComments} | Molter Frame: ${summary.molterFrame || 'none'}`);
  console.log('     Categories:');
  for (const [k, v] of Object.entries(summary.categories)) {
    console.log(`       ${k}: ${v.count} apps`);
  }
  if (summary.lowScoringApps.length) {
    console.log('     Low-scoring (need molting):');
    for (const a of summary.lowScoringApps) console.log(`       ${a.file}: ${a.score}`);
  }
};

COMMANDS.apps = async (page, mesh, args) => {
  const cat = args[0];
  const fresh = loadDataMesh();
  const list = getAppList(fresh, cat);
  console.log(`  📋 ${list.length} apps${cat ? ` in ${cat}` : ''}:`);
  for (const a of list.slice(0, 20)) {
    console.log(`     ${a.file} [${a.category}] ${a.title || ''}`);
  }
  if (list.length > 20) console.log(`     ... and ${list.length - 20} more`);
};

COMMANDS.status = async (page) => {
  const state = await getPageState(page);
  console.log('  📍 Page State:', JSON.stringify(state, null, 2));
};

COMMANDS.molt = async (page, mesh, args) => {
  const stem = args[0];
  if (!stem) { console.log('  ✗ Usage: molt <stem>'); return; }
  console.log(`  🔄 Triggering molt for ${stem}...`);
  try {
    const out = execSync(`python3 scripts/molt.py ${stem}.html --verbose`, {
      cwd: ROOT, encoding: 'utf8', timeout: 300000, stdio: ['pipe', 'pipe', 'pipe']
    });
    console.log(out.substring(0, 500));
  } catch (e) { console.error('  ✗ Molt failed:', e.message?.substring(0, 200)); }
};

COMMANDS.rank = async () => {
  console.log('  📊 Triggering ranking...');
  try {
    const out = execSync('python3 scripts/rank_games.py --verbose', {
      cwd: ROOT, encoding: 'utf8', timeout: 300000, stdio: ['pipe', 'pipe', 'pipe']
    });
    console.log(out.substring(0, 500));
  } catch (e) { console.error('  ✗ Ranking failed:', e.message?.substring(0, 200)); }
};

// ─── Data Slosh Engine ───────────────────────────────────────────────────────

async function dataSlosh(page, mesh) {
  // 1. Read current page state
  const pageState = await getPageState(page);

  // 2. Build fresh data mesh snapshot
  const fresh = loadDataMesh();
  const summary = meshSummary(fresh);

  // 3. Get visible feed content
  const feedSnapshot = await page.evaluate(() => {
    const posts = document.querySelectorAll('.post');
    return Array.from(posts).slice(0, 10).map((p, i) => {
      const title = (p.querySelector('.post-title') || {}).textContent || '';
      const desc = (p.querySelector('.post-desc') || {}).textContent || '';
      const flair = (p.querySelector('.post-flair') || {}).textContent || '';
      const votes = (p.querySelector('.vote-count') || {}).textContent || '0';
      return { index: i + 1, title, desc: desc.substring(0, 80), category: flair, votes };
    });
  });

  // 4. Ask LLM what to do next
  const prompt = `You are zoo-pilot, an autonomous browser agent driving the RappterZoo gallery UI.
You can see the page and have access to the full data mesh. Decide ONE action to take next.

CURRENT PAGE STATE:
${JSON.stringify(pageState, null, 1)}

VISIBLE FEED (first 10 posts):
${JSON.stringify(feedSnapshot, null, 1)}

DATA MESH SUMMARY:
- Total apps: ${summary.totalApps}
- Average score: ${summary.avgScore}
- Players: ${summary.playerCount}
- Molter frame: ${summary.molterFrame || 'none'}
- Categories: ${JSON.stringify(summary.categories)}
${summary.lowScoringApps.length ? '- Low-scoring apps needing attention: ' + JSON.stringify(summary.lowScoringApps) : ''}

YOUR GOAL: Browse the zoo like a curious human. Explore different categories, open interesting apps,
check comments, rate games, discover patterns. If you notice low-scoring apps or ones needing molts,
flag them. Use the data to guide your exploration — don't just random walk.

AVAILABLE ACTIONS (return exactly ONE as JSON):
- {"action":"search","query":"<text>"}
- {"action":"category","name":"<category_key>"}  (keys: all, featured, molted, games_puzzles, visual_art, etc.)
- {"action":"sort","mode":"<hot|new|rising|top|name>"}
- {"action":"open","n":<1-based index>}  (open nth visible post)
- {"action":"scroll","px":<pixels>}
- {"action":"back"}  (close current modal)
- {"action":"rate","stars":<1-5>}  (rate current open app)
- {"action":"comment","text":"<text>"}  (comment on current open app)
- {"action":"molt","stem":"<app-stem>"}  (trigger a molt on a low-quality app)
- {"action":"screenshot","name":"<name>"}

Think about what's most interesting or useful to do right now given the data.
If a modal is open, interact with it (rate, comment, scroll comments) or close it.
If the feed is showing, explore a category you haven't visited or open an intriguing app.

Return ONLY a JSON object with your chosen action. No explanation.`;

  await setStatus(page, '🧠 data-sloshing...');
  const raw = copilotCall(prompt);
  const decision = parseLLMJson(raw);

  if (!decision || !decision.action) {
    console.log('  ⚠ LLM returned no valid action, falling back to random browse');
    // Fallback: random exploration
    const fallbacks = ['scroll', 'open'];
    const fb = fallbacks[Math.floor(Math.random() * fallbacks.length)];
    if (fb === 'scroll') {
      await COMMANDS.scroll(page, fresh, [String(300 + Math.floor(Math.random() * 400))]);
    } else {
      const n = Math.floor(Math.random() * 5) + 1;
      await COMMANDS.open(page, fresh, [String(n)]);
    }
    return;
  }

  console.log(`  🧠 Slosh decision: ${JSON.stringify(decision)}`);

  // Execute the decision
  const { action, ...params } = decision;
  const handler = COMMANDS[action];
  if (handler) {
    const args = [];
    if (params.query) args.push(...params.query.split(' '));
    else if (params.name) args.push(params.name);
    else if (params.mode) args.push(params.mode);
    else if (params.n) args.push(String(params.n));
    else if (params.px) args.push(String(params.px));
    else if (params.stars) args.push(String(params.stars));
    else if (params.text) args.push(...params.text.split(' '));
    else if (params.stem) args.push(params.stem);
    await handler(page, mesh, args);
  } else {
    console.log(`  ⚠ Unknown action: ${action}`);
  }
}

COMMANDS.slosh = async (page, mesh) => {
  await dataSlosh(page, mesh);
};

// ─── Autonomous Mode ─────────────────────────────────────────────────────────

let autoRunning = false;
let autoTimer = null;

async function startAuto(page, mesh, durationSec = 300) {
  if (autoRunning) { console.log('  ⚠ Auto mode already running'); return; }
  autoRunning = true;
  console.log(`  🤖 Autonomous data-slosh mode — ${durationSec}s`);
  await setStatus(page, '🤖 autonomous mode');

  const startTime = Date.now();
  const deadline = startTime + durationSec * 1000;

  const loop = async () => {
    if (!autoRunning || Date.now() > deadline) {
      autoRunning = false;
      await setStatus(page, '⏹ auto mode ended');
      console.log(`  ⏹ Autonomous mode ended after ${Math.round((Date.now() - startTime) / 1000)}s`);
      return;
    }

    try {
      await dataSlosh(page, mesh);
    } catch (e) {
      console.error('  ⚠ Slosh error:', e.message?.substring(0, 100));
    }

    // Wait 2-5 seconds between actions (human-like pacing)
    const delay = 2000 + Math.floor(Math.random() * 3000);
    autoTimer = setTimeout(() => loop(), delay);
  };

  await loop();
}

COMMANDS.auto = async (page, mesh, args) => {
  const secs = parseInt(args[0]) || 300;
  startAuto(page, mesh, secs);
};

COMMANDS.stop = async (page) => {
  autoRunning = false;
  if (autoTimer) { clearTimeout(autoTimer); autoTimer = null; }
  await setStatus(page, '⏹ stopped');
  console.log('  ⏹ Autonomous mode stopped');
};

// ─── Main ────────────────────────────────────────────────────────────────────

async function main() {
  const args = process.argv.slice(2);
  const port = parseInt(args.find((_, i, a) => a[i - 1] === '--port') || '8765');
  const headless = args.includes('--headless');
  const autoMode = args.includes('--auto');
  const autoDuration = parseInt(args.find((_, i, a) => a[i - 1] === '--duration') || '300');

  console.log('\n  🦎 zoo-pilot — Data-Slosh Driven UI Pilot');
  console.log('  ──────────────────────────────────────────\n');

  // Load data mesh
  const mesh = loadDataMesh();
  const summary = meshSummary(mesh);
  console.log(`  📊 Data mesh: ${summary.totalApps} apps, ${summary.playerCount} players, avg score ${summary.avgScore}`);

  // Start server
  const server = await startServer(port);

  // Launch browser
  console.log(`  🚀 Launching browser (${headless ? 'headless' : 'visible'})...`);
  const browser = await chromium.launch({
    headless,
    slowMo: headless ? 0 : 50,
    args: ['--window-size=1440,900'],
  });
  const context = await browser.newContext({
    viewport: { width: 1440, height: 900 },
    deviceScaleFactor: 1,
  });
  const page = await context.newPage();

  // Navigate and inject cursor
  await page.goto(`http://localhost:${port}`, { waitUntil: 'networkidle' });
  await page.evaluate(CURSOR_INJECT);
  await setStatus(page, 'ready');
  console.log('  ✅ Page loaded, cursor injected\n');

  // Dismiss join overlay if it appears
  await page.waitForTimeout(2000);
  const state = await getPageState(page);
  if (state.joinOpen) {
    console.log('  👤 Join overlay detected — skipping as guest');
    await pilotClickSelector(page, '[data-action="skip"]', 'browsing as guest');
    await page.waitForTimeout(500);
  }

  // Re-inject cursor after any navigation
  page.on('load', async () => {
    try { await page.evaluate(CURSOR_INJECT); } catch {}
  });

  if (autoMode) {
    await startAuto(page, mesh, autoDuration);
    // Wait for auto to finish, then exit
    await new Promise((resolve) => {
      const check = setInterval(() => {
        if (!autoRunning) { clearInterval(check); resolve(); }
      }, 1000);
    });
  } else {
    // Interactive REPL
    const rl = readline.createInterface({ input: process.stdin, output: process.stdout });
    const prompt = () => rl.question('  zoo-pilot> ', async (line) => {
      const trimmed = line.trim();
      if (!trimmed) { prompt(); return; }
      if (trimmed === 'quit' || trimmed === 'exit') {
        rl.close();
        return;
      }
      const [cmd, ...cmdArgs] = trimmed.split(/\s+/);
      const handler = COMMANDS[cmd];
      if (handler) {
        try { await handler(page, mesh, cmdArgs); }
        catch (e) { console.error(`  ✗ Error: ${e.message}`); }
      } else {
        console.log(`  ✗ Unknown command: ${cmd}`);
        console.log('  Commands: search, category, sort, open, play, rate, comment, back, scroll,');
        console.log('            click, hover, type, key, auto, stop, screenshot, data, apps,');
        console.log('            status, slosh, molt, rank, quit');
      }
      prompt();
    });
    prompt();

    await new Promise((resolve) => rl.on('close', resolve));
  }

  // Cleanup
  console.log('\n  🛑 Shutting down...');
  await browser.close();
  server.close();
  console.log('  👋 Bye!\n');
  process.exit(0);
}

main().catch((e) => {
  console.error('Fatal:', e);
  process.exit(1);
});
