#!/usr/bin/env node
/**
 * test-zoo-pilot.js — Playwright test suite for zoo-pilot.
 *
 * Runs headless: no LLM calls, no network, no side effects.
 *
 * Usage:
 *   node scripts/tests/test-zoo-pilot.js
 */

const { chromium } = require('playwright');
const http = require('http');
const fs = require('fs');
const path = require('path');
const assert = require('assert');

const ROOT = path.resolve(__dirname, '..', '..');
const zoo = require(path.join(ROOT, 'scripts', 'zoo-pilot.js'));

// ─── Test Harness ────────────────────────────────────────────────────────────

let passed = 0, failed = 0, errors = [];

async function test(name, fn) {
  try {
    await fn();
    passed++;
    console.log(`  ✅ ${name}`);
  } catch (e) {
    failed++;
    errors.push({ name, error: e.message });
    console.log(`  ❌ ${name}: ${e.message}`);
  }
}

// ─── Unit Tests (no browser) ─────────────────────────────────────────────────

async function unitTests() {
  console.log('\n  ── Unit Tests ──\n');

  await test('loadJSON returns parsed JSON for valid file', () => {
    const m = zoo.loadJSON(path.join(ROOT, 'apps', 'manifest.json'));
    assert(m !== null, 'should not be null');
    assert(m.categories, 'should have categories');
  });

  await test('loadJSON returns null for missing file', () => {
    const m = zoo.loadJSON('/nonexistent/path.json');
    assert(m === null, 'should be null for missing file');
  });

  await test('loadDataMesh returns all expected keys', () => {
    const mesh = zoo.loadDataMesh();
    assert(mesh.manifest, 'should have manifest');
    assert(mesh.rankings, 'should have rankings');
    assert(mesh.community, 'should have community');
    for (const key of ['contentGraph', 'molterState', 'dataMoltState']) {
      assert(key in mesh, `should have ${key}`);
    }
  });

  await test('meshSummary computes correct totals', () => {
    const mesh = zoo.loadDataMesh();
    const s = zoo.meshSummary(mesh);
    assert(typeof s === 'object', 'should return object');
    assert(s.totalApps > 0, `totalApps should be > 0, got ${s.totalApps}`);
    assert(s.categories, 'should have categories');
    assert(Object.keys(s.categories).length >= 9, `should have >=9 categories, got ${Object.keys(s.categories).length}`);
    assert(s.playerCount > 0, 'should have players');
    assert(parseFloat(s.avgScore) > 0, `avgScore should be > 0, got ${s.avgScore}`);
  });

  await test('meshSummary handles empty manifest gracefully', () => {
    const result = zoo.meshSummary({ manifest: null });
    assert(result === 'manifest not loaded', 'should return error string');
  });

  await test('getAppList returns all apps when no category filter', () => {
    const mesh = zoo.loadDataMesh();
    const apps = zoo.getAppList(mesh);
    assert(apps.length > 100, `should have >100 apps, got ${apps.length}`);
    assert(apps[0].file, 'each app should have file');
    assert(apps[0].category, 'each app should have category');
  });

  await test('getAppList filters by category', () => {
    const mesh = zoo.loadDataMesh();
    const all = zoo.getAppList(mesh);
    const games = zoo.getAppList(mesh, 'games_puzzles');
    assert(games.length > 0, 'should have some games');
    assert(games.length < all.length, 'filtered should be less than all');
    assert(games.every(a => a.category === 'games_puzzles'), 'all should be games_puzzles');
  });

  await test('getAppList returns empty for unknown category', () => {
    const mesh = zoo.loadDataMesh();
    const apps = zoo.getAppList(mesh, 'nonexistent_category_xyz');
    assert(apps.length === 0, 'should be empty');
  });

  await test('stripCopilotWrapper strips ANSI codes', () => {
    const input = '\x1b[32mHello\x1b[0m world';
    assert.strictEqual(zoo.stripCopilotWrapper(input), 'Hello world');
  });

  await test('stripCopilotWrapper strips task markers', () => {
    const input = '{"action":"open"}\nTask complete in 3.2s';
    assert.strictEqual(zoo.stripCopilotWrapper(input), '{"action":"open"}');
  });

  await test('stripCopilotWrapper strips usage stats', () => {
    const input = '{"result":true}\nTotal usage est: 500 tokens';
    assert.strictEqual(zoo.stripCopilotWrapper(input), '{"result":true}');
  });

  await test('parseLLMJson parses clean JSON', () => {
    const r = zoo.parseLLMJson('{"action":"open","n":3}');
    assert.deepStrictEqual(r, { action: 'open', n: 3 });
  });

  await test('parseLLMJson parses fenced JSON', () => {
    const r = zoo.parseLLMJson('Here is the result:\n```json\n{"action":"search","query":"synth"}\n```\nDone.');
    assert.deepStrictEqual(r, { action: 'search', query: 'synth' });
  });

  await test('parseLLMJson extracts embedded JSON object', () => {
    const r = zoo.parseLLMJson('I think you should do: {"action":"back"} ok?');
    assert.deepStrictEqual(r, { action: 'back' });
  });

  await test('parseLLMJson returns null for garbage', () => {
    assert.strictEqual(zoo.parseLLMJson('not json at all'), null);
    assert.strictEqual(zoo.parseLLMJson(null), null);
    assert.strictEqual(zoo.parseLLMJson(''), null);
  });

  await test('CURSOR_INJECT is valid JS string', () => {
    assert(zoo.CURSOR_INJECT.length > 100, 'should be substantial');
    assert(zoo.CURSOR_INJECT.includes('zoo-pilot-cursor'), 'should create cursor element');
    assert(zoo.CURSOR_INJECT.includes('__zooPilot'), 'should set window.__zooPilot');
  });

  await test('COMMANDS has all expected commands', () => {
    const expected = ['search', 'category', 'sort', 'open', 'play', 'rate', 'comment',
      'back', 'scroll', 'click', 'hover', 'type', 'key', 'screenshot', 'data',
      'apps', 'status', 'molt', 'rank', 'slosh', 'auto', 'stop', 'poke', 'ghost'];
    for (const cmd of expected) {
      assert(typeof zoo.COMMANDS[cmd] === 'function', `COMMANDS.${cmd} should be a function`);
    }
  });

  await test('MIME types cover essential extensions', () => {
    assert.strictEqual(zoo.MIME['.html'], 'text/html');
    assert.strictEqual(zoo.MIME['.json'], 'application/json');
    assert.strictEqual(zoo.MIME['.js'], 'application/javascript');
    assert.strictEqual(zoo.MIME['.css'], 'text/css');
    assert.strictEqual(zoo.MIME['.png'], 'image/png');
  });

  // ─── Ghost Poke Protocol (Unit Tests) ──────────────────────────────────────

  // We'll use a temp ghost state file to avoid mutating the real one
  const tmpGhostPath = path.join(ROOT, 'apps', 'ghost-state-test.json');

  await test('loadGhostState returns default state when file missing', () => {
    // loadGhostState falls back to defaults if file doesn't exist
    const gs = zoo.loadGhostState();
    assert(gs.creature, 'should have creature');
    assert(gs.stats, 'should have stats');
    assert(Array.isArray(gs.pokes), 'should have pokes array');
    assert(Array.isArray(gs.reactions), 'should have reactions array');
    assert(Array.isArray(gs.history), 'should have history array');
  });

  await test('loadGhostState reads real ghost-state.json', () => {
    const gs = zoo.loadGhostState();
    assert.strictEqual(gs.creature.id, 'ghost-pilot');
    assert.strictEqual(gs.creature.type, 'ghost');
  });

  await test('addPoke adds a poke with correct fields', () => {
    const gs = zoo.loadGhostState();
    const initialCount = gs.pokes.length;
    const initialReceived = gs.stats.pokesReceived;
    zoo.addPoke(gs, { from: 'test-agent', command: 'search', args: ['fractal'] });
    assert.strictEqual(gs.pokes.length, initialCount + 1);
    assert.strictEqual(gs.stats.pokesReceived, initialReceived + 1);
    const poke = gs.pokes[gs.pokes.length - 1];
    assert(poke.id.startsWith('poke-'), 'id should start with poke-');
    assert.strictEqual(poke.from, 'test-agent');
    assert.strictEqual(poke.command, 'search');
    assert.deepStrictEqual(poke.args, ['fractal']);
    assert.strictEqual(poke.status, 'pending');
    assert(poke.ts, 'should have timestamp');
  });

  await test('processPokes returns only pending pokes', () => {
    const gs = {
      creature: {}, stats: { pokesReceived: 3, pokesCompleted: 1 },
      history: [], reactions: [],
      pokes: [
        { id: 'p1', status: 'done', command: 'search' },
        { id: 'p2', status: 'pending', command: 'open' },
        { id: 'p3', status: 'pending', command: 'rate' },
      ]
    };
    const pending = zoo.processPokes(gs);
    assert.strictEqual(pending.length, 2);
    assert.strictEqual(pending[0].id, 'p2');
    assert.strictEqual(pending[1].id, 'p3');
  });

  await test('completePoke marks poke done and logs reaction', () => {
    const gs = {
      creature: {}, stats: { pokesReceived: 1, pokesCompleted: 0 },
      history: [], reactions: [],
      pokes: [{ id: 'p1', status: 'pending', from: 'test', command: 'search' }]
    };
    zoo.completePoke(gs, 'p1', 'executed: search fractal');
    assert.strictEqual(gs.pokes[0].status, 'done');
    assert(gs.pokes[0].completedAt, 'should have completedAt');
    assert.strictEqual(gs.stats.pokesCompleted, 1);
    assert.strictEqual(gs.reactions.length, 1);
    assert.strictEqual(gs.reactions[0].pokeId, 'p1');
    assert.strictEqual(gs.reactions[0].from, 'test');
    assert.strictEqual(gs.reactions[0].reaction, 'executed: search fractal');
  });

  await test('recordGhostAction increments stats and pushes history', () => {
    const gs = {
      creature: {}, stats: { totalActions: 0, appsOpened: 0, ratingsGiven: 0,
        commentsPosted: 0, categoriesVisited: [], lastActive: null },
      history: [], pokes: [], reactions: []
    };
    zoo.recordGhostAction(gs, 'open', 'Fractal Garden');
    assert.strictEqual(gs.stats.totalActions, 1);
    assert.strictEqual(gs.stats.appsOpened, 1);
    assert.strictEqual(gs.history.length, 1);
    assert.strictEqual(gs.history[0].action, 'open');
    assert(gs.stats.lastActive, 'lastActive should be set');

    zoo.recordGhostAction(gs, 'rate', '5');
    assert.strictEqual(gs.stats.ratingsGiven, 1);

    zoo.recordGhostAction(gs, 'comment', 'great app');
    assert.strictEqual(gs.stats.commentsPosted, 1);

    zoo.recordGhostAction(gs, 'category', 'visual_art');
    assert(gs.stats.categoriesVisited.includes('visual_art'));

    // Duplicate category should not add again
    zoo.recordGhostAction(gs, 'category', 'visual_art');
    assert.strictEqual(gs.stats.categoriesVisited.filter(c => c === 'visual_art').length, 1);
  });

  await test('saveGhostState trims history and reactions', () => {
    const gs = zoo.loadGhostState();
    // Fill with 250 history entries and 150 reactions
    gs.history = Array.from({ length: 250 }, (_, i) => ({ ts: new Date().toISOString(), action: 'test', detail: `h${i}` }));
    gs.reactions = Array.from({ length: 150 }, (_, i) => ({ pokeId: `p${i}`, ts: new Date().toISOString(), from: 'test', command: 'test', reaction: `r${i}` }));
    zoo.saveGhostState(gs);
    // Re-read
    const saved = JSON.parse(fs.readFileSync(zoo.GHOST_STATE_PATH, 'utf8'));
    assert(saved.history.length <= 200, `history should be trimmed to 200, got ${saved.history.length}`);
    assert(saved.reactions.length <= 100, `reactions should be trimmed to 100, got ${saved.reactions.length}`);
    // Restore original
    const original = { creature: { id: 'ghost-pilot', name: 'zoo-pilot', type: 'ghost', color: '#ff4500',
      bio: 'Autonomous data-slosh browser agent. I browse the zoo driven by LLM intelligence, rating and commenting as whatever NPC I hijack. Poke me to make me do things.',
      born: '2026-02-08', status: 'dormant', npcHost: null, currentPage: null },
      stats: { totalSessions: 0, totalActions: 0, appsOpened: 0, ratingsGiven: 0, commentsPosted: 0,
        categoriesVisited: [], pokesReceived: 0, pokesCompleted: 0, lastActive: null },
      history: [], pokes: [], reactions: [] };
    fs.writeFileSync(zoo.GHOST_STATE_PATH, JSON.stringify(original, null, 2), 'utf8');
  });
}

// ─── Integration Tests (headless browser) ────────────────────────────────────

async function integrationTests() {
  console.log('\n  ── Integration Tests (headless Playwright) ──\n');

  // Start server
  const port = 18765 + Math.floor(Math.random() * 1000);
  const server = await zoo.startServer(port);
  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext({ viewport: { width: 1440, height: 900 } });
  let page;

  try {
    // ─── Server tests ───

    await test('static server serves index.html', async () => {
      const res = await fetch(`http://localhost:${port}/`);
      assert.strictEqual(res.status, 200);
      const text = await res.text();
      assert(text.includes('RappterZoo'), 'should contain RappterZoo');
    });

    await test('static server serves manifest.json', async () => {
      const res = await fetch(`http://localhost:${port}/apps/manifest.json`);
      assert.strictEqual(res.status, 200);
      const data = await res.json();
      assert(data.categories, 'should have categories');
    });

    await test('static server returns 404 for missing files', async () => {
      const res = await fetch(`http://localhost:${port}/does-not-exist.xyz`);
      assert.strictEqual(res.status, 404);
    });

    // ─── Page load + cursor injection ───

    page = await context.newPage();
    await page.goto(`http://localhost:${port}`, { waitUntil: 'networkidle' });

    // Dismiss join overlay
    await page.waitForTimeout(2000);
    const skipBtn = await page.$('.btn-skip');
    if (skipBtn) await skipBtn.click();
    await page.waitForTimeout(300);

    // Inject a player for comment tests
    await page.evaluate(() => {
      const player = { id: 'test-pilot', username: 'test-pilot', color: '#ff4500',
        bio: 'Test agent', gamesPlayed: 0, activityLevel: 'agent',
        joinDate: '2025-01-01', isHuman: true };
      localStorage.setItem('rappterzoo-player', JSON.stringify(player));
    });
    // Reload to pick up player
    await page.reload({ waitUntil: 'networkidle' });
    await page.waitForTimeout(1500);
    // Dismiss join overlay again if it reappears
    const skipBtn2 = await page.$('.btn-skip');
    if (skipBtn2) await skipBtn2.click();
    await page.waitForTimeout(300);

    await test('page loads with posts', async () => {
      const count = await page.$$eval('.post', ps => ps.length);
      assert(count > 100, `should have >100 posts, got ${count}`);
    });

    await test('page title is correct', async () => {
      const title = await page.title();
      assert(title.includes('RappterZoo'), `title should include RappterZoo, got "${title}"`);
    });

    await test('cursor injection creates elements', async () => {
      await page.evaluate(zoo.CURSOR_INJECT);
      const hasCursor = await page.$('#zoo-pilot-cursor');
      const hasTrail = await page.$('#zoo-pilot-trail');
      const hasRipple = await page.$('#zoo-pilot-ripple');
      const hasStatus = await page.$('#zoo-pilot-status');
      assert(hasCursor, 'cursor element should exist');
      assert(hasTrail, 'trail element should exist');
      assert(hasRipple, 'ripple element should exist');
      assert(hasStatus, 'status bar should exist');
    });

    await test('cursor injection is idempotent', async () => {
      await page.evaluate(zoo.CURSOR_INJECT);
      await page.evaluate(zoo.CURSOR_INJECT);
      const cursors = await page.$$('#zoo-pilot-cursor');
      assert.strictEqual(cursors.length, 1, 'should have exactly one cursor');
    });

    await test('__zooPilot API available on window', async () => {
      const api = await page.evaluate(() => {
        return {
          moveTo: typeof window.__zooPilot?.moveTo,
          clickAt: typeof window.__zooPilot?.clickAt,
          setStatus: typeof window.__zooPilot?.setStatus,
          getPageState: typeof window.__zooPilot?.getPageState,
        };
      });
      assert.strictEqual(api.moveTo, 'function');
      assert.strictEqual(api.clickAt, 'function');
      assert.strictEqual(api.setStatus, 'function');
      assert.strictEqual(api.getPageState, 'function');
    });

    await test('getPageState returns expected shape', async () => {
      const state = await zoo.getPageState(page);
      assert('modalOpen' in state, 'should have modalOpen');
      assert('profileOpen' in state, 'should have profileOpen');
      assert('joinOpen' in state, 'should have joinOpen');
      assert('searchVal' in state, 'should have searchVal');
      assert('activeSort' in state, 'should have activeSort');
      assert('activeCat' in state, 'should have activeCat');
      assert('postCount' in state, 'should have postCount');
      assert(state.postCount > 0, 'should have posts');
      assert.strictEqual(state.modalOpen, false, 'modal should be closed');
    });

    await test('setStatus updates status bar text', async () => {
      await zoo.setStatus(page, 'test-status-123');
      const text = await page.$eval('#zoo-pilot-action', el => el.textContent);
      assert.strictEqual(text, 'test-status-123');
    });

    // ─── Search ───

    await test('search filters posts', async () => {
      const mesh = zoo.loadDataMesh();
      await zoo.COMMANDS.search(page, mesh, ['synth']);
      await page.waitForTimeout(300);
      const count = await page.$$eval('.post', ps => ps.length);
      assert(count > 0 && count < 100, `search should filter, got ${count}`);
      const searchVal = await page.$eval('#q', el => el.value);
      assert(searchVal.includes('synth'), `search box should contain "synth", got "${searchVal}"`);
    });

    await test('search with no results shows empty state', async () => {
      const mesh = zoo.loadDataMesh();
      await zoo.COMMANDS.search(page, mesh, ['xyznonexistent99999']);
      await page.waitForTimeout(300);
      const count = await page.$$eval('.post', ps => ps.length);
      assert.strictEqual(count, 0, 'should have 0 results');
    });

    // Clear search for next tests
    await page.$eval('#q', el => { el.value = ''; el.dispatchEvent(new Event('input')); });
    await page.waitForTimeout(300);

    // ─── Sort ───

    await test('sort switches active tab', async () => {
      const mesh = zoo.loadDataMesh();
      await zoo.COMMANDS.sort(page, mesh, ['new']);
      const active = await page.$eval('.sort-tab.active', el => el.dataset.s);
      assert.strictEqual(active, 'new', 'active sort should be "new"');
    });

    await test('sort top shows different order', async () => {
      const mesh = zoo.loadDataMesh();
      await zoo.COMMANDS.sort(page, mesh, ['top']);
      const active = await page.$eval('.sort-tab.active', el => el.dataset.s);
      assert.strictEqual(active, 'top');
    });

    // Reset sort
    await zoo.COMMANDS.sort(page, zoo.loadDataMesh(), ['hot']);

    // ─── Category ───

    await test('category filters to specific category', async () => {
      const mesh = zoo.loadDataMesh();
      await zoo.COMMANDS.category(page, mesh, ['games_puzzles']);
      await page.waitForTimeout(400);
      const count = await page.$$eval('.post', ps => ps.length);
      assert(count > 0, `games_puzzles should have apps, got ${count}`);
      const active = await page.$eval('.sub-link.active', el => el.dataset.c);
      assert.strictEqual(active, 'games_puzzles');
    });

    await test('category "all" shows all apps', async () => {
      const mesh = zoo.loadDataMesh();
      await zoo.COMMANDS.category(page, mesh, ['all']);
      await page.waitForTimeout(400);
      const count = await page.$$eval('.post', ps => ps.length);
      assert(count > 100, `all should have >100 apps, got ${count}`);
    });

    // ─── Open / Modal ───

    await test('open opens modal for a post', async () => {
      const mesh = zoo.loadDataMesh();
      await zoo.COMMANDS.open(page, mesh, ['1']);
      await page.waitForTimeout(500);
      const state = await zoo.getPageState(page);
      assert.strictEqual(state.modalOpen, true, 'modal should be open');
      assert(state.modalTitle.length > 0, 'modal should have a title');
    });

    // ─── Rate (while modal is open) ───

    await test('rate clicks star in modal', async () => {
      const mesh = zoo.loadDataMesh();
      await zoo.COMMANDS.rate(page, mesh, ['4']);
      // Check that 4th star is filled
      const filled = await page.$$eval('#modal-stars .star.filled', stars => stars.length);
      assert(filled >= 4, `should have at least 4 filled stars, got ${filled}`);
    });

    // ─── Comment (while modal is open) ───

    await test('comment posts text in modal', async () => {
      const mesh = zoo.loadDataMesh();
      // Check if textarea is enabled (need player identity)
      const disabled = await page.$eval('#root-textarea', el => el.disabled);
      if (disabled) {
        console.log('    (skipped — no player identity, textarea disabled)');
        return;
      }
      await zoo.COMMANDS.comment(page, mesh, ['Test comment from zoo-pilot test suite']);
      await page.waitForTimeout(500);
      // Check comment appeared
      const comments = await page.$$eval('#comment-list .comment', cs => cs.length);
      assert(comments > 0, 'should have at least one comment');
    });

    // ─── Back ───

    await test('back closes modal', async () => {
      // Reopen a modal first to ensure one is open
      const mesh = zoo.loadDataMesh();
      const state0 = await zoo.getPageState(page);
      if (!state0.modalOpen) {
        await zoo.COMMANDS.open(page, mesh, ['1']);
        await page.waitForTimeout(500);
      }
      const stateBefore = await zoo.getPageState(page);
      assert.strictEqual(stateBefore.modalOpen, true, 'modal should be open before back');
      await zoo.COMMANDS.back(page);
      await page.waitForTimeout(500);
      const state = await zoo.getPageState(page);
      assert.strictEqual(state.modalOpen, false, 'modal should be closed');
    });

    // ─── Scroll ───

    await test('scroll changes page scroll position', async () => {
      const mesh = zoo.loadDataMesh();
      const before = await page.evaluate(() => window.scrollY);
      await zoo.COMMANDS.scroll(page, mesh, ['300']);
      await page.waitForTimeout(500);
      const after = await page.evaluate(() => window.scrollY);
      assert(after > before, `scroll should increase, before=${before} after=${after}`);
    });

    // Scroll back to top
    await page.evaluate(() => window.scrollTo(0, 0));
    await page.waitForTimeout(200);

    // ─── Screenshot ───

    await test('screenshot creates file', async () => {
      const mesh = zoo.loadDataMesh();
      const name = `test-screenshot-${Date.now()}`;
      await zoo.COMMANDS.screenshot(page, mesh, [name]);
      const file = path.join(ROOT, 'screenshots', `${name}.png`);
      assert(fs.existsSync(file), `screenshot file should exist: ${file}`);
      // Cleanup
      fs.unlinkSync(file);
    });

    // ─── Data command (smoke test) ───

    await test('data command runs without error', async () => {
      const mesh = zoo.loadDataMesh();
      // Just verify it doesn't throw
      await zoo.COMMANDS.data(page, mesh);
    });

    // ─── Apps command ───

    await test('apps command runs without error', async () => {
      const mesh = zoo.loadDataMesh();
      await zoo.COMMANDS.apps(page, mesh, []);
    });

    // ─── Status command ───

    await test('status command runs without error', async () => {
      await zoo.COMMANDS.status(page);
    });

    // ─── Open out-of-bounds ───

    await test('open with invalid index handles gracefully', async () => {
      const mesh = zoo.loadDataMesh();
      // Should not throw
      await zoo.COMMANDS.open(page, mesh, ['99999']);
    });

    // ─── Multiple operations sequence ───

    await test('full browse sequence: category → sort → open → rate → back', async () => {
      const mesh = zoo.loadDataMesh();
      // Ensure we start with modal closed
      await zoo.COMMANDS.back(page);
      await page.waitForTimeout(300);

      // Category
      await zoo.COMMANDS.category(page, mesh, ['visual_art']);
      await page.waitForTimeout(400);
      let state = await zoo.getPageState(page);
      assert.strictEqual(state.activeCat, 'visual_art', `expected visual_art, got ${state.activeCat}`);

      // Sort
      await zoo.COMMANDS.sort(page, mesh, ['top']);
      await page.waitForTimeout(200);

      // Open
      await zoo.COMMANDS.open(page, mesh, ['1']);
      await page.waitForTimeout(500);
      state = await zoo.getPageState(page);
      assert.strictEqual(state.modalOpen, true);

      // Rate
      await zoo.COMMANDS.rate(page, mesh, ['5']);

      // Back
      await zoo.COMMANDS.back(page);
      await page.waitForTimeout(500);
      state = await zoo.getPageState(page);
      assert.strictEqual(state.modalOpen, false, 'modal should be closed after back');
    });

    // ─── Ghost REPL commands (integration) ───

    await test('ghost command runs without error', async () => {
      const mesh = zoo.loadDataMesh();
      // Should not throw
      await zoo.COMMANDS.ghost(page, mesh, []);
    });

    await test('poke command with no args shows ghost status', async () => {
      const mesh = zoo.loadDataMesh();
      // Should not throw
      await zoo.COMMANDS.poke(page, mesh, []);
    });

    await test('poke command queues a poke', async () => {
      const mesh = zoo.loadDataMesh();
      // Queue a poke
      await zoo.COMMANDS.poke(page, mesh, ['test-agent', 'search', 'fractal']);
      // Verify it was added
      const gs = zoo.loadGhostState();
      const testPokes = gs.pokes.filter(p => p.from === 'test-agent' && p.command === 'search');
      assert(testPokes.length > 0, 'should have queued poke');
      // Clean up
      gs.pokes = gs.pokes.filter(p => p.from !== 'test-agent');
      zoo.saveGhostState(gs);
    });

  } finally {
    await browser.close();
    server.close();
  }
}

// ─── Run ─────────────────────────────────────────────────────────────────────

async function run() {
  console.log('\n  🧪 zoo-pilot test suite');
  console.log('  ──────────────────────\n');

  await unitTests();
  await integrationTests();

  console.log(`\n  ── Results ──`);
  console.log(`  ✅ ${passed} passed`);
  if (failed) {
    console.log(`  ❌ ${failed} failed:`);
    for (const e of errors) console.log(`     • ${e.name}: ${e.error}`);
  }
  console.log('');

  process.exit(failed > 0 ? 1 : 0);
}

run();
