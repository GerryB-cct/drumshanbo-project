// Service worker: offline fallback page and web push notifications.
const CACHE = 'dml-v1';
const PRECACHE = ['/offline', '/static/css/style.css', '/static/img/logo.svg', '/static/js/app.js'];

self.addEventListener('install', (event) => {
  event.waitUntil(caches.open(CACHE).then((cache) => cache.addAll(PRECACHE)).then(() => self.skipWaiting()));
});

self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys()
      .then((keys) => Promise.all(keys.filter((k) => k !== CACHE).map((k) => caches.delete(k))))
      .then(() => self.clients.claim())
  );
});

// Pages always come from the network (loan data must be fresh); show the offline page if that fails.
self.addEventListener('fetch', (event) => {
  const req = event.request;
  if (req.method !== 'GET') return;
  if (req.mode === 'navigate') {
    event.respondWith(fetch(req).catch(() => caches.match('/offline')));
    return;
  }
  const url = new URL(req.url);
  if (url.origin === location.origin && url.pathname.startsWith('/static/')) {
    event.respondWith(
      fetch(req)
        .then((res) => {
          const copy = res.clone();
          caches.open(CACHE).then((cache) => cache.put(req, copy));
          return res;
        })
        .catch(() => caches.match(req))
    );
  }
});

self.addEventListener('push', (event) => {
  let data = {};
  try { data = event.data ? event.data.json() : {}; } catch (e) { data = { body: event.data && event.data.text() }; }
  const title = data.title || 'Drumshanbo Music Library';
  event.waitUntil(
    self.registration.showNotification(title, {
      body: data.body || '',
      icon: '/static/img/icons/icon-192.png',
      badge: '/static/img/icons/icon-192.png',
      data: { url: data.url || '/admin/' },
    })
  );
});

// Tapping the notification opens the relevant admin page.
self.addEventListener('notificationclick', (event) => {
  event.notification.close();
  const target = new URL(event.notification.data.url || '/admin/', self.location.origin).href;
  event.waitUntil(
    self.clients.matchAll({ type: 'window', includeUncontrolled: true }).then((wins) => {
      for (const w of wins) {
        if (w.url === target && 'focus' in w) return w.focus();
      }
      return self.clients.openWindow(target);
    })
  );
});
