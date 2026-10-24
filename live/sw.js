const CACHE = 'pctv-live-shell-v1';
const SHELL = ['./','./index.html','./styles.css','./app.mjs','./catalog.mjs','./manifest.webmanifest','./icon-144.png','./icon-192.png','./icon-512.png','./vendor/hls-1.7.3.min.js','./vendor/hls-LICENSE.txt'];
const shellUrls = new Set(SHELL.map(path => new URL(path, self.registration.scope).href));
self.addEventListener('install', event => {
  event.waitUntil(caches.open(CACHE).then(cache => cache.addAll(SHELL)).then(() => self.skipWaiting()));
});
self.addEventListener('activate', event => {
  event.waitUntil(caches.keys().then(keys => Promise.all(keys.filter(key => key.startsWith('pctv-live-shell-') && key !== CACHE).map(key => caches.delete(key)))).then(() => self.clients.claim()));
});
self.addEventListener('fetch', event => {
  // Only exact, local app-shell URLs. Never intercept playlists, video, range requests or third-party traffic.
  if (event.request.method !== 'GET' || event.request.headers.has('range') || !shellUrls.has(event.request.url)) return;
  event.respondWith(caches.match(event.request).then(cached => cached || fetch(event.request)));
});
