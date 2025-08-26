// Service Worker per CIP Immobiliare PWA
const CACHE_NAME = 'cip-immobiliare-v1.0.0';
const STATIC_CACHE = 'cip-static-v1.0.0';
const DYNAMIC_CACHE = 'cip-dynamic-v1.0.0';

// Risorse da cacheare immediatamente
const STATIC_ASSETS = [
  '/',
  '/user/dashboard',
  '/user/search',
  '/user/new-project',
  '/user/portfolio',
  '/user/profile',
  '/assets/css/style.css',
  '/assets/css/mobile-optimizations.css',
  '/assets/css/output.css',
  '/assets/css/brand-colors.css',
  '/assets/js/app.js',
  '/assets/manifest.json',
  '/assets/icons/icon-192x192.png',
  '/assets/icons/icon-512x512.png'
];

// Strategie di cache
const CACHE_STRATEGIES = {
  STATIC: 'cache-first',
  DYNAMIC: 'network-first',
  API: 'stale-while-revalidate'
};

// Install event - cache delle risorse principali
self.addEventListener('install', event => {
  console.log('🔄 Service Worker installato');
  
  event.waitUntil(
    caches.open(STATIC_CACHE)
      .then(cache => {
        console.log('📦 Cache statica aperta');
        return cache.addAll(STATIC_ASSETS);
      })
      .then(() => {
        console.log('✅ Risorse principali cacheate');
        return self.skipWaiting();
      })
      .catch(error => {
        console.error('❌ Errore durante installazione:', error);
      })
  );
});

// Activate event - pulizia cache vecchie
self.addEventListener('activate', event => {
  console.log('🚀 Service Worker attivato');
  
  event.waitUntil(
    caches.keys()
      .then(cacheNames => {
        return Promise.all(
          cacheNames.map(cacheName => {
            if (cacheName !== STATIC_CACHE && cacheName !== DYNAMIC_CACHE) {
              console.log('🗑️ Rimuovo cache vecchia:', cacheName);
              return caches.delete(cacheName);
            }
          })
        );
      })
      .then(() => {
        console.log('✅ Cache pulita');
        return self.clients.claim();
      })
  );
});

// Fetch event - gestione richieste
self.addEventListener('fetch', event => {
  const { request } = event;
  const url = new URL(request.url);
  
  // Ignora richieste non HTTP
  if (!request.url.startsWith('http')) {
    return;
  }
  
  // Gestione API calls
  if (url.pathname.startsWith('/api/') || url.pathname.includes('portfolio/')) {
    event.respondWith(handleApiRequest(request));
    return;
  }
  
  // Gestione pagine HTML
  if (request.destination === 'document') {
    event.respondWith(handlePageRequest(request));
    return;
  }
  
  // Gestione assets statici
  if (request.destination === 'style' || 
      request.destination === 'script' || 
      request.destination === 'image') {
    event.respondWith(handleStaticAsset(request));
    return;
  }
  
  // Fallback per altre richieste
  event.respondWith(handleFallback(request));
});

// Gestione richieste API
async function handleApiRequest(request) {
  try {
    // Prova prima la rete
    const networkResponse = await fetch(request);
    
    // Cache la risposta per uso futuro
    const cache = await caches.open(DYNAMIC_CACHE);
    cache.put(request, networkResponse.clone());
    
    return networkResponse;
  } catch (error) {
    // Se la rete fallisce, prova la cache
    const cachedResponse = await caches.match(request);
    if (cachedResponse) {
      return cachedResponse;
    }
    
    // Fallback con risposta offline
    return new Response(
      JSON.stringify({ 
        error: 'Offline - Dati non disponibili',
        message: 'Connettiti a internet per aggiornare i dati'
      }),
      { 
        status: 503,
        headers: { 'Content-Type': 'application/json' }
      }
    );
  }
}

// Gestione richieste pagine
async function handlePageRequest(request) {
  try {
    // Prova prima la cache
    const cachedResponse = await caches.match(request);
    
    if (cachedResponse) {
      // Aggiorna la cache in background
      fetch(request).then(response => {
        if (response.ok) {
          caches.open(DYNAMIC_CACHE).then(cache => {
            cache.put(request, response);
          });
        }
      });
      
      return cachedResponse;
    }
    
    // Se non in cache, prova la rete
    const networkResponse = await fetch(request);
    
    if (networkResponse.ok) {
      // Cache la risposta
      const cache = await caches.open(DYNAMIC_CACHE);
      cache.put(request, networkResponse.clone());
    }
    
    return networkResponse;
  } catch (error) {
    // Fallback alla dashboard offline
    return caches.match('/user/dashboard');
  }
}

// Gestione assets statici
async function handleStaticAsset(request) {
  try {
    // Prova prima la cache
    const cachedResponse = await caches.match(request);
    
    if (cachedResponse) {
      return cachedResponse;
    }
    
    // Se non in cache, prova la rete
    const networkResponse = await fetch(request);
    
    if (networkResponse.ok) {
      // Cache la risposta
      const cache = await caches.open(STATIC_CACHE);
      cache.put(request, networkResponse.clone());
    }
    
    return networkResponse;
  } catch (error) {
    // Fallback con risorsa generica
    return new Response('', { status: 404 });
  }
}

// Gestione fallback
async function handleFallback(request) {
  try {
    const response = await fetch(request);
    return response;
  } catch (error) {
    // Fallback generico offline
    return new Response('Offline', { status: 503 });
  }
}

// Push notification event
self.addEventListener('push', event => {
  console.log('📱 Push notification ricevuta');
  
  const options = {
    body: event.data ? event.data.text() : 'Nuova notifica da CIP Immobiliare',
    icon: '/assets/icons/icon-192x192.png',
    badge: '/assets/icons/icon-72x72.png',
    vibrate: [100, 50, 100],
    data: {
      dateOfArrival: Date.now(),
      primaryKey: 1
    },
    actions: [
      {
        action: 'explore',
        title: 'Apri App',
        icon: '/assets/icons/icon-96x96.png'
      },
      {
        action: 'close',
        title: 'Chiudi',
        icon: '/assets/icons/icon-96x96.png'
      }
    ]
  };
  
  event.waitUntil(
    self.registration.showNotification('CIP Immobiliare', options)
  );
});

// Click su notification
self.addEventListener('notificationclick', event => {
  console.log('👆 Notification cliccata');
  
  event.notification.close();
  
  if (event.action === 'explore') {
    event.waitUntil(
      clients.openWindow('/user/dashboard')
    );
  }
});

// Background sync
self.addEventListener('sync', event => {
  console.log('🔄 Background sync:', event.tag);
  
  if (event.tag === 'background-sync') {
    event.waitUntil(doBackgroundSync());
  }
});

// Funzione background sync
async function doBackgroundSync() {
  try {
    // Sincronizza dati in background
    console.log('🔄 Sincronizzazione in background...');
    
    // TODO: Implementare sincronizzazione dati offline
    // - Salva modifiche profilo
    // - Aggiorna portfolio
    // - Invia notifiche
    
  } catch (error) {
    console.error('❌ Errore background sync:', error);
  }
}

// Message event per comunicazione con app
self.addEventListener('message', event => {
  console.log('💬 Messaggio ricevuto:', event.data);
  
  if (event.data && event.data.type === 'SKIP_WAITING') {
    self.skipWaiting();
  }
  
  if (event.data && event.data.type === 'GET_VERSION') {
    event.ports[0].postMessage({ version: CACHE_NAME });
  }
});

console.log('🚀 Service Worker PWA caricato:', CACHE_NAME);
