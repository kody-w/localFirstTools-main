#!/usr/bin/env node
/**
 * Runtime Harness — Playwright headless browser runner for RappterZoo games.
 *
 * Loads a single HTML game in Chromium, runs 7 runtime checks, and outputs
 * JSON results to stdout. Designed to be called by runtime_verify.py.
 *
 * Usage:
 *   node scripts/runtime_harness.js <url> [timeout_ms]
 *
 * Output: JSON on stdout with check results for each gate.
 */

const { chromium } = require('playwright');

const url = process.argv[2];
const timeout = parseInt(process.argv[3] || '10000', 10);

if (!url) {
  console.error('Usage: node runtime_harness.js <url> [timeout_ms]');
  process.exit(2);
}

(async () => {
  const result = {
    url,
    checks: {},
    errors: [],
    timestamp: new Date().toISOString(),
  };

  let browser;
  try {
    browser = await chromium.launch({ headless: true });
    const context = await browser.newContext({
      viewport: { width: 800, height: 600 },
    });
    const page = await context.newPage();

    // -----------------------------------------------------------------------
    // Collectors
    // -----------------------------------------------------------------------
    const consoleErrors = [];
    const pageErrors = [];
    const externalRequests = [];
    let rafCount = 0;
    let domContentLoadedTime = null;
    const navigationStart = Date.now();

    // Collect console.error messages
    page.on('console', msg => {
      if (msg.type() === 'error') {
        consoleErrors.push(msg.text());
      }
    });

    // Collect uncaught exceptions
    page.on('pageerror', err => {
      pageErrors.push(err.message || String(err));
    });

    // Intercept network requests — check for external domains
    await page.route('**/*', (route) => {
      const reqUrl = route.request().url();
      try {
        const parsed = new URL(reqUrl);
        const pageHost = new URL(url).hostname;
        if (parsed.hostname !== pageHost && parsed.hostname !== 'localhost' && parsed.hostname !== '127.0.0.1') {
          externalRequests.push(reqUrl);
        }
      } catch (_) {
        // data: URLs, etc. — ignore
      }
      route.continue();
    });

    // Inject rAF counter before page loads
    await page.addInitScript(() => {
      window.__rafCount = 0;
      const _raf = window.requestAnimationFrame;
      window.requestAnimationFrame = function(cb) {
        window.__rafCount++;
        return _raf.call(window, cb);
      };
    });

    // -----------------------------------------------------------------------
    // Check 7: Load Time — Navigate and measure DOMContentLoaded
    // -----------------------------------------------------------------------
    try {
      await page.goto(url, { waitUntil: 'domcontentloaded', timeout });
      domContentLoadedTime = Date.now() - navigationStart;
    } catch (err) {
      result.checks.loadTime = { pass: false, ms: null, error: err.message };
      result.checks.boot = { pass: false, errors: [err.message] };
      // If page doesn't even load, bail early
      result.pass = false;
      console.log(JSON.stringify(result));
      await browser.close();
      return;
    }

    result.checks.loadTime = {
      pass: domContentLoadedTime < 5000,
      ms: domContentLoadedTime,
    };

    // Wait for the game to boot and render (2 seconds)
    await page.waitForTimeout(2000);

    // -----------------------------------------------------------------------
    // Check 1: Boot — did JS execute without fatal errors?
    // -----------------------------------------------------------------------
    // Fatal errors: errors that prevent the game from running at all
    const fatalErrors = pageErrors.filter(e =>
      !e.includes('ResizeObserver') &&
      !e.includes('favicon')
    );
    result.checks.boot = {
      pass: fatalErrors.length === 0,
      errors: fatalErrors.slice(0, 10),
      consoleErrors: consoleErrors.slice(0, 10),
    };

    // -----------------------------------------------------------------------
    // Check 2: Canvas — does the canvas have non-transparent pixels?
    // -----------------------------------------------------------------------
    let canvasPixelCount = 0;
    let hasCanvas = false;
    try {
      canvasPixelCount = await page.evaluate(() => {
        const canvas = document.querySelector('canvas');
        if (!canvas) return -1; // No canvas element
        const ctx = canvas.getContext('2d');
        if (!ctx) return -1;
        const w = Math.min(canvas.width, 800);
        const h = Math.min(canvas.height, 600);
        if (w === 0 || h === 0) return 0;
        const data = ctx.getImageData(0, 0, w, h).data;
        let nonTransparent = 0;
        for (let i = 3; i < data.length; i += 4) {
          if (data[i] > 0) nonTransparent++;
        }
        return nonTransparent;
      });
      hasCanvas = canvasPixelCount !== -1;
    } catch (_) {
      // Canvas evaluation failed (e.g., WebGL context)
      // Try checking for WebGL canvas instead
      try {
        hasCanvas = await page.evaluate(() => !!document.querySelector('canvas'));
        if (hasCanvas) canvasPixelCount = 100; // Assume WebGL renders something
      } catch (_) {
        hasCanvas = false;
      }
    }

    result.checks.canvas = {
      pass: !hasCanvas || canvasPixelCount > 100,
      applicable: hasCanvas,
      pixelCount: canvasPixelCount,
    };

    // -----------------------------------------------------------------------
    // Check 3: Game Loop — is requestAnimationFrame being called?
    // -----------------------------------------------------------------------
    try {
      rafCount = await page.evaluate(() => window.__rafCount || 0);
    } catch (_) {
      rafCount = 0;
    }
    result.checks.gameLoop = {
      pass: rafCount > 5,
      rafCalls: rafCount,
    };

    // -----------------------------------------------------------------------
    // Check 4: No External Requests
    // -----------------------------------------------------------------------
    result.checks.noExternalReqs = {
      pass: externalRequests.length === 0,
      externalUrls: externalRequests.slice(0, 10),
    };

    // -----------------------------------------------------------------------
    // Check 5: Input Response — do pixels change after simulated input?
    // -----------------------------------------------------------------------
    let inputResponseDetected = false;
    if (hasCanvas) {
      try {
        // Take snapshot before input
        const before = await page.evaluate(() => {
          const canvas = document.querySelector('canvas');
          if (!canvas) return null;
          const ctx = canvas.getContext('2d');
          if (!ctx) return null;
          const w = Math.min(canvas.width, 800);
          const h = Math.min(canvas.height, 600);
          if (w === 0 || h === 0) return null;
          const data = ctx.getImageData(0, 0, w, h).data;
          // Sample every 100th pixel for efficiency
          const samples = [];
          for (let i = 0; i < data.length; i += 400) {
            samples.push(data[i], data[i+1], data[i+2], data[i+3]);
          }
          return samples;
        });

        // Send synthetic input events
        await page.keyboard.press('ArrowRight');
        await page.keyboard.press('ArrowRight');
        await page.keyboard.press('Space');
        await page.keyboard.press('Enter');

        // Click on canvas center
        const canvasBox = await page.evaluate(() => {
          const c = document.querySelector('canvas');
          if (!c) return null;
          const r = c.getBoundingClientRect();
          return { x: r.left + r.width / 2, y: r.top + r.height / 2 };
        });
        if (canvasBox) {
          await page.mouse.click(canvasBox.x, canvasBox.y);
        }

        // Wait for response
        await page.waitForTimeout(500);

        // Take snapshot after input
        const after = await page.evaluate(() => {
          const canvas = document.querySelector('canvas');
          if (!canvas) return null;
          const ctx = canvas.getContext('2d');
          if (!ctx) return null;
          const w = Math.min(canvas.width, 800);
          const h = Math.min(canvas.height, 600);
          if (w === 0 || h === 0) return null;
          const data = ctx.getImageData(0, 0, w, h).data;
          const samples = [];
          for (let i = 0; i < data.length; i += 400) {
            samples.push(data[i], data[i+1], data[i+2], data[i+3]);
          }
          return samples;
        });

        // Compare snapshots
        if (before && after && before.length === after.length) {
          let diffCount = 0;
          for (let i = 0; i < before.length; i++) {
            if (before[i] !== after[i]) diffCount++;
          }
          inputResponseDetected = diffCount > 0;
        } else if (before === null && after === null) {
          // No canvas to compare — skip this check
          inputResponseDetected = true; // N/A, assume pass
        }
      } catch (_) {
        // Input test failed — not fatal, might be WebGL
        inputResponseDetected = false;
      }
    } else {
      // Non-canvas app: check if any DOM changed after input
      try {
        const beforeHTML = await page.evaluate(() => document.body.innerHTML.length);
        await page.keyboard.press('Space');
        await page.keyboard.press('Enter');
        await page.waitForTimeout(500);
        const afterHTML = await page.evaluate(() => document.body.innerHTML.length);
        inputResponseDetected = beforeHTML !== afterHTML;
      } catch (_) {
        inputResponseDetected = false;
      }
    }

    result.checks.inputResponse = {
      pass: inputResponseDetected,
      applicable: true,
    };

    // -----------------------------------------------------------------------
    // Check 6: No Errors — combine console errors and page errors
    // -----------------------------------------------------------------------
    // Filter out benign errors
    const significantErrors = [...fatalErrors, ...consoleErrors].filter(e =>
      !e.includes('ResizeObserver') &&
      !e.includes('favicon') &&
      !e.includes('net::ERR_') // Network errors from blocked external requests
    );
    result.checks.noErrors = {
      pass: significantErrors.length === 0,
      errorCount: significantErrors.length,
      errors: significantErrors.slice(0, 10),
    };

    // -----------------------------------------------------------------------
    // Composite pass/fail
    // -----------------------------------------------------------------------
    const criticalChecks = ['boot', 'noErrors', 'loadTime'];
    const allChecks = Object.entries(result.checks);
    const criticalPass = criticalChecks.every(name => {
      const check = result.checks[name];
      return check && check.pass;
    });
    const totalPassing = allChecks.filter(([_, c]) => c.pass).length;

    result.pass = criticalPass && totalPassing >= 5;
    result.passCount = totalPassing;
    result.totalChecks = allChecks.length;

    console.log(JSON.stringify(result));
    await browser.close();

  } catch (err) {
    result.pass = false;
    result.errors.push(err.message || String(err));
    console.log(JSON.stringify(result));
    if (browser) await browser.close();
  }
})();
