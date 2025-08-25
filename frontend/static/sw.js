const CACHE_NAME = 'cip-immobiliare-v1.0.0';
const urlsToCache = [
  '/',
  '/dashboard',
  '/portfolio',
  '/projects',
  '/referral',
  '/profile',
  '/static/css/brand-colors.css',
  '/static/css/style.css',
  '/static/js/app.js'
];

// Install event - cache delle risorse principali
self.addEventListener('install', event => {
  event.waitUntil(
    caches.open(CACHE_NAME)
      .then(cache => {
        console.log('Opened cache');
        return cache.addAll(urlsToCache);
      })
  );
});

// Fetch event - strategia cache-first per risorse statiche
self.addEventListener('fetch', event => {
  event.respondWith(
    caches.match(event.request)
      .then(response => {
        // Cache hit - return response
        if (response) {
          return response;
        }
        
        // Clone della request
        const fetchRequest = event.request.clone();
        
        return fetch(fetchRequest).then(
          response => {
            // Check if we received a valid response
            if(!response || response.status !== 200 || response.type !== 'basic') {
              return response;
            }
            
            // Clone della response
            const responseToCache = response.clone();
            
            caches.open(CACHE_NAME)
              .then(cache => {
                cache.put(event.request, responseToCache);
              });
            
            return response;
          }
        );
      })
  );
});

// Activate event - pulizia cache vecchie
self.addEventListener('activate', event => {
  const cacheWhitelist = [CACHE_NAME];
  
  event.waitUntil(
    caches.keys().then(cacheNames => {
      return Promise.all(
        cacheNames.map(cacheName => {
          if (cacheWhitelist.indexOf(cacheName) === -1) {
            return caches.delete(cacheName);
          }
        })
      );
    })
  );
});

// Background sync per operazioni offline
self.addEventListener('sync', event => {
  if (event.tag === 'background-sync') {
    event.waitUntil(doBackgroundSync());
  }
});

// Push notifications
self.addEventListener('push', event => {
  const options = {
    body: event.data ? event.data.text() : 'Nuova notifica da CIP Immobiliare',
    icon: '/static/icons/icon-192x192.png',
    badge: '/static/icons/icon-72x72.png',
    vibrate: [100, 50, 100],
    data: {
      dateOfArrival: Date.now(),
      primaryKey: 1
    },
    actions: [
      {
        action: 'explore',
        title: 'Vedi Dettagli',
        icon: '/static/icons/icon-72x72.png'
      },
      {
        action: 'close',
        title: 'Chiudi',
        icon: '/static/icons/icon-72x72.png'
      }
    ]
  };
  
  event.waitUntil(
    self.registration.showNotification('CIP Immobiliare', options)
  );
});

// Notification click
self.addEventListener('notificationclick', event => {
  event.notification.close();
  
  if (event.action === 'explore') {
    event.waitUntil(
      clients.openWindow('/dashboard')
    );
  }
});

// Funzione per background sync
function doBackgroundSync() {
  // Implementa la logica per sincronizzare i dati offline
  console.log('Background sync in corso...');
  
  // Esempio: sincronizza investimenti offline
  return fetch('/api/sync-offline-data', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({
      timestamp: Date.now(),
      action: 'sync'
    })
  }).catch(error => {
    console.log('Background sync fallito:', error);
  });
}

// Intercepta le richieste API per cache intelligente
self.addEventListener('fetch', event => {
  if (event.request.url.includes('/api/')) {
    event.respondWith(
      fetch(event.request)
        .then(response => {
          // Cache delle risposte API per 5 minuti
          if (response.status === 200) {
            const responseClone = response.clone();
            caches.open(CACHE_NAME).then(cache => {
              cache.put(event.request, responseClone);
            });
          }
          return response;
        })
        .catch(() => {
          // Fallback alla cache se offline
          return caches.match(event.request);
        })
    );
  }
});

// Gestione errori
self.addEventListener('error', event => {
  console.error('Service Worker error:', event.error);
});

// Gestione promise rejection
self.addEventListener('unhandledrejection', event => {
  console.error('Service Worker unhandled rejection:', event.reason);
});
