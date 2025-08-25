// CIP Immobiliare - JavaScript principale per PWA

// Utility functions
const $ = (selector) => document.querySelector(selector);
const $$ = (selector) => document.querySelectorAll(selector);

// App state
const appState = {
    isOnline: navigator.onLine,
    currentUser: null,
    notifications: [],
    theme: localStorage.getItem('theme') || 'light'
};

// Initialize app
document.addEventListener('DOMContentLoaded', () => {
    initializeApp();
    setupEventListeners();
    setupPWAFeatures();
});

// Initialize app
function initializeApp() {
    console.log('🚀 CIP Immobiliare PWA inizializzata');
    
    // Set theme
    setTheme(appState.theme);
    
    // Check online status
    updateOnlineStatus();
    
    // Initialize components
    initializeComponents();
    
    // Show welcome message
    if (localStorage.getItem('firstVisit') === null) {
        showWelcomeMessage();
        localStorage.setItem('firstVisit', 'true');
    }
}

// Setup event listeners
function setupEventListeners() {
    // Online/offline events
    window.addEventListener('online', () => {
        appState.isOnline = true;
        updateOnlineStatus();
        showNotification('Connessione ripristinata', 'success');
    });
    
    window.addEventListener('offline', () => {
        appState.isOnline = false;
        updateOnlineStatus();
        showNotification('Modalità offline attiva', 'info');
    });
    
    // Theme toggle
    const themeToggle = $('#theme-toggle');
    if (themeToggle) {
        themeToggle.addEventListener('click', toggleTheme);
    }
    
    // Search functionality
    const searchInput = $('#search-input');
    if (searchInput) {
        searchInput.addEventListener('input', debounce(handleSearch, 300));
    }
    
    // Form submissions
    setupFormHandlers();
    
    // Mobile navigation
    setupMobileNavigation();
}

// Initialize components
function initializeComponents() {
    // Initialize tooltips
    initializeTooltips();
    
    // Initialize modals
    initializeModals();
    
    // Initialize charts if present
    if (typeof Chart !== 'undefined') {
        initializeCharts();
    }
    
    // Initialize lazy loading
    initializeLazyLoading();
}

// Setup PWA features
function setupPWAFeatures() {
    // Service Worker registration
    if ('serviceWorker' in navigator) {
        navigator.serviceWorker.register('/static/sw.js')
            .then(registration => {
                console.log('Service Worker registrato:', registration);
                setupServiceWorkerEvents(registration);
            })
            .catch(error => {
                console.error('Errore registrazione Service Worker:', error);
            });
    }
    
    // Install prompt
    setupInstallPrompt();
    
    // Background sync
    setupBackgroundSync();
    
    // Push notifications
    setupPushNotifications();
}

// Service Worker events
function setupServiceWorkerEvents(registration) {
    // Update found
    registration.addEventListener('updatefound', () => {
        const newWorker = registration.installing;
        newWorker.addEventListener('statechange', () => {
            if (newWorker.state === 'installed' && navigator.serviceWorker.controller) {
                showUpdateNotification();
            }
        });
    });
    
    // Controller change
    navigator.serviceWorker.addEventListener('controllerchange', () => {
        console.log('Nuovo Service Worker attivo');
    });
}

// Install prompt setup
function setupInstallPrompt() {
    let deferredPrompt;
    
    window.addEventListener('beforeinstallprompt', (e) => {
        e.preventDefault();
        deferredPrompt = e;
        
        // Show install button if hidden
        const installBtn = $('#install-app-btn');
        if (installBtn) {
            installBtn.style.display = 'block';
            installBtn.addEventListener('click', async () => {
                installBtn.style.display = 'none';
                deferredPrompt.prompt();
                const { outcome } = await deferredPrompt.userChoice;
                console.log('Risposta utente install prompt:', outcome);
                deferredPrompt = null;
            });
        }
    });
}

// Background sync setup
function setupBackgroundSync() {
    if ('serviceWorker' in navigator && 'SyncManager' in window) {
        navigator.serviceWorker.ready.then(registration => {
            // Register background sync
            registration.sync.register('background-sync')
                .then(() => {
                    console.log('Background sync registrato');
                })
                .catch(error => {
                    console.error('Errore background sync:', error);
                });
        });
    }
}

// Push notifications setup
function setupPushNotifications() {
    if ('serviceWorker' in navigator && 'PushManager' in window) {
        navigator.serviceWorker.ready.then(registration => {
            // Request notification permission
            if (Notification.permission === 'default') {
                Notification.requestPermission().then(permission => {
                    if (permission === 'granted') {
                        subscribeToPushNotifications(registration);
                    }
                });
            } else if (Notification.permission === 'granted') {
                subscribeToPushNotifications(registration);
            }
        });
    }
}

// Subscribe to push notifications
async function subscribeToPushNotifications(registration) {
    try {
        const subscription = await registration.pushManager.subscribe({
            userVisibleOnly: true,
            applicationServerKey: urlBase64ToUint8Array('YOUR_VAPID_PUBLIC_KEY')
        });
        
        // Send subscription to server
        await sendSubscriptionToServer(subscription);
        console.log('Push notification subscription completata');
    } catch (error) {
        console.error('Errore push notification subscription:', error);
    }
}

// Utility functions
function urlBase64ToUint8Array(base64String) {
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

// Send subscription to server
async function sendSubscriptionToServer(subscription) {
    try {
        const response = await fetch('/api/push-subscription', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify(subscription)
        });
        
        if (!response.ok) {
            throw new Error('Errore invio subscription al server');
        }
    } catch (error) {
        console.error('Errore invio subscription:', error);
    }
}

// Theme management
function setTheme(theme) {
    document.documentElement.setAttribute('data-theme', theme);
    appState.theme = theme;
    localStorage.setItem('theme', theme);
}

function toggleTheme() {
    const newTheme = appState.theme === 'light' ? 'dark' : 'light';
    setTheme(newTheme);
}

// Search functionality
function handleSearch(event) {
    const query = event.target.value.trim();
    if (query.length < 2) return;
    
    // Implement search logic
    searchProjects(query);
}

async function searchProjects(query) {
    try {
        const response = await fetch(`/api/search?q=${encodeURIComponent(query)}`);
        const results = await response.json();
        
        // Update UI with search results
        updateSearchResults(results);
    } catch (error) {
        console.error('Errore ricerca:', error);
    }
}

function updateSearchResults(results) {
    const resultsContainer = $('#search-results');
    if (!resultsContainer) return;
    
    // Clear previous results
    resultsContainer.innerHTML = '';
    
    if (results.length === 0) {
        resultsContainer.innerHTML = '<p class="text-cip-neutral-600">Nessun risultato trovato</p>';
        return;
    }
    
    // Display results
    results.forEach(result => {
        const resultElement = createSearchResultElement(result);
        resultsContainer.appendChild(resultElement);
    });
}

function createSearchResultElement(result) {
    const div = document.createElement('div');
    div.className = 'p-3 border-b border-cip-neutral-200 hover:bg-cip-neutral-50 cursor-pointer';
    div.innerHTML = `
        <h4 class="font-medium text-cip-neutral-900">${result.title}</h4>
        <p class="text-sm text-cip-neutral-600">${result.description}</p>
    `;
    
    div.addEventListener('click', () => {
        window.location.href = result.url;
    });
    
    return div;
}

// Form handlers
function setupFormHandlers() {
    // Investment form
    const investmentForm = $('#investment-form');
    if (investmentForm) {
        investmentForm.addEventListener('submit', handleInvestmentSubmit);
    }
    
    // Profile form
    const profileForm = $('#profile-form');
    if (profileForm) {
        profileForm.addEventListener('submit', handleProfileSubmit);
    }
}

async function handleInvestmentSubmit(event) {
    event.preventDefault();
    
    const form = event.target;
    const formData = new FormData(form);
    
    try {
        // Show loading state
        setFormLoading(form, true);
        
        const response = await fetch('/api/investments', {
            method: 'POST',
            body: formData
        });
        
        if (!response.ok) {
            throw new Error('Errore invio investimento');
        }
        
        const result = await response.json();
        
        // Show success message
        showNotification('Investimento inviato con successo!', 'success');
        
        // Reset form
        form.reset();
        
        // Close modal if present
        const modal = form.closest('.modal');
        if (modal) {
            closeModal(modal);
        }
        
    } catch (error) {
        console.error('Errore investimento:', error);
        showNotification('Errore nell\'invio dell\'investimento', 'error');
    } finally {
        setFormLoading(form, false);
    }
}

async function handleProfileSubmit(event) {
    event.preventDefault();
    
    const form = event.target;
    const formData = new FormData(form);
    
    try {
        setFormLoading(form, true);
        
        const response = await fetch('/api/profile/update', {
            method: 'POST',
            body: formData
        });
        
        if (!response.ok) {
            throw new Error('Errore aggiornamento profilo');
        }
        
        showNotification('Profilo aggiornato con successo!', 'success');
        
    } catch (error) {
        console.error('Errore profilo:', error);
        showNotification('Errore nell\'aggiornamento del profilo', 'error');
    } finally {
        setFormLoading(form, false);
    }
}

// Form loading state
function setFormLoading(form, loading) {
    const submitBtn = form.querySelector('button[type="submit"]');
    if (submitBtn) {
        submitBtn.disabled = loading;
        submitBtn.innerHTML = loading ? 
            '<span class="loading-spinner"></span> Invio...' : 
            submitBtn.getAttribute('data-original-text') || 'Invia';
    }
}

// Mobile navigation
function setupMobileNavigation() {
    const mobileNavToggle = $('#mobile-nav-toggle');
    const mobileNav = $('#mobile-nav');
    
    if (mobileNavToggle && mobileNav) {
        mobileNavToggle.addEventListener('click', () => {
            mobileNav.classList.toggle('hidden');
        });
    }
    
    // Close mobile nav when clicking outside
    document.addEventListener('click', (event) => {
        if (!mobileNav?.contains(event.target) && !mobileNavToggle?.contains(event.target)) {
            mobileNav?.classList.add('hidden');
        }
    });
}

// Component initializers
function initializeTooltips() {
    const tooltipElements = $$('[data-tooltip]');
    tooltipElements.forEach(element => {
        element.addEventListener('mouseenter', showTooltip);
        element.addEventListener('mouseleave', hideTooltip);
    });
}

function initializeModals() {
    const modalTriggers = $$('[data-modal]');
    modalTriggers.forEach(trigger => {
        trigger.addEventListener('click', () => {
            const modalId = trigger.getAttribute('data-modal');
            openModal(modalId);
        });
    });
    
    // Close modal on backdrop click
    const modals = $$('.modal');
    modals.forEach(modal => {
        modal.addEventListener('click', (event) => {
            if (event.target === modal) {
                closeModal(modal);
            }
        });
    });
}

function initializeCharts() {
    // Initialize portfolio chart
    const portfolioChart = $('#portfolio-chart');
    if (portfolioChart) {
        new Chart(portfolioChart, {
            type: 'doughnut',
            data: {
                labels: ['Investito', 'Rendimenti', 'Bonus'],
                datasets: [{
                    data: [70, 20, 10],
                    backgroundColor: ['#1e40af', '#0ea5e9', '#10b981']
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false
            }
        });
    }
}

function initializeLazyLoading() {
    if ('IntersectionObserver' in window) {
        const imageObserver = new IntersectionObserver((entries, observer) => {
            entries.forEach(entry => {
                if (entry.isIntersecting) {
                    const img = entry.target;
                    img.src = img.dataset.src;
                    img.classList.remove('lazy');
                    observer.unobserve(img);
                }
            });
        });
        
        const lazyImages = $$('img[data-src]');
        lazyImages.forEach(img => imageObserver.observe(img));
    }
}

// Modal functions
function openModal(modalId) {
    const modal = $(`#${modalId}`);
    if (modal) {
        modal.classList.remove('hidden');
        document.body.style.overflow = 'hidden';
    }
}

function closeModal(modal) {
    modal.classList.add('hidden');
    document.body.style.overflow = 'auto';
}

// Tooltip functions
function showTooltip(event) {
    const tooltipText = event.target.getAttribute('data-tooltip');
    const tooltip = document.createElement('div');
    tooltip.className = 'tooltip';
    tooltip.textContent = tooltipText;
    
    document.body.appendChild(tooltip);
    
    // Position tooltip
    const rect = event.target.getBoundingClientRect();
    tooltip.style.left = rect.left + rect.width / 2 - tooltip.offsetWidth / 2 + 'px';
    tooltip.style.top = rect.top - tooltip.offsetHeight - 5 + 'px';
}

function hideTooltip() {
    const tooltip = $('.tooltip');
    if (tooltip) {
        tooltip.remove();
    }
}

// Notification system
function showNotification(message, type = 'info', duration = 3000) {
    const notification = document.createElement('div');
    notification.className = `notification notification-${type} fade-in`;
    notification.innerHTML = `
        <div class="notification-content">
            <span class="notification-message">${message}</span>
            <button class="notification-close" onclick="this.parentElement.parentElement.remove()">×</button>
        </div>
    `;
    
    // Add to notifications container or body
    const container = $('#notifications-container') || document.body;
    container.appendChild(notification);
    
    // Auto remove after duration
    setTimeout(() => {
        if (notification.parentElement) {
            notification.remove();
        }
    }, duration);
    
    // Add to app state
    appState.notifications.push({
        id: Date.now(),
        message,
        type,
        timestamp: new Date()
    });
}

function showUpdateNotification() {
    if (confirm('È disponibile una nuova versione dell\'app. Vuoi aggiornare?')) {
        window.location.reload();
    }
}

// Utility functions
function debounce(func, wait) {
    let timeout;
    return function executedFunction(...args) {
        const later = () => {
            clearTimeout(timeout);
            func(...args);
        };
        clearTimeout(timeout);
        timeout = setTimeout(later, wait);
    };
}

function updateOnlineStatus() {
    const body = document.body;
    if (appState.isOnline) {
        body.classList.remove('offline');
    } else {
        body.classList.add('offline');
    }
}

function showWelcomeMessage() {
    showNotification('Benvenuto in CIP Immobiliare! 🏠', 'success', 5000);
}

// Export for global use
window.CIPApp = {
    showNotification,
    openModal,
    closeModal,
    setTheme,
    toggleTheme
};
