/**
 * Service Worker for push notifications.
 */

self.addEventListener('push', function(event) {
  if (!event.data) {
    return;
  }

  try {
    var data = event.data.json();
    var options = {
      body: data.body || '',
      icon: data.icon || '/static/icon-192.png',
      badge: data.badge || '/static/badge-72.png',
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

self.addEventListener('notificationclick', function(event) {
  event.notification.close();

  event.waitUntil(
    clients.matchAll({ type: 'window', includeUncontrolled: true })
      .then(function(clientList) {
        // Try to focus existing window
        for (var i = 0; i < clientList.length; i++) {
          var client = clientList[i];
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
