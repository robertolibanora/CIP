# 🏗️ CIP Immobiliare - Guida Completa Funzionalità

## 📋 **Indice**
1. [Architettura Generale](#architettura-generale)
2. [Sistema di Autenticazione](#sistema-di-autenticazione)
3. [Pagine User](#pagine-user)
4. [Pagine Admin](#pagine-admin)
5. [API e Backend](#api-e-backend)
6. [Database e Schema](#database-e-schema)
7. [Sicurezza e Middleware](#sicurezza-e-middleware)
8. [Design e UI/UX](#design-e-uiux)

---

## 🏛️ **Architettura Generale**

### **Struttura Progetto**
```
CIP Immobiliare/
├── backend/           # Logica business e API
├── frontend/          # Template e asset
├── config/            # Configurazioni e database
├── main.py            # Entry point applicazione
└── requirements.txt   # Dipendenze Python
```

### **Blueprint e Moduli**
- **`admin_bp`** - Gestione amministrativa completa
- **`user_bp`** - Funzionalità utente base
- **`auth_bp`** - Autenticazione e autorizzazione
- **`kyc_bp`** - Sistema Know Your Customer
- **`deposits_bp`** - Gestione ricariche
- **`withdrawals_bp`** - Gestione prelievi
- **`profits_bp`** - Gestione rendimenti
- **`portfolio_api_bp`** - API portfolio

---

## 🔐 **Sistema di Autenticazione**

### **Ruoli e Permessi**
- **`admin`** - Accesso completo a tutte le funzionalità
- **`investor`** - Utente normale con limitazioni KYC

### **Decoratori di Sicurezza**
- **`@login_required`** - Richiede autenticazione
- **`@admin_required`** - Richiede ruolo admin
- **`@kyc_verified`** - Richiede verifica KYC completata
- **`@can_access_portfolio`** - Verifica accesso portfolio
- **`@can_invest`** - Verifica capacità di investimento

### **Session Management**
- **`user_id`** - ID utente autenticato
- **`email`** - Email utente
- **`role`** - Ruolo (admin/investor)
- **`kyc_status`** - Stato verifica KYC

### **Creazione Admin Automatica**
Il sistema crea automaticamente l'utente amministratore all'avvio dell'applicazione.

#### **Configurazione Variabili Ambiente**
Configura le credenziali admin nel file `config/env.local`:
```bash
ADMIN_EMAIL=admin@cipimmobiliare.it
ADMIN_PASSWORD=SecureAdmin123!
ADMIN_NOME=Admin
ADMIN_COGNOME=CIP
ADMIN_TELEGRAM=admin_cip
ADMIN_TELEFONO=+39000000000
```

#### **Funzionamento**
- ✅ **Verifica Esistenza**: Controlla se esiste già un admin nel database
- ✅ **Creazione Automatica**: Crea l'admin solo se non esiste
- ✅ **Gestione Errori**: Non blocca l'avvio se c'è un errore database
- ✅ **Logging Sicuro**: Logga operazioni senza esporre credenziali
- ✅ **Password Hashata**: Usa SHA-256 come il resto del sistema

#### **Sicurezza**
- ⚠️ **Mai hardcoded**: Le credenziali sono sempre da variabili ambiente
- 🔐 **Hash sicuro**: Password hashata con SHA-256
- 📝 **Audit log**: Ogni tentativo di creazione viene loggato
- 🚫 **No duplicati**: Impedisce la creazione di admin multipli

---

## 👤 **Pagine User**

### **1. 🏠 Dashboard (`/user/dashboard`)**
**Template**: `frontend/templates/user/dashboard.html`

#### **Funzionalità Principali**
- **Overview Portfolio**: Visualizzazione 4 sezioni capitali
- **Statistiche Investimenti**: Totale investito, ROI medio
- **Investimenti Attivi**: Lista progetti con percentuali
- **Sistema Referral**: Contatore utenti invitati e bonus

#### **Dettagli Implementazione**
- **Portfolio 4 Sezioni**:
  - `free_capital` - Capitale libero (sempre prelevabile)
  - `invested_capital` - Capitale investito (bloccato)
  - `referral_bonus` - Bonus referral accumulati
  - `profits` - Profitti generati
- **Calcoli Automatici**: ROI medio, stato portfolio
- **Link Referral**: Generazione automatica link invito

#### **Tabelle Database Utilizzate**
- `users` - Dati utente e stato KYC
- `user_portfolios` - Portfolio 4 sezioni
- `investments` - Investimenti attivi
- `projects` - Dettagli progetti

---

### **2. 🔍 Search (`/user/search`)**
**Template**: `frontend/templates/user/search.html`

#### **Funzionalità Principali**
- **Ricerca Progetti**: Barra di ricerca con filtri
- **Grid Progetti**: Visualizzazione responsive progetti disponibili
- **Stato Investimenti**: Indicatori se già investito
- **Filtro KYC**: Limitazioni per utenti non verificati

#### **Dettagli Implementazione**
- **Ricerca Testuale**: Nome e descrizione progetti
- **Filtri Avanzati**: Status, tipo, localizzazione
- **Indicatori Visivi**: 
  - ✅ Progetto già investito
  - 💰 Importo investito
  - 📊 Percentuale completamento
- **Placeholder Immagini**: Struttura galleria foto

#### **Tabelle Database Utilizzate**
- `projects` - Lista progetti disponibili
- `investments` - Stato investimenti utente

---

### **3. ➕ New Project (`/user/new-project`)**
**Template**: `frontend/templates/user/new_project.html`

#### **Funzionalità Principali**
- **Verifica KYC**: Blocco se utente non verificato
- **Controllo Budget**: Verifica disponibilità saldo
- **Selezione Fonte**: Scelta sezione portafoglio
- **Wizard Investimento**: Form step-by-step

#### **Dettagli Implementazione**
- **Controlli Sicurezza**:
  - KYC verificato obbligatorio
  - Saldo sufficiente nella sezione scelta
  - Validazione importi e formati
- **Selezioni Portfolio**:
  - Capitale libero
  - Bonus referral
  - Profitti generati
- **Validazioni Business**:
  - Importo minimo progetto
  - Disponibilità fondi
  - Stato progetto attivo

#### **Tabelle Database Utilizzate**
- `user_portfolios` - Verifica disponibilità
- `projects` - Progetti disponibili
- `users` - Stato KYC

---

### **4. 📊 Portfolio (`/user/portfolio`)**
**Template**: `frontend/templates/user/portfolio.html`

#### **Funzionalità Principali**
- **Vista Dettagliata Portfolio**: 4 sezioni con dettagli
- **Storico Transazioni**: Movimenti e operazioni
- **Performance Investimenti**: ROI e rendimenti
- **Gestione Profilo**: Form dati personali

#### **Dettagli Implementazione**
- **Sezioni Portfolio**:
  - **Capitale Libero**: Saldo disponibile per prelievi
  - **Capitale Investito**: Totale progetti attivi
  - **Bonus Referral**: Accumulo commissioni 1%
  - **Profitti**: Rendimenti generati
- **Form Profilo**: Aggiornamento dati personali
- **Storico Movimenti**: Timeline transazioni

#### **Tabelle Database Utilizzate**
- `user_portfolios` - Dati portfolio
- `portfolio_transactions` - Storico movimenti
- `users` - Dati profilo

---

### **5. 👤 Profile (`/user/profile`)**
**Template**: `frontend/templates/user/profile.html`

#### **Funzionalità Principali**
- **Gestione KYC**: Upload documenti identità
- **Stato Verifica**: Tracking processo KYC
- **Dati Personali**: Aggiornamento informazioni
- **Sistema Referral**: Codice invito e statistiche

#### **Dettagli Implementazione**
- **Upload Documenti**:
  - Supporto PDF e immagini
  - Validazione formati
  - Categorizzazione documenti
- **Stati KYC**:
  - `unverified` - Non verificato
  - `pending` - In attesa verifica
  - `verified` - Verificato
  - `rejected` - Rifiutato
- **Referral System**:
  - Codice invito univoco
  - Statistiche utenti invitati
  - Bonus 1% automatici

#### **Tabelle Database Utilizzate**
- `users` - Dati profilo e referral
- `documents` - Documenti KYC
- `doc_categories` - Categorie documenti

---

### **6. 🔗 Referral Dashboard (`/referral/dashboard`)**
**Template**: `frontend/templates/referral/dashboard.html`

#### **Funzionalità Principali**
- **Statistiche Referral**: Contatori e metriche
- **Gestione Commissioni**: Bonus 1% automatici
- **Link Condivisione**: Generazione link invito
- **Network Utenti**: Albero referral

#### **Dettagli Implementazione**
- **Sistema Bonus**:
  - 1% automatico su investimenti invitati
  - Accumulo in sezione referral_bonus
  - Distribuzione mensile
- **Network Tracking**:
  - Utenti di livello 1 (diretti)
  - Utenti di livello 2 (indiretti)
  - Calcolo commissioni per livello

#### **Tabelle Database Utilizzate**
- `users` - Relazioni referral
- `referral_bonuses` - Storico bonus
- `investments` - Calcolo commissioni

---

## ⚙️ **Pagine Admin**

### **1. 🎯 Dashboard Admin (`/admin/`)**
**Template**: `frontend/templates/admin/dashboard.html`

#### **Funzionalità Principali**
- **Azioni Rapide**: 8 card per funzioni principali
- **Layout Minimal**: Nessuna sidebar, design pulito
- **Grid Responsive**: 1→2→4 colonne (mobile→tablet→desktop)

#### **8 Azioni Rapide**
1. **🔐 KYC** - Gestione documenti identità
2. **💰 Ricariche** - Approvazione bonifici
3. **💸 Prelievi** - Gestione richieste (48h max)
4. **🏗️ Progetti** - Gestione progetti immobiliari
5. **👥 Utenti** - Gestione utenti e investitori
6. **📊 Transazioni** - Monitoraggio e tracking
7. **🔗 Referral** - Distribuzione bonus 1%
8. **⚙️ Config** - IBAN e configurazioni

#### **Dettagli Implementazione**
- **Design System**: Palette colori dedicata per ogni azione
- **CSS Separato**: `admin-specific.css` senza conflitti user
- **Layout Responsive**: Grid CSS nativo
- **Hover Effects**: Elevazione e transizioni fluide

---

### **2. 📊 Metrics (`/admin/metrics`)**
**Route**: `backend/admin/routes.py`

#### **Funzionalità Principali**
- **Metriche Sistema**: Contatori e statistiche globali
- **Vista Database**: `v_admin_metrics`
- **API JSON**: Dati per dashboard e report

#### **Metriche Disponibili**
- `users_total` - Totale utenti registrati
- `users_verified` - Utenti KYC verificati
- `users_pending_kyc` - KYC in attesa
- `projects_active` - Progetti attivi
- `investments_total` - Totale investimenti
- `deposits_pending` - Ricariche in attesa
- `withdrawals_pending` - Prelievi in attesa

---

### **3. 🏗️ Projects Management (`/admin/projects/*`)**
**Route**: `backend/admin/routes.py`

#### **Funzionalità Principali**
- **Lista Progetti**: Vista completa con filtri
- **Nuovo Progetto**: Form creazione con upload file
- **Modifica Progetto**: Aggiornamento dati e status
- **Gestione File**: Foto e documenti progetti

#### **Dettagli Implementazione**
- **Upload File**:
  - Foto progetto (formati supportati)
  - Documenti PDF
  - Validazione dimensioni e tipi
- **Stati Progetto**:
  - `draft` - Bozza
  - `funding` - In raccolta fondi
  - `active` - Attivo
  - `completed` - Completato
  - `cancelled` - Annullato
- **Campi Progetto**:
  - Codice univoco
  - Nome e descrizione
  - Importo target e minimo
  - Date inizio/fine
  - Indirizzo e tipo

#### **Tabelle Database Utilizzate**
- `projects` - Dati progetti
- `uploads/` - File caricati

---

### **4. 👥 Users Management (`/admin/users/*`)**
**Route**: `backend/admin/routes.py`

#### **Funzionalità Principali**
- **Lista Utenti**: Ricerca e filtri avanzati
- **Dettaglio Utente**: Profilo completo e investimenti
- **Gestione KYC**: Approvazione/rifiuto documenti
- **Sistema Referral**: Cambio referrer e bonus

#### **Dettagli Implementazione**
- **Ricerca Utenti**:
  - Per email o nome
  - Filtro per stato KYC
  - Filtro per ruolo
- **Gestione KYC**:
  - Visualizzazione documenti
  - Cambio stato verifica
  - Note amministrative
- **Referral System**:
  - Cambio utente referrer
  - Gestione bonus manuali
  - Tracking network

#### **Tabelle Database Utilizzate**
- `users` - Dati utenti
- `documents` - Documenti KYC
- `investments` - Investimenti utente
- `referral_bonuses` - Bonus referral

---

### **5. 💰 Deposits Management (`/admin/deposits/*`)**
**Route**: `backend/deposits/routes.py`

#### **Funzionalità Principali**
- **Richieste Pending**: Lista bonifici in attesa
- **Approvazione/Rifiuto**: Gestione richieste
- **Configurazione IBAN**: Gestione conti bancari
- **Tracking Bonifici**: Riferimenti univoci

#### **Dettagli Implementazione**
- **Sistema Bonifici**:
  - Chiave univoca per ogni richiesta
  - Riferimento pagamento univoco
  - IBAN configurabile per ricariche
- **Workflow Approvazione**:
  - Verifica bonifico ricevuto
  - Aggiornamento portfolio utente
  - Notifica conferma
- **Configurazione IBAN**:
  - Banca e intestatario
  - Attivazione/disattivazione
  - Note amministrative

#### **Tabelle Database Utilizzate**
- `deposit_requests` - Richieste ricarica
- `iban_configurations` - Configurazione IBAN
- `user_portfolios` - Aggiornamento saldo

---

### **6. 💸 Withdrawals Management (`/admin/withdrawals/*`)**
**Route**: `backend/withdrawals/routes.py`

#### **Funzionalità Principali**
- **Richieste Prelievo**: Lista in attesa approvazione
- **Gestione 48h**: Timeline approvazione
- **Verifica Fondi**: Controllo disponibilità
- **Tracking Transazioni**: Storico operazioni

#### **Dettagli Implementazione**
- **Sistema Prelievi**:
  - Verifica disponibilità sezione
  - Controllo stato KYC
  - Timeline 48h per approvazione
- **Sezioni Portfolio**:
  - Capitale libero (sempre disponibile)
  - Bonus referral (dopo 30 giorni)
  - Profitti (dopo completamento progetto)
- **Workflow Approvazione**:
  - Verifica fondi
  - Aggiornamento portfolio
  - Registrazione transazione

#### **Tabelle Database Utilizzate**
- `withdrawal_requests` - Richieste prelievo
- `user_portfolios` - Verifica disponibilità
- `portfolio_transactions` - Storico transazioni

---

### **7. 🔐 KYC Management (`/admin/kyc/*`)**
**Route**: `backend/kyc/routes.py`

#### **Funzionalità Principali**
- **Verifica Documenti**: Approvazione identità
- **Gestione Stati**: Cambio status KYC
- **Upload Documenti**: Gestione file utente
- **Tracking Processo**: Storico verifiche

#### **Dettagli Implementazione**
- **Tipi Documenti**:
  - Documento identità (obbligatorio)
  - Documenti aggiuntivi
  - Categorizzazione automatica
- **Stati KYC**:
  - `unverified` → `pending` → `verified`/`rejected`
- **Workflow Verifica**:
  - Upload documento
  - Revisione admin
  - Approvazione/rifiuto
  - Notifica utente

#### **Tabelle Database Utilizzate**
- `users` - Stato KYC
- `documents` - Documenti caricati
- `doc_categories` - Categorie documenti

---

### **8. 📊 Transactions Management (`/admin/transactions/*`)**
**Route**: `backend/admin/routes.py`

#### **Funzionalità Principali**
- **Monitoraggio Completo**: Tutte le transazioni sistema
- **Filtri Avanzati**: Per tipo, utente, periodo
- **Tracking Stati**: Pending, completed, failed
- **Report Performance**: Metriche e statistiche

#### **Dettagli Implementazione**
- **Tipi Transazioni**:
  - Depositi e prelievi
  - Investimenti
  - Rendimenti
  - Bonus referral
- **Filtri Disponibili**:
  - Periodo temporale
  - Tipo operazione
  - Utente specifico
  - Stato transazione
- **Metriche Performance**:
  - Volume giornaliero
  - Trend temporali
  - Analisi utenti

#### **Tabelle Database Utilizzate**
- `portfolio_transactions` - Storico transazioni
- `deposit_requests` - Richieste ricarica
- `withdrawal_requests` - Richieste prelievo
- `investments` - Investimenti

---

### **9. 🔗 Referral Management (`/admin/referral/*`)**
**Route**: `backend/admin/routes.py`

#### **Funzionalità Principali**
- **Distribuzione Bonus**: Sistema automatico 1%
- **Overview Network**: Albero referral completo
- **Gestione Commissioni**: Bonus manuali e automatici
- **Tracking Performance**: Metriche sistema referral

#### **Dettagli Implementazione**
- **Sistema Bonus**:
  - 1% automatico su investimenti
  - Distribuzione mensile
  - Tracking per livello
- **Network Management**:
  - Visualizzazione albero
  - Statistiche per livello
  - Gestione relazioni
- **Commissioni**:
  - Calcolo automatico
  - Gestione manuale
  - Storico distribuzioni

#### **Tabelle Database Utilizzate**
- `users` - Relazioni referral
- `referral_bonuses` - Storico bonus
- `investments` - Calcolo commissioni

---

### **10. ⚙️ Settings Management (`/admin/settings/*`)**
**Route**: `backend/admin/routes.py`

#### **Funzionalità Principali**
- **Configurazione IBAN**: Gestione conti bancari
- **Parametri Sistema**: Configurazioni globali
- **Gestione File**: Upload e configurazioni
- **Backup Database**: Operazioni di manutenzione

#### **Dettagli Implementazione**
- **Configurazione IBAN**:
  - Banca e intestatario
  - Attivazione/disattivazione
  - Note amministrative
- **Parametri Sistema**:
  - Configurazioni globali
  - Limiti e soglie
  - Timeout e scadenze
- **Manutenzione**:
  - Backup database
  - Pulizia file temporanei
  - Log di sistema

#### **Tabelle Database Utilizzate**
- `iban_configurations` - Configurazione IBAN
- `system_settings` - Parametri sistema

---

## 🔌 **API e Backend**

### **Struttura API**
- **RESTful Design**: Endpoint standardizzati
- **JSON Response**: Formato dati consistente
- **Error Handling**: Gestione errori centralizzata
- **Rate Limiting**: Protezione da abusi

### **Endpoint Principali**
- **`/api/deposits/*`** - Gestione ricariche
- **`/api/withdrawals/*`** - Gestione prelievi
- **`/api/portfolio/*`** - Dati portfolio
- **`/api/kyc/*`** - Sistema KYC
- **`/api/profits/*`** - Gestione rendimenti

### **Autenticazione API**
- **Session-based**: Autenticazione web
- **Role-based**: Controllo accessi per ruolo
- **KYC-based**: Limitazioni per utenti non verificati

---

## 🗄️ **Database e Schema**

### **Tabelle Principali**
- **`users`** - Utenti e autenticazione
- **`projects`** - Progetti immobiliari
- **`investments`** - Investimenti utenti
- **`user_portfolios`** - Portfolio 4 sezioni
- **`portfolio_transactions`** - Storico transazioni
- **`documents`** - Documenti KYC
- **`referral_bonuses`** - Bonus referral

### **Viste Database**
- **`v_admin_metrics`** - Metriche sistema
- **`v_user_bonus`** - Bonus utente
- **`v_user_invested`** - Investimenti utente
- **`v_deposit_requests`** - Richieste ricarica
- **`v_withdrawal_requests`** - Richieste prelievo

### **Relazioni e Vincoli**
- **Foreign Keys**: Integrità referenziale
- **Check Constraints**: Validazione dati
- **Indexes**: Performance query
- **Triggers**: Aggiornamenti automatici

---

## 🛡️ **Sicurezza e Middleware**

### **Middleware di Autenticazione**
- **Session Management**: Gestione sessioni sicura
- **Role Verification**: Controllo ruoli e permessi
- **KYC Validation**: Verifica stato KYC
- **Request Logging**: Log accessi e operazioni

### **Validazioni e Sanitizzazione**
- **Input Validation**: Controllo dati in ingresso
- **SQL Injection Protection**: Prepared statements
- **XSS Protection**: Sanitizzazione output
- **CSRF Protection**: Protezione cross-site

### **File Upload Security**
- **Type Validation**: Controllo tipi file
- **Size Limits**: Limiti dimensioni
- **Virus Scanning**: Scansione malware
- **Secure Storage**: Archiviazione sicura

---

## 🎨 **Design e UI/UX**

### **Design System**
- **TailwindCSS**: Framework CSS utility-first
- **Responsive Design**: Mobile-first approach
- **Component Library**: Componenti riutilizzabili
- **Color Palette**: Palette colori brand

### **Layout e Navigazione**
- **Admin Layout**: Header minimal, nessuna sidebar
- **User Layout**: Header completo, bottom tabbar mobile
- **Responsive Grid**: Layout adattivo per tutti i dispositivi
- **Touch Optimization**: Ottimizzazioni per dispositivi touch

### **Componenti UI**
- **Action Cards**: Card azioni admin
- **KPI Widgets**: Widget metriche dashboard
- **Form Components**: Componenti form standardizzati
- **Modal e Popup**: Overlay e dialoghi
- **Loading States**: Stati di caricamento
- **Error Handling**: Gestione errori user-friendly

---

## 🚀 **Deployment e Manutenzione**

### **Script di Deploy**
- **`deploy.sh`** - Script deployment automatico
- **Docker Support** - Containerizzazione applicazione
- **Nginx Config** - Configurazione web server
- **Systemd Service** - Servizio sistema

### **Monitoraggio e Log**
- **Performance Monitoring** - Monitoraggio performance
- **Error Tracking** - Tracciamento errori
- **User Analytics** - Analisi utilizzo
- **System Health** - Stato sistema

### **Backup e Recovery**
- **Database Backup** - Backup automatico database
- **File Backup** - Backup file upload
- **Disaster Recovery** - Piano ripristino
- **Version Control** - Controllo versioni

---

## 📱 **Mobile e PWA**

### **Progressive Web App**
- **Service Worker** - Caching offline
- **Manifest** - Configurazione PWA
- **Install Prompt** - Installazione app
- **Offline Support** - Funzionalità offline

### **Mobile Optimization**
- **Touch Gestures** - Gesture touch
- **Responsive Images** - Immagini adattive
- **Performance** - Ottimizzazioni mobile
- **Accessibility** - Accessibilità mobile

---

## 🔮 **Roadmap e Sviluppi Futuri**

### **Fasi di Implementazione**
1. **✅ Fase 1**: Fondamentali e infrastruttura
2. **✅ Fase 2**: Pagine user e admin
3. **🔄 Fase 3**: Ottimizzazioni e performance
4. **📋 Fase 4**: Funzionalità avanzate

### **Funzionalità Pianificate**
- **Notifiche Push** - Sistema notifiche real-time
- **Analytics Avanzate** - Dashboard analitiche
- **API Pubbliche** - Endpoint pubblici
- **Integrazione Pagamenti** - Gateway pagamento
- **Multi-lingua** - Supporto lingue multiple

---

## 📞 **Supporto e Contatti**

### **Documentazione**
- **API Docs** - Documentazione endpoint
- **User Manual** - Guida utente
- **Admin Guide** - Guida amministratore
- **Developer Docs** - Documentazione sviluppatori

### **Canali Supporto**
- **Email Support** - support@cipimmobiliare.it
- **Telegram** - @cip_support
- **Documentazione** - docs.cipimmobiliare.it
- **GitHub Issues** - Repository GitHub

---

*Ultimo aggiornamento: Dicembre 2024*  
*Versione: 1.0.0*  
*Autore: Team CIP Immobiliare*
