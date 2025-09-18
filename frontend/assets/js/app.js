// CIP Immobiliare - PWA JavaScript
class CIPApp {
  constructor() {
    this.deferredPrompt = null;
    this.isOnline = navigator.onLine;
    this.registration = null;
    
    this.init();
  }
  
  async init() {
    console.log('🚀 Inizializzazione CIP Immobiliare PWA...');
    
    // Registra service worker
    await this.registerServiceWorker();
    
    // Setup event listeners
    this.setupEventListeners();
    
    // Setup install prompt
    this.setupInstallPrompt();
    
    // Setup offline detection
    this.setupOfflineDetection();
    
    // Setup push notifications
    await this.setupPushNotifications();
    
    // Setup background sync
    this.setupBackgroundSync();
    

    console.log('✅ CIP Immobiliare PWA inizializzato');
  }
  
  // =====================================================
  // SERVICE WORKER REGISTRATION
  // =====================================================
  
  async registerServiceWorker() {
    if ('serviceWorker' in navigator) {
      try {
        this.registration = await navigator.serviceWorker.register('/assets/sw.js');
        console.log('✅ Service Worker registrato:', this.registration);
        
        // Gestione aggiornamenti
        this.registration.addEventListener('updatefound', () => {
          const newWorker = this.registration.installing;
          
          newWorker.addEventListener('statechange', () => {
            if (newWorker.state === 'installed' && navigator.serviceWorker.controller) {
              this.showUpdateNotification();
            }
          });
        });
        
      } catch (error) {
        console.error('❌ Errore registrazione Service Worker:', error);
      }
    } else {
      console.warn('⚠️ Service Worker non supportato');
    }
  }
  
  // =====================================================
  // INSTALL PROMPT
  // =====================================================
  
  setupInstallPrompt() {
    window.addEventListener('beforeinstallprompt', (e) => {
      e.preventDefault();
      this.deferredPrompt = e;
      
      // Mostra pulsante install se nascosto
      this.showInstallButton();
    });
    
    // Gestione install completato
    window.addEventListener('appinstalled', () => {
      console.log('📱 App installata con successo');
      this.hideInstallButton();
      this.deferredPrompt = null;
      
      // Analytics
      this.trackEvent('app_installed');
    });
  }
  
  showInstallButton() {
    const installBtn = document.getElementById('install-app-btn');
    if (installBtn) {
      installBtn.style.display = 'block';
      installBtn.addEventListener('click', () => this.installApp());
    }
  }
  
  hideInstallButton() {
    const installBtn = document.getElementById('install-app-btn');
    if (installBtn) {
      installBtn.style.display = 'none';
    }
  }
  
  async installApp() {
    if (this.deferredPrompt) {
      this.deferredPrompt.prompt();
      
      const { outcome } = await this.deferredPrompt.userChoice;
      console.log('Risposta utente install prompt:', outcome);
      
      this.deferredPrompt = null;
      this.hideInstallButton();
    }
  }
  
  // =====================================================
  // OFFLINE DETECTION
  // =====================================================
  
  setupOfflineDetection() {
    window.addEventListener('online', () => {
      this.isOnline = true;
      this.hideOfflineBanner();
      this.syncOfflineData();
    });
    
    window.addEventListener('offline', () => {
      this.isOnline = false;
      this.showOfflineBanner();
    });
    
    // Controlla stato iniziale
    if (!this.isOnline) {
      this.showOfflineBanner();
    }
  }
  
  showOfflineBanner() {
    let banner = document.getElementById('offline-banner');
    if (!banner) {
      banner = document.createElement('div');
      banner.id = 'offline-banner';
      banner.className = 'fixed top-0 left-0 right-0 bg-red-500 text-white text-center py-2 z-50';
      banner.innerHTML = `
        <span class="flex items-center justify-center">
          <svg class="w-4 h-4 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-2.5L13.732 4c-.77-.833-1.964-.833-2.732 0L3.732 16.5c-.77.833.192 2.5 1.732 2.5z"/>
          </svg>
          Modalità offline - Alcune funzionalità potrebbero non essere disponibili
        </span>
      `;
      document.body.appendChild(banner);
    }
    banner.style.display = 'block';
  }
  
  hideOfflineBanner() {
    const banner = document.getElementById('offline-banner');
    if (banner) {
      banner.style.display = 'none';
    }
  }
  
  // =====================================================
  // PUSH NOTIFICATIONS
  // =====================================================
  
  async setupPushNotifications() {
    if ('Notification' in window && this.registration) {
      const permission = await Notification.requestPermission();
      
      if (permission === 'granted') {
        console.log('✅ Permessi notifiche concessi');
        await this.subscribeToPush();
      } else {
        console.log('❌ Permessi notifiche negati');
      }
    }
  }
  
  async subscribeToPush() {
    try {
      const subscription = await this.registration.pushManager.subscribe({
        userVisibleOnly: true,
        applicationServerKey: this.urlBase64ToUint8Array('YOUR_VAPID_PUBLIC_KEY')
      });
      
      console.log('📱 Sottoscrizione push completata:', subscription);
      
      // Invia subscription al server
      await this.sendSubscriptionToServer(subscription);
      
    } catch (error) {
      console.error('❌ Errore sottoscrizione push:', error);
    }
  }
  
  async sendSubscriptionToServer(subscription) {
    try {
      await fetch('/api/push-subscription', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(subscription)
      });
    } catch (error) {
      console.error('❌ Errore invio subscription al server:', error);
    }
  }
  
  urlBase64ToUint8Array(base64String) {
    const padding = '='.repeat((4 - base64String.length % 4) % 4);
    const base64 = (base64String + padding)
      .replace(/-/g, '+')
      .replace(/_/g, '/');
    
    const rawData = window.atob(base64);
    const outputArray = new Uint8Array(rawData.length);
    
    for (let i = 0; i < rawData.length; ++i) {
      outputArray[i] = rawData.charCodeAt(i);
    }
    return outputArray;
  }
  
  // =====================================================
  // BACKGROUND SYNC
  // =====================================================
  
  setupBackgroundSync() {
    if ('serviceWorker' in navigator && 'sync' in window.ServiceWorkerRegistration.prototype) {
      // Background sync per operazioni offline
      this.setupOfflineActions();
    }
  }
  
  setupOfflineActions() {
    // Form submission offline
    document.addEventListener('submit', (e) => {
      if (!this.isOnline) {
        e.preventDefault();
        this.handleOfflineForm(e.target);
      }
    });
  }
  
  async handleOfflineForm(form) {
    const formData = new FormData(form);
    const data = {
      action: form.action,
      method: form.method,
      data: Object.fromEntries(formData),
      timestamp: Date.now()
    };
    
    // Salva in IndexedDB per sync successivo
    await this.saveOfflineAction(data);
    
    // Mostra messaggio offline
    this.showMessage('Azione salvata offline - Verrà sincronizzata quando torni online', 'info');
  }
  
  async saveOfflineAction(action) {
    if ('indexedDB' in window) {
      const db = await this.openIndexedDB();
      const transaction = db.transaction(['offlineActions'], 'readwrite');
      const store = transaction.objectStore('offlineActions');
      
      await store.add(action);
    }
  }
  
  async openIndexedDB() {
    return new Promise((resolve, reject) => {
      const request = indexedDB.open('CIPOfflineDB', 1);
      
      request.onerror = () => reject(request.error);
      request.onsuccess = () => resolve(request.result);
      
      request.onupgradeneeded = (event) => {
        const db = event.target.result;
        if (!db.objectStoreNames.contains('offlineActions')) {
          db.createObjectStore('offlineActions', { keyPath: 'timestamp' });
        }
      };
    });
  }
  
  // =====================================================
  // OFFLINE DATA SYNC
  // =====================================================
  
  async syncOfflineData() {
    if ('indexedDB' in window) {
      try {
        const db = await this.openIndexedDB();
        const transaction = db.transaction(['offlineActions'], 'readonly');
        const store = transaction.objectStore('offlineActions');
        const actions = await store.getAll();
        
        for (const action of actions) {
          await this.processOfflineAction(action);
        }
        
        // Pulisci azioni processate
        await this.clearOfflineActions();
        
        console.log('✅ Dati offline sincronizzati');
        
      } catch (error) {
        console.error('❌ Errore sync dati offline:', error);
      }
    }
  }
  
  async processOfflineAction(action) {
    try {
      const response = await fetch(action.action, {
        method: action.method,
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(action.data)
      });
      
      if (response.ok) {
        console.log('✅ Azione offline processata:', action);
      }
      
    } catch (error) {
      console.error('❌ Errore processamento azione offline:', action, error);
    }
  }
  
  async clearOfflineActions() {
    if ('indexedDB' in window) {
      const db = await this.openIndexedDB();
      const transaction = db.transaction(['offlineActions'], 'readwrite');
      const store = transaction.objectStore('offlineActions');
      
      await store.clear();
    }
  }
  
  // =====================================================
  // UTILITY FUNCTIONS
  // =====================================================
  
  showMessage(message, type = 'info') {
    const messageDiv = document.createElement('div');
    messageDiv.className = `fixed top-4 right-4 p-4 rounded-lg shadow-lg z-50 ${
      type === 'error' ? 'bg-red-500 text-white' :
      type === 'success' ? 'bg-green-500 text-white' :
      'bg-blue-500 text-white'
    }`;
    messageDiv.textContent = message;
    
    document.body.appendChild(messageDiv);
    
    setTimeout(() => {
      messageDiv.remove();
    }, 5000);
  }
  
  trackEvent(eventName, data = {}) {
    // Analytics tracking
    if (typeof gtag !== 'undefined') {
      gtag('event', eventName, data);
    }
    
    console.log('📊 Event tracked:', eventName, data);
  }
  
  // =====================================================
  // EVENT LISTENERS
  // =====================================================
  
  setupEventListeners() {
    // Gestione errori globali
    window.addEventListener('error', (e) => {
      console.error('❌ Errore globale:', e.error);
      this.trackEvent('app_error', { error: e.error.message });
    });
  
    // Gestione promise rejection
    window.addEventListener('unhandledrejection', (e) => {
      console.error('❌ Promise rejection non gestita:', e.reason);
      this.trackEvent('promise_rejection', { reason: e.reason });
    });
    
    // Gestione visibility change
    document.addEventListener('visibilitychange', () => {
      if (document.hidden) {
        this.trackEvent('app_background');
      } else {
        this.trackEvent('app_foreground');
      }
    });

  }
  
  showUpdateNotification() {
    const updateDiv = document.createElement('div');
    updateDiv.className = 'fixed bottom-20 left-4 right-4 bg-blue-500 text-white p-4 rounded-lg shadow-lg z-50';
    updateDiv.innerHTML = `
      <div class="flex items-center justify-between">
        <span>🔄 Nuova versione disponibile</span>
        <button onclick="location.reload()" class="bg-white text-blue-500 px-3 py-1 rounded text-sm">
          Aggiorna
        </button>
      </div>
    `;
    
    document.body.appendChild(updateDiv);
    
    setTimeout(() => {
      updateDiv.remove();
    }, 10000);
  }
}

// =====================================================
// INITIALIZATION
// =====================================================

// Inizializza app quando DOM è pronto
document.addEventListener('DOMContentLoaded', () => {
  window.cipApp = new CIPApp();
});

// Inizializza app se DOM è già pronto
if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', () => {
    window.cipApp = new CIPApp();
  });
} else {
  window.cipApp = new CIPApp();
}

console.log('🚀 CIP Immobiliare PWA JavaScript caricato');

// =====================================================
// Cache buster Wed Sep 17 15:47:19 CEST 2025
