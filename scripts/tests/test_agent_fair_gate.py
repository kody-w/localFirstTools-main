"""Mutation and reporting tests for the Agent World's Fair gate."""

import copy
import json
import re
import shutil
import subprocess
import sys
import uuid
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace

import pytest


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))

import agent_fair_gate as gate


@contextmanager
def fixture_root(relative_paths):
    root = Path(__file__).resolve().parent / (
        ".agent-fair-gate-" + uuid.uuid4().hex
    )
    root.mkdir()
    try:
        for relative in relative_paths:
            source = ROOT / relative
            target = root / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            if source.is_dir():
                shutil.copytree(source, target)
            else:
                shutil.copy2(source, target)
        yield root
    finally:
        shutil.rmtree(root, ignore_errors=True)


def result_map(results):
    return {result.name: result for result in results}


def write_events(path, events):
    path.write_bytes(gate.fair_builder._event_bytes(events))


def core_paths():
    return [
        "apps/agent-fair",
        "apps/agent-park/park-state.json",
        "apps/agent-park/events.jsonl",
        "apps/organism-frames.jsonl",
    ]


def rewind_to_prepared_phase(root):
    ledger_path = root / gate.ORGANISM_LEDGER_RELATIVE
    raw_lines = [
        line
        for line in ledger_path.read_text(encoding="utf-8").splitlines()
        if line
    ]
    frames = [json.loads(line) for line in raw_lines]
    release_indexes = [
        index
        for index, frame in enumerate(frames)
        if (
            frame.get("payload", {}).get("event")
            == "agent-worlds-fair-release"
            or str(
                frame.get("payload", {}).get("event_id", "")
            ).startswith(gate.RELEASE_EVENT_PREFIX)
        )
    ]
    if release_indexes:
        cutoff = release_indexes[0]
        frames = frames[:cutoff]
        ledger_path.write_text(
            "".join(line + "\n" for line in raw_lines[:cutoff]),
            encoding="utf-8",
        )
        projection_path = root / gate.ORGANISM_PROJECTION_RELATIVE
        if projection_path.is_file():
            gate.organism_ledger.write_projection(frames, projection_path)

    index_path = root / gate.SYNDICATION_INDEX_RELATIVE
    snapshot_path = root / gate.SYNDICATION_SNAPSHOT_RELATIVE
    if index_path.is_file() and snapshot_path.is_file():
        index = gate._json(index_path)
        entries = index["deltas"]
        deltas = [
            gate._json(
                root / "apps/syndication" / entry["path"]
            )
            for entry in entries
        ]
        cutoff = next(
            (
                offset
                for offset, delta in enumerate(deltas)
                if any(
                    type(frame) is dict
                    and (
                        frame.get("payload", {}).get("event")
                        == "agent-worlds-fair-release"
                        or str(
                            frame.get("payload", {}).get("event_id", "")
                        ).startswith(gate.RELEASE_EVENT_PREFIX)
                    )
                    for frame in delta.get("changes", {}).get(
                        "frame_appends",
                        [],
                    )
                )
            ),
            len(deltas),
        )
        for entry in entries[cutoff:]:
            (root / "apps/syndication" / entry["path"]).unlink()
        entries = entries[:cutoff]
        deltas = deltas[:cutoff]
        replay = gate.build_syndication.replay_immutable_deltas(deltas)
        latest = entries[-1]
        head = {
            "path": latest["path"],
            "sequence": latest["sequence"],
            "sha256": latest["sha256"],
            "url": latest["url"],
        }
        index["deltas"] = entries
        index["delta_count"] = len(entries)
        index["head"] = head
        index["cursor"]["head_seq"] = latest["sequence"]
        index["next_frame_challenge_seed"] = latest["block"][
            "next_frame_challenge_seed"
        ]
        index_path.write_text(
            json.dumps(index, sort_keys=True, separators=(",", ":")) + "\n",
            encoding="utf-8",
        )
        snapshot = gate._json(snapshot_path)
        snapshot.update({
            "apps": replay["apps"],
            "data_objects": replay["data_objects"],
            "data_tombstones": replay["data_tombstones"],
            "frames": replay["frames"],
            "head": head,
            "tombstones": replay["tombstones"],
            "counts": {
                "active_apps": len(replay["apps"]),
                "attention_data_objects": len(replay["data_objects"]),
                "data_tombstones": len(replay["data_tombstones"]),
                "frames": len(replay["frames"]),
                "tombstones": len(replay["tombstones"]),
            },
            "checkpoint": {
                "delta_sha256": latest["sha256"],
                "next_frame_challenge_seed": latest["block"][
                    "next_frame_challenge_seed"
                ],
                "since_seq": latest["sequence"],
            },
        })
        snapshot_path.write_text(
            json.dumps(snapshot, sort_keys=True, separators=(",", ":"))
            + "\n",
            encoding="utf-8",
        )

    assert gate.resolve_release_phase(root) == "prepared"


def next_organism_utc(root):
    frames = gate.organism_ledger.read_frames(
        root / gate.ORGANISM_LEDGER_RELATIVE
    )
    return (
        datetime.strptime(
            frames[-1]["utc"],
            "%Y-%m-%dT%H:%M:%S.%fZ",
        ).replace(tzinfo=timezone.utc)
        + timedelta(minutes=1)
    ).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def set_release_environment(monkeypatch, release_utc):
    release_epoch = int(
        datetime.fromisoformat(
            release_utc.replace("Z", "+00:00")
        ).timestamp()
    )
    evidence = {
        "actor": "fair-gate-test",
        "attestation_sha256": "1" * 64,
        "aud": gate.OIDC_AUDIENCE,
        "environment": gate.OIDC_ENVIRONMENT,
        "event_name": gate.OIDC_EVENT_NAME,
        "exp": release_epoch + 300,
        "iss": gate.OIDC_ISSUER,
        "nbf": release_epoch - 10,
        "ref": gate.OIDC_REF,
        "repository": gate.OIDC_REPOSITORY,
        "run_id": "123456",
        "workflow_ref": gate.OIDC_WORKFLOW_REF,
    }
    monkeypatch.setattr(
        gate.fair_builder,
        "_github_oidc_approval_evidence",
        lambda: copy.deepcopy(evidence),
    )
    return evidence


def browser_fixture_paths():
    return [
        gate.APP_RELATIVE,
        gate.SERVICE_WORKER_RELATIVE,
        "apps/agent-fair",
        gate.ORGANISM_PROJECTION_RELATIVE,
        "node_modules",
    ]


SERVICE_WORKER_PROBE = r"""
const { chromium } = require("playwright");
const target = process.argv[1];
const probe = process.argv[2];
const cacheName = "agent-worlds-fair-v4-buzzsaw-20260816";
const oldCacheName = "agent-worlds-fair-v3-release-20260816";
const foreignCacheName = "unrelated-rappterzoo-cache-probe";
let browser;

async function waitFair(page) {
  await page.waitForFunction(
    () => window.__AGENT_FAIR_TEST__
      && typeof window.__AGENT_FAIR_TEST__.ready === "function",
    null,
    { timeout: 15000 }
  );
  await page.evaluate(() => window.__AGENT_FAIR_TEST__.ready());
}

async function requestStatus(page) {
  return page.evaluate(async () => {
    const registration = await navigator.serviceWorker.ready;
    const worker = navigator.serviceWorker.controller
      || registration.active
      || registration.waiting;
    if (!worker) throw new Error("active worker unavailable");
    return new Promise((resolve, reject) => {
      const channel = new MessageChannel();
      const timer = setTimeout(
        () => reject(new Error("cache status timeout")),
        5000
      );
      channel.port1.onmessage = (event) => {
        clearTimeout(timer);
        resolve(event.data);
      };
      worker.postMessage(
        { type: "agent-fair-cache-status" },
        [channel.port2]
      );
    });
  });
}

async function inspectInstalledCache(page) {
  return page.evaluate(async (names) => {
    const expectedUrls = [
      "/apps/3d-immersive/agent-worlds-fair.html",
      "/apps/3d-immersive/agent-worlds-fair-sw.js",
      "/apps/agent-fair/fair-state.json",
      "/apps/agent-fair/events.jsonl",
      "/apps/agent-fair/agent-contract.json",
      "/apps/agent-fair/district.json",
      "/apps/organism-frames.json"
    ].map((path) => location.origin + path);
    const keys = await caches.keys();
    const cache = await caches.open(names.current);
    const requests = await cache.keys();
    const urls = requests.map((request) => request.url);
    const digests = [];
    for (const request of requests) {
      const response = await cache.match(request);
      const expected = response.headers.get(
        "X-Agent-Fair-Cache-SHA256"
      );
      const bytes = await response.clone().arrayBuffer();
      const digest = await crypto.subtle.digest("SHA-256", bytes);
      const actual = Array.from(
        new Uint8Array(digest),
        (value) => value.toString(16).padStart(2, "0")
      ).join("");
      digests.push({ url: request.url, expected, actual });
    }
    const beforeUnknown = [...urls].sort();
    const unknown = await fetch("./agent-worlds-fair-missing-probe.txt");
    const afterUnknown = (await cache.keys())
      .map((request) => request.url)
      .sort();
    const optionalUrl = location.origin + "/apps/organism-frames.json";
    const optionalResponse = await cache.match(optionalUrl);
    await cache.delete(optionalUrl);
    const optionalMissing = await new Promise((resolve, reject) => {
      const registrationPromise = navigator.serviceWorker.ready;
      registrationPromise.then((registration) => {
        const worker = navigator.serviceWorker.controller
          || registration.active
          || registration.waiting;
        const channel = new MessageChannel();
        const timer = setTimeout(
          () => reject(new Error("optional status timeout")),
          5000
        );
        channel.port1.onmessage = (event) => {
          clearTimeout(timer);
          resolve(event.data);
        };
        worker.postMessage(
          { type: "agent-fair-cache-status" },
          [channel.port2]
        );
      }, reject);
    });
    await cache.put(optionalUrl, optionalResponse);
    const workerUrl = (
      location.origin
      + "/apps/3d-immersive/agent-worlds-fair-sw.js"
    );
    await cache.put(
      workerUrl,
      new Response("corrupt", {
        status: 200,
        headers: { "Content-Type": "text/javascript" }
      })
    );
    const corrupt = await new Promise((resolve, reject) => {
      navigator.serviceWorker.ready.then((registration) => {
        const worker = navigator.serviceWorker.controller
          || registration.active
          || registration.waiting;
        const channel = new MessageChannel();
        const timer = setTimeout(
          () => reject(new Error("corrupt status timeout")),
          5000
        );
        channel.port1.onmessage = (event) => {
          clearTimeout(timer);
          resolve(event.data);
        };
        worker.postMessage(
          { type: "agent-fair-cache-status" },
          [channel.port2]
        );
      }, reject);
    });
    return {
      cacheKeys: keys,
      cacheUrls: urls,
      expectedUrls,
      digests,
      unknownStatus: unknown.status,
      unknownCacheUnchanged: (
        JSON.stringify(beforeUnknown) === JSON.stringify(afterUnknown)
      ),
      optionalMissing,
      corrupt,
      corruptStillCached: Boolean(await cache.match(workerUrl))
    };
  }, {
    current: cacheName,
    old: oldCacheName,
    foreign: foreignCacheName
  });
}

(async () => {
  browser = await chromium.launch({ headless: true });
  const context = await browser.newContext();
  const page = await context.newPage();
  await page.goto(probe, { waitUntil: "domcontentloaded" });
  await page.evaluate(async ([oldName, foreignName]) => {
    await caches.open(oldName);
    await caches.open(foreignName);
  }, [oldCacheName, foreignCacheName]);
  await page.goto(target, {
    waitUntil: "domcontentloaded",
    timeout: 15000
  });
  await waitFair(page);
  await page.evaluate(() => navigator.serviceWorker.ready);
  await page.reload({
    waitUntil: "domcontentloaded",
    timeout: 15000
  });
  await waitFair(page);
  const status = await requestStatus(page);
  const cache = await inspectInstalledCache(page);
  await context.close();

  const coldContext = await browser.newContext();
  const coldPage = await coldContext.newPage();
  await coldPage.goto(probe, { waitUntil: "domcontentloaded" });
  const coldBefore = await coldPage.evaluate(async () => ({
    caches: await caches.keys(),
    registrations: (
      await navigator.serviceWorker.getRegistrations()
    ).length
  }));
  await coldContext.setOffline(true);
  let coldNavigationFailed = false;
  try {
    await coldPage.goto(target, {
      waitUntil: "domcontentloaded",
      timeout: 10000
    });
  } catch (_) {
    coldNavigationFailed = true;
  }
  await coldContext.close();

  const ownKeys = cache.cacheKeys.filter(
    (key) => key.startsWith("agent-worlds-fair-")
  );
  const results = {
    cacheVersionExact: (
      ownKeys.length === 1 && ownKeys[0] === cacheName
    ),
    exactAssetCoverage: (
      cache.cacheUrls.length === 7
      && [...cache.cacheUrls].sort().join("\n")
        === [...cache.expectedUrls].sort().join("\n")
    ),
    cacheReady: (
      status.ready === true
      && status.missingRequired.length === 0
      && status.missingOptional.length === 0
      && status.unexpected.length === 0
    ),
    oldOwnCacheRemoved: !cache.cacheKeys.includes(oldCacheName),
    foreignCachePreserved: cache.cacheKeys.includes(foreignCacheName),
    cacheDigestsValid: (
      cache.digests.length === 7
      && cache.digests.every(
        (value) => /^[0-9a-f]{64}$/.test(value.expected || "")
          && value.expected === value.actual
      )
    ),
    unknownRequestPassesThrough: (
      cache.unknownStatus === 404 && cache.unknownCacheUnchanged
    ),
    optionalLossRejected: (
      cache.optionalMissing.ready === false
      && cache.optionalMissing.missingOptional.length === 1
    ),
    corruptEntryRejected: (
      cache.corrupt.ready === false
      && cache.corrupt.invalidRequired.includes(
        new URL(
          "/apps/3d-immersive/agent-worlds-fair-sw.js",
          target
        ).href
      )
      && cache.corruptStillCached === false
    ),
    coldOfflineTruthful: (
      coldBefore.caches.length === 0
      && coldBefore.registrations === 0
      && coldNavigationFailed
    )
  };
  await browser.close();
  console.log(JSON.stringify({ results, status, cache, coldBefore }));
})().catch(async (error) => {
  try {
    if (browser) await browser.close();
  } catch (_) {}
  console.error(error.stack || error.message);
  process.exit(1);
});
"""


SERVICE_WORKER_UPDATE_PROBE = r"""
const { chromium } = require("playwright");
const { createHash } = require("crypto");
const fs = require("fs");
const target = process.argv[1];
const htmlPath = process.argv[2];
const workerPath = process.argv[3];
const cacheName = "agent-worlds-fair-v4-buzzsaw-20260816";
const legacyCacheName = "agent-worlds-fair-v3-release-20260816";
const currentHtml = fs.readFileSync(htmlPath, "utf8");
const currentWorker = fs.readFileSync(workerPath, "utf8");
const markerName = "agent-fair-shell-revision";
let browser;

function variant(label) {
  if (currentHtml.includes('name="' + markerName + '"')) {
    throw new Error("source HTML already contains the test revision marker");
  }
  return currentHtml.replace(
    "</head>",
    '<meta name="' + markerName + '" content="' + label + '">\n</head>'
  );
}

function sha256(value) {
  return createHash("sha256").update(value, "utf8").digest("hex");
}

function writeRevision(path, value, seconds) {
  fs.writeFileSync(path, value);
  fs.utimesSync(path, seconds, seconds);
}

async function waitFair(page) {
  await page.waitForFunction(
    () => window.__AGENT_FAIR_TEST__
      && typeof window.__AGENT_FAIR_TEST__.ready === "function",
    null,
    { timeout: 20000 }
  );
  await page.evaluate(() => window.__AGENT_FAIR_TEST__.ready());
}

async function revision(page) {
  return page.evaluate(
    (name) => document.querySelector(
      'meta[name="' + name + '"]'
    )?.content || "",
    markerName
  );
}

async function cacheEvidence(page) {
  return page.evaluate(async (name) => {
    const expectedUrls = [
      "/apps/3d-immersive/agent-worlds-fair.html",
      "/apps/3d-immersive/agent-worlds-fair-sw.js",
      "/apps/agent-fair/fair-state.json",
      "/apps/agent-fair/events.jsonl",
      "/apps/agent-fair/agent-contract.json",
      "/apps/agent-fair/district.json",
      "/apps/organism-frames.json"
    ].map((path) => location.origin + path);
    const keys = await caches.keys();
    const cache = await caches.open(name);
    const requests = await cache.keys();
    const htmlUrl = (
      location.origin
      + "/apps/3d-immersive/agent-worlds-fair.html"
    );
    const response = await cache.match(htmlUrl);
    const text = await response.clone().text();
    const bytes = new TextEncoder().encode(text);
    const digest = await crypto.subtle.digest("SHA-256", bytes);
    const bodyHash = Array.from(
      new Uint8Array(digest),
      (value) => value.toString(16).padStart(2, "0")
    ).join("");
    return {
      bodyHash,
      digestHeader: response.headers.get(
        "X-Agent-Fair-Cache-SHA256"
      ),
      keys,
      revision: new DOMParser().parseFromString(
        text,
        "text/html"
      ).querySelector(
        'meta[name="agent-fair-shell-revision"]'
      )?.content || "",
      urls: requests.map((request) => request.url),
      expectedUrls
    };
  }, cacheName);
}

async function updateRegistration(page) {
  return page.evaluate(async () => {
    const registration = await navigator.serviceWorker.getRegistration();
    const previous = registration?.active;
    if (!registration || !previous) {
      throw new Error("legacy active worker is unavailable");
    }
    await registration.update();
    const next = registration.installing || registration.waiting;
    if (!next || next === previous) {
      throw new Error("updated worker was not discovered");
    }
    if (next.state !== "activated") {
      await new Promise((resolve, reject) => {
        const timeout = setTimeout(
          () => reject(new Error("updated worker activation timed out")),
          15000
        );
        next.addEventListener("statechange", () => {
          if (next.state === "activated") {
            clearTimeout(timeout);
            resolve();
          } else if (next.state === "redundant") {
            clearTimeout(timeout);
            reject(new Error("updated worker became redundant"));
          }
        });
      });
    }
    return {
      previous: previous.scriptURL,
      updated: registration.active?.scriptURL || ""
    };
  });
}

const legacyWorker = `
"use strict";
const CACHE_NAME = "${legacyCacheName}";
const HTML_URL = "./agent-worlds-fair.html";
self.addEventListener("install", (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME)
      .then((cache) => cache.add(HTML_URL))
      .then(() => self.skipWaiting())
  );
});
self.addEventListener("activate", (event) => {
  event.waitUntil(self.clients.claim());
});
self.addEventListener("message", (event) => {
  if (event.data?.type !== "agent-fair-cache-status") return;
  event.waitUntil(
    caches.open(CACHE_NAME).then(async (cache) => {
      const cached = await cache.keys();
      event.ports[0]?.postMessage({
        type: "agent-fair-cache-status",
        cacheName: CACHE_NAME,
        cached: cached.map((request) => request.url),
        missingRequired: [],
        ready: false
      });
    })
  );
});
self.addEventListener("fetch", (event) => {
  if (event.request.method !== "GET") return;
  const url = new URL(event.request.url);
  if (url.pathname.endsWith("/agent-worlds-fair.html")) {
    event.respondWith(
      caches.match(event.request, { ignoreSearch: true })
        .then((cached) => cached || fetch(event.request))
    );
  }
});
`;

(async () => {
  const oldHtml = variant("old-shell");
  const updatedHtml = variant("updated-shell");
  const futureHtml = variant("future-shell");
  const baseTime = Math.floor(Date.now() / 1000) + 2;
  writeRevision(htmlPath, oldHtml, baseTime);
  writeRevision(workerPath, legacyWorker, baseTime);

  browser = await chromium.launch({ headless: true });
  const context = await browser.newContext();
  const page = await context.newPage();
  await page.goto(target, {
    waitUntil: "domcontentloaded",
    timeout: 20000
  });
  await waitFair(page);
  await page.reload({
    waitUntil: "domcontentloaded",
    timeout: 20000
  });
  await waitFair(page);
  const legacyRevision = await revision(page);

  writeRevision(htmlPath, updatedHtml, baseTime + 2);
  writeRevision(workerPath, currentWorker, baseTime + 2);
  const registration = await updateRegistration(page);
  const updatedCache = await cacheEvidence(page);

  await context.setOffline(true);
  await page.reload({
    waitUntil: "domcontentloaded",
    timeout: 20000
  });
  await waitFair(page);
  const updatedOfflineRevision = await revision(page);

  await context.setOffline(false);
  writeRevision(htmlPath, futureHtml, baseTime + 4);
  await page.reload({
    waitUntil: "domcontentloaded",
    timeout: 20000
  });
  await waitFair(page);
  const futureOnlineRevision = await revision(page);
  await page.waitForFunction(
    async ([name, expected]) => {
      const cache = await caches.open(name);
      const response = await cache.match(
        location.origin
        + "/apps/3d-immersive/agent-worlds-fair.html"
      );
      return response && (await response.clone().text()).includes(expected);
    },
    [cacheName, 'content="future-shell"'],
    { timeout: 10000 }
  );
  const futureCache = await cacheEvidence(page);

  await context.setOffline(true);
  await page.reload({
    waitUntil: "domcontentloaded",
    timeout: 20000
  });
  await waitFair(page);
  const futureOfflineRevision = await revision(page);

  const sorted = (values) => [...values].sort().join("\n");
  const results = {
    legacyShellWasControlled: legacyRevision === "old-shell",
    cacheVersionMigrated: (
      updatedCache.keys.length === 1
      && updatedCache.keys[0] === cacheName
    ),
    updateInstalledChangedWorker: (
      registration.previous === registration.updated
      && sha256(legacyWorker) !== sha256(currentWorker)
    ),
    updateRepopulatedExactAssets: (
      updatedCache.urls.length === 7
      && sorted(updatedCache.urls) === sorted(updatedCache.expectedUrls)
    ),
    updateReplacedShellBytes: (
      updatedCache.revision === "updated-shell"
      && updatedCache.bodyHash === sha256(updatedHtml)
      && updatedCache.digestHeader === updatedCache.bodyHash
    ),
    updatedShellWorksOffline: (
      updatedOfflineRevision === "updated-shell"
    ),
    htmlOnlyReloadRefreshesShell: (
      futureOnlineRevision === "future-shell"
      && futureCache.revision === "future-shell"
      && futureCache.bodyHash === sha256(futureHtml)
      && futureCache.digestHeader === futureCache.bodyHash
    ),
    htmlOnlyRefreshWorksOffline: (
      futureOfflineRevision === "future-shell"
    )
  };
  await browser.close();
  console.log(JSON.stringify({
    results,
    hashes: {
      currentHtml: sha256(currentHtml),
      currentWorker: sha256(currentWorker),
      updatedHtml: sha256(updatedHtml),
      futureHtml: sha256(futureHtml)
    }
  }));
})().catch(async (error) => {
  try {
    if (browser) await browser.close();
  } catch (_) {}
  console.error(error.stack || error.message);
  process.exitCode = 1;
}).finally(() => {
  fs.writeFileSync(htmlPath, currentHtml);
  fs.writeFileSync(workerPath, currentWorker);
});
"""


def service_worker_probe(root):
    node = shutil.which("node")
    assert node is not None, "node is required for service-worker measurement"
    package = root / "node_modules/playwright/package.json"
    assert package.is_file(), "repository Playwright is required"
    probe_path = root / "probe.html"
    probe_path.write_text("<!doctype html><title>probe</title>", encoding="utf-8")
    with gate._serve(root) as base_url:
        process = subprocess.run(
            [
                node,
                "-e",
                SERVICE_WORKER_PROBE,
                base_url + gate.APP_RELATIVE.as_posix(),
                base_url + "probe.html",
            ],
            cwd=str(root),
            text=True,
            capture_output=True,
            timeout=90,
            check=False,
        )
    assert process.returncode == 0, process.stderr
    return json.loads(process.stdout)["results"]


def service_worker_update_probe(root):
    node = shutil.which("node")
    assert node is not None, "node is required for service-worker measurement"
    package = root / "node_modules/playwright/package.json"
    assert package.is_file(), "repository Playwright is required"
    with gate._serve(root) as base_url:
        process = subprocess.run(
            [
                node,
                "-e",
                SERVICE_WORKER_UPDATE_PROBE,
                base_url + gate.APP_RELATIVE.as_posix(),
                str(root / gate.APP_RELATIVE),
                str(root / gate.SERVICE_WORKER_RELATIVE),
            ],
            cwd=str(root),
            text=True,
            capture_output=True,
            timeout=120,
            check=False,
        )
    assert process.returncode == 0, process.stderr
    return json.loads(process.stdout)


def test_static_inventory_passes_for_resolved_release_phase():
    phase = gate.resolve_release_phase(ROOT)
    results = gate.run_static_checks(ROOT, phase)
    assert len(results) == len(gate.STATIC_CHECKS)
    assert [result.name for result in results] == [
        name for name, _check in gate.STATIC_CHECKS
    ]
    assert len({result.name for result in results}) == len(results)
    assert all(result.passed for result in results), [
        (result.name, result.detail)
        for result in results
        if not result.passed
    ]


@pytest.mark.parametrize(
    "mutation,check_name",
    [
        ("event", "fair.bundle-exact"),
        ("duplicate-agent", "fair.submissions"),
        ("resource-cap", "fair.safety-resource-caps"),
        ("weights", "fair.voting-scoring"),
        ("economy", "fair.synthetic-balance"),
        ("winner", "fair.constrained-winners"),
        ("authority", "fair.customer-authority"),
    ],
)
def test_important_fair_mutations_turn_red(mutation, check_name):
    checks = dict(gate.STATIC_CHECKS)
    with fixture_root(core_paths()) as root:
        baseline = gate._run_check(
            check_name,
            lambda: checks[check_name](root),
        )
        assert baseline.passed, baseline.detail

        if mutation in {
            "event",
            "duplicate-agent",
            "resource-cap",
            "weights",
        }:
            events = gate._json_lines(root / gate.EVENTS_RELATIVE)
            if mutation == "event":
                events[2]["payload"]["submission"]["attractions"][0][
                    "novelty"
                ] = 1
            elif mutation == "duplicate-agent":
                submissions = [
                    event
                    for event in events
                    if event["kind"] == "fair.submission"
                ]
                submissions[1]["payload"]["submission"]["agent"][
                    "identity_id"
                ] = submissions[0]["payload"]["submission"]["agent"][
                    "identity_id"
                ]
            elif mutation == "resource-cap":
                submission = next(
                    event
                    for event in events
                    if event["kind"] == "fair.submission"
                )
                submission["payload"]["submission"]["attractions"][0][
                    "resource_request"
                ]["attention"] = 21
            else:
                evaluation = next(
                    event
                    for event in events
                    if event["kind"] == "fair.evaluation"
                )
                evaluation["payload"]["score_weights_bps"]["admissions"] = 4499
            write_events(root / gate.EVENTS_RELATIVE, events)
        elif mutation == "economy":
            state = gate._json(root / gate.STATE_RELATIVE)
            state["economy"]["total_credits"] -= 1
            (root / gate.STATE_RELATIVE).write_text(
                json.dumps(state, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
        elif mutation == "winner":
            state = gate._json(root / gate.STATE_RELATIVE)
            state["winners"][0], state["winners"][1] = (
                state["winners"][1],
                state["winners"][0],
            )
            (root / gate.STATE_RELATIVE).write_text(
                json.dumps(state, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
        else:
            contract = gate._json(root / gate.CONTRACT_RELATIVE)
            contract["control_boundary"]["vendor_shutdown"] = True
            (root / gate.CONTRACT_RELATIVE).write_text(
                json.dumps(contract, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )

        result = gate._run_check(
            check_name,
            lambda: checks[check_name](root),
        )
        assert result.passed is False


@pytest.mark.parametrize(
    "mutation,check_name",
    [
        ("csp", "app.csp"),
        ("path", "app.same-origin-paths"),
        ("worker", "app.service-worker-contract"),
    ],
)
def test_app_security_mutations_turn_red(mutation, check_name):
    paths = [gate.APP_RELATIVE, gate.SERVICE_WORKER_RELATIVE]
    checks = dict(gate.STATIC_CHECKS)
    with fixture_root(paths) as root:
        baseline = gate._run_check(
            check_name,
            lambda: checks[check_name](root),
        )
        assert baseline.passed, baseline.detail
        if mutation == "csp":
            path = root / gate.APP_RELATIVE
            text = path.read_text(encoding="utf-8")
            assert "connect-src 'self'" in text
            path.write_text(
                text.replace("connect-src 'self'", "connect-src *", 1),
                encoding="utf-8",
            )
        elif mutation == "path":
            path = root / gate.APP_RELATIVE
            text = path.read_text(encoding="utf-8")
            marker = "../agent-fair/fair-state.json"
            assert marker in text
            path.write_text(
                text.replace(
                    marker,
                    "https://example.test/fair-state.json",
                    1,
                ),
                encoding="utf-8",
            )
        else:
            path = root / gate.SERVICE_WORKER_RELATIVE
            text = path.read_text(encoding="utf-8")
            marker = "url.origin !== self.location.origin"
            assert marker in text
            path.write_text(
                text.replace(marker, "false", 1),
                encoding="utf-8",
            )
        result = gate._run_check(
            check_name,
            lambda: checks[check_name](root),
        )
        assert result.passed is False


def test_service_worker_runtime_state_invariants():
    with fixture_root(browser_fixture_paths()) as root:
        results = service_worker_probe(root)
    assert all(results.values()), [
        name for name, passed in results.items() if not passed
    ]


def test_same_cache_version_refreshes_changed_shell_bytes():
    with fixture_root(browser_fixture_paths()) as root:
        evidence = service_worker_update_probe(root)
    assert all(evidence["results"].values()), [
        name
        for name, passed in evidence["results"].items()
        if not passed
    ]
    assert all(
        re.fullmatch(r"[0-9a-f]{64}", value)
        for value in evidence["hashes"].values()
    )


@pytest.mark.parametrize(
    ("old", "new", "invariant"),
    [
        (
            "key.startsWith(CACHE_PREFIX) && key !== CACHE_NAME",
            "false",
            "oldOwnCacheRemoved",
        ),
        (
            "key.startsWith(CACHE_PREFIX) && key !== CACHE_NAME",
            "key !== CACHE_NAME",
            "foreignCachePreserved",
        ),
        (
            (
                "if (!expected || !/^[0-9a-f]{64}$/.test(expected)) "
                "return false;"
            ),
            (
                "if (!expected || !/^[0-9a-f]{64}$/.test(expected)) "
                "return true;"
            ),
            "corruptEntryRejected",
        ),
        (
            (
                "&& optional.every((url) => "
                "cachedUrls.has(url) && !invalid.has(url))"
            ),
            "&& true",
            "optionalLossRejected",
        ),
        (
            "if (!APP_SHELL_URLS.has(requestUrl)) return;",
            "if (!APP_SHELL_URLS.has(requestUrl)) {}",
            "unknownRequestPassesThrough",
        ),
    ],
)
def test_service_worker_runtime_mutations_turn_red(
    old,
    new,
    invariant,
):
    with fixture_root(browser_fixture_paths()) as root:
        path = root / gate.SERVICE_WORKER_RELATIVE
        text = path.read_text(encoding="utf-8")
        assert old in text
        path.write_text(text.replace(old, new, 1), encoding="utf-8")
        results = service_worker_probe(root)
    assert results[invariant] is False


@pytest.mark.parametrize(
    ("old", "new", "check_name"),
    [
        (
            '"agent-worlds-fair-v4-buzzsaw-20260816"',
            '"agent-worlds-fair-v0-mutation"',
            "browser.service-worker-cache",
        ),
        (
            '  "../agent-fair/district.json"\n',
            "",
            "browser.service-worker-cache",
        ),
        (
            "await cache.addAll(APP_SHELL);",
            'throw new Error("storage denied");',
            "browser.service-worker-cache",
        ),
        (
            'if (cached) return withProvenance(cached, "cache");',
            "if (cached) return unavailableResponse(unavailableMessage);",
            "browser.warm-offline-reload",
        ),
    ],
)
def test_service_worker_browser_gate_mutations_turn_red(
    old,
    new,
    check_name,
):
    with fixture_root(browser_fixture_paths()) as root:
        path = root / gate.SERVICE_WORKER_RELATIVE
        text = path.read_text(encoding="utf-8")
        assert old in text
        path.write_text(text.replace(old, new, 1), encoding="utf-8")
        results = result_map(gate.run_browser_checks(root, "released"))
    assert results[check_name].passed is False


def test_release_phase_rejects_local_spoof_and_requires_workflow(monkeypatch):
    paths = core_paths() + [
        ".github/workflows/agent-fair-release.yml",
        ".github/workflows/moonshot-gate.yml",
        "apps/organism-frames.json",
        "apps/manifest.json",
    ]
    with fixture_root(paths) as root:
        rewind_to_prepared_phase(root)
        prepared = gate._run_check(
            "organism.fair-release",
            lambda: gate._check_organism_release(root, "prepared"),
        )
        assert prepared.passed, prepared.detail
        assert (
            gate._release_candidate_digest(root)
            == gate.EXPECTED_RELEASE_CANDIDATE_DIGEST
        )

        for name in (
            "ACTIONS_ID_TOKEN_REQUEST_URL",
            "ACTIONS_ID_TOKEN_REQUEST_TOKEN",
            "GITHUB_ACTIONS",
            "GITHUB_EVENT_NAME",
            "GITHUB_REF_NAME",
            "AGENT_FAIR_CUSTOMER_APPROVED",
            "GITHUB_ACTOR",
            "GITHUB_RUN_ID",
            "GITHUB_REPOSITORY",
        ):
            monkeypatch.delenv(name, raising=False)
        with pytest.raises(gate.fair_builder.FairError):
            gate.fair_builder.apply_release(
                gate.EXPECTED_BUNDLE_DIGEST,
                gate.EXPECTED_DISTRICT_DIGEST,
                root=root,
                utc=next_organism_utc(root),
            )

        workflow = root / ".github/workflows/agent-fair-release.yml"
        original_workflow = workflow.read_text(encoding="utf-8")
        workflow.write_text(
            original_workflow.replace("workflow_dispatch:", "push:", 1),
            encoding="utf-8",
        )
        workflow_result = gate._run_check(
            "release.workflow",
            lambda: gate._release_workflow_evidence(
                root,
                gate.EXPECTED_RELEASE_CANDIDATE_DIGEST,
            ),
        )
        assert workflow_result.passed is False
        workflow.write_text(original_workflow, encoding="utf-8")

        release_utc = next_organism_utc(root)
        set_release_environment(monkeypatch, release_utc)
        gate.fair_builder.apply_release(
            gate.EXPECTED_BUNDLE_DIGEST,
            gate.EXPECTED_DISTRICT_DIGEST,
            root=root,
            utc=release_utc,
        )
        assert gate.resolve_release_phase(root) == "released"
        released = gate._run_check(
            "organism.fair-release",
            lambda: gate._check_organism_release(root, "released"),
        )
        assert released.passed, released.detail

        ledger = root / gate.ORGANISM_LEDGER_RELATIVE
        values = [
            json.loads(line)
            for line in ledger.read_text(encoding="utf-8").splitlines()
            if line
        ]
        values[-1]["payload"]["approval_evidence"][
            "event_name"
        ] = "push"
        ledger.write_text(
            "".join(
                json.dumps(value, sort_keys=True, separators=(",", ":"))
                + "\n"
                for value in values
            ),
            encoding="utf-8",
        )
        result = gate._run_check(
            "organism.fair-release",
            lambda: gate._check_organism_release(root, "released"),
        )
        assert result.passed is False


def test_prepared_phase_rejects_candidate_and_profile_spoofs():
    paths = core_paths() + [
        "apps/manifest.json",
        "apps/organism-frames.json",
        "apps/syndication",
    ]
    with fixture_root(paths) as root:
        rewind_to_prepared_phase(root)
        organism = gate._run_check(
            "organism.fair-release",
            lambda: gate._check_organism_release(root, "prepared"),
        )
        profile = gate._run_check(
            "syndication.profile10-fair-descriptors",
            lambda: gate._check_profile10_descriptors(root, "prepared"),
        )
        assert organism.passed, organism.detail
        assert profile.passed, profile.detail

        candidate_path = root / gate.RELEASE_CANDIDATE_RELATIVE
        original_candidate = candidate_path.read_bytes()
        candidate = json.loads(original_candidate)
        candidate["candidate_digest"] = "0" * 64
        candidate_path.write_text(
            json.dumps(candidate, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        spoofed_candidate = gate._run_check(
            "organism.fair-release",
            lambda: gate._check_organism_release(root, "prepared"),
        )
        assert spoofed_candidate.passed is False
        candidate_path.write_bytes(original_candidate)

        snapshot_path = root / gate.SYNDICATION_SNAPSHOT_RELATIVE
        snapshot = gate._json(snapshot_path)
        snapshot["data_objects"].append({
            "kind": "agent-worlds-fair-object",
            "path": gate.STATE_RELATIVE.as_posix(),
        })
        snapshot_path.write_text(
            json.dumps(snapshot, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        assert gate.resolve_release_phase(root) == "released"
        spoofed_apply = gate._run_check(
            "syndication.profile10-fair-descriptors",
            lambda: gate._check_profile10_descriptors(root, "prepared"),
        )
        assert spoofed_apply.passed is False


def test_oidc_verifier_rejects_all_authority_spoofs(monkeypatch):
    baseline = gate._run_check(
        "release.oidc-verifier",
        gate._check_oidc_verifier,
    )
    assert baseline.passed, baseline.detail

    original = gate.fair_builder.verify_github_oidc_token
    calls = 0
    valid_evidence = None

    def permissive(token, jwks, now=None):
        nonlocal calls, valid_evidence
        calls += 1
        if calls == 1:
            valid_evidence = original(token, jwks, now=now)
        return copy.deepcopy(valid_evidence)

    monkeypatch.setattr(
        gate.fair_builder,
        "verify_github_oidc_token",
        permissive,
    )
    permissive = gate._run_check(
        "release.oidc-verifier",
        gate._check_oidc_verifier,
    )
    assert permissive.passed is False
    assert "accepted unsigned token" in permissive.detail


def test_oidc_request_endpoint_spoof_turns_red(monkeypatch):
    monkeypatch.setattr(
        gate.fair_builder,
        "_oidc_request_url",
        lambda value: value,
    )
    result = gate._run_check(
        "release.oidc-verifier",
        gate._check_oidc_verifier,
    )
    assert result.passed is False
    assert "request audience binding changed" in result.detail


def test_oidc_source_and_pr_workflow_mutations_turn_red():
    paths = core_paths() + [
        ".github/workflows/agent-fair-release.yml",
        ".github/workflows/moonshot-gate.yml",
        "apps/manifest.json",
        "apps/organism-frames.json",
        "scripts/agent_world_fair.py",
    ]
    with fixture_root(paths) as root:
        baseline = gate._run_check(
            "release.oidc-pr-authority",
            lambda: gate._check_oidc_pr_authority(root),
        )
        assert baseline.passed, baseline.detail

        source_path = root / "scripts/agent_world_fair.py"
        source = source_path.read_text(encoding="utf-8")
        marker = 'header.get("alg") != "RS256"'
        assert marker in source
        source_path.write_text(
            source.replace(marker, "False", 1),
            encoding="utf-8",
        )
        source_mutation = gate._run_check(
            "release.oidc-pr-authority",
            lambda: gate._check_oidc_pr_authority(root),
        )
        assert source_mutation.passed is False
        source_path.write_text(source, encoding="utf-8")

        workflow_path = root / ".github/workflows/agent-fair-release.yml"
        workflow = workflow_path.read_text(encoding="utf-8")
        workflow_path.write_text(
            workflow
            + "\n      - name: Forbidden direct push\n"
            + "        run: git push origin HEAD:main\n",
            encoding="utf-8",
        )
        workflow_mutation = gate._run_check(
            "release.oidc-pr-authority",
            lambda: gate._check_oidc_pr_authority(root),
        )
        assert workflow_mutation.passed is False


def test_missing_or_overridden_codeowner_turns_red():
    with fixture_root([".github/CODEOWNERS"]) as root:
        path = root / ".github/CODEOWNERS"
        baseline = gate._run_check(
            "release.codeowners",
            lambda: gate._check_release_codeowners(root),
        )
        assert baseline.passed, baseline.detail

        original = path.read_text(encoding="utf-8")
        path.unlink()
        missing = gate._run_check(
            "release.codeowners",
            lambda: gate._check_release_codeowners(root),
        )
        assert missing.passed is False

        path.write_text(
            original + "\n/apps/agent-fair/ @untrusted-owner\n",
            encoding="utf-8",
        )
        overridden = gate._run_check(
            "release.codeowners",
            lambda: gate._check_release_codeowners(root),
        )
        assert overridden.passed is False


def test_release_artifact_after_pr_turns_red():
    paths = [
        ".github/workflows/agent-fair-release.yml",
    ]
    with fixture_root(paths) as root:
        path = root / paths[0]
        baseline = gate._run_check(
            "release.attestation-artifact",
            lambda: gate._check_release_artifact_workflow(root),
        )
        assert baseline.passed, baseline.detail
        text = path.read_text(encoding="utf-8")
        original = text
        start = text.index(
            "      - name: Upload deterministic release attestation"
        )
        end = text.index(
            "      - name: Create or update release pull request",
            start,
        )
        block = text[start:end]
        text = text[:start] + text[end:]
        insert = text.index(
            "      - name: Release repository writer lock"
        )
        path.write_text(
            text[:insert] + block + text[insert:],
            encoding="utf-8",
        )
        result = gate._run_check(
            "release.attestation-artifact",
            lambda: gate._check_release_artifact_workflow(root),
        )
        assert result.passed is False
        assert "before PR creation" in result.detail

        path.write_text(
            original
            + "\n      - name: Premature provenance claim\n"
            + "        env:\n"
            + "          AGENT_FAIR_RELEASE_ATTESTATION: forged.json\n"
            + "        run: 'true'\n",
            encoding="utf-8",
        )
        premature_claim = gate._run_check(
            "release.attestation-artifact",
            lambda: gate._check_release_artifact_workflow(root),
        )
        assert premature_claim.passed is False
        assert "structural-only" in premature_claim.detail


@pytest.mark.parametrize(
    ("old", "new"),
    [
        (
            "          verify-pr\n",
            "          inspect-only\n",
        ),
        (
            "  agent-fair-release-attestation:",
            "  skipped-release-attestation:",
        ),
        (
            "  pull_request:\n",
            "  pull_request:\n"
            "    paths:\n"
            "      - apps/agent-fair/**\n",
        ),
        (
            "      - name: Reject untrusted branch dispatch\n",
            "",
        ),
    ],
)
def test_all_pr_attestation_workflow_mutations_turn_red(old, new):
    paths = [
        ".github/workflows/agent-fair-release-attestation.yml",
        "scripts/verify_agent_fair_release_attestation.py",
    ]
    with fixture_root(paths) as root:
        path = root / paths[0]
        text = path.read_text(encoding="utf-8")
        assert old in text
        path.write_text(text.replace(old, new, 1), encoding="utf-8")
        result = gate._run_check(
            "release.all-pr-attestation",
            lambda: gate._check_pr_attestation_workflow(root),
        )
        assert result.passed is False


@pytest.mark.parametrize(
    ("old", "new"),
    [
        (
            'if head_ref.startswith("release/agent-fair-"):',
            "if False:",
        ),
        (
            '              "apps/organism-frames.json",\n',
            "",
        ),
        (
            '              "apps/syndication/",\n',
            "",
        ),
        (
            "bootstrap pull request contains a fair release event",
            "bootstrap release events allowed",
        ),
        (
            "if: steps.trusted.outputs.available == 'true'",
            "if: steps.trusted.outputs.available == 'false'",
        ),
        (
            "          GITHUB_TOKEN: ${{ github.token }}\n",
            "",
        ),
        (
            "          --wait-seconds 300\n",
            "          --wait-seconds 0\n",
        ),
        (
            '              "scripts/verify_agent_fair_release_attestation.py",\n',
            '              "scripts/verify_agent_fair_release_attestation.py",\n'
            '              "README.md",\n',
        ),
        (
            'str(payload.get("event_id", "")).startswith(',
            'str(payload.get("event_id", "")).endswith(',
        ),
        (
            '${BASE_SHA}:scripts/agent_world_fair.py',
            '${HEAD_SHA}:scripts/agent_world_fair.py',
        ),
        (
            '              "skill.md",\n',
            "",
        ),
    ],
)
def test_bootstrap_workflow_mutations_turn_red(old, new):
    paths = [
        ".github/workflows/agent-fair-release-attestation.yml",
        "scripts/verify_agent_fair_release_attestation.py",
    ]
    with fixture_root(paths) as root:
        path = root / paths[0]
        text = path.read_text(encoding="utf-8")
        assert old in text
        path.write_text(text.replace(old, new), encoding="utf-8")
        result = gate._run_check(
            "release.all-pr-attestation",
            lambda: gate._check_pr_attestation_workflow(root),
        )
        assert result.passed is False


@pytest.mark.parametrize(
    ("old", "new"),
    [
        (
            'BOOTSTRAP_ALLOWED_PATHS = {\n'
            '    ".github/CODEOWNERS",',
            'BOOTSTRAP_ALLOWED_PATHS = {\n'
            '    "README.md",\n'
            '    ".github/CODEOWNERS",',
        ),
        (
            'BOOTSTRAP_FORBIDDEN_PREFIXES = (\n'
            '    "apps/organism-frames.json",\n'
            '    "apps/syndication/",\n'
            ")",
            "BOOTSTRAP_FORBIDDEN_PREFIXES = ()",
        ),
    ],
)
def test_bootstrap_verifier_policy_mutations_turn_red(old, new):
    paths = [
        ".github/workflows/agent-fair-release-attestation.yml",
        "scripts/verify_agent_fair_release_attestation.py",
    ]
    with fixture_root(paths) as root:
        path = root / paths[1]
        text = path.read_text(encoding="utf-8")
        assert old in text
        path.write_text(text.replace(old, new, 1), encoding="utf-8")
        result = gate._run_check(
            "release.all-pr-attestation",
            lambda: gate._check_pr_attestation_workflow(root),
        )
        assert result.passed is False


def test_bootstrap_verifier_rejects_release_authority_mutations(
    monkeypatch,
):
    verifier = gate.release_attestation
    base_sha = "a" * 40
    head_sha = "b" * 40
    monkeypatch.setattr(
        verifier,
        "_changed_paths",
        lambda _root, _base, _head: [
            "scripts/verify_agent_fair_release_attestation.py"
        ],
    )
    monkeypatch.setattr(
        verifier,
        "_git_bytes",
        lambda _root, _arguments: b"",
    )
    valid = verifier.verify_bootstrap_install(
        ROOT,
        base_sha,
        head_sha,
        "feature/install-attestation-verifier",
    )
    assert valid["status"] == "bootstrap-not-release"
    assert valid["valid"] is True

    with pytest.raises(
        verifier.AttestationError,
        match="cannot use a release branch",
    ):
        verifier.verify_bootstrap_install(
            ROOT,
            base_sha,
            head_sha,
            "release/agent-fair-123",
        )

    for changed in (
        ["apps/organism-frames.json"],
        ["apps/organism-frames.jsonl"],
        ["apps/syndication/index.json"],
    ):
        monkeypatch.setattr(
            verifier,
            "_changed_paths",
            lambda _root, _base, _head, value=changed: value,
        )
        with pytest.raises(
            verifier.AttestationError,
            match="forbidden generated release paths",
        ):
            verifier.verify_bootstrap_install(
                ROOT,
                base_sha,
                head_sha,
                "feature/install-attestation-verifier",
            )

    monkeypatch.setattr(
        verifier,
        "_changed_paths",
        lambda _root, _base, _head: ["README.md"],
    )
    with pytest.raises(
        verifier.AttestationError,
        match="outside the one-time allowlist",
    ):
        verifier.verify_bootstrap_install(
            ROOT,
            base_sha,
            head_sha,
            "feature/install-attestation-verifier",
        )

    monkeypatch.setattr(
        verifier,
        "_changed_paths",
        lambda _root, _base, _head: [
            "scripts/verify_agent_fair_release_attestation.py"
        ],
    )
    for payload in (
        {"event": "agent-worlds-fair-release"},
        {"event_id": "agent-worlds-fair-release:forged"},
    ):
        release_line = json.dumps({
            "payload": payload,
        }).encode("utf-8") + b"\n"
        monkeypatch.setattr(
            verifier,
            "_git_bytes",
            lambda _root, _arguments, value=release_line: value,
        )
        with pytest.raises(
            verifier.AttestationError,
            match="contains a fair release event",
        ):
            verifier.verify_bootstrap_install(
                ROOT,
                base_sha,
                head_sha,
                "feature/install-attestation-verifier",
            )


def test_permissive_release_branch_nonrelease_path_turns_red():
    paths = [
        ".github/workflows/agent-fair-release-attestation.yml",
        "scripts/verify_agent_fair_release_attestation.py",
    ]
    with fixture_root(paths) as root:
        path = root / paths[1]
        text = path.read_text(encoding="utf-8")
        marker = "release branch does not contain a fair release frame"
        assert marker in text
        path.write_text(
            text.replace(
                marker,
                "release branch may omit its fair release frame",
                1,
            ),
            encoding="utf-8",
        )
        result = gate._run_check(
            "release.all-pr-attestation",
            lambda: gate._check_pr_attestation_workflow(root),
        )
        assert result.passed is False
        assert "verifier markers missing" in result.detail


def test_cross_origin_artifact_auth_forwarding_turns_red():
    paths = [
        ".github/workflows/agent-fair-release-attestation.yml",
        "scripts/verify_agent_fair_release_attestation.py",
    ]
    with fixture_root(paths) as root:
        path = root / paths[1]
        text = path.read_text(encoding="utf-8")
        marker = 'redirected.remove_header("Authorization")'
        assert marker in text
        path.write_text(
            text.replace(marker, "pass", 1),
            encoding="utf-8",
        )
        result = gate._run_check(
            "release.all-pr-attestation",
            lambda: gate._check_pr_attestation_workflow(root),
        )
        assert result.passed is False
        assert "verifier markers missing" in result.detail


@pytest.mark.parametrize(
    ("relative", "old", "new"),
    [
        (
            ".github/workflows/agent-fair-release.yml",
            "id-token: write",
            "id-token: none",
        ),
        (
            ".github/workflows/agent-fair-release.yml",
            "gh pr create",
            "gh issue create",
        ),
        (
            ".github/workflows/moonshot-gate.yml",
            "moonshot-gate:",
            "renamed-gate:",
        ),
        (
            ".github/workflows/moonshot-gate.yml",
            "agent_fair_gate.py --phase released",
            "agent_fair_gate.py --phase prepared",
        ),
        (
            ".github/workflows/moonshot-gate.yml",
            "context=moonshot-gate",
            "context=forged-gate",
        ),
    ],
)
def test_workflow_protection_mutations_turn_red(relative, old, new):
    paths = core_paths() + [
        ".github/workflows/agent-fair-release.yml",
        ".github/workflows/moonshot-gate.yml",
        "apps/manifest.json",
        "scripts/agent_world_fair.py",
    ]
    with fixture_root(paths) as root:
        path = root / relative
        text = path.read_text(encoding="utf-8")
        assert old in text
        path.write_text(text.replace(old, new, 1), encoding="utf-8")
        result = gate._run_check(
            "release.oidc-pr-authority",
            lambda: gate._check_oidc_pr_authority(root),
        )
        assert result.passed is False


def test_repository_protection_api_verification(monkeypatch):
    class Response:
        status = 200

        def __init__(self, payload):
            self.payload = payload

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def read(self):
            return json.dumps(self.payload).encode("utf-8")

    def protected(request, timeout=8):
        del timeout
        if "/environments/" in request.full_url:
            return Response(
                {
                    "name": "agent-fair-production",
                    "protection_rules": [
                        {
                            "type": "required_reviewers",
                            "reviewers": [{"type": "User"}],
                        }
                    ]
                }
            )
        if request.full_url.endswith("/actions/permissions/workflow"):
            return Response(
                {
                    "default_workflow_permissions": "write",
                    "can_approve_pull_request_reviews": False,
                }
            )
        return Response(
            {
                "required_pull_request_reviews": {},
                "required_status_checks": {
                    "contexts": [
                        "moonshot-gate",
                        "agent-fair-release-attestation",
                    ],
                    "checks": [],
                },
            }
        )

    monkeypatch.setenv("GITHUB_TOKEN", "not-logged")
    monkeypatch.setenv("GITHUB_REPOSITORY", gate.OIDC_REPOSITORY)
    monkeypatch.setattr(gate.urllib.request, "urlopen", protected)
    valid = gate._run_check(
        "release.repository-protection",
        lambda: gate._check_repository_protection(ROOT),
    )
    assert valid.passed, valid.detail

    def missing_main_protection(request, timeout=8):
        del timeout
        if "/environments/" in request.full_url:
            return Response(
                {
                    "name": "agent-fair-production",
                    "protection_rules": [
                        {
                            "type": "required_reviewers",
                            "reviewers": [{"type": "User"}],
                        }
                    ],
                }
            )
        if request.full_url.endswith("/actions/permissions/workflow"):
            return Response(
                {
                    "default_workflow_permissions": "write",
                    "can_approve_pull_request_reviews": False,
                }
            )
        return Response(
            {
                "required_pull_request_reviews": None,
                "required_status_checks": {"contexts": []},
            }
        )

    monkeypatch.setattr(
        gate.urllib.request,
        "urlopen",
        missing_main_protection,
    )
    invalid = gate._run_check(
        "release.repository-protection",
        lambda: gate._check_repository_protection(ROOT),
    )
    assert invalid.passed is False
    assert "pull requests and moonshot" in invalid.detail

    def missing_reviewer(request, timeout=8):
        del timeout
        if "/environments/" in request.full_url:
            return Response(
                {
                    "name": "agent-fair-production",
                    "protection_rules": [],
                }
            )
        if request.full_url.endswith("/actions/permissions/workflow"):
            return Response(
                {
                    "default_workflow_permissions": "write",
                    "can_approve_pull_request_reviews": False,
                }
            )
        return Response(
            {
                "required_pull_request_reviews": {},
                "required_status_checks": {
                    "contexts": [
                        "moonshot-gate",
                        "agent-fair-release-attestation",
                    ],
                },
            }
        )

    monkeypatch.setattr(
        gate.urllib.request,
        "urlopen",
        missing_reviewer,
    )
    reviewer = gate._run_check(
        "release.repository-protection",
        lambda: gate._check_repository_protection(ROOT),
    )
    assert reviewer.passed is False
    assert "required reviewer" in reviewer.detail

    def actions_can_approve(request, timeout=8):
        del timeout
        if "/environments/" in request.full_url:
            return Response(
                {
                    "name": "agent-fair-production",
                    "protection_rules": [
                        {
                            "type": "required_reviewers",
                            "reviewers": [{"type": "User"}],
                        }
                    ],
                }
            )
        if request.full_url.endswith("/actions/permissions/workflow"):
            return Response(
                {
                    "default_workflow_permissions": "write",
                    "can_approve_pull_request_reviews": True,
                }
            )
        return Response(
            {
                "required_pull_request_reviews": {},
                "required_status_checks": {
                    "contexts": [
                        "moonshot-gate",
                        "agent-fair-release-attestation",
                    ],
                    "checks": [],
                },
            }
        )

    monkeypatch.setattr(
        gate.urllib.request,
        "urlopen",
        actions_can_approve,
    )
    approvals = gate._run_check(
        "release.repository-protection",
        lambda: gate._check_repository_protection(ROOT),
    )
    assert approvals.passed is False
    assert "Actions pull request approvals" in approvals.detail

    def offline(*_args, **_kwargs):
        raise gate.urllib.error.URLError("offline")

    monkeypatch.setattr(gate.urllib.request, "urlopen", offline)
    unavailable = gate._run_check(
        "release.repository-protection",
        lambda: gate._check_repository_protection(ROOT),
    )
    assert unavailable.passed is True
    assert "offline" in unavailable.detail

    def unauthorized(*_args, **_kwargs):
        raise gate.urllib.error.HTTPError(
            "https://api.github.com/",
            401,
            "unauthorized",
            {},
            None,
        )

    monkeypatch.setattr(gate.urllib.request, "urlopen", unauthorized)
    denied = gate._run_check(
        "release.repository-protection",
        lambda: gate._check_repository_protection(ROOT),
    )
    assert denied.passed is False
    assert "HTTP 401" in denied.detail


def test_atomic_fair_release_delta_rejects_partial_publication():
    release_frame = {
        "payload": {
            "event_id": (
                gate.RELEASE_EVENT_PREFIX
                + gate.EXPECTED_BUNDLE_DIGEST
                + ":"
                + gate.EXPECTED_DISTRICT_DIGEST
            )
        }
    }
    descriptors = [
        {"path": path}
        for path in sorted(gate.FAIR_RESOURCE_PATHS)
    ]
    valid = [{
        "changes": {
            "data_tombstones": [],
            "data_upserts": descriptors,
            "frame_appends": [release_frame],
        }
    }]
    assert gate._require_atomic_fair_release_delta(valid) == release_frame

    partial = copy.deepcopy(valid)
    partial[0]["changes"]["data_upserts"].pop()
    with pytest.raises(gate.GateError):
        gate._require_atomic_fair_release_delta(partial)

    tombstoned = copy.deepcopy(valid)
    tombstoned[0]["changes"]["data_tombstones"] = [{
        "path": gate.STATE_RELATIVE.as_posix()
    }]
    with pytest.raises(gate.GateError):
        gate._require_atomic_fair_release_delta(tombstoned)


def test_released_phase_validates_static_and_browser_authority(
    monkeypatch,
):
    paths = [
        ".github/workflows/agent-fair-release.yml",
        ".github/workflows/moonshot-gate.yml",
        "apps/3d-immersive/agent-worlds-fair.html",
        "apps/3d-immersive/agent-worlds-fair-sw.js",
        "apps/agent-fair",
        "apps/agent-park",
        "apps/attention",
        "apps/looking-glass",
        "apps/manifest.json",
        "apps/organism-frames.json",
        "apps/organism-frames.jsonl",
        "apps/syndication",
        "node_modules",
    ]
    with fixture_root(paths) as root:
        rewind_to_prepared_phase(root)
        manifest_path = root / "apps/manifest.json"
        manifest = gate._json(manifest_path)
        category_name, category = next(
            (name, value)
            for name, value in manifest["categories"].items()
            if any(
                app.get("file") == "agent-worlds-fair.html"
                for app in value["apps"]
            )
        )
        fair_app = next(
            app
            for app in category["apps"]
            if app.get("file") == "agent-worlds-fair.html"
        )
        manifest["categories"] = {
            category_name: {
                **category,
                "apps": [fair_app],
                "count": 1,
            }
        }
        manifest["totalApps"] = 1
        manifest_path.write_text(
            json.dumps(manifest, indent=2) + "\n",
            encoding="utf-8",
        )

        release_utc = next_organism_utc(root)
        set_release_environment(monkeypatch, release_utc)
        gate.fair_builder.apply_release(
            gate.EXPECTED_BUNDLE_DIGEST,
            gate.EXPECTED_DISTRICT_DIGEST,
            root=root,
            utc=release_utc,
        )
        gate.build_syndication.build(
            root,
            "https://kody-w.github.io/localFirstTools-main/",
        )

        assert gate.resolve_release_phase(root) == "released"
        organism = gate._run_check(
            "organism.fair-release",
            lambda: gate._check_organism_release(root, "released"),
        )
        profile = gate._run_check(
            "syndication.profile10-fair-descriptors",
            lambda: gate._check_profile10_descriptors(root, "released"),
        )
        assert organism.passed, organism.detail
        assert "structural-only local mode" in organism.detail
        assert profile.passed, profile.detail

        candidate = gate._json(root / gate.RELEASE_CANDIDATE_RELATIVE)
        release = gate._fair_release_frames(
            gate._verified_organism_frames(root)
        )[0]
        base_sha = "a" * 40
        head_sha = "b" * 40
        attestation = (
            gate.release_attestation.build_release_attestation(
                candidate,
                release,
                base_sha,
                head_sha,
            )
        )
        attestation_path = root / "agent-fair-release-attestation.json"
        attestation_path.write_bytes(
            gate.fair_builder._pretty_bytes(attestation)
        )
        monkeypatch.setattr(
            gate.release_attestation,
            "verify_ci_release_attestation",
            lambda path, _root: {
                "artifact": str(path),
                "candidate_digest": gate.EXPECTED_RELEASE_CANDIDATE_DIGEST,
                "release_commit_sha": head_sha,
                "release_event_id": attestation["release_event_id"],
                "run_id": "123456",
                "status": "attestation-verified",
                "valid": True,
            },
        )
        local_spoof = gate._run_check(
            "organism.fair-release",
            lambda: gate._check_organism_release(
                root,
                "released",
                attestation_path,
            ),
        )
        assert local_spoof.passed is False

        for name, value in {
            "GITHUB_ACTIONS": "true",
            "GITHUB_EVENT_NAME": "workflow_dispatch",
            "GITHUB_JOB": "release",
            "GITHUB_REF": "refs/heads/main",
            "GITHUB_REPOSITORY": gate.OIDC_REPOSITORY,
            "GITHUB_WORKFLOW": "Release Agent World's Fair",
        }.items():
            monkeypatch.setenv(name, value)
        pre_pr = gate._run_check(
            "organism.fair-release",
            lambda: gate._check_organism_release(
                root,
                "released",
                attestation_path,
            ),
        )
        assert pre_pr.passed is False

        event_path = root / "agent-fair-release-pr-event.json"
        event_path.write_text(
            json.dumps(
                {
                    "repository": {
                        "full_name": gate.OIDC_REPOSITORY,
                    },
                    "pull_request": {
                        "base": {"ref": "main", "sha": base_sha},
                        "head": {
                            "ref": "release/agent-fair-123456",
                            "sha": head_sha,
                            "repo": {
                                "full_name": gate.OIDC_REPOSITORY,
                            },
                        },
                    },
                },
                indent=2,
                sort_keys=True,
            )
            + "\n",
            encoding="utf-8",
        )
        for name, value in {
            "GITHUB_ACTIONS": "true",
            "GITHUB_BASE_REF": "main",
            "GITHUB_EVENT_NAME": "pull_request",
            "GITHUB_EVENT_PATH": str(event_path),
            "GITHUB_HEAD_REF": "release/agent-fair-123456",
            "GITHUB_JOB": "agent-fair-release-attestation",
            "GITHUB_REPOSITORY": gate.OIDC_REPOSITORY,
            "GITHUB_WORKFLOW": "Agent Fair Release Attestation",
        }.items():
            monkeypatch.setenv(name, value)
        attested = gate._run_check(
            "organism.fair-release",
            lambda: gate._check_organism_release(
                root,
                "released",
                attestation_path,
            ),
        )
        assert attested.passed, attested.detail
        assert "attestation-verified PR" in attested.detail

        forged = copy.deepcopy(attestation)
        forged["candidate_digest"] = "0" * 64
        attestation_path.write_bytes(
            gate.fair_builder._pretty_bytes(forged)
        )
        forged_result = gate._run_check(
            "organism.fair-release",
            lambda: gate._check_organism_release(
                root,
                "released",
                attestation_path,
            ),
        )
        assert forged_result.passed is False
        attestation_path.write_bytes(
            gate.fair_builder._pretty_bytes(attestation)
        )

        event = json.loads(event_path.read_text(encoding="utf-8"))
        event["pull_request"]["head"]["sha"] = "c" * 40
        event_path.write_text(
            json.dumps(event, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        wrong_pr = gate._run_check(
            "organism.fair-release",
            lambda: gate._check_organism_release(
                root,
                "released",
                attestation_path,
            ),
        )
        assert wrong_pr.passed is False

        browser = result_map(gate.run_browser_checks(root, "released"))
        assert all(result.passed for result in browser.values()), [
            (name, result.detail)
            for name, result in browser.items()
            if not result.passed
        ]
        protected = browser["browser.protected-release-authority"]
        assert protected.passed, protected.detail
        assert '"release":' in protected.detail

        app_path = root / gate.APP_RELATIVE
        app = app_path.read_text(encoding="utf-8")
        truthful_copy = re.search(
            r"browser validated (?:bounded|exact) approval evidence, "
            r"the OIDC validity window at release time, and frame binding"
            r"(?:—|, )not the signature",
            app,
            re.IGNORECASE,
        )
        assert truthful_copy is not None
        app_path.write_text(
            app[:truthful_copy.start()]
            + "browser cryptographically verified OIDC/JWKS from "
            + "bounded evidence alone"
            + app[truthful_copy.end():],
            encoding="utf-8",
        )
        misleading = result_map(
            gate.run_browser_checks(root, "released")
        )["browser.protected-release-authority"]
        assert misleading.passed is False


def test_mcp_vote_credit_schema_mutation_turns_red():
    paths = core_paths() + [
        ".well-known/mcp.json",
        "apps/3d-immersive/agent-worlds-fair.html",
        "apps/manifest.json",
        "docs/AGENT-WORLDS-FAIR.md",
        "scripts/rappterzoo_mcp.py",
    ]
    with fixture_root(paths) as root:
        path = root / "scripts/rappterzoo_mcp.py"
        text = path.read_text(encoding="utf-8")
        assert "MAX_FAIR_ADMISSION_CREDITS = 120" in text
        path.write_text(
            text.replace(
                "MAX_FAIR_ADMISSION_CREDITS = 120",
                "MAX_FAIR_ADMISSION_CREDITS = 119",
                1,
            ),
            encoding="utf-8",
        )
        result = gate._run_check(
            "mcp.fair-prompt-tools-resources",
            lambda: gate._check_mcp_runtime(root),
        )
        assert result.passed is False
        assert "MCP fair vote schema changed" in result.detail


def test_playwright_unavailable_fails_every_browser_check(monkeypatch):
    monkeypatch.setattr(gate.shutil, "which", lambda _name: None)
    results = gate.run_browser_checks(ROOT)
    assert [result.name for result in results] == list(
        gate.BROWSER_CHECK_NAMES
    )
    assert all(result.passed is False for result in results)
    assert all("unavailable" in result.detail for result in results)


def test_unmeasured_browser_assertion_turns_red(monkeypatch):
    with fixture_root([]) as root:
        app = root / gate.APP_RELATIVE
        app.parent.mkdir(parents=True, exist_ok=True)
        app.write_text("<!doctype html>", encoding="utf-8")
        package = root / "node_modules/playwright/package.json"
        package.parent.mkdir(parents=True)
        package.write_text("{}", encoding="utf-8")
        calls = {"count": 0}

        def fake_run(*_args, **_kwargs):
            calls["count"] += 1
            if calls["count"] == 1:
                return SimpleNamespace(returncode=0, stdout="", stderr="")
            values = {
                name: {"pass": True, "detail": "measured"}
                for name in gate.BROWSER_CHECK_NAMES
                if name != "browser.forged-import-rejection"
            }
            return SimpleNamespace(
                returncode=0,
                stdout=json.dumps({"results": values}),
                stderr="",
            )

        monkeypatch.setattr(gate.shutil, "which", lambda _name: "node")
        monkeypatch.setattr(gate.subprocess, "run", fake_run)
        results = result_map(gate.run_browser_checks(root))
        assert results["browser.cold-start"].passed is True
        missing = results["browser.forged-import-rejection"]
        assert missing.passed is False
        assert "not measured" in missing.detail


def test_browser_safety_and_durable_stop_mutations_turn_red():
    paths = [
        gate.APP_RELATIVE,
        gate.SERVICE_WORKER_RELATIVE,
        "apps/agent-fair",
        gate.ORGANISM_PROJECTION_RELATIVE,
        "node_modules",
    ]
    with fixture_root(paths) as root:
        baseline = result_map(gate.run_browser_checks(root))
        assert baseline["browser.unsafe-input-rejection"].passed is True
        assert baseline["browser.durable-stop"].passed is True

        app = root / gate.APP_RELATIVE
        text = app.read_text(encoding="utf-8")
        safety = "attraction.safety_declaration === SAFE_DECLARATION"
        forbidden = (
            "if (containsForbiddenProposalContent(action.payload)) "
            "return false;"
        )
        stop = 'safeStorageSet(STORAGE_KEYS.stopped, "STOPPED");'
        action_domain = (
            'action: "rappterzoo/agent-fair-local-action/1\\n",'
        )
        forbidden_return = (
            "return activeMarkup.test(text) || forbiddenClass.test(text);"
        )
        resource_keys = (
            "|| !hasExactKeys(attraction.resource_request, RESOURCE_KEYS)"
        )
        category = "&& ALLOWED_CATEGORIES.has(attraction.category)"
        canonical_agent = "&& !canonicalAgentIds.has(agent.identity_id)"
        canonical_attraction = (
            "&& !canonicalAttractionIds.has(attraction.id)"
        )
        safety_values = (
            "&& SAFETY_KEYS.every((key) => "
            "value[key] === SAFE_CONTRACT[key]);"
        )
        import_keys = (
            "if (!hasExactKeys(imported, BRANCH_KEYS)) "
            'throw new Error("Import envelope has unknown or missing keys.");'
        )
        assemble_guard = (
            "if (!app.canonicalValid) {\n"
            '        return { ok: false, reason: "Canonical fair truth is '
            'DRIFT or unavailable; assembly is read-only." };\n'
            "      }"
        )
        absolute_time = (
            "Math.max(0, now - app.playbackAnchorReal) * app.speed"
        )
        assert safety in text
        assert forbidden in text
        assert stop in text
        assert action_domain in text
        assert forbidden_return in text
        assert resource_keys in text
        assert category in text
        assert canonical_agent in text
        assert canonical_attraction in text
        assert safety_values in text
        assert import_keys in text
        assert assemble_guard in text
        assert absolute_time in text
        text = text.replace(
            safety,
            'typeof attraction.safety_declaration === "string"',
            1,
        ).replace(
            forbidden,
            "void action.payload;",
            1,
        ).replace(
            stop,
            "void STORAGE_KEYS.stopped;",
            1,
        ).replace(
            action_domain,
            'action: "rappterzoo/agent-fair-local-action/2\\n",',
            1,
        ).replace(
            forbidden_return,
            "return false;",
            1,
        ).replace(
            resource_keys,
            "|| false",
            1,
        ).replace(
            category,
            '&& typeof attraction.category === "string"',
            1,
        ).replace(
            canonical_agent,
            "&& true",
            1,
        ).replace(
            canonical_attraction,
            "&& true",
            1,
        ).replace(
            safety_values,
            "&& true;",
            1,
        ).replace(
            import_keys,
            "if (false) throw new Error();",
            1,
        ).replace(
            assemble_guard,
            "if (false) {}",
            1,
        ).replace(
            absolute_time,
            (
                "Math.min(100, Math.max(0, now - "
                "app.playbackAnchorReal)) * app.speed"
            ),
            1,
        )
        app.write_text(text, encoding="utf-8")

        mutated = result_map(gate.run_browser_checks(root))
        assert mutated["browser.unsafe-input-rejection"].passed is False
        assert mutated["browser.durable-stop"].passed is False
        assert mutated["browser.deterministic-exports"].passed is False
        assert (
            mutated["browser.unknown-resource-key-rejection"].passed
            is False
        )
        assert (
            mutated["browser.duplicate-canonical-id-rejection"].passed
            is False
        )
        assert mutated["browser.unsafe-boolean-rejection"].passed is False
        assert (
            mutated["browser.active-markup-key-value-rejection"].passed
            is False
        )
        assert (
            mutated["browser.arbitrary-category-rejection"].passed
            is False
        )
        assert (
            mutated["browser.release-authority-import-rejection"].passed
            is False
        )
        assert mutated["browser.drift-mutations-disabled"].passed is False
        assert mutated["browser.wall-clock-stall"].passed is False


def test_cli_json_reports_exact_counts(monkeypatch, capsys):
    static = [
        gate.CheckResult(name, True, "static")
        for name, _check in gate.STATIC_CHECKS
    ]
    browser = [
        gate.CheckResult(name, True, "browser")
        for name in gate.BROWSER_CHECK_NAMES
    ]
    monkeypatch.setattr(
        gate,
        "run_gate",
        lambda _root, _phase="auto": static + browser,
    )
    assert gate.main(["--root", str(ROOT), "--json"]) == 0
    payload = json.loads(capsys.readouterr().out)
    static_count = len(gate.STATIC_CHECKS)
    browser_count = len(gate.BROWSER_CHECK_NAMES)
    phase = gate.resolve_release_phase(ROOT)
    assert payload["gate"] == "agent-worlds-fair"
    assert payload["release_phase"] == phase
    assert payload["release_provenance"] == (
        "prepared-no-release"
        if phase == "prepared"
        else "structural-only-local"
    )
    assert (
        payload["release_candidate_digest"]
        == gate.EXPECTED_RELEASE_CANDIDATE_DIGEST
    )
    assert payload["passed"] is True
    assert payload["counts"] == {
        "total": static_count + browser_count,
        "passed": static_count + browser_count,
        "failed": 0,
        "static": static_count,
        "browser": browser_count,
    }


def test_cli_release_phase_override_is_reported(monkeypatch, capsys):
    seen = {}

    def fake_gate(_root, phase="auto"):
        seen["phase"] = phase
        return []

    monkeypatch.setattr(gate, "run_gate", fake_gate)
    assert gate.main([
        "--root",
        str(ROOT),
        "--phase",
        "released",
        "--json",
    ]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert seen["phase"] == "released"
    assert payload["release_phase"] == "released"
    assert payload["release_provenance"] == "structural-only-local"


def test_cli_attestation_path_is_reported(monkeypatch, capsys):
    seen = {}
    monkeypatch.setenv("GITHUB_EVENT_NAME", "pull_request")

    def fake_gate(_root, phase="auto", attestation_path=None):
        seen["phase"] = phase
        seen["attestation_path"] = attestation_path
        return []

    monkeypatch.setattr(gate, "run_gate", fake_gate)
    assert gate.main([
        "--root",
        str(ROOT),
        "--phase",
        "released",
        "--attestation",
        "ci/agent-fair-release-attestation.json",
        "--json",
    ]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert seen == {
        "phase": "released",
        "attestation_path": (
            ROOT / "ci/agent-fair-release-attestation.json"
        ).resolve(),
    }
    assert payload["release_provenance"] == "attestation-verified-pr"


def test_optional_github_repository_protection(monkeypatch):
    monkeypatch.setenv("GITHUB_TOKEN", "test-token")
    monkeypatch.setenv("GITHUB_REPOSITORY", gate.OIDC_REPOSITORY)
    valid_environment = {
        "name": "agent-fair-production",
        "protection_rules": [{
            "type": "required_reviewers",
            "reviewers": [{"type": "User", "reviewer": {"id": 1}}],
        }],
    }
    valid_protection = {
        "required_pull_request_reviews": {
            "required_approving_review_count": 1,
        },
        "required_status_checks": {
            "strict": True,
            "contexts": [
                "moonshot-gate",
                "agent-fair-release-attestation",
            ],
        },
    }
    valid_workflow_permissions = {
        "default_workflow_permissions": "write",
        "can_approve_pull_request_reviews": False,
    }
    responses = iter([
        valid_environment,
        valid_protection,
        valid_workflow_permissions,
    ])
    monkeypatch.setattr(
        gate,
        "_github_api_json",
        lambda _url, _token: next(responses),
    )
    result = gate._run_check(
        "release.github-config",
        lambda: gate._check_repository_protection(ROOT),
    )
    assert result.passed, result.detail

    responses = iter([
        {"name": "agent-fair-production", "protection_rules": []},
        valid_protection,
        valid_workflow_permissions,
    ])
    monkeypatch.setattr(
        gate,
        "_github_api_json",
        lambda _url, _token: next(responses),
    )
    missing_reviewer = gate._run_check(
        "release.github-config",
        lambda: gate._check_repository_protection(ROOT),
    )
    assert missing_reviewer.passed is False

    responses = iter([
        valid_environment,
        {
            "required_pull_request_reviews": None,
            "required_status_checks": {"contexts": ["unrelated"]},
        },
        valid_workflow_permissions,
    ])
    monkeypatch.setattr(
        gate,
        "_github_api_json",
        lambda _url, _token: next(responses),
    )
    missing_protection = gate._run_check(
        "release.github-config",
        lambda: gate._check_repository_protection(ROOT),
    )
    assert missing_protection.passed is False

    responses = iter([
        valid_environment,
        {
            "required_pull_request_reviews": {
                "required_approving_review_count": 1,
            },
            "required_status_checks": {
                "contexts": ["moonshot-gate"],
            },
        },
        valid_workflow_permissions,
    ])
    monkeypatch.setattr(
        gate,
        "_github_api_json",
        lambda _url, _token: next(responses),
    )
    missing_attestation = gate._run_check(
        "release.github-config",
        lambda: gate._check_repository_protection(ROOT),
    )
    assert missing_attestation.passed is False
    assert "agent-fair-release-attestation" in missing_attestation.detail
