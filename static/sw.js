const CACHE = 'flash-static-v5';
const STATIC = ['/static/style.css?v=4.1', '/static/app.js', '/static/icons/icon-192.png', '/static/icons/icon-512.png', '/offline'];

self.addEventListener('install', e => {
  e.waitUntil(caches.open(CACHE).then(c => c.addAll(STATIC)));
  self.skipWaiting();
});

self.addEventListener('activate', e => {
  e.waitUntil(
    caches.keys().then(keys => Promise.all(keys.filter(k => k !== CACHE).map(k => caches.delete(k))))
  );
  self.clients.claim();
});

self.addEventListener('fetch', e => {
  if (e.request.method !== 'GET' || new URL(e.request.url).origin !== self.location.origin) return;

  if (e.request.mode === 'navigate') {
    e.respondWith(fetch(e.request).catch(() => caches.match('/offline')));
    return;
  }

  if (new URL(e.request.url).pathname.startsWith('/static/')) {
    // Network-First para arquivos estáticos: busca versão atualizada na rede e usa cache como fallback offline
    e.respondWith(
      fetch(e.request)
        .then(response => {
          if (response.ok) {
            const copy = response.clone();
            caches.open(CACHE).then(c => c.put(e.request, copy));
          }
          return response;
        })
        .catch(() => caches.match(e.request))
    );
  }
});
