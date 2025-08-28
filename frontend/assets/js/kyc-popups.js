/**
 * KYC Popups - Sistema di popup informativi per sezioni bloccate
 * Spiega chiaramente perché l'utente non può accedere a determinate funzionalità
 */

class KYCPopupManager {
    constructor() {
        this.init();
    }

    init() {
        // Aggiungi event listener per i link bloccati
        this.addBlockedLinksListeners();
        
        // Aggiungi event listener per i pulsanti bloccati
        this.addBlockedButtonsListeners();
        
        // Inizializza popup esistenti
        this.initExistingPopups();
    }

    /**
     * Aggiunge event listener per i link che potrebbero essere bloccati
     */
    addBlockedLinksListeners() {
        // Seleziona tutti i link che potrebbero essere bloccati
        const blockedLinks = document.querySelectorAll('a[href*="/user/new-project"], a[href*="/user/portfolio"], a[href*="/user/projects"]');
        
        blockedLinks.forEach(link => {
            link.addEventListener('click', (e) => {
                e.preventDefault();
                this.showKYCPopup(link.getAttribute('href'));
            });
        });
    }

    /**
     * Aggiunge event listener per i pulsanti bloccati
     */
    addBlockedButtonsListeners() {
        // Seleziona pulsanti con classi specifiche
        const blockedButtons = document.querySelectorAll('.btn-invest, .btn-portfolio, .btn-new-project');
        
        blockedButtons.forEach(button => {
            button.addEventListener('click', (e) => {
                e.preventDefault();
                this.showKYCPopup(button.dataset.target || '/user/dashboard');
            });
        });
    }

    /**
     * Inizializza popup esistenti nel DOM
     */
    initExistingPopups() {
        // Chiudi popup quando si clicca fuori
        document.addEventListener('click', (e) => {
            if (e.target.classList.contains('kyc-popup-overlay')) {
                this.closePopup();
            }
        });

        // Chiudi popup con ESC
        document.addEventListener('keydown', (e) => {
            if (e.key === 'Escape') {
                this.closePopup();
            }
        });
    }

    /**
     * Mostra popup KYC per la sezione specificata
     */
    showKYCPopup(targetSection) {
        // Controlla direttamente lo stato KYC senza verificare autenticazione
        // (l'autenticazione viene gestita dal server)
        this.checkKYCStatus().then(kycStatus => {
            if (kycStatus === 'verified') {
                // KYC verificato, reindirizza alla sezione
                window.location.href = targetSection;
            } else if (kycStatus === 'error' || kycStatus === 'unverified') {
                // KYC non verificato o errore, mostra popup appropriato
                this.showKYCRestrictionPopup(targetSection, kycStatus);
            } else {
                // Stato KYC sconosciuto, reindirizza alla sezione (il server gestirà l'accesso)
                window.location.href = targetSection;
            }
        });
    }

    /**
     * Controlla lo stato KYC dell'utente
     */
    async checkKYCStatus() {
        try {
            const response = await fetch('/kyc/api/status');
            if (response.ok) {
                const data = await response.json();
                return data.kyc_status || 'unverified';
            } else if (response.status === 401) {
                // Utente non autenticato
                return 'unauthenticated';
            } else {
                // Altri errori
                return 'error';
            }
        } catch (error) {
            console.error('Errore nel controllo KYC:', error);
            return 'error';
        }
    }

    /**
     * Mostra popup per restrizioni KYC
     */
    showKYCRestrictionPopup(targetSection, kycStatus) {
        const sectionNames = {
            '/user/new-project': 'Nuovi Investimenti',
            '/user/portfolio': 'Portafoglio',
            '/user/projects': 'Progetti Disponibili'
        };

        const sectionName = sectionNames[targetSection] || 'questa sezione';
        
        let title, message, actions;

        if (kycStatus === 'unverified') {
            title = '📋 Verifica Identità Richiesta';
            message = `Per accedere a <strong>${sectionName}</strong>, devi prima completare la verifica della tua identità (KYC).<br><br>
                      <strong>Come procedere:</strong><br>
                      1️⃣ Vai al tuo profilo<br>
                      2️⃣ Carica un documento d'identità valido<br>
                      3️⃣ Attendi l'approvazione dell'amministratore<br><br>
                      <em>La verifica richiede solitamente 24-48 ore.</em>`;
            
            actions = [
                {
                    text: '🆔 Vai al Profilo',
                    class: 'btn-primary',
                    action: () => window.location.href = '/user/profile'
                },
                {
                    text: '❓ Maggiori Info',
                    class: 'btn-secondary',
                    action: () => this.showKYCInfoPopup()
                },
                {
                    text: '✖️ Chiudi',
                    class: 'btn-outline',
                    action: () => this.closePopup()
                }
            ];
        } else if (kycStatus === 'pending') {
            title = '⏳ Verifica in Corso';
            message = `La verifica della tua identità è in corso di revisione.<br><br>
                      <strong>Stato attuale:</strong> In attesa di approvazione<br>
                      <strong>Tempo stimato:</strong> 24-48 ore<br><br>
                      <em>Riceverai una notifica quando la verifica sarà completata.</em>`;
            
            actions = [
                {
                    text: '🔄 Controlla Stato',
                    class: 'btn-primary',
                    action: () => window.location.href = '/user/profile'
                },
                {
                    text: '✖️ Chiudi',
                    class: 'btn-outline',
                    action: () => this.closePopup()
                }
            ];
        } else if (kycStatus === 'rejected') {
            title = '❌ Verifica Rifiutata';
            message = `La verifica della tua identità è stata rifiutata.<br><br>
                      <strong>Possibili cause:</strong><br>
                      • Documento non leggibile o scaduto<br>
                      • Informazioni non corrispondenti<br>
                      • Documento non valido<br><br>
                      <em>Puoi caricare un nuovo documento per riprovare.</em>`;
            
            actions = [
                {
                    text: '🔄 Riprova',
                    class: 'btn-primary',
                    action: () => window.location.href = '/user/profile'
                },
                {
                    text: '❓ Aiuto',
                    class: 'btn-secondary',
                    action: () => this.showKYCInfoPopup()
                },
                {
                    text: '✖️ Chiudi',
                    class: 'btn-outline',
                    action: () => this.closePopup()
                }
            ];
        } else if (kycStatus === 'unauthenticated') {
            // Utente non autenticato
            title = '🔐 Accesso Richiesto';
            message = 'Devi effettuare il login per accedere a questa sezione.';
            
            actions = [
                {
                    text: 'Vai al Login',
                    class: 'btn-primary',
                    action: () => window.location.href = '/auth/login'
                },
                {
                    text: 'Chiudi',
                    class: 'btn-secondary',
                    action: () => this.closePopup()
                }
            ];
        } else {
            // Stato sconosciuto o errore
            title = '❓ Accesso Non Disponibile';
            message = `Non è possibile accedere a <strong>${sectionName}</strong> al momento.<br><br>
                      <em>Riprova più tardi o contatta il supporto se il problema persiste.</em>`;
            
            actions = [
                {
                    text: '🔄 Riprova',
                    class: 'btn-primary',
                    action: () => window.location.reload()
                },
                {
                    text: '✖️ Chiudi',
                    class: 'btn-outline',
                    action: () => this.closePopup()
                }
            ];
        }

        const popup = this.createPopup({ title, message, actions });
        this.showPopup(popup);
    }

    /**
     * Mostra popup informativo sul KYC
     */
    showKYCInfoPopup() {
        const popup = this.createPopup({
            title: 'ℹ️ Cos\'è il KYC?',
            message: `<strong>KYC (Know Your Customer)</strong> è un processo di verifica dell'identità richiesto per legge.<br><br>
                      <strong>Perché è necessario:</strong><br>
                      • Proteggere gli investitori<br>
                      • Prevenire frodi e riciclaggio<br>
                      • Rispettare le normative finanziarie<br><br>
                      <strong>Documenti accettati:</strong><br>
                      • Carta d'identità (fronte e retro)<br>
                      • Passaporto<br>
                      • Patente di guida<br><br>
                      <em>I tuoi dati sono protetti e sicuri.</em>`,
            actions: [
                {
                    text: '🆔 Inizia Verifica',
                    class: 'btn-primary',
                    action: () => window.location.href = '/user/profile'
                },
                {
                    text: '✖️ Chiudi',
                    class: 'btn-outline',
                    action: () => this.closePopup()
                }
            ]
        });
        this.showPopup(popup);
    }

    /**
     * Crea il popup HTML
     */
    createPopup({ title, message, actions }) {
        const popup = document.createElement('div');
        popup.className = 'kyc-popup-overlay';
        
        // Crea la struttura HTML base
        popup.innerHTML = `
            <div class="kyc-popup">
                <div class="kyc-popup-header">
                    <h3>${title}</h3>
                    <button class="kyc-popup-close">×</button>
                </div>
                <div class="kyc-popup-body">
                    <div class="kyc-popup-message">${message}</div>
                </div>
                <div class="kyc-popup-footer">
                    ${actions.map((action, index) => `
                        <button class="btn ${action.class}" data-action-index="${index}">
                            ${action.text}
                        </button>
                    `).join('')}
                </div>
            </div>
        `;
        
        // Aggiungi event listener per il pulsante di chiusura
        const closeButton = popup.querySelector('.kyc-popup-close');
        closeButton.addEventListener('click', () => this.closePopup());
        
        // Aggiungi event listener per i pulsanti delle azioni
        const actionButtons = popup.querySelectorAll('[data-action-index]');
        actionButtons.forEach((button, index) => {
            button.addEventListener('click', () => {
                const action = actions[index];
                if (action && typeof action.action === 'function') {
                    this.executeAction(action.action);
                }
            });
        });
        
        return popup;
    }

    /**
     * Mostra il popup
     */
    showPopup(popup) {
        // Rimuovi popup esistenti
        this.closePopup();
        
        // Aggiungi popup al DOM
        document.body.appendChild(popup);
        
        // Aggiungi classe per animazione
        setTimeout(() => popup.classList.add('show'), 10);
        
        // Blocca scroll del body
        document.body.style.overflow = 'hidden';
    }

    /**
     * Chiudi il popup
     */
    closePopup() {
        const existingPopup = document.querySelector('.kyc-popup-overlay');
        if (existingPopup) {
            existingPopup.classList.remove('show');
            setTimeout(() => {
                if (existingPopup.parentNode) {
                    existingPopup.parentNode.removeChild(existingPopup);
                }
                // Ripristina scroll del body
                document.body.style.overflow = '';
            }, 200);
        }
    }

    /**
     * Esegue un'azione e chiude il popup
     */
    executeAction(action) {
        this.closePopup();
        if (typeof action === 'function') {
            action();
        }
    }
}

// Inizializza il manager quando il DOM è pronto
document.addEventListener('DOMContentLoaded', () => {
    window.kycPopupManager = new KYCPopupManager();
});

// Esporta per uso esterno
if (typeof module !== 'undefined' && module.exports) {
    module.exports = KYCPopupManager;
}
