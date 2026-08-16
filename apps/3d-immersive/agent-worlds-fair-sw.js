"use strict";

const CACHE_NAME = "agent-worlds-fair-v4-buzzsaw-20260816";
const CACHE_PREFIX = "agent-worlds-fair-";
const CACHE_DIGEST_HEADER = "X-Agent-Fair-Cache-SHA256";
const RELEASE_TRUTH_PROFILE = "workflow-attested-browser-structural-v1";
const DATA_PATHS = [
  "../agent-fair/fair-state.json",
  "../agent-fair/events.jsonl",
  "../agent-fair/agent-contract.json",
  "../agent-fair/district.json"
];
const OPTIONAL_DATA_PATHS = [
  "../organism-frames.json"
];
const REQUIRED_PATHS = [
  "./agent-worlds-fair.html",
  "./agent-worlds-fair-sw.js",
  ...DATA_PATHS
];
const APP_SHELL = [...REQUIRED_PATHS, ...OPTIONAL_DATA_PATHS];
const APP_SHELL_URLS = new Set(APP_SHELL.map((path) => new URL(path, self.location.href).href));
const DATA_URLS = new Set([...DATA_PATHS, ...OPTIONAL_DATA_PATHS].map((path) => new URL(path, self.location.href).href));
let cacheInstallError = null;

function withProvenance(response, provenance) {
  const headers = new Headers(response.headers);
  headers.set("X-Agent-Fair-Provenance", provenance);
  return new Response(response.body, {
    status: response.status,
    statusText: response.statusText,
    headers
  });
}

function normalizedUrl(value) {
  const url = new URL(value, self.location.href);
  url.search = "";
  url.hash = "";
  return url.href;
}

async function sha256(bytes) {
  const digest = await self.crypto.subtle.digest("SHA-256", bytes);
  return Array.from(new Uint8Array(digest), (value) => value.toString(16).padStart(2, "0")).join("");
}

async function responseWithDigest(response) {
  const bytes = await response.arrayBuffer();
  const headers = new Headers(response.headers);
  headers.set(CACHE_DIGEST_HEADER, await sha256(bytes));
  return new Response(bytes, {
    status: response.status,
    statusText: response.statusText,
    headers
  });
}

async function validCachedResponse(response) {
  if (!response || !response.ok) return false;
  const expected = response.headers.get(CACHE_DIGEST_HEADER);
  if (!expected || !/^[0-9a-f]{64}$/.test(expected)) return false;
  return expected === await sha256(await response.clone().arrayBuffer());
}

async function stampCacheEntry(cache, url, required) {
  const response = await cache.match(url);
  if (!response) {
    if (required) throw new Error("Required cache entry missing: " + url);
    return false;
  }
  if (!response.ok) {
    await cache.delete(url);
    if (required) throw new Error("Required cache entry is not successful: " + url);
    return false;
  }
  await cache.put(url, await responseWithDigest(response));
  return true;
}

async function populateCache() {
  const cache = await caches.open(CACHE_NAME);
  await cache.addAll(APP_SHELL);

  const cached = await cache.keys();
  await Promise.all(cached
    .filter((request) => !APP_SHELL_URLS.has(request.url))
    .map((request) => cache.delete(request)));

  await Promise.all(REQUIRED_PATHS.map((path) => (
    stampCacheEntry(cache, new URL(path, self.location.href).href, true)
  )));
  await Promise.all(OPTIONAL_DATA_PATHS.map((path) => (
    stampCacheEntry(cache, new URL(path, self.location.href).href, true)
  )));
}

async function matchCached(request) {
  try {
    const cached = await caches.match(request, {
      cacheName: CACHE_NAME,
      ignoreSearch: true
    });
    if (!cached) return null;
    if (await validCachedResponse(cached)) return cached;
    const cache = await caches.open(CACHE_NAME);
    await cache.delete(request, { ignoreSearch: true });
  } catch (_error) {
    return null;
  }
  return null;
}

function updateCache(event, requestUrl, response) {
  event.waitUntil(
    caches.open(CACHE_NAME)
      .then(async (cache) => {
        await cache.put(requestUrl, await responseWithDigest(response));
      })
      .catch(() => false)
  );
}

function unavailableResponse(message) {
  return new Response(message, {
    status: 503,
    headers: { "Content-Type": "text/plain", "X-Agent-Fair-Provenance": "unavailable" }
  });
}

async function networkFirst(event, request, requestUrl, unavailableMessage) {
  if (self.navigator.onLine !== false) {
    try {
      const response = await fetch(request);
      if (!response.ok) throw new Error("Canonical source HTTP " + response.status);
      updateCache(event, requestUrl, response.clone());
      return withProvenance(response, "network");
    } catch (_error) {
      // A verified cache entry is the only offline fallback.
    }
  }
  const cached = await matchCached(request);
  if (cached) return withProvenance(cached, "cache");
  return unavailableResponse(unavailableMessage);
}

async function cacheStatus() {
  const required = REQUIRED_PATHS.map((path) => new URL(path, self.location.href).href);
  const optional = OPTIONAL_DATA_PATHS.map((path) => new URL(path, self.location.href).href);
  try {
    const keys = await caches.keys();
    const cache = keys.includes(CACHE_NAME) ? await caches.open(CACHE_NAME) : null;
    const cached = cache ? await cache.keys() : [];
    const cachedUrls = new Set(cached.map((request) => request.url));
    const invalid = new Set();
    if (cache) {
      await Promise.all([...required, ...optional].map(async (url) => {
        if (!cachedUrls.has(url)) return;
        const response = await cache.match(url);
        if (!await validCachedResponse(response)) {
          invalid.add(url);
          await cache.delete(url);
        }
      }));
    }
    const unexpected = cached
      .map((request) => request.url)
      .filter((url) => !APP_SHELL_URLS.has(url));
    return {
      type: "agent-fair-cache-status",
      cacheName: CACHE_NAME,
      releaseTruthProfile: RELEASE_TRUTH_PROFILE,
      cached: cached.map((request) => request.url),
      required,
      optional,
      missingRequired: required.filter((url) => !cachedUrls.has(url)),
      missingOptional: optional.filter((url) => !cachedUrls.has(url)),
      invalidRequired: required.filter((url) => invalid.has(url)),
      invalidOptional: optional.filter((url) => invalid.has(url)),
      unexpected,
      ready: required.every((url) => cachedUrls.has(url) && !invalid.has(url))
        && optional.every((url) => cachedUrls.has(url) && !invalid.has(url))
        && unexpected.length === 0,
      error: cacheInstallError
    };
  } catch (error) {
    return {
      type: "agent-fair-cache-status",
      cacheName: CACHE_NAME,
      releaseTruthProfile: RELEASE_TRUTH_PROFILE,
      cached: [],
      required,
      optional,
      missingRequired: required,
      missingOptional: optional,
      invalidRequired: [],
      invalidOptional: [],
      unexpected: [],
      ready: false,
      error: "Cache Storage unavailable: " + String(error && error.message ? error.message : error)
    };
  }
}

self.addEventListener("install", (event) => {
  event.waitUntil(
    populateCache()
      .catch(async (error) => {
        cacheInstallError = "Cache install unavailable: " + String(
          error && error.message ? error.message : error
        );
        try {
          await caches.delete(CACHE_NAME);
        } catch (_cleanupError) {
          // Installation still fails closed if Cache Storage cleanup fails.
        }
        throw error;
      })
      .then(() => self.skipWaiting())
  );
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys()
      .then((keys) => Promise.all(
        keys
          .filter((key) => key.startsWith(CACHE_PREFIX) && key !== CACHE_NAME)
          .map((key) => caches.delete(key))
      ))
      .catch((error) => {
        cacheInstallError = cacheInstallError || (
          "Cache activation unavailable: "
          + String(error && error.message ? error.message : error)
        );
      })
      .then(() => self.clients.claim())
  );
});

self.addEventListener("message", (event) => {
  if (!event.data || event.data.type !== "agent-fair-cache-status") return;
  event.waitUntil(
    cacheStatus()
      .then((status) => {
        if (event.ports && event.ports[0]) event.ports[0].postMessage(status);
        else if (event.source) event.source.postMessage(status);
      })
  );
});

self.addEventListener("fetch", (event) => {
  const request = event.request;
  if (request.method !== "GET") return;

  const url = new URL(request.url);
  if (url.origin !== self.location.origin) {
    event.respondWith(new Response("Cross-origin requests are forbidden.", {
      status: 403,
      headers: { "Content-Type": "text/plain", "X-Agent-Fair-Provenance": "blocked-cross-origin" }
    }));
    return;
  }

  const requestUrl = normalizedUrl(url.href);
  if (DATA_URLS.has(requestUrl)) {
    event.respondWith(networkFirst(
      event,
      request,
      requestUrl,
      "Canonical fair source unavailable."
    ));
    return;
  }

  if (!APP_SHELL_URLS.has(requestUrl)) return;
  event.respondWith(networkFirst(
    event,
    request,
    requestUrl,
    "Agent World's Fair app shell unavailable."
  ));
});
