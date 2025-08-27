# ROADMAP STRATEGICA PERFEZIONAMENTO NAVBAR - CIP Immobiliare

## 🎯 Strategia Generale
**Obiettivo**: Perfezionare una ad una tutte le pagine della navbar seguendo un approccio iterativo e metodico.

**Metodologia**: 
- Scope freeze per pagina (lavoro solo sulla pagina selezionata)
- Analisi → Design → Implementazione → Test → Approvazione → Merge
- Zero regressioni, mantenimento coerenza architetturale
- **Approccio a basso rischio**: Implementazione incrementale con dipendenze minime

---

## 🆕 **NUOVE FUNZIONALITÀ STRATEGICHE**

### **🔐 Sistema KYC e Verifica Identità**
- **Upload documenti identità**: PDF e immagini accettati
- **Documento richiesto**: Uno solo (fronte e retro)
- **Verifica admin**: Approvazione manuale a discrezione admin (non automatica)
- **Stato utente**: Pending KYC → KYC Approved → Can Invest
- **Rejection handling**: Utente può ricaricare nuovo documento se rifiutato
- **Timing**: KYC obbligatorio dopo registrazione per sbloccare tutte le opzioni

### **💰 Sistema Ricariche e Budget Portafoglio**
- **Richiesta ricarica**: Minimo 500€, nessun tetto massimo
- **Frequenza**: Nessun limite, admin approva ogni singola richiesta
- **Generazione IBAN**: Sempre lo stesso IBAN (configurabile da admin)
- **Chiave univoca**: 6 caratteri alfanumerici per identificare transazione
- **Causale bonifico**: Chiave randomica per identificare transazione
- **Approvazione admin**: Dopo ricezione bonifico esterno (solo tramite chiave causale)
- **Gestione discrepanze**: Admin rifiuta richiesta se bonifico non corrisponde
- **Timeout**: Nessuno, admin può eliminare richieste manualmente
- **Budget autonomo**: Utente investe liberamente senza ulteriori approvazioni

### **🏦 Sistema Portafoglio e Gestione Capitali**
- **4 Sezioni distinte**:
  - **Capitale Libero**: Soldi non investiti, sempre prelevabili
  - **Capitale Investito**: Bloccato fino alla vendita dell'immobile
  - **Bonus**: 1% referral, sempre disponibili per prelievo/investimento
  - **Profitti**: Rendimenti accumulati, prelevabili o reinvestibili
- **Valuta**: Sistema gestito in dollari con conversioni automatiche
- **Movimenti**: Bonus possono essere spostati in capitale libero per investimenti

### **📈 Sistema Rendimenti e Vendite Immobili**
- **Calcolo rendimenti**: Admin inserisce prezzo di vendita, sistema calcola profitti proporzionali
- **Referral bonus**: 1% del profitto va a chi ha invitato l'utente
- **Accumulo**: Rendimenti si accumulano nel tempo, non obbligatorio prelevarli
- **Reinvestimento**: Rendimenti possono essere reinvestiti
- **Vendita profittevole**: Capitale torna in capitale libero, profitti in sezione profitti
- **Vendita in perdita**: Capitale torna in capitale libero, nessun profitto
- **Notifiche**: Utente riceve notifica quando immobile viene venduto

### **💸 Sistema Prelievi e Ritiri**
- **Richiedente**: Solo utente proprietario
- **Sezioni prelevabili**: Bonus, capitale libero, profitti
- **Capitale investito**: NON prelevabile (bloccato fino vendita)
- **Minimo prelievo**: 50 dollari
- **Processo**: Utente richiede → Admin conferma → Bonifico
- **Timing approvazione**: Massimo 48h per approvazione admin
- **Bonifico**: Si adatta ai tempi della banca

### **📸 Gestione Progetti con Immagini**
- **Foto progetti**: Placeholder implementati per galleria immagini
- **Visualizzazione**: Grid responsive con immagini e dettagli

### **📱 Requisiti Tecnici**
- **Mobile-first**: Tutte le funzionalità devono funzionare perfettamente su mobile
- **Upload documenti**: Ottimizzato per mobile
- **Notifiche**: NESSUNA notifica automatica richiesta
- **Dashboard admin**: Vista unificata per richieste pendenti (lavoro futuro)

---

## 📱 Voci Navbar Identificate

### **Bottom Navigation (Mobile-First)**
1. **🏠 Dashboard** (`/user/dashboard`) 
2. **🔍 Search** (`/user/search`) 
3. **➕ New Project** (`/user/new_project`) 
4. **📊 Portfolio** (`/user/portfolio`) 
5. **👤 Profile** (`/user/profile`) 

### **Header Navigation (Desktop)**
6. **🔐 Auth** (`/auth/*`) 
7. **⚙️ Admin** (`/admin/*`) 

---

## 🚀 **ROADMAP STRATEGICA A BASSO RISCHIO**

### **📋 FASE 1: FONDAMENTI E INFRASTRUTTURA**
*Implementazione incrementale delle basi per minimizzare rischi*

#### **1.1 Database e Modelli Base** ✅
- [x] **Schema KYC**: Tabelle documenti e stati verifica
- [x] **Schema Portafoglio**: 4 sezioni capitali con relazioni
- [x] **Schema Ricariche**: Richieste, IBAN, chiavi univoche
- [x] **Schema Prelievi**: Richieste e stati approvazione
- [x] **Schema Rendimenti**: Calcoli profitti e referral

#### **1.2 API Endpoints Base** ✅
- [x] **KYC API**: Upload, verifica, stati
- [x] **Portafoglio API**: Lettura 4 sezioni, movimenti
- [x] **Ricariche API**: Richieste, approvazioni
- [x] **Prelievi API**: Richieste, approvazioni
- [x] **Rendimenti API**: Calcoli e distribuzioni

#### **1.3 Autenticazione e Autorizzazioni** 
- [ ] **Middleware KYC**: Blocco funzionalità per utenti non verificati
- [ ] **Ruoli e Permessi**: Admin vs User permissions
- [ ] **Validazioni**: Controlli sicurezza e business logic

---

### **📋 FASE 2: IMPLEMENTAZIONE INCREMENTALE PAGINE**
*Ogni pagina viene completata al 100% prima di passare alla successiva*

#### **2.1 Profile - Sistema KYC** 🎯 **PRIORITÀ 1** ✅
*Motivazione: Base per tutte le altre funzionalità, rischio minimo*
- [x] **Upload Documenti**: Gestione file PDF e immagini, upload documento identità nella pagina profilo user
- [x] **Stato KYC**: Visualizzazione e tracking verifica
- [x] **Form Profilo**: Dati personali e preferenze, sulla pagina portafoglio dell'user 
- [x] **Gestione Referral**: Codice invito e bonus accumulati, funzionante, ogni utente che viene invitato fa ricevere l'1% di guadagno sull'investimento fatto dall'invitato a chi ha invitato
- [x] **Mobile Optimization**: Upload ottimizzato per mobile
- **Complessità**: Media
- **Dipendenze**: Database KYC, API endpoints
- **Rischio**: Basso (CRUD base + upload)

#### **2.2 Auth System - Verifiche e Blocchi** 🎯 **PRIORITÀ 2**
*Motivazione: Sicurezza e controllo accessi, dipende da KYC*
- [ ] **Verifica KYC**: Controllo stato prima di abilitare funzionalità
- [ ] **Blocco Funzionalità**: Limitazioni per utenti non verificati
- [ ] **Login/Register**: Autenticazione base
- [ ] **Session Management**: Gestione sessioni sicure
- **Complessità**: Bassa
- **Dipendenze**: Sistema KYC
- **Rischio**: Basso (middleware e controlli)

#### **2.3 Portfolio - Gestione 4 Sezioni** 🎯 **PRIORITÀ 3**
*Motivazione: Core business logic, dipende da KYC e auth*
- [ ] **Visualizzazione 4 Sezioni**: Capitale libero, investito, bonus, profitti
- [ ] **Storico Ricariche**: Tracciamento ricariche e stati
- [ ] **Sistema Prelievi**: Richieste prelievo da sezioni disponibili
- [ ] **Movimenti Capitali**: Spostamenti tra sezioni portafoglio
- [ ] **Rendimenti**: Visualizzazione profitti accumulati e reinvestibili
- [ ] **Mobile Optimization**: Interfaccia ottimizzata per mobile
- **Complessità**: Alta
- **Dipendenze**: Sistema KYC, Auth, Database portafoglio
- **Rischio**: Medio (business logic complessa)

#### **2.4 Dashboard - Overview Completo** 🎯 **PRIORITÀ 4**
*Motivazione: Visualizzazione dati, dipende da portfolio*
- [ ] **KYC Status**: Indicatore stato verifica identità
- [ ] **4 Sezioni Portafoglio**: Visualizzazione saldi e stati
- [ ] **Stato Investimenti**: Indicatori investimenti attivi e bloccati
- [ ] **KPI e Metriche**: Overview performance e trend
- [ ] **Mobile Optimization**: Dashboard responsive
- **Complessità**: Media
- **Dipendenze**: Portfolio, KYC, Auth
- **Rischio**: Basso (solo visualizzazione)

#### **2.5 New Project - Investimenti** 🎯 **PRIORITÀ 5**
*Motivazione: Funzionalità core, dipende da tutto il sistema*
- [ ] **Verifica KYC**: Blocco se utente non verificato
- [ ] **Controllo Budget**: Verifica disponibilità saldo
- [ ] **Selezione Fonte**: Scelta sezione portafoglio per investimento
- [ ] **Calcolo Disponibilità**: Mostra importi disponibili per sezione
- [ ] **Wizard Investimento**: Form step-by-step ottimizzato
- [ ] **Mobile Optimization**: Form responsive
- **Complessità**: Media
- **Dipendenze**: KYC, Portfolio, Auth
- **Rischio**: Medio (form complesso + business logic)

#### **2.6 Search - Ricerca Progetti** 🎯 **PRIORITÀ 6**
*Motivazione: Funzionalità di supporto, dipendenze minime*
- [ ] **Immagini Progetti**: Placeholder per galleria foto
- [ ] **Filtro KYC**: Mostra solo progetti per utenti verificati
- [ ] **Stato Investimenti**: Indicatori se progetto già investito
- [ ] **Ricerca e Filtri**: Funzionalità base di ricerca
- [ ] **Mobile Optimization**: Ricerca ottimizzata per mobile
- **Complessità**: Bassa
- **Dipendenze**: KYC, Projects
- **Rischio**: Basso (solo lettura + filtri)

#### **2.7 Admin Panel - Gestione Sistema** 🎯 **PRIORITÀ 7**
*Motivazione: Gestione completa, dipende da tutte le funzionalità*
- [ ] **Gestione KYC**: Approvazione documenti identità
- [ ] **Gestione Ricariche**: Approvazione richieste dopo bonifici
- [ ] **Gestione Rendimenti**: Inserimento prezzi vendita, calcolo profitti
- [ ] **Gestione Prelievi**: Approvazione richieste prelievo (48h max)
- [ ] **Gestione Referral**: Distribuzione bonus 1% profitti
- [ ] **Configurazione IBAN**: Impostazione IBAN unico per ricariche
- [ ] **Monitoraggio Transazioni**: Tracking chiavi univoche e stati
- [ ] **Vendite Immobili**: Gestione vendite e distribuzione capitali
- [ ] **Mobile Optimization**: Admin panel responsive
- **Complessità**: Molto Alta
- **Dipendenze**: Tutte le funzionalità precedenti
- **Rischio**: Alto (gestione completa sistema)

---

### **📋 FASE 3: OTTIMIZZAZIONE E HARDENING**
*Perfezionamento finale e testing completo*

#### **3.1 Testing e Validazione** ✅
- [ ] **Unit Tests**: Test individuali per ogni componente
- [ ] **Integration Tests**: Test integrazione tra moduli
- [ ] **End-to-End Tests**: Test flussi completi utente
- [ ] **Mobile Testing**: Test su dispositivi reali
- [ ] **Security Testing**: Test sicurezza e vulnerabilità

#### **3.2 Performance e Ottimizzazione** ✅
- [ ] **Database Optimization**: Query e indici ottimizzati
- [ ] **Caching**: Cache per dati frequentemente acceduti
- [ ] **Mobile Performance**: Ottimizzazioni specifiche mobile
- [ ] **Load Testing**: Test sotto carico

#### **3.3 Accessibilità e UX** ✅
- [ ] **WCAG 2.1 AA**: Standard accessibilità
- [ ] **Mobile UX**: Esperienza utente ottimizzata
- [ ] **Error Handling**: Gestione errori user-friendly
- [ ] **Loading States**: Stati di caricamento chiari

---

## 📊 **MATRICE RISCHI E DIPENDENZE**

| Pagina | Complessità | Dipendenze | Rischio | Priorità |
|--------|-------------|------------|---------|----------|
| **Profile** | Media | Database KYC | Basso | 1️⃣ |
| **Auth** | Bassa | KYC | Basso | 2️⃣ |
| **Portfolio** | Alta | KYC + Auth + DB | Medio | 3️⃣ |
| **Dashboard** | Media | Portfolio | Basso | 4️⃣ |
| **New Project** | Media | KYC + Portfolio | Medio | 5️⃣ |
| **Search** | Bassa | KYC + Projects | Basso | 6️⃣ |
| **Admin Panel** | Molto Alta | Tutto | Alto | 7️⃣ |

---

## 🎯 **COME PROCEDERE**

1. **Inizia con FASE 1**: Completare infrastruttura e API base
2. **Procedi con FASE 2**: Implementa una pagina alla volta seguendo l'ordine
3. **Ogni pagina deve essere 100% completa** prima di passare alla successiva
4. **Testa ogni implementazione** per evitare regressioni
5. **FASE 3**: Ottimizzazione e hardening finale

**Vuoi iniziare con la FASE 1 (infrastruttura) o preferisci saltare direttamente a una pagina specifica?** 🚀

---

*Documento creato: 2024-12-19*
*Stato: Riorganizzato strategicamente per minimizzare rischi*
*Ultimo aggiornamento: 2024-12-19*
