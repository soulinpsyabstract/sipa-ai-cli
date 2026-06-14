/* ===== SIPA AI — Service Worker ===== */
'use strict';

const CACHE_NAME = 'sipa-ai-v1';
const CACHE_STATIC = 'sipa-ai-static-v1';

const STATIC_ASSETS = [
  '/',
  '/index.html',
  '/app.js',
  '/style.css',
  '/manifest.json',
];

const API_PATTERNS = ['/ask', '/health', '/models'];

// ── Install: pre-cache static assets ─────────────────────────────────────────
self.addEventListener('install', event => {
  event.waitUntil(
    caches.open(CACHE_STATIC)
      .then(cache => cache.addAll(STATIC_ASSETS))
      .then(() => self.skipWaiting())
  );
});

// ── Activate: clean old caches ────────────────────────────────────────────────
self.addEventListener('activate', event => {
  event.waitUntil(
    caches.keys().then(keys =>
      Promise.all(
        keys
          .filter(k => k !== CACHE_STATIC && k !== CACHE_NAME)
          .map(k => caches.delete(k))
      )
    ).then(() => self.clients.claim())
  );
});

// ── Fetch strategy ────────────────────────────────────────────────────────────
self.addEventListener('fetch', event => {
  const { request } = event;
  const url = new URL(request.url);

  // Skip non-GET for cache logic (POST /ask goes straight to network)
  if (request.method !== 'GET') {
    event.respondWith(networkOrOffline(request));
    return;
  }

  // API routes → Network first, no cache
  if (isApiRequest(url)) {
    event.respondWith(networkOrOffline(request));
    return;
  }

  // Static assets → Cache first, then network, update cache in background
  event.respondWith(cacheFirstWithUpdate(request));
});

// ── Network first (API calls) ─────────────────────────────────────────────────
async function networkOrOffline(request) {
  try {
    return await fetch(request);
  } catch {
    // For POST /ask, return structured offline response
    if (request.method === 'POST' && request.url.includes('/ask')) {
      return new Response(
        JSON.stringify({
          response: 'SIPA AI офлайн. Проверь подключение к сети.',
          layer: null,
          model: 'offline',
          elapsed: 0,
        }),
        {
          status: 200,
          headers: { 'Content-Type': 'application/json' },
        }
      );
    }
    return offlinePage();
  }
}

// ── Cache first with background update ───────────────────────────────────────
async function cacheFirstWithUpdate(request) {
  const cached = await caches.match(request);

  const fetchPromise = fetch(request)
    .then(async response => {
      if (response && response.ok) {
        const cache = await caches.open(CACHE_STATIC);
        cache.put(request, response.clone());
      }
      return response;
    })
    .catch(() => null);

  return cached || (await fetchPromise) || offlinePage();
}

// ── Offline fallback page ─────────────────────────────────────────────────────
function offlinePage() {
  const html = `<!DOCTYPE html>
<html lang="ru">
<head>
  <meta charset="UTF-8"/>
  <meta name="viewport" content="width=device-width, initial-scale=1.0"/>
  <title>SIPA AI — Офлайн</title>
  <style>
    * { box-sizing: border-box; margin: 0; padding: 0; }
    body {
      min-height: 100vh;
      background: #0a0a0f;
      color: #e8e8f0;
      font-family: system-ui, sans-serif;
      display: flex;
      align-items: center;
      justify-content: center;
      flex-direction: column;
      gap: 16px;
      padding: 24px;
      text-align: center;
    }
    .icon { font-size: 52px; margin-bottom: 8px; }
    h1 { font-size: 20px; color: #6c63ff; }
    p { font-size: 14px; color: #8888aa; max-width: 320px; line-height: 1.6; }
    button {
      margin-top: 8px;
      padding: 10px 24px;
      background: #6c63ff;
      color: #fff;
      border: none;
      border-radius: 8px;
      font-size: 14px;
      cursor: pointer;
    }
  </style>
</head>
<body>
  <div class="icon">◈</div>
  <h1>SIPA AI офлайн</h1>
  <p>Нет подключения к сети. Проверь интернет и попробуй снова.</p>
  <button onclick="location.reload()">Обновить</button>
</body>
</html>`;

  return new Response(html, {
    status: 200,
    headers: { 'Content-Type': 'text/html; charset=utf-8' },
  });
}

// ── Helpers ───────────────────────────────────────────────────────────────────
function isApiRequest(url) {
  return API_PATTERNS.some(p => url.pathname.startsWith(p))
    || url.hostname !== self.location.hostname;
}

// ── Push notifications (future) ───────────────────────────────────────────────
self.addEventListener('push', event => {
  if (!event.data) return;
  let data = {};
  try { data = event.data.json(); } catch { data = { title: 'SIPA AI', body: event.data.text() }; }
  event.waitUntil(
    self.registration.showNotification(data.title || 'SIPA AI', {
      body: data.body || '',
      icon: '/icon-192.png',
      badge: '/icon-192.png',
    })
  );
});
