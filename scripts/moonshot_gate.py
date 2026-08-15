#!/usr/bin/env python3
"""Fail-closed acceptance gate for the Organism Observatory."""

import argparse
import importlib.util
import hashlib
import html
import json
import math
import os
import re
import shutil
import subprocess
import sys
import tempfile
import threading
import unicodedata
import uuid
import xml.etree.ElementTree as ET
from contextlib import contextmanager
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple


ROOT = Path(__file__).resolve().parent.parent
APP_RELATIVE = Path("apps/3d-immersive/organism-observatory.html")
LEDGER_RELATIVE = Path("apps/organism-frames.jsonl")
PROJECTION_RELATIVE = Path("apps/organism-frames.json")
APP_URL_SUFFIX = "/apps/3d-immersive/organism-observatory.html"
STREAM_ID = "net:rappterzoo"
PARTICLE_SPACE = "rapp/1:particle"
WAVE_SPACE = "rapp/1:wave"
PUBLIC_VISIBILITY = "public-metadata"
MAX_SAFE_INTEGER = (1 << 53) - 1
MAX_CANONICAL_BYTES = 1024 * 1024
PROJECTION_LIMIT = 1000
FRAME_KEYS = {
    "spec",
    "kind",
    "stream_id",
    "seq",
    "utc",
    "payload",
    "payload_hash",
    "frame_hash",
    "prev",
    "prev_wave",
    "sig",
}
FORBIDDEN_PUBLIC_KEYS = {
    "accesstoken",
    "apikey",
    "authtoken",
    "authorization",
    "bearer",
    "biometric",
    "claimcode",
    "clientsecret",
    "cookie",
    "credential",
    "credentials",
    "face_landmarks",
    "facelandmarks",
    "godd",
    "identity_template",
    "identitytemplate",
    "landmarks",
    "media",
    "password",
    "private",
    "privatekey",
    "pulse",
    "pulse_bpm",
    "pulse_bpm_estimate",
    "pulsebpm",
    "pulsebpmestimate",
    "raw_media",
    "rawmedia",
    "refreshtoken",
    "secret",
    "sessiontoken",
    "token",
}
KIND_RE = re.compile(
    r"^[a-z0-9]+(?:-[a-z0-9]+)*\.[a-z0-9]+(?:-[a-z0-9]+)*$"
)
HASH_RE = re.compile(r"^[0-9a-f]{64}$")
UTC_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}Z$")

THEME_SCRIPT = """(() => {
    const param = new URLSearchParams(window.location.search).get("scoutTheme");
    const theme =
      param || (window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light");
    document.documentElement.setAttribute("data-theme", theme);
  })();"""

THEME_VARIABLES = """:root {
  color-scheme: light;
  --cp-bg: #f7f4ef;
  --cp-bg-elevated: #fcfbf8;
  --cp-surface: #ffffff;
  --cp-surface-soft: #f5f5f5;
  --cp-border: #dedede;
  --cp-border-strong: #919191;
  --cp-text: #242424;
  --cp-text-muted: #5c5c5c;
  --cp-text-soft: #6f6f6f;
  --cp-accent: #b11f4b;
  --cp-accent-hover: #9a1a41;
  --cp-accent-soft: rgba(177, 31, 75, 0.08);
  --cp-accent-fg: #ffffff;
  --cp-success: #16a34a;
  --cp-danger: #dc2626;
  --cp-warning: #f59e0b;
  --cp-link: #0078d4;
  --cp-shadow: 0 18px 48px rgba(0, 0, 0, 0.12);
  --cp-overlay: rgba(255, 255, 255, 0.8);
  --cp-panel: rgba(255, 255, 255, 0.86);
  --cp-panel-strong: rgba(255, 255, 255, 0.96);
  --cp-sheen: rgba(255, 255, 255, 0.55);
  --cp-highlight: rgba(177, 31, 75, 0.12);
}
html[data-theme="dark"] {
  color-scheme: dark;
  --cp-bg: #3d3b3a;
  --cp-bg-elevated: #343231;
  --cp-surface: #292929;
  --cp-surface-soft: #2e2e2e;
  --cp-border: #474747;
  --cp-border-strong: #5f5f5f;
  --cp-text: #dedede;
  --cp-text-muted: #919191;
  --cp-text-soft: #b0b0b0;
  --cp-accent: #fd8ea1;
  --cp-accent-hover: #fb7b91;
  --cp-accent-soft: rgba(253, 142, 161, 0.14);
  --cp-accent-fg: #1a1a1a;
  --cp-success: #4ade80;
  --cp-danger: #f87171;
  --cp-warning: #fbbf24;
  --cp-link: #4da6ff;
  --cp-shadow: 0 18px 48px rgba(0, 0, 0, 0.32);
  --cp-overlay: rgba(41, 41, 41, 0.88);
  --cp-panel: rgba(41, 41, 41, 0.72);
  --cp-panel-strong: rgba(41, 41, 41, 0.96);
  --cp-sheen: rgba(255, 255, 255, 0.04);
  --cp-highlight: rgba(253, 142, 161, 0.12);
}"""

COLOR_LITERAL_RE = re.compile(
    r"#[0-9a-fA-F]{3,8}\b|"
    r"\b(?:rgb|rgba|hsl|hsla|lab|lch|oklab|oklch|color)\s*\(",
    re.IGNORECASE,
)
NAMED_COLOR_RE = re.compile(
    r"\b(?:black|white|red|green|blue|yellow|orange|purple|pink|brown|"
    r"gray|grey|cyan|magenta|teal|navy|maroon|lime|aqua|silver|gold)"
    r"(?![\w-])",
    re.IGNORECASE,
)

BROWSER_SCRIPT = r"""
const { chromium } = require("playwright");
const target = process.argv[1];
const readyTimeout = Number(process.argv[2] || 12000);

function textOf(element) {
  return [
    element.getAttribute("aria-label") || "",
    element.getAttribute("title") || "",
    element.getAttribute("name") || "",
    element.id || "",
    element.getAttribute("data-action") || "",
    element.getAttribute("data-control") || "",
    element.getAttribute("data-testid") || "",
    element.textContent || ""
  ].join(" ").replace(/\s+/g, " ").trim();
}

async function findElement(page, selector, expression) {
  const handles = await page.$$(selector);
  for (const handle of handles) {
    const descriptor = await handle.evaluate(textOf);
    if (expression.test(descriptor)) return handle;
  }
  return null;
}

async function stateSnapshot(page) {
  return page.evaluate(() => JSON.stringify({
    text: document.body.innerText,
    states: Array.from(document.querySelectorAll(
      "[aria-pressed],[aria-selected],[data-mode],[data-view],[data-filter]," +
      "[data-state],[data-active]"
    )).map((node) => [
      node.id,
      node.getAttribute("aria-pressed"),
      node.getAttribute("aria-selected"),
      node.getAttribute("data-mode"),
      node.getAttribute("data-view"),
      node.getAttribute("data-filter"),
      node.getAttribute("data-state"),
      node.getAttribute("data-active")
    ]),
    items: document.querySelectorAll(
      "[data-frame],[data-organism],tbody tr,.frame,.frame-row,.organism,.organism-card"
    ).length
  }));
}

async function exerciseChoice(page, kind) {
  const pattern = kind === "mode"
    ? /\b(mode|view|projection|timeline|organisms?|frames?|ledger|table|cards?)\b/i
    : /\b(filter|search|kind|organism|event)\b/i;
  const strict = kind === "mode"
    ? /\b(mode|view|projection)\b/i
    : /\b(filter|search)\b/i;
  const selector = kind === "mode"
    ? "select,button,[role=tab],input[type=radio]"
    : "select,input[type=search],input[type=text]";
  let control = kind === "mode" ? await page.$("#kindMode") : await page.$("#searchInput");
  if (!control) control = await findElement(page, selector, strict);
  if (!control) control = await findElement(page, selector, pattern);
  if (!control) return { pass: false, reason: kind + " control not found" };

  const before = await stateSnapshot(page);
  const tag = await control.evaluate((node) => node.tagName.toLowerCase());
  const type = await control.evaluate((node) => (node.type || "").toLowerCase());
  if (tag === "select") {
    const values = await control.evaluate((node) =>
      Array.from(node.options).filter((option) => !option.disabled).map((option) => option.value)
    );
    const current = await control.inputValue();
    const next = values.find((value) => value !== current);
    if (next === undefined) return { pass: false, reason: kind + " has no alternate option" };
    await control.selectOption(next);
  } else if (tag === "input" && type === "radio") {
    await control.check();
  } else if (tag === "input") {
    await control.fill("zoo.observation");
  } else {
    await control.click();
  }
  await page.waitForTimeout(150);
  const after = await stateSnapshot(page);
  return {
    pass: before !== after,
    reason: before !== after ? "state changed" : kind + " did not change rendered state"
  };
}

async function integrityText(page) {
  return page.evaluate(() => {
    const nodes = Array.from(document.querySelectorAll(
      "[data-integrity-status],[data-integrity],[role=status],[aria-live]"
    ));
    const exact = nodes.find((node) => /^\s*(VALID|DRIFT)\s*$/i.test(node.textContent || ""));
    if (exact) return exact.textContent.trim().toUpperCase();
    const containing = nodes.find((node) => /\b(VALID|DRIFT)\b/i.test(node.textContent || ""));
    return containing ? containing.textContent.trim().toUpperCase() : "";
  });
}

(async () => {
  const result = {
    ready: { pass: false },
  playback: { pass: false },
  modeFilter: { pass: false },
    keyboard: { pass: false },
    tamperRestore: { pass: false },
    export: { pass: false },
    mobile: { pass: false },
    errors: [],
    externalRequests: [],
    dataRequests: []
  };
  let browser;
  try {
    browser = await chromium.launch({ headless: true });
    const context = await browser.newContext({ viewport: { width: 1280, height: 800 } });
    const page = await context.newPage();
    const consoleErrors = [];
    const pageErrors = [];
    const requestFailures = [];
    const badResponses = [];
    const requests = [];

    page.on("console", (message) => {
      if (message.type() === "error") consoleErrors.push(message.text());
    });
    page.on("pageerror", (error) => pageErrors.push(error.message || String(error)));
    page.on("requestfailed", (request) => {
      requestFailures.push(request.url() + ": " + (request.failure()?.errorText || "failed"));
    });
    page.on("response", (response) => {
      if (response.status() >= 400) badResponses.push(response.status() + " " + response.url());
    });
    page.on("request", (request) => requests.push(request.url()));

    await page.goto(target, { waitUntil: "domcontentloaded", timeout: readyTimeout });
    await page.waitForFunction(() => {
      const htmlReady = document.documentElement.dataset.ready === "true";
      const bodyReady = document.body && document.body.dataset.ready === "true";
      const marker = document.querySelector('[data-ready="true"],[data-state="ready"]');
      const health = document.querySelector("#healthText,[data-integrity-status]");
      const verified = health && /\b(?:VALID|\d+\s+frames?\s+verified)\b/i.test(
        health.textContent || ""
      );
      return htmlReady || bodyReady || Boolean(marker) || Boolean(verified);
    }, null, { timeout: readyTimeout });

    const pageOrigin = new URL(target).origin;
    result.externalRequests = requests.filter((value) => {
      if (/^(data|blob|about):/i.test(value)) return false;
      return new URL(value).origin !== pageOrigin;
    });
    result.dataRequests = requests.filter((value) =>
      /\/apps\/organism-frames\.jsonl?(?:$|[?#])/.test(value)
    );
    const loadedLedger = requests.some((value) =>
      /\/apps\/organism-frames\.jsonl(?:$|[?#])/.test(value)
    );
    const loadedProjection = requests.some((value) =>
      /\/apps\/organism-frames\.json(?:$|[?#])/.test(value)
    );
    const initialIntegrity = await integrityText(page);
    result.errors = [...consoleErrors, ...pageErrors, ...requestFailures, ...badResponses];
    result.ready = {
      pass: loadedLedger && loadedProjection && initialIntegrity.includes("VALID") &&
        result.errors.length === 0 && result.externalRequests.length === 0,
      loadedLedger,
      loadedProjection,
      initialIntegrity,
      errorCount: result.errors.length,
      externalCount: result.externalRequests.length
    };

    const playControl = await findElement(
      page,
      "button,[role=button]",
      /\bplay(?:back)?\b/i
    );
    if (playControl) {
      const beforePlayback = await page.evaluate(() => JSON.stringify({
        timeline: document.querySelector("#timeline")?.value || "",
        frame: document.querySelector("#hudFrame")?.textContent || "",
        playhead: document.body.dataset.playhead || ""
      }));
      await playControl.click();
      await page.waitForTimeout(500);
      const afterPlayback = await page.evaluate(() => JSON.stringify({
        timeline: document.querySelector("#timeline")?.value || "",
        frame: document.querySelector("#hudFrame")?.textContent || "",
        playhead: document.body.dataset.playhead || ""
      }));
      result.playback = {
        pass: beforePlayback !== afterPlayback,
        before: beforePlayback,
        after: afterPlayback
      };
      const descriptor = await playControl.evaluate(textOf);
      if (/\bpause\b/i.test(descriptor)) await playControl.click();
    }

    const filter = await exerciseChoice(page, "filter");
    const mode = await exerciseChoice(page, "mode");
    result.modeFilter = {
      pass: mode.pass && filter.pass,
      mode,
      filter
    };

    await page.evaluate(() => {
      if (document.activeElement instanceof HTMLElement) document.activeElement.blur();
      document.body.focus();
    });
    const focused = [];
    for (let index = 0; index < 4; index += 1) {
      await page.keyboard.press("Tab");
      focused.push(await page.evaluate(() => {
        const node = document.activeElement;
        if (!node || node === document.body) return "";
        return [
          node.tagName,
          node.id,
          node.getAttribute("aria-label") || "",
          (node.textContent || "").trim()
        ].join(":");
      }));
    }
    result.keyboard = {
      pass: new Set(focused.filter(Boolean)).size >= 3,
      focused
    };

    const tamper = await findElement(
      page,
      "button,[role=button]",
      /\b(tamper|corrupt|inject drift|break chain)\b/i
    );
    const restore = await findElement(
      page,
      "button,[role=button]",
      /\b(restore|repair|reset ledger|reset data)\b/i
    );
    let drift = "";
    let valid = "";
    if (tamper && restore) {
      try {
        await tamper.click();
        await page.waitForFunction(() => {
          const nodes = Array.from(document.querySelectorAll(
            "[data-integrity-status],[data-integrity],[role=status],[aria-live]"
          ));
          return nodes.some((node) => /\bDRIFT\b/i.test(node.textContent || ""));
        }, null, { timeout: 2500 });
        drift = await integrityText(page);
        await restore.click();
        await page.waitForFunction(() => {
          const nodes = Array.from(document.querySelectorAll(
            "[data-integrity-status],[data-integrity],[role=status],[aria-live]"
          ));
          return nodes.some((node) => /\bVALID\b/i.test(node.textContent || ""));
        }, null, { timeout: 2500 });
        valid = await integrityText(page);
      } catch (_) {
        drift = await integrityText(page);
      }
    }
    result.tamperRestore = {
      pass: Boolean(tamper && restore && drift.includes("DRIFT") && valid.includes("VALID")),
      drift,
      valid
    };

    await page.evaluate(() => {
      window.__moonshotExport = [];
      const originalCreateObjectURL = URL.createObjectURL.bind(URL);
      URL.createObjectURL = (blob) => {
        window.__moonshotExport.push({
          kind: "blob",
          size: blob && typeof blob.size === "number" ? blob.size : 0,
          type: blob && blob.type ? blob.type : ""
        });
        return originalCreateObjectURL(blob);
      };
      HTMLAnchorElement.prototype.click = function() {
        window.__moonshotExport.push({
          kind: "anchor",
          download: this.download || "",
          href: this.href || ""
        });
      };
    });
    const exportButton = await findElement(
      page,
      "button,[role=button],a",
      /\b(export|download)\b/i
    );
    if (exportButton) {
      await exportButton.click();
      await page.waitForTimeout(100);
    }
    const exportEvents = await page.evaluate(() => window.__moonshotExport || []);
    result.export = {
      pass: Boolean(
        exportButton &&
        exportEvents.some((event) => event.kind === "blob" && event.size > 0) &&
        exportEvents.some((event) =>
          event.kind === "anchor" && /\.(json|jsonl|ndjson)$/i.test(event.download || "")
        )
      ),
      events: exportEvents
    };

    await page.setViewportSize({ width: 390, height: 844 });
    await page.waitForTimeout(150);
    const layout = await page.evaluate(() => {
      const root = document.documentElement;
      const overflowing = Array.from(document.querySelectorAll("body *"))
        .filter((node) => {
          const rect = node.getBoundingClientRect();
          return rect.right > root.clientWidth + 1 || rect.left < -1;
        })
        .slice(0, 10)
        .map((node) => ({
          tag: node.tagName,
          id: node.id,
          className: typeof node.className === "string" ? node.className : ""
        }));
      return {
        clientWidth: root.clientWidth,
        scrollWidth: root.scrollWidth,
        overflowing
      };
    });
    result.mobile = {
      pass: layout.scrollWidth <= layout.clientWidth + 1 && layout.overflowing.length === 0,
      layout
    };

    result.pass = [
      result.ready,
      result.playback,
      result.modeFilter,
      result.keyboard,
      result.tamperRestore,
      result.export,
      result.mobile
    ].every((check) => check.pass);
    console.log(JSON.stringify(result));
    await browser.close();
  } catch (error) {
    result.errors.push(error && error.message ? error.message : String(error));
    result.pass = false;
    console.log(JSON.stringify(result));
    if (browser) await browser.close();
  }
})().catch((error) => {
  console.log(JSON.stringify({ pass: false, fatal: error.message || String(error) }));
  process.exitCode = 1;
});
"""

GALLERY_DIGG_BROWSER_SCRIPT = r"""
const { chromium } = require("playwright");
const baseUrl = process.argv[1];
const timeout = Number(process.argv[2] || 15000);

function errorCollectors(page) {
  const errors = [];
  page.on("pageerror", (error) => errors.push(error.message || String(error)));
  page.on("console", (message) => {
    if (message.type() === "error") errors.push(message.text());
  });
  return errors;
}

async function waitForPosts(page) {
  await page.waitForSelector(".post", { state: "visible", timeout });
  return page.locator(".post").count();
}

async function storageDeniedContext(browser, viewport) {
  const context = await browser.newContext({ viewport });
  await context.addInitScript(() => {
    for (const name of ["getItem", "setItem", "removeItem", "clear"]) {
      Object.defineProperty(Storage.prototype, name, {
        configurable: true,
        value() { throw new DOMException("storage denied", "SecurityError"); }
      });
    }
  });
  return context;
}

(async () => {
  const result = {
    galleryBoot: { pass: false },
    galleryCacheOffline: { pass: false },
    galleryStorageDenied: { pass: false },
    galleryVoting: { pass: false },
    galleryMobileTargets: { pass: false },
    galleryBridgeRuntime: { pass: false },
    diggStorageDenied: { pass: false },
    diggCanvasA11y: { pass: false }
  };
  let browser;
  try {
    browser = await chromium.launch({ headless: true });

    const galleryContext = await browser.newContext({
      viewport: { width: 1280, height: 800 }
    });
    const gallery = await galleryContext.newPage();
    const galleryErrors = errorCollectors(gallery);
    await gallery.goto(baseUrl, { waitUntil: "domcontentloaded", timeout });
    const onlineCount = await waitForPosts(gallery);
    const firstTitle = await gallery.locator(".post-title").first().textContent();
    const bootErrors = galleryErrors.slice();
    result.galleryBoot = {
      pass: onlineCount > 0 && bootErrors.length === 0,
      onlineCount,
      errors: bootErrors
    };

    const voteButton = gallery.locator(".vote-btn[data-vote='1']").first();
    const votePost = voteButton.locator("xpath=ancestor::*[contains(@class,'post')][1]");
    const voteCount = votePost.locator(".vote-count");
    const beforeVote = Number(await voteCount.textContent());
    await voteButton.click();
    const afterVote = Number(await votePost.locator(".vote-count").textContent());
    const voted = await votePost.locator(".vote-btn[data-vote='1']").getAttribute("class");
    await votePost.locator(".vote-btn[data-vote='1']").click();
    const afterToggle = Number(await votePost.locator(".vote-count").textContent());
    const toggledClass = await votePost.locator(".vote-btn[data-vote='1']").getAttribute("class");
    result.galleryVoting = {
      pass: afterVote === beforeVote + 1 &&
        /\bvoted\b/.test(voted || "") &&
        afterToggle === beforeVote &&
        !/\bvoted\b/.test(toggledClass || ""),
      beforeVote,
      afterVote,
      afterToggle,
      voted,
      toggledClass
    };

    await gallery.locator(".post-footer button[data-action='detail']").first().click();
    await gallery.waitForSelector("#tl-viewport", { state: "attached", timeout });
    const frameHandle = await gallery.$("#tl-viewport");
    const frame = frameHandle ? await frameHandle.contentFrame() : null;
    let bridged = false;
    let frameUrl = "";
    if (frame) {
      await frame.waitForLoadState("domcontentloaded", { timeout });
      await gallery.waitForTimeout(250);
      bridged = await frame.evaluate(() => window.__rz_bridged === true);
      frameUrl = frame.url();
    }
    result.galleryBridgeRuntime = {
      pass: Boolean(frame && bridged && !/^about:blank/.test(frameUrl)),
      bridged,
      frameUrl
    };
    await gallery.locator("#modal-close").click();

    await gallery.route("**/apps/manifest.json", (route) => route.abort());
    await gallery.route("**/apps/archive/manifest.json", (route) => route.abort());
    await gallery.route("**/apps/community.json", (route) => route.abort());
    await gallery.reload({ waitUntil: "domcontentloaded", timeout });
    const offlineCount = await waitForPosts(gallery);
    const offlineTitle = await gallery.locator(".post-title").first().textContent();
    result.galleryCacheOffline = {
      pass: offlineCount === onlineCount &&
        offlineCount > 0 &&
        offlineTitle === firstTitle,
      onlineCount,
      offlineCount,
      firstTitle,
      offlineTitle
    };
    await galleryContext.close();

    const deniedGalleryContext = await storageDeniedContext(
      browser,
      { width: 1280, height: 800 }
    );
    const deniedGallery = await deniedGalleryContext.newPage();
    const deniedGalleryErrors = errorCollectors(deniedGallery);
    await deniedGallery.goto(baseUrl, {
      waitUntil: "domcontentloaded",
      timeout
    });
    const deniedGalleryCount = await waitForPosts(deniedGallery);
    result.galleryStorageDenied = {
      pass: deniedGalleryCount > 0 && deniedGalleryErrors.length === 0,
      postCount: deniedGalleryCount,
      errors: deniedGalleryErrors
    };
    await deniedGalleryContext.close();

    const mobileContext = await browser.newContext({
      viewport: { width: 390, height: 844 }
    });
    const mobile = await mobileContext.newPage();
    await mobile.goto(baseUrl, { waitUntil: "domcontentloaded", timeout });
    await waitForPosts(mobile);
    const mobileTargets = await mobile.evaluate(() => {
      const selector = [
        ".sidebar-toggle",
        ".player-chip",
        ".sort-tab",
        ".vote-btn",
        ".post-footer button",
        ".post-footer a",
        ".sub-link"
      ].join(",");
      return Array.from(document.querySelectorAll(selector)).map((node) => {
        const rect = node.getBoundingClientRect();
        const style = getComputedStyle(node);
        const intersects = rect.right > 0 && rect.bottom > 0 &&
          rect.left < innerWidth && rect.top < innerHeight;
        const visible = style.display !== "none" &&
          style.visibility !== "hidden" &&
          Number(style.opacity || 1) > 0 &&
          intersects;
        return {
          descriptor: [
            node.tagName,
            node.className,
            node.getAttribute("aria-label") || "",
            (node.textContent || "").trim()
          ].join(":").slice(0, 180),
          visible,
          width: rect.width,
          height: rect.height
        };
      }).filter((item) => item.visible);
    });
    const undersized = mobileTargets.filter(
      (item) => item.width < 44 || item.height < 44
    );
    result.galleryMobileTargets = {
      pass: mobileTargets.length >= 5 && undersized.length === 0,
      targetCount: mobileTargets.length,
      undersized: undersized.slice(0, 20)
    };
    await mobileContext.close();

    const diggContext = await storageDeniedContext(
      browser,
      { width: 900, height: 800 }
    );
    const digg = await diggContext.newPage();
    const diggErrors = errorCollectors(digg);
    await digg.goto(baseUrl + "apps/data-tools/digg.html", {
      waitUntil: "domcontentloaded",
      timeout
    });
    await digg.waitForSelector(".card", { state: "visible", timeout });
    const diggCards = await digg.locator(".card").count();
    result.diggStorageDenied = {
      pass: diggCards > 0 && diggErrors.length === 0,
      cardCount: diggCards,
      errors: diggErrors
    };

    const canvas = digg.locator("#chain-canvas");
    const initial = {
      role: await canvas.getAttribute("role"),
      label: await canvas.getAttribute("aria-label"),
      pressed: await canvas.getAttribute("aria-pressed"),
      tabIndex: await canvas.getAttribute("tabindex")
    };
    await canvas.focus();
    await digg.keyboard.press("Space");
    await digg.waitForTimeout(50);
    const paused = {
      label: await canvas.getAttribute("aria-label"),
      pressed: await canvas.getAttribute("aria-pressed")
    };
    await digg.keyboard.press("Space");
    await digg.waitForTimeout(50);
    const resumed = {
      label: await canvas.getAttribute("aria-label"),
      pressed: await canvas.getAttribute("aria-pressed")
    };
    result.diggCanvasA11y = {
      pass: initial.role === "button" &&
        initial.tabIndex === "0" &&
        /\bchain\b/i.test(initial.label || "") &&
        /\bplaying\b/i.test(initial.label || "") &&
        initial.pressed === "false" &&
        paused.pressed === "true" &&
        /\bpaused\b/i.test(paused.label || "") &&
        resumed.pressed === "false" &&
        /\bplaying\b/i.test(resumed.label || ""),
      initial,
      paused,
      resumed
    };
    await diggContext.close();

    result.pass = Object.values(result).every(
      (value) => value && value.pass === true
    );
    console.log(JSON.stringify(result));
    await browser.close();
  } catch (error) {
    result.fatal = error && error.message ? error.message : String(error);
    result.pass = false;
    console.log(JSON.stringify(result));
    if (browser) await browser.close();
  }
})().catch((error) => {
  console.log(JSON.stringify({ pass: false, fatal: error.message || String(error) }));
  process.exitCode = 1;
});
"""


@dataclass
class CheckResult:
    name: str
    passed: bool
    detail: str


class GateError(ValueError):
    """A deterministic gate failure."""


class QuietHandler(SimpleHTTPRequestHandler):
    def log_message(self, format_string: str, *args: Any) -> None:
        return


def _compact(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


def _result(name: str, passed: bool, detail: str) -> CheckResult:
    return CheckResult(name=name, passed=bool(passed), detail=detail)


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _script_blocks(source: str) -> List[Tuple[str, str]]:
    return [
        (match.group(1), match.group(2))
        for match in re.finditer(
            r"<script\b([^>]*)>(.*?)</script\s*>",
            source,
            re.IGNORECASE | re.DOTALL,
        )
    ]


def _style_text(source: str) -> str:
    return "\n".join(
        match.group(1)
        for match in re.finditer(
            r"<style\b[^>]*>(.*?)</style\s*>",
            source,
            re.IGNORECASE | re.DOTALL,
        )
    )


def check_app_measurable(app_path: Path) -> CheckResult:
    try:
        source = app_path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as error:
        return _result("app.measurable", False, str(error))
    passed = bool(source.strip()) and "<html" in source.lower()
    return _result(
        "app.measurable",
        passed,
        "{} UTF-8 bytes".format(len(source.encode("utf-8"))) if passed else "empty or not HTML",
    )


def check_theme_script(source: str) -> CheckResult:
    scripts = _script_blocks(source)
    if not scripts:
        return _result("theme.script", False, "no script blocks")
    attributes, body = scripts[0]
    passed = not attributes.strip() and _compact(body) == _compact(THEME_SCRIPT)
    return _result(
        "theme.script",
        passed,
        "exact Clawpilot detector is the first script"
        if passed
        else "first script is not the exact Clawpilot detector",
    )


def check_theme_variables(source: str) -> CheckResult:
    styles = _compact(_style_text(source))
    expected = _compact(THEME_VARIABLES)
    count = styles.count(expected)
    remainder = styles.replace(expected, "", 1) if count else styles
    redeclarations = re.findall(r"--cp-[a-z0-9-]+\s*:", remainder, re.IGNORECASE)
    passed = count == 1 and not redeclarations
    return _result(
        "theme.variables",
        passed,
        "exact light and dark declarations appear once"
        if passed
        else "theme block count={} extra declarations={}".format(
            count,
            len(redeclarations),
        ),
    )


def check_component_colors(source: str) -> CheckResult:
    styles = _compact(_style_text(source))
    expected = _compact(THEME_VARIABLES)
    component_styles = styles.replace(expected, "", 1)
    inline_styles = " ".join(
        match.group(2)
        for match in re.finditer(
            r"\bstyle\s*=\s*(['\"])(.*?)\1",
            source,
            re.IGNORECASE | re.DOTALL,
        )
    )
    scripts = "\n".join(body for _, body in _script_blocks(source)[1:])
    candidates = component_styles + "\n" + inline_styles + "\n" + scripts
    literals = sorted(set(COLOR_LITERAL_RE.findall(candidates)))
    named = sorted(
        set(NAMED_COLOR_RE.findall(component_styles + "\n" + inline_styles))
    )
    script_named = re.findall(
        r"\.style\.(?:color|background|backgroundColor|borderColor|fill|stroke)"
        r"\s*=\s*['\"]([^'\"]+)['\"]",
        scripts,
        re.IGNORECASE,
    )
    named.extend(
        value
        for value in script_named
        if NAMED_COLOR_RE.search(value) or COLOR_LITERAL_RE.search(value)
    )
    passed = not literals and not named
    return _result(
        "styles.token-colors",
        passed,
        "component colors use Clawpilot variables"
        if passed
        else "hardcoded color literal(s): {}".format(
            ", ".join((literals + named)[:6])
        ),
    )


def check_dangerous_javascript(source: str) -> CheckResult:
    patterns = {
        "eval": r"\beval\s*\(",
        "new Function": r"\bnew\s+Function\s*\(",
        "document.write": r"\bdocument\s*\.\s*write(?:ln)?\s*\(",
    }
    found = [
        label
        for label, pattern in patterns.items()
        if re.search(pattern, source, re.IGNORECASE)
    ]
    return _result(
        "security.no-dynamic-code",
        not found,
        "no dynamic code sinks" if not found else "found " + ", ".join(found),
    )


def _csp_directives(source: str) -> Dict[str, List[str]]:
    match = re.search(
        r"<meta\b(?=[^>]*http-equiv\s*=\s*(['\"])Content-Security-Policy\1)"
        r"[^>]*content\s*=\s*(['\"])(.*?)\2[^>]*>",
        source,
        re.IGNORECASE | re.DOTALL,
    )
    if not match:
        match = re.search(
            r"<meta\b(?=[^>]*content\s*=\s*(['\"])(.*?)\1)"
            r"[^>]*http-equiv\s*=\s*(['\"])Content-Security-Policy\3[^>]*>",
            source,
            re.IGNORECASE | re.DOTALL,
        )
        if not match:
            return {}
        content = match.group(2)
    else:
        content = match.group(3)
    directives = {}
    for raw_directive in html.unescape(content).split(";"):
        parts = raw_directive.strip().split()
        if parts:
            directives[parts[0].lower()] = [part.lower() for part in parts[1:]]
    return directives


def check_csp(source: str) -> CheckResult:
    directives = _csp_directives(source)
    requirements = {
        "script-src": {"'self'", "'unsafe-inline'"},
        "style-src": {"'self'", "'unsafe-inline'"},
        "connect-src": {"'self'"},
        "object-src": {"'none'"},
        "base-uri": {"'none'"},
    }
    missing = []
    default_values = set(directives.get("default-src", []))
    if not default_values.intersection({"'self'", "'none'"}):
        missing.append("default-src")
    for directive, values in requirements.items():
        actual = set(directives.get(directive, []))
        if not values.issubset(actual):
            missing.append(directive)
    unsafe = any(
        "*" in values or "'unsafe-eval'" in values
        for values in directives.values()
    )
    connect_values = set(directives.get("connect-src", []))
    connect_closed = connect_values.issubset({"'self'"})
    passed = bool(directives) and not missing and not unsafe and connect_closed
    return _result(
        "security.csp",
        passed,
        "restrictive inline-compatible CSP present"
        if passed
        else "missing={} unsafe={} connect={}".format(
            ",".join(missing) or "none",
            unsafe,
            sorted(connect_values),
        ),
    )


def check_same_origin_data_urls(source: str) -> CheckResult:
    required = {
        "../organism-frames.jsonl",
        "../organism-frames.json",
    }
    string_calls = re.findall(
        r"\b(?:fetch|EventSource|WebSocket)\s*\(\s*(['\"`])([^'\"`]+)\1",
        source,
        re.IGNORECASE,
    )
    urls = [value.strip() for _, value in string_calls]
    present = {
        expected
        for expected in required
        if (
            any(value.split("?", 1)[0] == expected for value in urls)
            or re.search(
                r"['\"`]" + re.escape(expected) + r"['\"`]",
                source,
            )
        )
    }
    external = [
        value
        for value in urls
        if re.match(r"^(?:https?:)?//|^wss?:", value, re.IGNORECASE)
    ]
    passed = present == required and not external
    return _result(
        "data.same-origin-urls",
        passed,
        "both canonical data files use relative same-origin fetches"
        if passed
        else "present={} external={}".format(sorted(present), external),
    )


def _manifest_categories(manifest: Any) -> Dict[str, Any]:
    if not isinstance(manifest, dict):
        return {}
    categories = manifest.get("categories")
    return categories if isinstance(categories, dict) else manifest


def check_manifest_registration(root: Path) -> CheckResult:
    try:
        manifest = _load_json(root / "apps/manifest.json")
        category = _manifest_categories(manifest)["3d_immersive"]
        apps = category["apps"]
        matches = [
            item
            for item in apps
            if isinstance(item, dict)
            and item.get("file") == "organism-observatory.html"
        ]
        passed = (
            category.get("folder") == "3d-immersive"
            and category.get("count") == len(apps)
            and len(matches) == 1
            and "organism" in str(matches[0].get("title", "")).lower()
            and matches[0].get("description")
            and matches[0].get("tags")
        )
        detail = "one complete entry and exact category count" if passed else (
            "matches={} declared={} actual={}".format(
                len(matches),
                category.get("count"),
                len(apps),
            )
        )
    except (OSError, ValueError, KeyError, TypeError) as error:
        passed = False
        detail = str(error)
    return _result("registration.manifest", passed, detail)


def _feed_json_has_app(feed: Any) -> bool:
    if not isinstance(feed, dict):
        return False
    for entry in feed.get("dataFeedElement", []):
        if not isinstance(entry, dict):
            continue
        item = entry.get("item", {})
        if (
            isinstance(item, dict)
            and str(item.get("url", "")).endswith(APP_URL_SUFFIX)
            and "organism" in str(item.get("name", "")).lower()
        ):
            return True
    return False


def check_feed_registration(root: Path) -> CheckResult:
    problems = []
    try:
        if not _feed_json_has_app(_load_json(root / "apps/feed.json")):
            problems.append("feed.json")
    except (OSError, ValueError) as error:
        problems.append("feed.json: {}".format(error))
    try:
        tree = ET.parse(str(root / "apps/feed.xml"))
        values = [
            (node.text or "").strip()
            for node in tree.iter()
            if node.tag.rsplit("}", 1)[-1] in {"link", "guid"}
        ]
        if not any(value.endswith(APP_URL_SUFFIX) for value in values):
            problems.append("feed.xml")
    except (OSError, ValueError, ET.ParseError) as error:
        problems.append("feed.xml: {}".format(error))
    return _result(
        "registration.feeds",
        not problems,
        "JSON-LD and RSS entries present" if not problems else "; ".join(problems),
    )


def check_discovery_registration(root: Path) -> CheckResult:
    required_toc = {
        "/apps/feed.json",
        "/apps/manifest.json",
        "/apps/organism-frames.json",
        "/apps/organism-frames.jsonl",
    }
    try:
        general = _load_json(root / ".well-known/feeddata-general")
        toc = _load_json(root / ".well-known/feeddata-toc")
        general_urls = {
            str(general.get("url", "")),
            str(general.get("contentUrl", "")),
        }
        def collect_urls(value: Any) -> List[str]:
            if isinstance(value, dict):
                result = []
                for key, item in value.items():
                    if key == "url" and isinstance(item, str):
                        result.append(item)
                    else:
                        result.extend(collect_urls(item))
                return result
            if isinstance(value, list):
                result = []
                for item in value:
                    result.extend(collect_urls(item))
                return result
            return []

        toc_urls = set(collect_urls(toc))
        general_ok = any(value.endswith("/apps/feed.json") for value in general_urls)
        app_ok = any(value.endswith(APP_URL_SUFFIX) for value in toc_urls)
        missing = [
            suffix
            for suffix in required_toc
            if not any(value.endswith(suffix) for value in toc_urls)
        ]
        passed = general_ok and app_ok and not missing
        detail = "feed and organism sources are discoverable" if passed else (
            "general_ok={} app_ok={} missing={}".format(
                general_ok,
                app_ok,
                missing,
            )
        )
    except (OSError, ValueError, TypeError) as error:
        passed = False
        detail = str(error)
    return _result("registration.discovery", passed, detail)


def _normalize_json(value: Any, depth: int = 1) -> Any:
    if depth > 64:
        raise GateError("JSON nesting exceeds 64 levels")
    if value is None or type(value) is bool:
        return value
    if type(value) is int:
        if not -MAX_SAFE_INTEGER <= value <= MAX_SAFE_INTEGER:
            raise GateError("integer exceeds the safe range")
        return value
    if type(value) is float:
        raise GateError("binary64 number is outside the restricted profile")
    if type(value) is str:
        if unicodedata.normalize("NFC", value) != value:
            raise GateError("string is not NFC")
        if any(0xD800 <= ord(character) <= 0xDFFF for character in value):
            raise GateError("lone surrogate")
        return value
    if isinstance(value, (list, tuple)):
        return [_normalize_json(item, depth + 1) for item in value]
    if type(value) is dict:
        result = {}
        for key, item in value.items():
            if type(key) is not str:
                raise GateError("non-string object key")
            try:
                key.encode("ascii")
            except UnicodeEncodeError as error:
                raise GateError("non-ASCII object key") from error
            if unicodedata.normalize("NFC", key) != key:
                raise GateError("object key is not NFC")
            result[key] = _normalize_json(item, depth + 1)
        return result
    raise GateError("unsupported JSON value")


def canonical_bytes(value: Any) -> bytes:
    encoded = json.dumps(
        _normalize_json(value),
        ensure_ascii=False,
        allow_nan=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    if len(encoded) > MAX_CANONICAL_BYTES:
        raise GateError("canonical value exceeds one MiB")
    return encoded


def hash_value(space: str, value: Any) -> str:
    if space not in {PARTICLE_SPACE, WAVE_SPACE}:
        raise GateError("unsupported hash domain")
    return hashlib.sha256(
        space.encode("ascii") + b"\n" + canonical_bytes(value)
    ).hexdigest()


def _forbidden_key(value: Any) -> Optional[str]:
    if type(value) is dict:
        for key, item in value.items():
            token = "".join(
                character.lower()
                for character in key
                if character.isalnum()
            )
            if token in FORBIDDEN_PUBLIC_KEYS:
                return key
            nested = _forbidden_key(item)
            if nested:
                return nested
    elif isinstance(value, list):
        for item in value:
            nested = _forbidden_key(item)
            if nested:
                return nested
    return None


def verify_frames(frames: Sequence[Dict[str, Any]]) -> Dict[str, Any]:
    previous = None
    previous_molter_frame = None
    event_ids = set()
    for index, frame in enumerate(frames):
        if type(frame) is not dict or set(frame) != FRAME_KEYS:
            raise GateError("frame {} does not have exactly eleven keys".format(index))
        if frame["spec"] != "rapp/1":
            raise GateError("frame {} spec".format(index))
        if frame["stream_id"] != STREAM_ID:
            raise GateError("frame {} stream".format(index))
        if not isinstance(frame["kind"], str) or not KIND_RE.fullmatch(frame["kind"]):
            raise GateError("frame {} kind".format(index))
        if frame["seq"] != index:
            raise GateError("frame {} sequence".format(index))
        if not isinstance(frame["utc"], str) or not UTC_RE.fullmatch(frame["utc"]):
            raise GateError("frame {} UTC".format(index))
        try:
            moment = datetime.fromisoformat(
                frame["utc"].replace("Z", "+00:00")
            ).astimezone(timezone.utc)
            normalized_utc = (
                moment.strftime("%Y-%m-%dT%H:%M:%S.%f")[:23] + "Z"
            )
        except ValueError as error:
            raise GateError("frame {} UTC".format(index)) from error
        if normalized_utc != frame["utc"]:
            raise GateError("frame {} UTC normalization".format(index))
        if type(frame["payload"]) is not dict:
            raise GateError("frame {} payload".format(index))
        payload = frame["payload"]
        if payload.get("schema") != "rappterzoo-organism-frame/1":
            raise GateError("frame {} payload schema".format(index))
        if payload.get("visibility") != PUBLIC_VISIBILITY:
            raise GateError("frame {} visibility".format(index))
        forbidden = _forbidden_key(payload)
        if forbidden:
            raise GateError("frame {} forbidden key {}".format(index, forbidden))
        event_id = payload.get("event_id")
        if not isinstance(event_id, str) or not event_id:
            raise GateError("frame {} event_id".format(index))
        for required in ("event", "organism"):
            if not isinstance(payload.get(required), str) or not payload[required]:
                raise GateError(
                    "frame {} payload {}".format(index, required)
                )
        for optional in (
            "display_name",
            "kennel",
            "neighborhood",
            "organism_type",
        ):
            if optional in payload and not isinstance(payload[optional], str):
                raise GateError(
                    "frame {} payload {}".format(index, optional)
                )
        if event_id in event_ids:
            raise GateError("duplicate event_id {}".format(event_id))
        event_ids.add(event_id)
        if not isinstance(frame["payload_hash"], str) or not HASH_RE.fullmatch(
            frame["payload_hash"]
        ):
            raise GateError("frame {} payload hash shape".format(index))
        if not isinstance(frame["frame_hash"], str) or not HASH_RE.fullmatch(
            frame["frame_hash"]
        ):
            raise GateError("frame {} frame hash shape".format(index))
        if frame["payload_hash"] != hash_value(PARTICLE_SPACE, payload):
            raise GateError("frame {} payload hash mismatch".format(index))
        wave_preimage = {
            key: value
            for key, value in frame.items()
            if key not in {"frame_hash", "sig"}
        }
        if frame["frame_hash"] != hash_value(WAVE_SPACE, wave_preimage):
            raise GateError("frame {} frame hash mismatch".format(index))
        if frame["sig"] is not None:
            raise GateError("frame {} asserts a public signature".format(index))
        if previous is None:
            if frame["prev"] is not None or frame["prev_wave"] is not None:
                raise GateError("genesis links")
        else:
            if frame["utc"] < previous["utc"]:
                raise GateError("timestamps not monotonic")
            if frame["prev"] != previous["payload_hash"]:
                raise GateError("payload chain")
            if frame["prev_wave"] != previous["frame_hash"]:
                raise GateError("wave chain")
        if payload.get("event") == "autonomous-frame":
            molter_frame = payload.get("molter_frame")
            if (
                type(molter_frame) is not int
                or molter_frame < 0
                or molter_frame > MAX_SAFE_INTEGER
                or event_id != "molter-frame:{}".format(molter_frame)
            ):
                raise GateError("autonomous frame ordering metadata")
            if (
                previous_molter_frame is not None
                and molter_frame <= previous_molter_frame
            ):
                raise GateError("autonomous molter ordering")
            previous_molter_frame = molter_frame
        previous = frame
    return {
        "valid": True,
        "frame_count": len(frames),
        "head": (
            {
                "seq": frames[-1]["seq"],
                "payload_hash": frames[-1]["payload_hash"],
                "frame_hash": frames[-1]["frame_hash"],
            }
            if frames
            else None
        ),
    }


def read_ledger(path: Path) -> List[Dict[str, Any]]:
    if not path.is_file():
        raise GateError("ledger missing")
    frames = []
    with path.open("rb") as handle:
        for line_number, raw in enumerate(handle, 1):
            if not raw.endswith(b"\n"):
                raise GateError("line {} lacks newline".format(line_number))
            line = raw[:-1]
            if not line:
                raise GateError("blank line {}".format(line_number))
            try:
                frame = json.loads(line.decode("utf-8"))
            except (UnicodeDecodeError, ValueError) as error:
                raise GateError("invalid line {}".format(line_number)) from error
            if canonical_bytes(frame) != line:
                raise GateError("non-canonical line {}".format(line_number))
            frames.append(frame)
    if not frames:
        raise GateError("ledger is empty")
    verify_frames(frames)
    return frames


def organism_summary(frames: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
    organisms = {}
    for frame in frames:
        payload = frame["payload"]
        organism_id = payload.get("organism", "rappterzoo")
        summary = organisms.setdefault(
            organism_id,
            {
                "id": organism_id,
                "display_name": payload.get("display_name", organism_id),
                "organism_type": payload.get("organism_type", "ecosystem"),
                "neighborhood": payload.get("neighborhood", "rappterzoo"),
                "kennel": payload.get("kennel"),
                "first_seq": frame["seq"],
                "last_seq": frame["seq"],
                "frame_count": 0,
                "last_seen": frame["utc"],
                "kinds": [],
                "kind_counts": {},
                "event_counts": {},
                "layout_seed": hashlib.sha256(
                    (
                        "rappterzoo/observatory-organism/1\n"
                        + organism_id
                    ).encode("utf-8")
                ).hexdigest(),
            },
        )
        summary["display_name"] = payload.get("display_name", summary["display_name"])
        summary["organism_type"] = payload.get(
            "organism_type",
            summary["organism_type"],
        )
        summary["neighborhood"] = payload.get(
            "neighborhood",
            summary["neighborhood"],
        )
        summary["kennel"] = payload.get("kennel", summary["kennel"])
        summary["last_seq"] = frame["seq"]
        summary["last_seen"] = frame["utc"]
        summary["frame_count"] += 1
        kind_counts = summary["kind_counts"]
        kind_counts[frame["kind"]] = kind_counts.get(frame["kind"], 0) + 1
        event = payload["event"]
        event_counts = summary["event_counts"]
        event_counts[event] = event_counts.get(event, 0) + 1
        if frame["kind"] not in summary["kinds"]:
            summary["kinds"].append(frame["kind"])
    for summary in organisms.values():
        summary["kinds"].sort()
        summary["kind_counts"] = dict(sorted(summary["kind_counts"].items()))
        summary["event_counts"] = dict(sorted(summary["event_counts"].items()))
    return sorted(
        organisms.values(),
        key=lambda item: (-item["frame_count"], item["id"]),
    )


def _segment_digest(frames: Sequence[Dict[str, Any]]) -> str:
    digest = hashlib.sha256()
    digest.update(b"rappterzoo/projection-segment/1\n")
    for frame in frames:
        digest.update(frame["frame_hash"].encode("ascii"))
        digest.update(b"\n")
    return digest.hexdigest()


def _segment_metadata(frames: Sequence[Dict[str, Any]]) -> Dict[str, Any]:
    if not frames:
        return {
            "first_seq": None,
            "last_seq": None,
            "first_prev": None,
            "first_prev_wave": None,
            "head_payload_hash": None,
            "head_frame_hash": None,
            "hash_domain": "rappterzoo/projection-segment/1",
            "segment_hash": _segment_digest([]),
        }
    first = frames[0]
    last = frames[-1]
    return {
        "first_seq": first["seq"],
        "last_seq": last["seq"],
        "first_prev": first["prev"],
        "first_prev_wave": first["prev_wave"],
        "head_payload_hash": last["payload_hash"],
        "head_frame_hash": last["frame_hash"],
        "hash_domain": "rappterzoo/projection-segment/1",
        "segment_hash": _segment_digest(frames),
    }


def _observatory_metadata(
    frames: Sequence[Dict[str, Any]],
    organisms: Sequence[Dict[str, Any]],
) -> Dict[str, Any]:
    return {
        "schema": "rappterzoo-organism-observatory/1",
        "layout_inputs": {
            "frame_order": "seq-ascending",
            "frame_seed": "frame_hash",
            "organism_seed": "organisms[].layout_seed",
            "time_axis": "utc",
        },
        "stream_seed": hashlib.sha256(
            (
                "rappterzoo/observatory-stream/1\n"
                + STREAM_ID
            ).encode("ascii")
        ).hexdigest(),
        "timeline": {
            "first_seq": frames[0]["seq"] if frames else None,
            "last_seq": frames[-1]["seq"] if frames else None,
            "first_utc": frames[0]["utc"] if frames else None,
            "last_utc": frames[-1]["utc"] if frames else None,
        },
        "organism_count": len(organisms),
    }


def _subscriber_chain_claims() -> Dict[str, str]:
    return {
        "chain_model": (
            "git-backed-content-addressed-append-only-transparency-chain"
        ),
        "blockchain_style": "hash-chain-analogy-only",
        "single_subscriber": "one-independent-local-replica",
        "multiple_subscribers": (
            "independent-custody-and-verification-if-separately-controlled"
        ),
        "publisher_authority": "centralized",
        "witness_quorum": "not-established",
        "consensus": "none",
        "mining": "none",
        "token": "none",
    }


def expected_projection(frames: Sequence[Dict[str, Any]]) -> Dict[str, Any]:
    integrity = verify_frames(frames)
    visible_frames = list(frames[-PROJECTION_LIMIT:])
    segment = _segment_metadata(visible_frames)
    organisms = organism_summary(frames)
    start_seq = segment["first_seq"]
    return {
        "schema": "rappterzoo-organism-feed/1",
        "generated_at": frames[-1]["utc"] if frames else None,
        "stream_id": STREAM_ID,
        "append_only_source": "organism-frames.jsonl",
        "digg_view": "data-tools/digg.html",
        "frame_control": {
            "mode": "assigned",
            "model": "bitcoin-inspired-append-only-block-sequencing",
            "description": "not-Bitcoin-and-not-decentralized-consensus",
            "authority": "centralized-main-assembler",
            "assigned_folding": "enabled-with-bounded-assembler-leases",
            "live_election": "disabled",
            "synthetic_proofs": "tests-only",
            "future_activation": (
                "explicit-owner-gate-after-measured-public-soak"
            ),
            "activation_evidence": [
                "bounded-cost",
                "fork-free-lineage",
                "public-soak-stability",
                "replay-tamper-resistance",
                "subscriber-witness-evidence",
            ],
            "consensus": "none",
            "mining": "none",
            "currency": "none",
            "compute_incentive": "none",
            "permanent_authority": "none",
        },
        "transparency_chain": dict(
            _subscriber_chain_claims(),
            replication="subscriber-local-prefix-replica-and-checkpoint",
            fork_policy=(
                "previously-witnessed-non-ancestor-is-explicit-drift"
            ),
            witness_receipts=(
                "content-addressed-structural-observations"
            ),
        ),
        "privacy": {
            "projection": PUBLIC_VISIBILITY,
            "private_godd_media": "excluded",
            "raw_frames": "excluded",
            "biometric_values": "excluded",
        },
        "rapp1": {
            "wire_shape": "exact-eleven-key-frame",
            "hash_domains": [PARTICLE_SPACE, WAVE_SPACE],
            "canonicalization": {
                "profile": "restricted-rapp1-json-v1",
                "compatible_subset_of": "RFC 8785",
                "object_keys": "ASCII",
                "strings": "NFC",
                "numbers": "I-JSON-safe-integers-only",
                "binary64": "forbidden",
            },
            "acceptance": "structural-unverified",
            "reason": (
                "No authenticated RAPP/1 Section 13 registry or swarm "
                "signature is asserted by this public projection."
            ),
        },
        "integrity": dict(
            integrity,
            scope="full-ledger",
            projected_segment=dict(valid=True, **segment),
        ),
        "pagination": {
            "mode": "bounded-tail",
            "order": "seq-ascending",
            "limit": PROJECTION_LIMIT,
            "start_seq": start_seq,
            "end_seq": segment["last_seq"],
            "has_older": start_seq is not None and start_seq > 0,
            "older_before_seq": (
                start_seq
                if start_seq is not None and start_seq > 0
                else None
            ),
            "has_newer": False,
        },
        "segment": segment,
        "organisms": organisms,
        "observatory": _observatory_metadata(frames, organisms),
        "frames": visible_frames,
        "projection_frame_count": len(visible_frames),
        "total_frame_count": len(frames),
    }


def check_ledger(root: Path) -> Tuple[CheckResult, Optional[List[Dict[str, Any]]]]:
    try:
        frames = read_ledger(root / LEDGER_RELATIVE)
        return (
            _result(
                "ledger.exact-chain",
                True,
                "{} canonical linked frames".format(len(frames)),
            ),
            frames,
        )
    except (OSError, ValueError, GateError) as error:
        return _result("ledger.exact-chain", False, str(error)), None


def check_projection(
    root: Path,
    frames: Optional[Sequence[Dict[str, Any]]],
) -> CheckResult:
    if frames is None:
        return _result("projection.exact", False, "ledger is not measurable")
    try:
        path = root / PROJECTION_RELATIVE
        raw = path.read_bytes()
        actual = json.loads(raw.decode("utf-8"))
        expected = expected_projection(frames)
        deterministic = (
            json.dumps(
                actual,
                ensure_ascii=False,
                indent=2,
                sort_keys=True,
            )
            + "\n"
        ).encode("utf-8")
        passed = actual == expected and raw == deterministic
        detail = "projection is an exact ledger derivation" if passed else (
            "projection differs from exact derivation or deterministic bytes"
        )
    except (OSError, ValueError, GateError) as error:
        passed = False
        detail = str(error)
    return _result("projection.exact", passed, detail)


def check_public_privacy(
    source: str,
    frames: Optional[Sequence[Dict[str, Any]]],
    root: Path,
) -> CheckResult:
    if frames is None:
        return _result("privacy.public-only", False, "ledger is not measurable")
    try:
        projection = _load_json(root / PROJECTION_RELATIVE)
        privacy = projection.get("privacy")
        data_ok = (
            privacy
            == {
                "projection": PUBLIC_VISIBILITY,
                "private_godd_media": "excluded",
                "raw_frames": "excluded",
                "biometric_values": "excluded",
            }
            and all(_forbidden_key(frame["payload"]) is None for frame in frames)
        )
        notice_ok = (
            re.search(
                r"public[- ]metadata|allowlisted public|public organism ledger",
                source,
                re.IGNORECASE,
            )
            is not None
            and re.search(
                r"private.{0,80}excluded|excluded.{0,80}private|"
                r"without exposing non-public|non-public.{0,80}excluded",
                source,
                re.IGNORECASE | re.DOTALL,
            )
            is not None
            and re.search(
                r"biometric.{0,80}excluded|excluded.{0,80}biometric|"
                r"['\"]biometric['\"]",
                source,
                re.IGNORECASE | re.DOTALL,
            )
            is not None
        )
        passed = data_ok and notice_ok
        detail = "public metadata only, with exclusions disclosed" if passed else (
            "data_ok={} notice_ok={}".format(data_ok, notice_ok)
        )
    except (OSError, ValueError, TypeError) as error:
        passed = False
        detail = str(error)
    return _result("privacy.public-only", passed, detail)


def _attributes(raw: str) -> Dict[str, str]:
    attributes = {}
    for match in re.finditer(
        r"([:\w-]+)(?:\s*=\s*(?:\"([^\"]*)\"|'([^']*)'|([^\s>]+)))?",
        raw,
    ):
        attributes[match.group(1).lower()] = next(
            (value for value in match.groups()[1:] if value is not None),
            "",
        )
    return attributes


def _button_descriptors(source: str) -> List[Tuple[Dict[str, str], str]]:
    buttons = []
    for match in re.finditer(
        r"<button\b([^>]*)>(.*?)</button\s*>",
        source,
        re.IGNORECASE | re.DOTALL,
    ):
        text = html.unescape(re.sub(r"<[^>]+>", " ", match.group(2)))
        buttons.append((_attributes(match.group(1)), _compact(text)))
    return buttons


def _control_descriptor(attributes: Dict[str, str], text: str = "") -> str:
    return " ".join(
        [
            attributes.get("id", ""),
            attributes.get("name", ""),
            attributes.get("aria-label", ""),
            attributes.get("title", ""),
            attributes.get("data-action", ""),
            attributes.get("data-control", ""),
            attributes.get("data-testid", ""),
            text,
        ]
    )


def check_accessibility_controls(source: str) -> CheckResult:
    lower = source.lower()
    buttons = _button_descriptors(source)
    button_accessible = all(
        bool(text or attributes.get("aria-label") or attributes.get("aria-labelledby"))
        for attributes, text in buttons
    )
    labels = set(
        re.findall(
            r"<label\b[^>]*\bfor\s*=\s*['\"]([^'\"]+)['\"]",
            source,
            re.IGNORECASE,
        )
    )
    unlabeled = []
    controls = re.finditer(
        r"<(input|select|textarea)\b([^>]*)>",
        source,
        re.IGNORECASE | re.DOTALL,
    )
    for match in controls:
        attributes = _attributes(match.group(2))
        if attributes.get("type", "").lower() == "hidden":
            continue
        accessible = (
            attributes.get("aria-label")
            or attributes.get("aria-labelledby")
            or attributes.get("title")
            or attributes.get("id") in labels
        )
        if not accessible:
            unlabeled.append(attributes.get("id") or match.group(1))
    descriptors = [
        _control_descriptor(attributes, text)
        for attributes, text in buttons
    ]
    descriptors.extend(
        _control_descriptor(_attributes(match.group(1)))
        for match in re.finditer(
            r"<(?:input|select|textarea)\b([^>]*)>",
            source,
            re.IGNORECASE | re.DOTALL,
        )
    )
    mode = any(re.search(r"(mode|view|projection)", value, re.IGNORECASE) for value in descriptors)
    filtering = any(re.search(r"(filter|search)", value, re.IGNORECASE) for value in descriptors)
    playback = any(re.search(r"\b(play|pause|playback)\b", value, re.IGNORECASE) for value in descriptors)
    semantic = not re.search(
        r"<(?:div|span)\b[^>]*\bonclick\s*=",
        source,
        re.IGNORECASE,
    )
    foundations = all(
        [
            re.search(r"<html\b[^>]*\blang\s*=", source, re.IGNORECASE),
            re.search(r"<meta\b[^>]*name\s*=\s*['\"]viewport['\"]", source, re.IGNORECASE),
            "<main" in lower,
            "<h1" in lower,
            "aria-live" in lower or 'role="status"' in lower or "role='status'" in lower,
            ":focus-visible" in source,
            "prefers-reduced-motion" in source,
            re.search(r"\bkeydown\b", source, re.IGNORECASE),
            re.search(r"Arrow(?:Left|Right|Up|Down)|\bHome\b|\bEnd\b", source),
        ]
    )
    passed = (
        len(buttons) >= 5
        and button_accessible
        and not unlabeled
        and mode
        and filtering
        and playback
        and semantic
        and foundations
    )
    return _result(
        "controls.accessibility",
        passed,
        "semantic labeled controls, focus, keyboard, motion, and landmarks"
        if passed
        else (
            "buttons={} button_labels={} unlabeled={} mode={} filter={} "
            "playback={} semantic={} foundations={}"
        ).format(
            len(buttons),
            button_accessible,
            unlabeled,
            mode,
            filtering,
            playback,
            semantic,
            foundations,
        ),
    )


def check_io_tamper_hooks(source: str) -> CheckResult:
    buttons = [
        _control_descriptor(attributes, text)
        for attributes, text in _button_descriptors(source)
    ]
    inputs = [
        _attributes(match.group(1))
        for match in re.finditer(
            r"<input\b([^>]*)>",
            source,
            re.IGNORECASE | re.DOTALL,
        )
    ]
    import_control = any(
        item.get("type", "").lower() == "file"
        and re.search(r"json|ndjson|jsonl", item.get("accept", ""), re.IGNORECASE)
        for item in inputs
    )
    export_control = any(re.search(r"\b(export|download)\b", value, re.IGNORECASE) for value in buttons)
    tamper_control = any(re.search(r"\b(tamper|corrupt|break chain)\b", value, re.IGNORECASE) for value in buttons)
    restore_control = any(
        re.search(
            r"\b(restore|repair|reset ledger|reset data|reset lab)\b",
            value,
            re.IGNORECASE,
        )
        for value in buttons
    )
    implementation = all(
        [
            re.search(r"\b(?:FileReader|\.text\s*\(\s*\))", source),
            re.search(r"\bBlob\s*\(", source),
            "URL.createObjectURL" in source,
            re.search(r"\bDRIFT\b", source),
            re.search(r"\bVALID\b", source),
            re.search(r"data-integrity-status|data-integrity|role\s*=\s*['\"]status", source, re.IGNORECASE),
        ]
    )
    passed = (
        import_control
        and export_control
        and tamper_control
        and restore_control
        and implementation
    )
    return _result(
        "controls.io-tamper",
        passed,
        "measurable import, export, tamper, restore, VALID, and DRIFT hooks"
        if passed
        else "import={} export={} tamper={} restore={} implementation={}".format(
            import_control,
            export_control,
            tamper_control,
            restore_control,
            implementation,
        ),
    )


def check_wall_clock_playback(source: str) -> CheckResult:
    requirements = [
        re.search(r"\bperformance\s*\.\s*now\s*\(", source),
        re.search(r"\brequestAnimationFrame\s*\(", source),
        re.search(r"\b(?:elapsed|delta|wallClock|lastTick|startedAt)\b", source, re.IGNORECASE),
        re.search(r"\b(?:playback|playhead|playing)\b", source, re.IGNORECASE),
    ]
    passed = all(requirements)
    return _result(
        "playback.wall-clock",
        passed,
        "requestAnimationFrame advances from performance.now elapsed time"
        if passed
        else "required wall-clock primitives are incomplete",
    )


def check_small_viewport_static(source: str) -> CheckResult:
    viewport = re.search(
        r"<meta\b[^>]*name\s*=\s*['\"]viewport['\"][^>]*content\s*=\s*"
        r"['\"][^'\"]*width=device-width[^'\"]*['\"]",
        source,
        re.IGNORECASE,
    )
    if not viewport:
        viewport = re.search(
            r"<meta\b[^>]*content\s*=\s*['\"][^'\"]*width=device-width[^'\"]*['\"]"
            r"[^>]*name\s*=\s*['\"]viewport['\"]",
            source,
            re.IGNORECASE,
        )
    media = re.search(
        r"@media\s*\([^)]*(?:max-width\s*:\s*(?:[0-6]\d{2})px|width\s*<=\s*(?:[0-6]\d{2})px)",
        source,
        re.IGNORECASE,
    )
    flexible = re.search(
        r"\b(?:min|max|clamp)\s*\(|grid-template-columns\s*:\s*repeat\s*\(\s*auto-fit",
        source,
        re.IGNORECASE,
    )
    passed = bool(viewport and media and flexible)
    return _result(
        "responsive.static",
        passed,
        "device viewport, compact breakpoint, and flexible sizing"
        if passed
        else "viewport={} media={} flexible={}".format(
            bool(viewport),
            bool(media),
            bool(flexible),
        ),
    )


def run_static_checks(
    root: Path,
    app_relative: Path = APP_RELATIVE,
) -> List[CheckResult]:
    app_path = root / app_relative
    measurable = check_app_measurable(app_path)
    checks = [measurable]
    try:
        source = _read_text(app_path) if measurable.passed else ""
    except (OSError, UnicodeError):
        source = ""
    content_checks = [
        check_theme_script,
        check_theme_variables,
        check_component_colors,
        check_dangerous_javascript,
        check_csp,
        check_same_origin_data_urls,
    ]
    for function in content_checks:
        try:
            checks.append(function(source))
        except Exception as error:
            checks.append(
                _result(
                    getattr(function, "__name__", "content-check"),
                    False,
                    "unmeasurable: {}".format(error),
                )
            )
    checks.extend(
        [
            check_manifest_registration(root),
            check_feed_registration(root),
            check_discovery_registration(root),
        ]
    )
    ledger_check, frames = check_ledger(root)
    checks.append(ledger_check)
    checks.append(check_projection(root, frames))
    checks.append(check_public_privacy(source, frames, root))
    for function in (
        check_accessibility_controls,
        check_io_tamper_hooks,
        check_wall_clock_playback,
        check_small_viewport_static,
    ):
        try:
            checks.append(function(source))
        except Exception as error:
            checks.append(
                _result(
                    getattr(function, "__name__", "content-check"),
                    False,
                    "unmeasurable: {}".format(error),
                )
            )
    return checks


EXPANDED_REQUIRED_FILES = (
    "scripts/rappterzoo_mcp.py",
    "skill.md",
    "heartbeat.md",
    "skill.json",
    ".well-known/mcp.json",
    "apps/syndication/index.json",
    "apps/syndication/snapshot.json",
    "apps/syndication/feed.xml",
    "apps/syndication/feed.json",
    "scripts/build_syndication.py",
    "scripts/rappterzoo_sync.py",
    "scripts/attention_portal.py",
    "apps/attention/policy.json",
    "apps/attention/prompt-contract.json",
)


def _load_module(path: Path, prefix: str) -> Any:
    if not path.is_file():
        raise GateError("missing {}".format(path))
    name = "_moonshot_{}_{}".format(prefix, uuid.uuid4().hex)
    specification = importlib.util.spec_from_file_location(name, str(path))
    if specification is None or specification.loader is None:
        raise GateError("cannot load {}".format(path))
    module = importlib.util.module_from_spec(specification)
    sys.modules[name] = module
    try:
        specification.loader.exec_module(module)
    finally:
        sys.modules.pop(name, None)
    return module


@contextmanager
def _workspace(root: Path, label: str) -> Iterable[Path]:
    parent = root / "scripts" / "tests"
    if not parent.is_dir():
        parent = root / "scripts"
    if not parent.is_dir():
        raise GateError("repository scripts directory is missing")
    with tempfile.TemporaryDirectory(
        prefix=".moonshot-{}-".format(label),
        dir=str(parent),
    ) as temporary:
        yield Path(temporary)


@contextmanager
def _serve(root: Path) -> Iterable[str]:
    handler = partial(QuietHandler, directory=str(root))
    server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield "http://127.0.0.1:{}/".format(server.server_address[1])
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


def _mcp_messages(root: Path, messages: Sequence[Dict[str, Any]]) -> List[Any]:
    script = root / "scripts/rappterzoo_mcp.py"
    if not script.is_file():
        raise GateError("MCP server is missing")
    environment = dict(os.environ)
    environment.pop("RAPPTERZOO_MCP_WRITES", None)
    payload = "".join(
        json.dumps(message, separators=(",", ":")) + "\n"
        for message in messages
    )
    completed = subprocess.run(
        [sys.executable, str(script), "--root", str(root)],
        cwd=str(root),
        env=environment,
        input=payload,
        capture_output=True,
        text=True,
        check=False,
        timeout=20,
    )
    if completed.returncode != 0:
        raise GateError(
            "MCP stdio failed: {}".format(
                completed.stderr.strip() or completed.stdout.strip()
            )
        )
    lines = [line for line in completed.stdout.splitlines() if line.strip()]
    try:
        values = [json.loads(line) for line in lines]
    except ValueError as error:
        raise GateError("MCP emitted invalid JSON") from error
    if len(values) != len(messages):
        raise GateError(
            "MCP response count {} != {}".format(len(values), len(messages))
        )
    return values


def check_expanded_files(root: Path) -> CheckResult:
    missing = []
    unreadable = []
    for relative in EXPANDED_REQUIRED_FILES:
        path = root / relative
        if not path.is_file():
            missing.append(relative)
            continue
        try:
            path.read_bytes()
        except OSError:
            unreadable.append(relative)
    delta_dir = root / "apps/syndication/deltas"
    deltas = list(delta_dir.glob("*.json")) if delta_dir.is_dir() else []
    passed = not missing and not unreadable and bool(deltas)
    return _result(
        "expanded.files-measurable",
        passed,
        "{} immutable delta files".format(len(deltas))
        if passed
        else "missing={} unreadable={} deltas={}".format(
            missing,
            unreadable,
            len(deltas),
        ),
    )


def _runtime_mcp_surface(root: Path) -> Dict[str, Any]:
    messages = [
        {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
            },
        },
        {
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/list",
            "params": {},
        },
        {
            "jsonrpc": "2.0",
            "id": 3,
            "method": "resources/list",
            "params": {},
        },
        {
            "jsonrpc": "2.0",
            "id": 4,
            "method": "prompts/list",
            "params": {},
        },
    ]
    values = _mcp_messages(root, messages)
    for value in values:
        if "error" in value:
            raise GateError("MCP surface returned {}".format(value["error"]))
    return {
        "initialize": values[0]["result"],
        "tools": values[1]["result"]["tools"],
        "resources": values[2]["result"]["resources"],
        "prompts": values[3]["result"]["prompts"],
    }


def check_mcp_parity(root: Path) -> CheckResult:
    try:
        runtime = _runtime_mcp_surface(root)
        static = _load_json(root / ".well-known/mcp.json")
        package = _load_json(root / "skill.json")
        module = _load_module(
            root / "scripts/rappterzoo_mcp.py",
            "mcp_parity",
        )
        initialized = runtime["initialize"]
        static_server = static.get("server_info", {})
        runtime_server = initialized.get("serverInfo", {})
        identity_ok = (
            static.get("protocol_version")
            == initialized.get("protocolVersion")
            and static_server.get("name") == runtime_server.get("name")
            and static_server.get("version") == runtime_server.get("version")
            and package.get("version") == runtime_server.get("version")
        )
        tools_ok = static.get("tools") == runtime["tools"]
        static_resource_uris = {
            item.get("uri")
            for item in static.get("resources", [])
            if isinstance(item, dict)
        }
        uncovered_resources = []
        for runtime_uri, descriptor in module.RESOURCE_MAP.items():
            relative = descriptor[0]
            if runtime_uri == "rappterzoo://mcp-manifest":
                continue
            if not any(
                isinstance(uri, str) and uri.endswith("/" + relative)
                for uri in static_resource_uris
            ):
                uncovered_resources.append(runtime_uri)
        runtime_resource_uris = {
            item.get("uri")
            for item in runtime["resources"]
            if isinstance(item, dict)
        }
        resources_ok = (
            runtime_resource_uris == set(module.RESOURCE_MAP)
            and not uncovered_resources
        )
        prompts_ok = static.get("prompts") == runtime["prompts"]
        passed = identity_ok and tools_ok and resources_ok and prompts_ok
        detail = (
            "static discovery exactly mirrors live stdio"
            if passed
            else (
                "identity={} versions={}/{}/{} tools={}/{} runtime_resources={} "
                "uncovered={} prompts={}/{}"
            ).format(
                identity_ok,
                static_server.get("version"),
                runtime_server.get("version"),
                package.get("version"),
                len(static.get("tools", [])),
                len(runtime["tools"]),
                len(runtime["resources"]),
                uncovered_resources,
                len(static.get("prompts", [])),
                len(runtime["prompts"]),
            )
        )
    except (OSError, ValueError, GateError, KeyError, TypeError) as error:
        passed = False
        detail = str(error)
    return _result("mcp.runtime-static-parity", passed, detail)


def check_mcp_writes_default(root: Path) -> CheckResult:
    try:
        environment = dict(os.environ)
        environment.pop("RAPPTERZOO_MCP_WRITES", None)
        completed = subprocess.run(
            [
                sys.executable,
                str(root / "scripts/rappterzoo_mcp.py"),
                "--root",
                str(root),
                "--self-test",
            ],
            cwd=str(root),
            env=environment,
            capture_output=True,
            text=True,
            check=False,
            timeout=20,
        )
        self_test = json.loads(completed.stdout)
        package = _load_json(root / "skill.json")
        static = _load_json(root / ".well-known/mcp.json")
        mcp_package = package.get("moltbot", {}).get("mcp", {})
        stdio = static.get("stdio_server", {})
        passed = (
            completed.returncode == 0
            and self_test.get("ok") is True
            and self_test.get("writes_enabled") is False
            and mcp_package.get("writes_default") is False
            and mcp_package.get("write_opt_in_env")
            == "RAPPTERZOO_MCP_WRITES=1"
            and stdio.get("write_default") == "prepared-not-submitted"
            and stdio.get("enable_submitted_writes")
            == "RAPPTERZOO_MCP_WRITES=1"
        )
        detail = (
            "writes are prepared-only until explicit operator opt-in"
            if passed
            else "self_test={} package={} static={}".format(
                self_test.get("writes_enabled"),
                mcp_package,
                stdio.get("write_default"),
            )
        )
    except (OSError, ValueError, KeyError, TypeError) as error:
        passed = False
        detail = str(error)
    return _result("mcp.writes-default-off", passed, detail)


def check_mcp_first_use(root: Path) -> CheckResult:
    try:
        skill = _read_text(root / "skill.md")
        heartbeat = _read_text(root / "heartbeat.md")
        package = _load_json(root / "skill.json")
        surface = _runtime_mcp_surface(root)
        prompt_names = {
            item.get("name")
            for item in surface["prompts"]
            if isinstance(item, dict)
        }
        resources = {
            item.get("uri")
            for item in surface["resources"]
            if isinstance(item, dict)
        }
        prompt_value = _mcp_messages(
            root,
            [{
                "jsonrpc": "2.0",
                "id": 1,
                "method": "prompts/get",
                "params": {"name": "rappterzoo_first_use"},
            }],
        )[0]
        prompt_text = prompt_value["result"]["messages"][0][
            "content"
        ]["text"]
        package_files = package.get("moltbot", {}).get("files", {})
        skill_ok = all(
            token in skill
            for token in (
                "## First Use: Join Through MCP",
                "--self-test",
                "tools/list",
                "resources/list",
                "RAPPTERZOO_MCP_WRITES=1",
                "at most one",
            )
        )
        heartbeat_ok = all(
            token in heartbeat
            for token in (
                "rappterzoo_sync.py status",
                "rappterzoo_sync.py sync",
                "conditional HTTP",
                "at most one contribution",
                "HEARTBEAT_OK",
            )
        ) and "constant polling loop" in heartbeat
        required_runtime_resources = {
            "rappterzoo://skill",
            "rappterzoo://heartbeat",
            "rappterzoo://syndication-index",
        }
        missing_runtime_resources = sorted(
            required_runtime_resources - resources
        )
        runtime_ok = (
            "rappterzoo_first_use" in prompt_names
            and not missing_runtime_resources
            and all(
                token in prompt_text
                for token in (
                    "get_home",
                    "rappterzoo://heartbeat",
                    "writes disabled",
                    "one bounded contribution",
                )
            )
        )
        package_ok = (
            "SKILL.md" in package_files
            and "HEARTBEAT.md" in package_files
            and "MCP_SERVER.py" in package_files
        )
        passed = skill_ok and heartbeat_ok and runtime_ok and package_ok
        detail = (
            "first-use prompt, skill, package, and bounded heartbeat agree"
            if passed
            else (
                "skill={} heartbeat={} runtime={} missing_resources={} "
                "package={}"
            ).format(
                skill_ok,
                heartbeat_ok,
                runtime_ok,
                missing_runtime_resources,
                package_ok,
            )
        )
    except (OSError, ValueError, GateError, KeyError, TypeError) as error:
        passed = False
        detail = str(error)
    return _result("mcp.first-use-heartbeat", passed, detail)


def _stable_json_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        allow_nan=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8") + b"\n"


def _syndication_modules(root: Path) -> Tuple[Any, Any]:
    builder = _load_module(
        root / "scripts/build_syndication.py",
        "syndication_builder",
    )
    sync = _load_module(
        root / "scripts/rappterzoo_sync.py",
        "syndication_sync",
    )
    return builder, sync


def check_syndication_chain(root: Path) -> CheckResult:
    try:
        _builder, sync = _syndication_modules(root)
        directory = root / "apps/syndication"
        index_path = directory / "index.json"
        snapshot_path = directory / "snapshot.json"
        index_raw = index_path.read_bytes()
        snapshot_raw = snapshot_path.read_bytes()
        index = json.loads(index_raw.decode("utf-8"))
        snapshot = json.loads(snapshot_raw.decode("utf-8"))
        if index_raw != _stable_json_bytes(index):
            raise GateError("index is not deterministic JSON")
        if snapshot_raw != _stable_json_bytes(snapshot):
            raise GateError("snapshot is not deterministic JSON")
        if index.get("profile") != sync.PROFILE:
            raise GateError(
                "index profile {} != sync profile {}".format(
                    index.get("profile"),
                    sync.PROFILE,
                )
            )
        entries = sync.validate_index(index)
        for entry in entries:
            delta_path = directory / entry["path"]
            if not delta_path.is_file():
                raise GateError("missing delta {}".format(entry["path"]))
            data = delta_path.read_bytes()
            if delta_path.stem != entry["sha256"]:
                raise GateError("delta filename is not its content ID")
            if len(data) != entry["size"]:
                raise GateError("delta size mismatch")
            sync.validate_delta(data, entry)
        snapshot_entry = index.get("snapshot", {})
        if (
            hashlib.sha256(snapshot_raw).hexdigest()
            != snapshot_entry.get("sha256")
            or len(snapshot_raw) != snapshot_entry.get("size")
        ):
            raise GateError("snapshot descriptor mismatch")
        counts = snapshot.get("counts", {})
        if (
            counts.get("active_apps") != len(snapshot.get("apps", []))
            or counts.get("frames") != len(snapshot.get("frames", []))
            or counts.get("attention_data_objects")
            != len(snapshot.get("data_objects", []))
            or index.get("delta_count") != len(entries)
        ):
            raise GateError("snapshot counts disagree")
        checkpoint = snapshot.get("checkpoint", {})
        head = index.get("head")
        if entries and (
            checkpoint.get("delta_sha256") != entries[-1]["sha256"]
            or checkpoint.get("since_seq") != entries[-1]["sequence"]
            or head.get("sha256") != entries[-1]["sha256"]
        ):
            raise GateError("snapshot/index checkpoint mismatch")
        passed = True
        detail = "{} immutable linked deltas verified".format(len(entries))
    except Exception as error:
        passed = False
        detail = str(error)
    return _result("syndication.immutable-chain", passed, detail)


def check_syndication_feed_ids(root: Path) -> CheckResult:
    try:
        directory = root / "apps/syndication"
        index = _load_json(directory / "index.json")
        json_feed = _load_json(directory / "feed.json")
        atom = ET.parse(str(directory / "feed.xml")).getroot()
        namespace = {"atom": "http://www.w3.org/2005/Atom"}
        atom_ids = [
            node.text
            for node in atom.findall("atom:entry/atom:id", namespace)
        ]
        json_ids = [
            item.get("id")
            for item in json_feed.get("items", [])
            if isinstance(item, dict)
        ]
        expected = [
            "urn:sha256:{}".format(entry["sha256"])
            for entry in reversed(index.get("deltas", []))
        ]
        passed = atom_ids == json_ids == expected
        detail = (
            "{} Atom/JSON Feed delta IDs agree".format(len(expected))
            if passed
            else "atom={} json={} expected={}".format(
                atom_ids[:3],
                json_ids[:3],
                expected[:3],
            )
        )
    except (OSError, ValueError, ET.ParseError, TypeError) as error:
        passed = False
        detail = str(error)
    return _result("syndication.feed-id-parity", passed, detail)


def _fixture_frame(builder: Any) -> Dict[str, Any]:
    payload = {
        "display_name": "Gate Fixture",
        "event": "bootstrap",
        "event_id": "moonshot-fixture:0",
        "organism": "moonshot-fixture",
        "schema": builder.FRAME_SCHEMA,
        "visibility": "public-metadata",
    }
    frame = {
        "frame_hash": "0" * 64,
        "kind": "zoo.snapshot",
        "payload": payload,
        "payload_hash": builder.frame_hash_value(
            builder.PARTICLE_SPACE,
            payload,
        ),
        "prev": None,
        "prev_wave": None,
        "seq": 0,
        "sig": None,
        "spec": "rapp/1",
        "stream_id": "net:rappterzoo",
        "utc": "2026-08-15T17:06:24.449Z",
    }
    wave = {
        key: value
        for key, value in frame.items()
        if key not in {"frame_hash", "sig"}
    }
    frame["frame_hash"] = builder.frame_hash_value(
        builder.WAVE_SPACE,
        wave,
    )
    return frame


def _write_build_fixture(
    repository: Path,
    builder: Any,
) -> None:
    app_dir = repository / "apps/demo"
    app_dir.mkdir(parents=True)
    app_bytes = b"<!DOCTYPE html><title>Fixture</title><main>fixture</main>\n"
    (app_dir / "fixture.html").write_bytes(app_bytes)
    manifest = {
        "categories": {
            "demo": {
                "apps": [{
                    "complexity": "simple",
                    "created": "2026-08-15",
                    "description": "Moonshot fixture",
                    "featured": False,
                    "file": "fixture.html",
                    "tags": ["fixture"],
                    "title": "Fixture",
                    "type": "interactive",
                }],
                "count": 1,
                "folder": "demo",
                "title": "Demo",
            }
        },
        "meta": {"lastUpdated": "2026-08-15", "version": "1.0"},
    }
    (repository / "apps/manifest.json").write_bytes(
        builder.stable_json_bytes(manifest)
    )
    frame = _fixture_frame(builder)
    (repository / "apps/organism-frames.jsonl").write_bytes(
        builder.canonical_frame_bytes(frame) + b"\n"
    )


def check_syndication_idempotence(root: Path) -> CheckResult:
    try:
        builder = _load_module(
            root / "scripts/build_syndication.py",
            "idempotent_builder",
        )
        with _workspace(root, "build") as temporary:
            repository = temporary / "repo"
            repository.mkdir()
            _write_build_fixture(repository, builder)
            first = builder.build(repository, "https://example.invalid/zoo/")
            files = sorted(
                path
                for path in (repository / "apps/syndication").rglob("*")
                if path.is_file()
            )
            before = {
                path.relative_to(repository).as_posix(): (
                    path.read_bytes(),
                    path.stat().st_mtime_ns,
                )
                for path in files
            }
            second = builder.build(repository, "https://example.invalid/zoo/")
            after_files = sorted(
                path
                for path in (repository / "apps/syndication").rglob("*")
                if path.is_file()
            )
            after = {
                path.relative_to(repository).as_posix(): (
                    path.read_bytes(),
                    path.stat().st_mtime_ns,
                )
                for path in after_files
            }
        passed = (
            first.get("delta_count") == second.get("delta_count")
            and second.get("delta_created") is False
            and all(
                value is False
                for value in second.get("written", {}).values()
            )
            and before == after
        )
        detail = (
            "two builds are byte- and mtime-idempotent"
            if passed
            else "second={}".format(second)
        )
    except Exception as error:
        passed = False
        detail = str(error)
    return _result("syndication.build-idempotent", passed, detail)


def _remove_fixture_app(repository: Path, builder: Any) -> None:
    path = repository / "apps/manifest.json"
    manifest = json.loads(path.read_text(encoding="utf-8"))
    category = manifest["categories"]["demo"]
    category["apps"] = []
    category["count"] = 0
    path.write_bytes(builder.stable_json_bytes(manifest))


def _expect_error(call: Any, error_type: Any) -> bool:
    try:
        call()
    except error_type:
        return True
    return False


def check_sync_adversarial(root: Path) -> CheckResult:
    try:
        builder, sync = _syndication_modules(root)
        with _workspace(root, "sync") as temporary:
            repository = temporary / "repo"
            repository.mkdir()
            _write_build_fixture(repository, builder)
            with _serve(repository) as base_url:
                builder.build(repository, base_url)
                index_url = base_url + "apps/syndication/index.json"
                state = temporary / "state"
                first = sync.sync_repository(
                    state,
                    index_url,
                    fetch_apps=True,
                )
                index = _load_json(
                    repository / "apps/syndication/index.json"
                )
                replay = json.loads(json.dumps(index))
                replay["deltas"].append(dict(replay["deltas"][0]))
                replay["delta_count"] = len(replay["deltas"])
                replay_rejected = _expect_error(
                    lambda: sync.validate_index(replay),
                    sync.SyncError,
                )
                gap = json.loads(json.dumps(index))
                gap["deltas"][0]["sequence"] = 1
                gap_rejected = _expect_error(
                    lambda: sync.validate_index(gap),
                    sync.SyncError,
                )
                entry = index["deltas"][0]
                delta = (
                    repository
                    / "apps/syndication"
                    / entry["path"]
                ).read_bytes()
                tamper_rejected = _expect_error(
                    lambda: sync.validate_delta(delta + b" ", entry),
                    sync.SyncError,
                )
                local = temporary / "local.html"
                local_bytes = b"<title>Local overlay survives</title>\n"
                local.write_bytes(local_bytes)
                sync.add_local_app(
                    state,
                    local,
                    "apps/demo/fixture.html",
                    "Local Fixture",
                )
                _remove_fixture_app(repository, builder)
                builder.build(repository, base_url)
                connection = sync.connect_state(state)
                try:
                    with connection:
                        connection.execute(
                            "DELETE FROM meta WHERE key IN (?, ?)",
                            ("etag", "last_modified"),
                        )
                finally:
                    connection.close()
                second = sync.sync_repository(state, index_url)
                materialized = temporary / "materialized"
                sync.materialize(state, materialized)
                overlay_ok = (
                    materialized
                    / "apps/demo/fixture.html"
                ).read_bytes() == local_bytes
                replay_noop = sync.sync_repository(
                    state,
                    index_url,
                ).get("applied_deltas") == 0
        passed = (
            first.get("applied_deltas") == 1
            and second.get("applied_deltas") == 1
            and replay_rejected
            and gap_rejected
            and tamper_rejected
            and overlay_ok
            and replay_noop
        )
        detail = (
            "replay, gap, tamper rejected; overlay and idempotent replay preserved"
            if passed
            else (
                "first={} second={} replay={} gap={} tamper={} "
                "overlay={} noop={}"
            ).format(
                first,
                second,
                replay_rejected,
                gap_rejected,
                tamper_rejected,
                overlay_ok,
                replay_noop,
            )
        )
    except Exception as error:
        passed = False
        detail = str(error)
    return _result("sync.replay-gap-tamper-overlay", passed, detail)


def check_attention_contracts(root: Path) -> CheckResult:
    try:
        portal = _load_module(
            root / "scripts/attention_portal.py",
            "attention_contract",
        )
        policy = portal.validate_policy(
            _load_json(root / "apps/attention/policy.json")
        )
        prompt = portal.validate_prompt_contract(
            _load_json(root / "apps/attention/prompt-contract.json")
        )
        budgets = (
            1
            <= policy["attention_budget"]
            <= policy["candidate_budget"]
            <= policy["max_group_records"]
        )
        output = json.dumps(prompt.get("output_contract", {})).lower()
        selected_only = (
            "attention_budget" in output
            and "candidate_record_ids" in output
            and "no additional" in output
        )
        verified_objects = 0
        for path in sorted((root / "apps/attention").rglob("*.json")):
            value = portal._load_json(path)
            if path.name in {"policy.json", "prompt-contract.json"}:
                continue
            schema = value.get("schema") if isinstance(value, dict) else None
            if schema == getattr(
                portal,
                "FRAME_CONTROL_CONFIG_SCHEMA",
                None,
            ):
                portal.validate_frame_control_config(value)
                verified_objects += 1
            elif schema == getattr(portal, "REQUEST_SCHEMA", None):
                portal.verify_request(value)
                verified_objects += 1
            elif schema == getattr(portal, "GROUP_SCHEMA", None):
                portal.verify_group_object(value)
                verified_objects += 1
            elif schema == getattr(portal, "RECEIPT_OBJECT_SCHEMA", None):
                digest = value.get("receipt_object_digest")
                if (
                    not isinstance(digest, str)
                    or path.stem != digest
                    or portal._receipt_digest(value) != digest
                ):
                    raise GateError(
                        "attention receipt object digest mismatch"
                    )
                verified_objects += 1
            elif schema == getattr(portal, "SHARD_WRITER_SCHEMA", None):
                required = {
                    "schema",
                    "shard_id",
                    "shard_count",
                    "shard_index",
                    "endpoint_identity_digest",
                }
                if (
                    set(value) != required
                    or not isinstance(value.get("shard_id"), str)
                    or not isinstance(value.get("shard_count"), int)
                    or not isinstance(value.get("shard_index"), int)
                ):
                    raise GateError("invalid attention shard writer")
                verified_objects += 1
            elif schema == getattr(portal, "DIMENSION_SCHEMA", None):
                verifier = getattr(
                    portal,
                    "verify_dimension_object",
                    None,
                )
                if verifier is None:
                    raise GateError(
                        "attention dimension object has no verifier"
                    )
                verifier(value)
                verified_objects += 1
            else:
                raise GateError(
                    "unknown attention object schema at {}".format(path)
                )
        passed = budgets and selected_only
        detail = (
            "bounded policy, selected-only prompt, {} objects verified".format(
                verified_objects
            )
            if passed
            else "budgets={} selected_only={}".format(
                budgets,
                selected_only,
            )
        )
    except Exception as error:
        passed = False
        detail = str(error)
    return _result("attention.contracts-objects", passed, detail)


def _attention_records(count: int) -> List[Dict[str, Any]]:
    return [
        {
            "record_id": "comment:{:03d}".format(index),
            "kind": "comment",
            "created_at": "2026-08-15T16:{:02d}:00.000Z".format(index),
            "visibility": "public-metadata",
            "public_text": "Public evidence {:03d}".format(index),
            "priority": index,
            "source_ref": "community:comment:{:03d}".format(index),
        }
        for index in range(count)
    ]


def _prepare_attention(
    portal: Any,
    records: List[Dict[str, Any]],
    prompt: Dict[str, Any],
    policy: Dict[str, Any],
    attention_dir: Path,
    endpoint: str = "moonshot-writer",
) -> List[Dict[str, Any]]:
    return portal.prepare_requests(
        records,
        prompt,
        policy,
        scope_id="moonshot:2026-08-15",
        source="community-comments",
        window_start="2026-08-15T16:00:00.000Z",
        window_end="2026-08-15T17:00:00.000Z",
        base_record_hash="1" * 64,
        base_frame_hash="2" * 64,
        endpoint_identity=endpoint,
        evaluation_axis="community-value",
        shard_count=3,
        attention_dir=attention_dir,
    )


def _evaluation_for(portal: Any, request: Dict[str, Any]) -> Dict[str, Any]:
    descriptors = {
        item["record_id"]: item
        for item in request["record_descriptors"]
    }
    selected_id = request["candidate_record_ids"][0]
    value = {
        "schema": portal.EVALUATION_SCHEMA,
        "request_digest": request["request_digest"],
        "input_digest": request["input_digest"],
        "prompt_digest": request["prompt_digest"],
        "selected": [{
            "record_id": selected_id,
            "record_digest": descriptors[selected_id]["record_digest"],
            "score": request["policy"]["score_min"] + 1,
            "reason": "Selected public evidence is specific.",
        }],
    }
    for key in (
        "shard_id",
        "scope_digest",
        "base_record_hash",
        "base_frame_hash",
        "endpoint_identity_digest",
        "evaluation_axis",
    ):
        if key in request:
            value[key] = request[key]
    if "group_assessment" in getattr(portal, "EVALUATION_KEYS", set()):
        value["group_assessment"] = {
            "attention_state": "hot",
            "polarity": "positive",
            "mutation_recommendation": "promote",
            "reason": "The bounded group contains actionable evidence.",
        }
    return value


def check_attention_lineage(root: Path) -> CheckResult:
    try:
        portal = _load_module(
            root / "scripts/attention_portal.py",
            "attention_lineage",
        )
        policy = portal.validate_policy(
            _load_json(root / "apps/attention/policy.json")
        )
        prompt = portal.validate_prompt_contract(
            _load_json(root / "apps/attention/prompt-contract.json")
        )
        with _workspace(root, "attention") as temporary:
            prepared = _prepare_attention(
                portal,
                _attention_records(8),
                prompt,
                policy,
                temporary / "attention",
            )
            request = prepared[0]["request"]
            evaluation = _evaluation_for(portal, request)
            result = portal.apply_evaluation(
                request,
                evaluation,
                attention_dir=temporary / "attention",
                ledger_path=temporary / "frames.jsonl",
                projection_path=temporary / "frames.json",
                utc="2026-08-15T17:10:00.000Z",
            )
            group = result["group"]
            selected = {
                item["record_id"]
                for item in group["selected_records"]
            }
            nonselected = (
                group["unselected_candidate_records"]
                + group["never_candidate_records"]
            )
            descriptor_only = all(
                set(item) == portal.DESCRIPTOR_KEYS
                for item in nonselected
            )
            budget_ok = (
                1
                <= group["selected_count"]
                <= group["attention_budget"]
                <= group["candidate_budget"]
            )
            unselected_id = nonselected[0]["record_id"]
            receipt = {
                "schema": portal.RECEIPT_SCHEMA,
                "run_kind": "mutation",
                "mutation_id": "moonshot:mutation:1",
                "group_object_digest": group["group_object_digest"],
                "attention_frame_seq": result["frame"]["seq"],
                "attention_frame_hash": result["frame"]["frame_hash"],
                "consumed_record_ids": [unselected_id],
                "output_digest": "3" * 64,
                "output_media_type": "application/json",
                "mutation_prompt_digest": "4" * 64,
            }
            for key in getattr(portal, "RECEIPT_KEYS", set()):
                if key not in receipt:
                    receipt[key] = (
                        []
                        if key.endswith("_digests")
                        else "none"
                        if key.endswith("_mode")
                        else None
                    )
            unselected_rejected = _expect_error(
                lambda: portal.record_mutation_receipt(
                    receipt,
                    attention_dir=temporary / "attention",
                    ledger_path=temporary / "frames.jsonl",
                    projection_path=temporary / "frames.json",
                ),
                portal.AttentionError,
            )
        passed = (
            bool(selected)
            and descriptor_only
            and budget_ok
            and unselected_rejected
        )
        detail = (
            "budgets enforced; only selected IDs may enter mutation lineage"
            if passed
            else "selected={} descriptors={} budget={} rejected={}".format(
                selected,
                descriptor_only,
                budget_ok,
                unselected_rejected,
            )
        )
    except Exception as error:
        passed = False
        detail = str(error)
    return _result("attention.budgets-selected-lineage", passed, detail)


def check_attention_shards_dimensions(root: Path) -> CheckResult:
    try:
        portal = _load_module(
            root / "scripts/attention_portal.py",
            "attention_shards",
        )
        builder = _load_module(
            root / "scripts/build_syndication.py",
            "attention_dimensions",
        )
        policy = portal.validate_policy(
            _load_json(root / "apps/attention/policy.json")
        )
        prompt = portal.validate_prompt_contract(
            _load_json(root / "apps/attention/prompt-contract.json")
        )
        records = _attention_records(18)
        with _workspace(root, "shards") as temporary:
            scopes = []
            observed = set()
            collision = False
            for index in range(6):
                scope = "moonshot-scope-{}".format(index)
                prepared = portal.prepare_requests(
                    records,
                    prompt,
                    policy,
                    scope_id=scope,
                    source="community-comments",
                    window_start="2026-08-15T16:00:00.000Z",
                    window_end="2026-08-15T17:00:00.000Z",
                    base_record_hash="1" * 64,
                    base_frame_hash="2" * 64,
                    endpoint_identity="moonshot-writer",
                    evaluation_axis="community-value",
                    shard_count=6,
                    attention_dir=temporary / "attention",
                )
                request = prepared[0]["request"]
                pair = (request["scope_digest"], request["shard_id"])
                if request["scope_digest"] in observed:
                    collision = True
                observed.add(request["scope_digest"])
                scopes.append(pair)
            writer_collision_rejected = _expect_error(
                lambda: portal.prepare_requests(
                    records,
                    prompt,
                    policy,
                    scope_id="moonshot-scope-0",
                    source="community-comments",
                    window_start="2026-08-15T16:00:00.000Z",
                    window_end="2026-08-15T17:00:00.000Z",
                    base_record_hash="1" * 64,
                    base_frame_hash="2" * 64,
                    endpoint_identity="unauthorized-writer",
                    evaluation_axis="community-value",
                    shard_count=6,
                    attention_dir=temporary / "attention",
                ),
                portal.AttentionError,
            )
        dimensions = [
            {
                "base_record_id": "record-rare",
                "branch": "hot",
                "dimension_id": "dimension-hot",
                "drift": {"signal": "promote"},
                "schema": "rappterzoo-dimension/1",
                "visibility": "public-metadata",
            },
            {
                "base_record_id": "record-rare",
                "branch": "cold",
                "dimension_id": "dimension-cold",
                "drift": {"signal": "hold"},
                "schema": "rappterzoo-dimension/1",
                "visibility": "public-metadata",
            },
        ]
        metadata = builder._dimension_metadata(
            dimensions,
            "apps/attention/dimension.json",
        )
        dimensions_ok = (
            metadata.get("branches_present") == ["hot", "cold"]
            and metadata.get("merge_order") == ["hot", "cold"]
            and metadata.get("dimension_ids")
            == ["dimension-cold", "dimension-hot"]
            and metadata.get("base_record_id") == "record-rare"
        )
        passed = (
            not collision
            and len(scopes) == 6
            and writer_collision_rejected
            and dimensions_ok
        )
        detail = (
            "deterministic shard ownership and hot/cold dimensions preserved"
            if passed
            else "collision={} writer={} dimensions={}".format(
                collision,
                writer_collision_rejected,
                metadata,
            )
        )
    except Exception as error:
        passed = False
        detail = str(error)
    return _result("attention.shards-dimensions", passed, detail)


def check_fold_safety(root: Path) -> CheckResult:
    try:
        builder = _load_module(
            root / "scripts/build_syndication.py",
            "fold_safety",
        )
        with _workspace(root, "fold") as temporary:
            unauthorized = {
                "schema": "rappterzoo-fold-shard-lease/1",
                "type": "fold-shard-lease",
                "visibility": "public-metadata",
                "assignment_id": "assignment-1",
                "lease_id": "lease-1",
                "shard_id": "shard-1",
                "authorization": "unauthorized",
                "frame_control_mode": "assigned",
                "lease_bounds": {
                    "actions": ["evaluate"],
                    "max_output_bytes": 1024,
                },
                "issued_at": "2026-08-15T17:00:00.000Z",
                "expires_at": "2026-08-15T17:30:00.000Z",
            }
            live_proof = {
                "assembler_status": "accepted",
                "challenge_id": "live-challenge",
                "frame_control_mode": "proof-of-fold",
                "kind": "fold-proof",
                "main_append": True,
                "proof_id": "live-proof",
                "shard_id": "live-shard",
                "visibility": "public-metadata",
            }

            def rejected(
                name: str,
                directory_name: str,
                value: Dict[str, Any],
            ) -> bool:
                repository = temporary / name
                directory = repository / "apps" / directory_name
                directory.mkdir(parents=True)
                path = directory / (name + ".json")
                path.write_bytes(builder.stable_json_bytes(value))
                try:
                    descriptors = builder.build_public_data_descriptors(
                        repository,
                        "https://example.invalid/zoo/",
                    )
                except builder.SyndicationError:
                    return True
                relative = path.relative_to(repository).as_posix()
                return all(
                    item.get("path") != relative
                    for item in descriptors
                )

            lease_rejected = rejected(
                "unauthorized",
                "shards",
                unauthorized,
            )
            proof_rejected = rejected(
                "live-proof",
                "fold",
                live_proof,
            )
        rollout = getattr(builder, "SOAK_ROLLOUT", {})
        frame_control = getattr(builder, "FRAME_CONTROL_SCHEMA", {})
        disabled_proof = builder.proof_of_fold_metadata(
            {"data_upserts": []}
        )
        soak_declared = (
            rollout.get("phase") == "initial-public-soak"
            and rollout.get("live_race") is False
            and rollout.get("synthetic_proofs") == "tests-only"
            and frame_control.get("public_soak_allowed")
            == ["observer", "assigned"]
            and frame_control.get("public_soak_default") == "observer"
            and disabled_proof.get("status") == "disabled-observer"
            and disabled_proof.get("synthetic_test_only") is False
        )
        passed = lease_rejected and proof_rejected and soak_declared
        detail = (
            "unauthorized leases rejected and proof-of-fold disabled in soak"
            if passed
            else "lease_rejected={} proof_rejected={} soak_declared={}".format(
                lease_rejected,
                proof_rejected,
                soak_declared,
            )
        )
    except Exception as error:
        passed = False
        detail = str(error)
    return _result("fold.authorized-leases-soak", passed, detail)


def run_expanded_checks(root: Path) -> List[CheckResult]:
    functions = [
        check_expanded_files,
        check_mcp_parity,
        check_mcp_writes_default,
        check_mcp_first_use,
        check_syndication_chain,
        check_syndication_feed_ids,
        check_syndication_idempotence,
        check_sync_adversarial,
        check_attention_contracts,
        check_attention_lineage,
        check_attention_shards_dimensions,
        check_fold_safety,
    ]
    checks = []
    for function in functions:
        try:
            checks.append(function(root))
        except Exception as error:
            checks.append(
                _result(
                    "expanded.{}".format(function.__name__),
                    False,
                    "unmeasurable: {}".format(error),
                )
            )
    return checks


def check_gallery_bridge_syntax(root: Path) -> CheckResult:
    try:
        source = _read_text(root / "index.html")
        match = re.search(
            r"\bvar\s+bridgeScript\s*=\s*(.*?);"
            r"\s*function\s+wrapWithBridge\b",
            source,
            re.DOTALL,
        )
        if not match:
            raise GateError("gallery bridgeScript expression is missing")
        node = shutil.which("node")
        if not node:
            raise GateError("Node.js is unavailable")
        expression = match.group(1).strip()
        completed = subprocess.run(
            [
                node,
                "-e",
                (
                    "const source=eval(process.argv[1]);"
                    "new Function(source);"
                    "if(!source.includes('rappterzoo-heartbeat'))"
                    "throw new Error('heartbeat missing');"
                    "if(!source.includes('rappterzoo-cmd'))"
                    "throw new Error('command bridge missing');"
                ),
                expression,
            ],
            cwd=str(root),
            capture_output=True,
            text=True,
            check=False,
            timeout=15,
        )
        passed = completed.returncode == 0
        detail = (
            "iframe bridge expression and injected program parse"
            if passed
            else completed.stderr.strip() or completed.stdout.strip()
        )
    except (OSError, ValueError, GateError) as error:
        passed = False
        detail = str(error)
    return _result("gallery.iframe-bridge-syntax", passed, detail)


def _ui_runtime_results(payload: Dict[str, Any]) -> List[CheckResult]:
    mapping = [
        ("gallery.boot-errors", "galleryBoot"),
        ("gallery.offline-cache", "galleryCacheOffline"),
        ("gallery.storage-denied", "galleryStorageDenied"),
        ("gallery.voting-live", "galleryVoting"),
        ("gallery.mobile-targets", "galleryMobileTargets"),
        ("gallery.iframe-bridge-runtime", "galleryBridgeRuntime"),
        ("digg.storage-denied", "diggStorageDenied"),
        ("digg.canvas-accessible-state", "diggCanvasA11y"),
    ]
    results = []
    for name, key in mapping:
        value = payload.get(key, {})
        passed = isinstance(value, dict) and value.get("pass") is True
        detail = json.dumps(
            value if value else {"fatal": payload.get("fatal")},
            sort_keys=True,
            separators=(",", ":"),
        )
        results.append(_result(name, passed, detail[:1800]))
    return results


def run_gallery_digg_browser_checks(
    root: Path,
    ready_timeout_ms: int = 15000,
    playwright_cwd: Optional[Path] = None,
) -> List[CheckResult]:
    names = [
        "gallery.boot-errors",
        "gallery.offline-cache",
        "gallery.storage-denied",
        "gallery.voting-live",
        "gallery.mobile-targets",
        "gallery.iframe-bridge-runtime",
        "digg.storage-denied",
        "digg.canvas-accessible-state",
    ]

    def all_failed(detail: str) -> List[CheckResult]:
        return [_result(name, False, detail) for name in names]

    if not (root / "index.html").is_file():
        return all_failed("gallery is missing")
    if not (root / "apps/data-tools/digg.html").is_file():
        return all_failed("Digg is missing")
    node = shutil.which("node")
    if not node:
        return all_failed("Node.js is unavailable; Playwright cannot be measured")
    module_cwd = playwright_cwd or root
    probe = subprocess.run(
        [node, "-e", "require.resolve('playwright')"],
        cwd=str(module_cwd),
        capture_output=True,
        text=True,
        check=False,
    )
    if probe.returncode != 0:
        return all_failed(
            "repo-installed Playwright is unavailable: "
            + (probe.stderr.strip() or probe.stdout.strip())
        )
    with _serve(root) as base_url:
        try:
            completed = subprocess.run(
                [
                    node,
                    "-e",
                    GALLERY_DIGG_BROWSER_SCRIPT,
                    base_url,
                    str(ready_timeout_ms),
                ],
                cwd=str(module_cwd),
                capture_output=True,
                text=True,
                check=False,
                timeout=max(60, int(ready_timeout_ms / 1000) + 45),
            )
        except subprocess.TimeoutExpired:
            return all_failed("gallery/Digg Playwright runtime timed out")
    lines = [
        line.strip()
        for line in completed.stdout.splitlines()
        if line.strip()
    ]
    if not lines:
        return all_failed(
            "gallery/Digg Playwright produced no JSON: "
            + (completed.stderr.strip() or "unknown failure")
        )
    try:
        payload = json.loads(lines[-1])
    except ValueError:
        return all_failed("invalid gallery/Digg Playwright JSON")
    if not isinstance(payload, dict):
        return all_failed("gallery/Digg Playwright payload is not an object")
    return _ui_runtime_results(payload)


def _browser_results_from_payload(payload: Dict[str, Any]) -> List[CheckResult]:
    mapping = [
        ("runtime.ready-network-errors", "ready"),
        ("runtime.playback-wall-clock", "playback"),
        ("runtime.mode-filter", "modeFilter"),
        ("runtime.keyboard", "keyboard"),
        ("runtime.tamper-restore", "tamperRestore"),
        ("runtime.export", "export"),
        ("runtime.mobile-390x844", "mobile"),
    ]
    results = []
    top_level = {
        "errors": payload.get("errors", []),
        "externalRequests": payload.get("externalRequests", []),
        "dataRequests": payload.get("dataRequests", []),
    }
    for name, key in mapping:
        value = payload.get(key, {})
        passed = isinstance(value, dict) and value.get("pass") is True
        detail_value = value if value else top_level
        detail = json.dumps(detail_value, sort_keys=True, separators=(",", ":"))
        results.append(_result(name, passed, detail[:1200]))
    return results


def run_browser_checks(
    root: Path,
    app_relative: Path = APP_RELATIVE,
    ready_timeout_ms: int = 12000,
    playwright_cwd: Optional[Path] = None,
) -> List[CheckResult]:
    app_path = root / app_relative
    names = [
        "runtime.ready-network-errors",
        "runtime.playback-wall-clock",
        "runtime.mode-filter",
        "runtime.keyboard",
        "runtime.tamper-restore",
        "runtime.export",
        "runtime.mobile-390x844",
    ]

    def all_failed(detail: str) -> List[CheckResult]:
        return [_result(name, False, detail) for name in names]

    if not app_path.is_file():
        return all_failed("app is missing")
    node = shutil.which("node")
    if not node:
        return all_failed("Node.js is unavailable; Playwright cannot be measured")
    module_cwd = playwright_cwd or root
    probe = subprocess.run(
        [node, "-e", "require.resolve('playwright')"],
        cwd=str(module_cwd),
        capture_output=True,
        text=True,
        check=False,
    )
    if probe.returncode != 0:
        return all_failed(
            "repo-installed Playwright is unavailable: "
            + (probe.stderr.strip() or probe.stdout.strip())
        )

    handler = partial(QuietHandler, directory=str(root))
    server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        port = server.server_address[1]
        url = "http://127.0.0.1:{}{}".format(port, "/" + app_relative.as_posix())
        try:
            completed = subprocess.run(
                [
                    node,
                    "-e",
                    BROWSER_SCRIPT,
                    url,
                    str(ready_timeout_ms),
                ],
                cwd=str(module_cwd),
                capture_output=True,
                text=True,
                check=False,
                timeout=max(30, int(ready_timeout_ms / 1000) + 20),
            )
        except subprocess.TimeoutExpired:
            return all_failed("Playwright runtime timed out")
        output_lines = [
            line.strip()
            for line in completed.stdout.splitlines()
            if line.strip()
        ]
        if not output_lines:
            return all_failed(
                "Playwright produced no JSON: "
                + (completed.stderr.strip() or "unknown failure")
            )
        try:
            payload = json.loads(output_lines[-1])
        except ValueError:
            return all_failed("invalid Playwright JSON: " + output_lines[-1][:500])
        if not isinstance(payload, dict):
            return all_failed("Playwright payload is not an object")
        if "fatal" in payload:
            return all_failed(str(payload["fatal"]))
        return _browser_results_from_payload(payload)
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


def run_gate(
    root: Path = ROOT,
    app_relative: Path = APP_RELATIVE,
) -> List[CheckResult]:
    checks = run_static_checks(root, app_relative)
    checks.extend(run_expanded_checks(root))
    checks.append(check_gallery_bridge_syntax(root))
    checks.extend(run_gallery_digg_browser_checks(root))
    checks.extend(run_browser_checks(root, app_relative))
    return checks


def _print_report(checks: Iterable[CheckResult], as_json: bool = False) -> None:
    materialized = list(checks)
    passed = all(check.passed for check in materialized)
    if as_json:
        print(
            json.dumps(
                {
                    "pass": passed,
                    "passed": sum(check.passed for check in materialized),
                    "total": len(materialized),
                    "checks": [asdict(check) for check in materialized],
                },
                indent=2,
                sort_keys=True,
            )
        )
        return
    for check in materialized:
        print(
            "[{}] {}: {}".format(
                "PASS" if check.passed else "FAIL",
                check.name,
                check.detail,
            )
        )
    print(
        "MOONSHOT GATE: {} ({}/{})".format(
            "PASS" if passed else "FAIL",
            sum(check.passed for check in materialized),
            len(materialized),
        )
    )


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="Fail-closed Organism Observatory acceptance gate",
    )
    parser.add_argument(
        "--root",
        type=Path,
        default=ROOT,
        help="repository root (default: inferred from this script)",
    )
    parser.add_argument(
        "--app",
        type=Path,
        default=APP_RELATIVE,
        help="app path relative to the repository root",
    )
    parser.add_argument("--json", action="store_true", help="emit JSON")
    arguments = parser.parse_args(argv)
    root = arguments.root.resolve()
    checks = run_gate(root, arguments.app)
    _print_report(checks, arguments.json)
    return 0 if all(check.passed for check in checks) else 1


if __name__ == "__main__":
    sys.exit(main())
