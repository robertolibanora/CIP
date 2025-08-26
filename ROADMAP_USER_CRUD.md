# 🧪 ROADMAP USER CRUD - CIP IMMOBILIARE

## 📋 **OVERVIEW TESTING STRATEGY**

Questa roadmap si concentra **SOLO** sul modulo USER per verificare ogni singolo dettaglio del CRUD prima di procedere con gli altri moduli.

---

## 🎯 **FOCUS: MODULO USER (backend/user/routes.py)**

### **📊 Obiettivo Principale**
Verificare che **TUTTE** le operazioni CRUD del modulo user funzionino perfettamente prima di testare altri moduli.

---

## 🔍 **STEP 1: ANALISI STRUTTURA MODULO USER**

### **📁 File da Analizzare**
- [ ] **`backend/user/routes.py`** - Contiene tutte le rotte user
- [ ] **`backend/user/__init__.py`** - Inizializzazione modulo
- [ ] **Template associati** - Dashboard e portfolio user

### **🔗 Rotte da Identificare**
- [ ] **GET** `/user/dashboard` - Dashboard principale
- [ ] **GET** `/user/portfolio` - Portfolio utente
- [ ] **GET** `/user/requests` - Richieste investimento
- [ ] **POST** `/user/requests/new` - Nuova richiesta
- [ ] **PUT** `/user/requests/<id>/edit` - Modifica richiesta
- [ ] **DELETE** `/user/requests/<id>` - Cancellazione richiesta

### **📊 Database Tables Coinvolte**
- [ ] **`users`** - Dati utente
- [ ] **`user_portfolio`** - Portfolio utente
- [ ] **`investment_requests`** - Richieste investimento
- [ ] **`projects`** - Progetti disponibili

---

## 🧪 **STEP 2: TEST CONNESSIONE E STRUTTURA BASE**

### **🔌 Test Connessione Database**
```bash
# Verifica connessione PostgreSQL
psql -d cip -c "SELECT 1"

# Verifica tabelle esistenti
psql -d cip -c "\dt"

# Verifica schema user_portfolio
psql -d cip -c "\d user_portfolio"
```

### **📁 Test Struttura File**
- [ ] **File esiste**: `backend/user/routes.py`
- [ ] **Blueprint registrato**: `user_bp` in `main.py`
- [ ] **Template esistono**: `frontend/templates/user/`
- [ ] **Static files**: CSS/JS per user dashboard

### **🔗 Test Rotte Base**
```bash
# Test endpoint user (dovrebbe redirect a login se non autenticato)
curl -I http://localhost:8069/user/dashboard

# Verifica blueprint registrato
curl -I http://localhost:8069/user/
```

---

## 👤 **STEP 3: TEST AUTHENTICATION USER**

### **📝 CREATE - Registrazione Utente**
```bash
# Test registrazione nuovo utente
curl -X POST http://localhost:8069/auth/register \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "email=testuser@example.com&password=test123&full_name=Test User"

# Verifica risposta
# Status: 200/302 (successo)
# Redirect: /auth/login o /user/dashboard
```

**Validazioni da Testare:**
- [ ] **Email valida**: `test@example.com` → Successo
- [ ] **Email duplicata**: `admin@example.com` → Errore 400
- [ ] **Email non valida**: `invalid-email` → Errore 400
- [ ] **Password vuota**: `password=` → Errore 400
- [ ] **Full name vuoto**: `full_name=` → Errore 400

### **🔍 READ - Login Utente**
```bash
# Test login utente registrato
curl -X POST http://localhost:8069/auth/login \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "email=testuser@example.com&password=test123"

# Verifica sessione creata
curl -b cookies.txt http://localhost:8069/auth/me
```

**Validazioni da Testare:**
- [ ] **Credenziali corrette** → Successo + Sessione
- [ ] **Email non esistente** → Errore 401
- [ ] **Password sbagliata** → Errore 401
- [ ] **Account disabilitato** → Gestione corretta

---

## 📊 **STEP 4: TEST DASHBOARD USER**

### **🔍 READ - Dashboard Principale**
```bash
# Test accesso dashboard (con sessione valida)
curl -b cookies.txt http://localhost:8069/user/dashboard

# Verifica risposta JSON
# Dovrebbe contenere: total_invested, active_count, total_yields, referral_bonus
```

**Dati da Verificare:**
- [ ] **`total_invested`** - Calcolo corretto da `user_portfolio`
- [ ] **`active_count`** - Conteggio investimenti attivi
- [ ] **`total_yields`** - Somma yields da investimenti
- [ ] **`referral_bonus`** - Commissioni referral totali

### **🔍 READ - Portfolio Utente**
```bash
# Test accesso portfolio
curl -b cookies.txt http://localhost:8069/user/portfolio

# Verifica lista investimenti
curl -b cookies.txt "http://localhost:8069/user/portfolio?status=active"
curl -b cookies.txt "http://localhost:8069/user/portfolio?status=completed"
```

**Funzionalità da Verificare:**
- [ ] **Filtri status** - active, completed, cancelled
- [ ] **Paginazione** - se molti investimenti
- [ ] **Join con projects** - dati progetto completi
- [ ] **Calcoli yields** - ROI per ogni investimento

---

## 💰 **STEP 5: TEST GESTIONE RICHIESTE INVESTIMENTO**

### **📝 CREATE - Nuova Richiesta**
```bash
# Test creazione richiesta investimento
curl -X POST http://localhost:8069/user/requests/new \
  -b cookies.txt \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "project_id=1&amount=1000&description=Test investment"
```

**Validazioni da Testare:**
- [ ] **Project ID valido** → Successo
- [ ] **Project ID non esistente** → Errore 400
- [ ] **Amount positivo** → Successo
- [ ] **Amount negativo** → Errore 400
- [ ] **Amount > target_amount** → Errore 400
- [ ] **Progetto non in funding** → Errore 400

### **🔍 READ - Lista Richieste**
```bash
# Test lista richieste utente
curl -b cookies.txt http://localhost:8069/user/requests

# Verifica filtri
curl -b cookies.txt "http://localhost:8069/user/requests?status=pending"
curl -b cookies.txt "http://localhost:8069/user/requests?status=approved"
```

**Dati da Verificare:**
- [ ] **Solo proprie richieste** - Sicurezza
- [ ] **Stato corretto** - pending, approved, rejected
- [ ] **Dati progetto** - title, target_amount, status
- [ ] **Timestamp** - created_at, updated_at

### **🔄 UPDATE - Modifica Richiesta**
```bash
# Test modifica richiesta (solo pending)
curl -X PUT http://localhost:8069/user/requests/1/edit \
  -b cookies.txt \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "amount=1500&description=Updated investment"
```

**Validazioni da Testare:**
- [ ] **Solo richieste pending** → Modificabili
- [ ] **Solo proprie richieste** → Sicurezza
- [ ] **Amount valido** → Aggiornamento
- [ ] **Description aggiornata** → Database
- [ **Timestamp updated** → Aggiornamento

### **🗑️ DELETE - Cancellazione Richiesta**
```bash
# Test cancellazione richiesta
curl -X DELETE http://localhost:8069/user/requests/1 \
  -b cookies.txt
```

**Validazioni da Testare:**
- [ ] **Solo richieste pending** → Cancellabili
- [ ] **Solo proprie richieste** → Sicurezza
- [ ] **Rimozione database** → Verifica
- [ ] **Risposta corretta** → 200/204

---

## 🔒 **STEP 6: TEST SICUREZZA E AUTORIZZAZIONE**

### **🚫 Test Accesso Non Autorizzato**
```bash
# Test accesso senza login
curl -I http://localhost:8069/user/dashboard

# Test accesso con sessione scaduta
curl -b expired_cookies.txt http://localhost:8069/user/dashboard

# Test accesso a richieste di altri utenti
curl -b cookies.txt http://localhost:8069/user/requests/999
```

**Sicurezza da Verificare:**
- [ ] **Redirect a login** se non autenticato
- [ ] **Errore 403** per accesso non autorizzato
- [ ] **Isolamento dati** - solo propri dati
- [ ] **Session validation** - sessione valida

### **🔐 Test Validazione Input**
```bash
# Test SQL injection
curl -X POST http://localhost:8069/user/requests/new \
  -b cookies.txt \
  -d "project_id=1'; DROP TABLE users; --&amount=1000"

# Test XSS
curl -X POST http://localhost:8069/user/requests/new \
  -b cookies.txt \
  -d "project_id=1&amount=1000&description=<script>alert('xss')</script>"
```

**Protezioni da Verificare:**
- [ ] **SQL Injection** - Parametri sanitizzati
- [ ] **XSS** - HTML/JS escapato
- [ ] **CSRF** - Token protezione
- [ ] **Input validation** - Dati validati

---

## 📊 **STEP 7: TEST PERFORMANCE E SCALABILITÀ**

### **⚡ Test Response Time**
```bash
# Test tempo risposta dashboard
time curl -b cookies.txt http://localhost:8069/user/dashboard

# Test tempo risposta portfolio
time curl -b cookies.txt http://localhost:8069/user/portfolio

# Obiettivo: < 200ms per endpoint
```

### **📈 Test Concorrenza**
```bash
# Test accessi simultanei (se possibile)
for i in {1..10}; do
  curl -b cookies.txt http://localhost:8069/user/dashboard &
done
wait
```

**Performance da Verificare:**
- [ ] **Response time** < 200ms
- [ ] **Database queries** ottimizzate
- [ ] **Concorrenza** gestita correttamente
- [ ] **Memory usage** stabile

---

## 🧹 **STEP 8: PULIZIA E VERIFICA FINALE**

### **🗄️ Verifica Database**
```bash
# Verifica integrità dati
psql -d cip -c "SELECT COUNT(*) FROM users WHERE email = 'testuser@example.com'"
psql -d cip -c "SELECT COUNT(*) FROM investment_requests WHERE user_id = (SELECT id FROM users WHERE email = 'testuser@example.com')"

# Verifica foreign keys
psql -d cip -c "SELECT * FROM investment_requests ir JOIN users u ON ir.user_id = u.id WHERE u.email = 'testuser@example.com'"
```

### **📋 Checklist Finale**
- [ ] **Tutte le rotte user** funzionano
- [ ] **CRUD completo** per richieste investimento
- [ ] **Sicurezza** implementata correttamente
- [ ] **Performance** accettabili
- [ ] **Database** integro e consistente

---

## 🚨 **PROBLEMI COMUNI E SOLUZIONI**

### **❌ Errore 500 - Internal Server Error**
1. **Controlla log Flask** - `python main.py`
2. **Verifica database** - `psql -d cip -c "SELECT 1"`
3. **Controlla import** - Moduli caricati correttamente

### **❌ Errore 404 - Not Found**
1. **Verifica blueprint** - Registrato in `main.py`
2. **Controlla URL** - Rotte definite correttamente
3. **Verifica template** - File esistono

### **❌ Errore 403 - Forbidden**
1. **Verifica autenticazione** - Sessione valida
2. **Controlla autorizzazione** - Ruolo utente
3. **Verifica middleware** - `@require_login`

---

## 🎯 **CRITERI DI SUCCESSO STEP USER**

### **✅ Funzionalità Core**
- [ ] **Dashboard user** carica correttamente
- [ ] **Portfolio** mostra dati corretti
- [ ] **CRUD richieste** completo e funzionante
- [ ] **Filtri e paginazione** funzionano

### **✅ Sicurezza**
- [ ] **Autenticazione** richiesta per tutte le pagine
- [ ] **Autorizzazione** - solo propri dati
- [ ] **Validazione input** previene attacchi
- [ ] **Session management** sicuro

### **✅ Performance**
- [ ] **Response time** < 200ms
- [ ] **Database queries** ottimizzate
- [ ] **Concorrenza** gestita correttamente

---

## 🔄 **PROSSIMI STEP (DOPO USER)**

Una volta che il modulo USER funziona perfettamente:

1. **🔐 AUTH Module** - Login, registrazione, logout
2. **💰 PORTFOLIO Module** - Investimenti, referral
3. **👨‍💼 ADMIN Module** - Gestione sistema
4. **🔗 INTEGRATION** - Test end-to-end

---

**🎯 Obiettivo Step User: Modulo USER completamente funzionante e testato prima di procedere con altri moduli!**

**💡 Suggerimento: Testa ogni step individualmente e verifica che funzioni prima di passare al successivo.**
