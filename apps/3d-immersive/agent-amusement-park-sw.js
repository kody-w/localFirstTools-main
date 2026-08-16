"use strict";

const VERSION = "rappterzoo-agent-park-v2-20260815-r2";
const CACHE_PREFIX = "rappterzoo-agent-park-";
const CACHE_NAME = VERSION;
const SAFETY_CACHE = "rappterzoo-customer-safety-v1";
let offlineUntil = 0;
const SAFETY_URL = new URL("./agent-amusement-park-stop-state.json", self.location.href).href;
const URLS = Object.freeze({
  shell: new URL("./agent-amusement-park.html", self.location.href).href,
  park: new URL("../agent-park/park-state.json", self.location.href).href,
  events: new URL("../agent-park/events.jsonl", self.location.href).href,
  contractV2: new URL("../agent-park/agent-contract-v2.json", self.location.href).href,
  contractV1: new URL("../agent-park/agent-contract.json", self.location.href).href,
  organism: new URL("../organism-frames.json", self.location.href).href
});

async function fetchAndCache(cache, url) {
  const response = await fetch(url, {
    cache: "no-cache",
    credentials: "same-origin"
  });
  if (!response.ok) throw new Error("Cannot cache " + url + ": HTTP " + response.status);
  await cache.put(url, response.clone());
  return response;
}

async function installCache() {
  const cache = await caches.open(CACHE_NAME);
  await Promise.all([
    fetchAndCache(cache, URLS.shell),
    fetchAndCache(cache, URLS.park),
    fetchAndCache(cache, URLS.events),
    fetchAndCache(cache, URLS.organism)
  ]);
  try {
    await fetchAndCache(cache, URLS.contractV2);
  } catch (error) {
    await fetchAndCache(cache, URLS.contractV1);
  }
}

self.addEventListener("install", (event) => {
  event.waitUntil(installCache().then(() => self.skipWaiting()));
});

self.addEventListener("activate", (event) => {
  event.waitUntil((async () => {
    const names = await caches.keys();
    await Promise.all(names
      .filter((name) => name.startsWith(CACHE_PREFIX) && name !== CACHE_NAME)
      .map((name) => caches.delete(name)));
    await self.clients.claim();
  })());
});

async function networkFirst(request, cacheKey) {
  const cache = await caches.open(CACHE_NAME);
  if (request.mode !== "navigate" && Date.now() < offlineUntil) {
    const cached = await cache.match(cacheKey);
    if (cached) return withProvenance(cached, "cache");
  }
  try {
    const response = await fetch(request);
    if (response.ok && request.mode === "navigate") offlineUntil = 0;
    if (response.ok) await cache.put(cacheKey, response.clone());
    return withProvenance(response, "network");
  } catch (error) {
    offlineUntil = Date.now() + 15000;
    const cached = await cache.match(cacheKey);
    if (cached) return withProvenance(cached, "cache");
    throw error;
  }
}

function withProvenance(response, provenance) {
  const headers = new Headers(response.headers);
  headers.set("X-RappterZoo-Provenance", provenance);
  headers.set("X-RappterZoo-Cache-Version", VERSION);
  return new Response(response.body, {
    status: response.status,
    statusText: response.statusText,
    headers
  });
}

self.addEventListener("fetch", (event) => {
  const request = event.request;
  if (request.method !== "GET") return;
  const url = new URL(request.url);
  if (url.origin !== self.location.origin) return;

  if (request.mode === "navigate" && url.pathname === new URL(URLS.shell).pathname) {
    event.respondWith(networkFirst(request, URLS.shell));
    return;
  }

  const cacheKey = Object.values(URLS).find((candidate) => candidate === url.href);
  if (cacheKey) event.respondWith(networkFirst(request, cacheKey));
});

self.addEventListener("message", (event) => {
  if (!event.ports?.[0]) return;
  event.waitUntil((async () => {
    if (event.data?.type === "SAFETY_STOP_SET") {
      const cache = await caches.open(SAFETY_CACHE);
      await cache.put(SAFETY_URL, new Response(JSON.stringify({
        engaged: event.data.engaged === true
      }), {
        headers: { "content-type": "application/json" }
      }));
      event.ports[0].postMessage({ ok: true, engaged: event.data.engaged === true });
      return;
    }
    if (event.data?.type === "SAFETY_STOP_GET") {
      const cache = await caches.open(SAFETY_CACHE);
      const response = await cache.match(SAFETY_URL);
      const value = response ? await response.json() : { engaged: false };
      event.ports[0].postMessage({ ok: true, engaged: value.engaged === true });
      return;
    }
    if (event.data?.type !== "CACHE_STATUS") {
      event.ports[0].postMessage({ ok: false, error: "Unsupported message" });
      return;
    }
    const cache = await caches.open(CACHE_NAME);
    const required = [URLS.shell, URLS.park, URLS.events, URLS.organism];
    const cached = [];
    for (const url of required) {
      if (await cache.match(url)) cached.push(url);
    }
    let contractSource = "missing";
    if (await cache.match(URLS.contractV2)) {
      cached.push(URLS.contractV2);
      contractSource = "v2";
    } else if (await cache.match(URLS.contractV1)) {
      cached.push(URLS.contractV1);
      contractSource = "v1-fallback";
    }
    event.ports[0].postMessage({
      version: VERSION,
      ready: cached.length === 5 && contractSource !== "missing",
      contractSource,
      cached
    });
  })());
});
