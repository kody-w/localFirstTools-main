"use strict";

const CACHE_NAME = "agent-worlds-fair-v3-release-20260816";
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
const DATA_URLS = new Set([...DATA_PATHS, ...OPTIONAL_DATA_PATHS].map((path) => new URL(path, self.location.href).href));

function withProvenance(response, provenance) {
  const headers = new Headers(response.headers);
  headers.set("X-Agent-Fair-Provenance", provenance);
  return new Response(response.body, {
    status: response.status,
    statusText: response.statusText,
    headers
  });
}

async function cacheStatus() {
  const cache = await caches.open(CACHE_NAME);
  const cached = await cache.keys();
  const cachedUrls = new Set(cached.map((request) => request.url));
  const required = REQUIRED_PATHS.map((path) => new URL(path, self.location.href).href);
  const optional = OPTIONAL_DATA_PATHS.map((path) => new URL(path, self.location.href).href);
  return {
    type: "agent-fair-cache-status",
    cacheName: CACHE_NAME,
    releaseTruthProfile: RELEASE_TRUTH_PROFILE,
    cached: cached.map((request) => request.url),
    required,
    optional,
    missingRequired: required.filter((url) => !cachedUrls.has(url)),
    missingOptional: optional.filter((url) => !cachedUrls.has(url)),
    ready: required.every((url) => cachedUrls.has(url))
  };
}

self.addEventListener("install", (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME)
      .then(async (cache) => {
        await cache.addAll(REQUIRED_PATHS);
        await Promise.all(OPTIONAL_DATA_PATHS.map((path) => cache.add(path).catch(() => false)));
      })
      .then(() => self.skipWaiting())
  );
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys()
      .then((keys) => Promise.all(
        keys.filter((key) => key !== CACHE_NAME).map((key) => caches.delete(key))
      ))
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

  if (DATA_URLS.has(url.href)) {
    if (self.navigator.onLine === false) {
      event.respondWith(
        caches.match(request, { ignoreSearch: true }).then((cached) => {
          if (cached) return withProvenance(cached, "cache");
          return new Response("Canonical fair source unavailable.", {
            status: 503,
            headers: { "Content-Type": "text/plain", "X-Agent-Fair-Provenance": "unavailable" }
          });
        })
      );
      return;
    }
    event.respondWith(
      fetch(request)
        .then((response) => {
          if (!response.ok) throw new Error("Canonical source HTTP " + response.status);
          const copy = response.clone();
          event.waitUntil(caches.open(CACHE_NAME).then((cache) => cache.put(request, copy)));
          return withProvenance(response, "network");
        })
        .catch(async () => {
          const cached = await caches.match(request, { ignoreSearch: true });
          if (cached) return withProvenance(cached, "cache");
          return new Response("Canonical fair source unavailable.", {
            status: 503,
            headers: { "Content-Type": "text/plain", "X-Agent-Fair-Provenance": "unavailable" }
          });
        })
    );
    return;
  }

  event.respondWith(
    caches.match(request, { ignoreSearch: true }).then((cached) => {
      if (cached) return withProvenance(cached, "cache");
      return fetch(request).then((response) => {
        if (!response.ok) throw new Error("App shell HTTP " + response.status);
        const copy = response.clone();
        event.waitUntil(caches.open(CACHE_NAME).then((cache) => cache.put(request, copy)));
        return withProvenance(response, "network");
      }).catch(() => {
        return new Response("Agent World's Fair app shell unavailable.", {
          status: 503,
          headers: { "Content-Type": "text/plain", "X-Agent-Fair-Provenance": "unavailable" }
        });
      });
    })
  );
});
