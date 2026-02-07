/**
 * Service Worker for PoopyFeed PWA.
 * Handles offline caching and push notifications.
 */

const CACHE_NAME = 'poopyfeed-v1';
const OFFLINE_URL = '/offline/';

// Assets to cache on install (cache individually to allow partial success)
const PRECACHE_ASSETS = [
  OFFLINE_URL,
  '/static/js/datetime.js',
  '/static/images/favicon.svg',
];

// Install event - cache assets individually (resilient to failures)
self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME)
      .then((cache) => {
        return Promise.all(
          PRECACHE_ASSETS.map((url) =>
            cache.add(url).catch(() => {
              // Individual asset failed, continue with others
            })
          )
        );
      })
      .then(() => self.skipWaiting())
  );
});

// Activate event - clean old caches
self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys().then((cacheNames) => {
      return Promise.all(
        cacheNames.map((cacheName) => {
          if (cacheName.startsWith('poopyfeed-') && cacheName !== CACHE_NAME) {
            return caches.delete(cacheName);
          }
        })
      );
    }).then(() => self.clients.claim())
  );
});

// Fetch event - network first with cache fallback
self.addEventListener('fetch', (event) => {
  const { request } = event;

  // Skip non-GET requests
  if (request.method !== 'GET') {
    return;
  }

  // Skip admin and accounts (auth-related) requests
  const url = new URL(request.url);
  if (url.pathname.startsWith('/admin/') || url.pathname.startsWith('/accounts/')) {
    return;
  }

  event.respondWith(
    fetch(request)
      .then((response) => {
        // Cache successful responses
        if (response && response.status === 200) {
          const responseToCache = response.clone();
          caches.open(CACHE_NAME).then((cache) => {
            cache.put(request, responseToCache);
          });
        }
        return response;
      })
      .catch(() => {
        // Offline - try cache first
        return caches.match(request).then((cachedResponse) => {
          if (cachedResponse) {
            return cachedResponse;
          }
          // For navigation requests, show offline page
          if (request.mode === 'navigate') {
            return caches.match(OFFLINE_URL);
          }
          // For other requests, return empty response
          return new Response('', { status: 503, statusText: 'Offline' });
        });
      })
  );
});

// Push notification handling
self.addEventListener('push', (event) => {
  if (!event.data) {
    return;
  }

  try {
    const data = event.data.json();
    const options = {
      body: data.body || '',
      icon: data.icon || '/static/images/favicon.svg',
      badge: data.badge || '/static/images/favicon.svg',
      tag: data.tag || 'default',
      requireInteraction: true,
      data: {
        url: data.data && data.data.url ? data.data.url : '/children/',
      },
    };

    event.waitUntil(
      self.registration.showNotification(data.title || 'PoopyFeed', options)
    );
  } catch (error) {
    console.error('Push event error:', error);
  }
});

// Notification click handling
self.addEventListener('notificationclick', (event) => {
  event.notification.close();

  event.waitUntil(
    clients.matchAll({ type: 'window', includeUncontrolled: true })
      .then((clientList) => {
        // Try to focus existing window
        for (const client of clientList) {
          if (client.url.includes('/children') && 'focus' in client) {
            return client.focus();
          }
        }
        // Open new window if none exists
        if (clients.openWindow) {
          return clients.openWindow(event.notification.data.url || '/children/');
        }
      })
  );
});
