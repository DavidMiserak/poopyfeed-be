/**
 * Push notification subscription management.
 */
var PushNotifications = (function() {
  'use strict';

  var publicVapidKey = null;

  /**
   * Initialize push notifications with VAPID public key.
   */
  async function init(vapidKey) {
    publicVapidKey = vapidKey;

    if (!('serviceWorker' in navigator) || !('PushManager' in window)) {
      console.warn('Push notifications not supported');
      return false;
    }

    try {
      await navigator.serviceWorker.register('/static/js/service-worker.js');
      return true;
    } catch (error) {
      console.error('Service Worker registration failed:', error);
      return false;
    }
  }

  /**
   * Subscribe to push notifications.
   */
  async function subscribe() {
    try {
      var registration = await navigator.serviceWorker.ready;

      var permission = await Notification.requestPermission();
      if (permission !== 'granted') {
        return { success: false, error: 'Permission denied' };
      }

      var subscription = await registration.pushManager.subscribe({
        userVisibleOnly: true,
        applicationServerKey: urlBase64ToUint8Array(publicVapidKey),
      });

      var response = await fetch('/notifications/api/push/subscribe/', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-CSRFToken': getCsrfToken(),
        },
        body: JSON.stringify({ subscription: subscription.toJSON() }),
      });

      if (!response.ok) {
        throw new Error('Failed to save subscription');
      }

      return { success: true };

    } catch (error) {
      console.error('Subscription failed:', error);
      return { success: false, error: error.message };
    }
  }

  /**
   * Unsubscribe from push notifications.
   */
  async function unsubscribe() {
    try {
      var registration = await navigator.serviceWorker.ready;
      var subscription = await registration.pushManager.getSubscription();

      if (subscription) {
        await subscription.unsubscribe();

        await fetch('/notifications/api/push/unsubscribe/', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': getCsrfToken(),
          },
          body: JSON.stringify({ endpoint: subscription.endpoint }),
        });
      }

      return { success: true };

    } catch (error) {
      console.error('Unsubscribe failed:', error);
      return { success: false, error: error.message };
    }
  }

  /**
   * Check if user is currently subscribed.
   */
  async function isSubscribed() {
    try {
      if (!('serviceWorker' in navigator)) {
        return false;
      }
      var registration = await navigator.serviceWorker.ready;
      var subscription = await registration.pushManager.getSubscription();
      return subscription !== null;
    } catch (error) {
      return false;
    }
  }

  /**
   * Check if push notifications are supported.
   */
  function isSupported() {
    return 'serviceWorker' in navigator && 'PushManager' in window;
  }

  /**
   * Convert VAPID key from base64 to Uint8Array.
   */
  function urlBase64ToUint8Array(base64String) {
    var padding = '='.repeat((4 - base64String.length % 4) % 4);
    var base64 = (base64String + padding)
      .replace(/-/g, '+')
      .replace(/_/g, '/');

    var rawData = window.atob(base64);
    var outputArray = new Uint8Array(rawData.length);

    for (var i = 0; i < rawData.length; ++i) {
      outputArray[i] = rawData.charCodeAt(i);
    }
    return outputArray;
  }

  /**
   * Get CSRF token from cookie.
   */
  function getCsrfToken() {
    var name = 'csrftoken';
    var cookieValue = null;
    if (document.cookie && document.cookie !== '') {
      var cookies = document.cookie.split(';');
      for (var i = 0; i < cookies.length; i++) {
        var cookie = cookies[i].trim();
        if (cookie.substring(0, name.length + 1) === (name + '=')) {
          cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
          break;
        }
      }
    }
    return cookieValue;
  }

  return {
    init: init,
    subscribe: subscribe,
    unsubscribe: unsubscribe,
    isSubscribed: isSubscribed,
    isSupported: isSupported,
    getCsrfToken: getCsrfToken
  };
})();
