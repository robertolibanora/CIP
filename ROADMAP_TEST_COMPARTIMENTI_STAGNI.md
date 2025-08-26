# 🧪 ROADMAP DI TEST - COMPARTIMENTI STAGNI USER

## 📋 OBIETTIVI DELLA VALIDAZIONE

Ogni pagina User deve essere testata per verificare:
1. **Accessibilità solo tramite navbar** - Niente accessi diretti "sparsi"
2. **Tabella SQL corrispondente funziona correttamente**
3. **Logica della pagina rispetta il suo compartimento**

## 🏗️ STRUTTURA COMPARTIMENTI STAGNI

### 1. **DASHBOARD** (`/user/dashboard`)
- **Blueprint**: `dashboard_bp`
- **Tabelle SQL**: `users`, `investments`, `investment_yields`, `referral_bonuses`
- **Funzionalità**: Vista generale portfolio, statistiche, investimenti attivi
- **Accesso**: Solo tramite navbar mobile-nav.html

### 2. **PORTFOLIO** (`/user/portfolio`)
- **Blueprint**: `portfolio_bp`
- **Tabelle SQL**: `investments`, `projects`, `investment_yields`
- **Funzionalità**: Dettaglio investimenti attivi/completati, rendimenti
- **Accesso**: Solo tramite navbar mobile-nav.html

### 3. **PROGETTI** (`/user/projects`)
- **Blueprint**: `projects_bp`
- **Tabelle SQL**: `projects` (solo lettura)
- **Funzionalità**: Lista progetti disponibili per investimento
- **Accesso**: Solo tramite navbar mobile-nav.html

### 4. **REFERRAL** (`/user/referral`)
- **Blueprint**: `referral_bp`
- **Tabelle SQL**: `users`, `investments`, `referral_bonuses`
- **Funzionalità**: Sistema referral, bonus, statistiche
- **Accesso**: Solo tramite navbar mobile-nav.html

### 5. **PROFILO** (`/user/profile`)
- **Blueprint**: `profile_bp`
- **Tabelle SQL**: `users` (lettura e scrittura)
- **Funzionalità**: Gestione account, aggiornamento dati
- **Accesso**: Solo tramite navbar mobile-nav.html

### 6. **RICERCA** (`/user/search`)
- **Blueprint**: `search_bp`
- **Tabelle SQL**: `projects` (solo lettura)
- **Funzionalità**: Ricerca progetti disponibili
- **Accesso**: Solo tramite navbar mobile-nav.html

### 7. **NUOVO INVESTIMENTO** (`/user/new-project`)
- **Blueprint**: `new_project_bp`
- **Tabelle SQL**: `projects` (solo lettura)
- **Funzionalità**: Selezione progetto per nuovo investimento
- **Accesso**: Solo tramite navbar mobile-nav.html

## 🧪 SEQUENZA DI VERIFICHE

### FASE 1: Validazione Accessi
```bash
# Test 1: Accesso diretto alle route (DEVE FALLIRE)
curl -s -o /dev/null -w "%{http_code}" http://localhost:8090/user/dashboard
curl -s -o /dev/null -w "%{http_code}" http://localhost:8090/user/portfolio
curl -s -o /dev/null -w "%{http_code}" http://localhost:8090/user/projects
curl -s -o /dev/null -w "%{http_code}" http://localhost:8090/user/referral
curl -s -o /dev/null -w "%{http_code}" http://localhost:8090/user/profile
curl -s -o /dev/null -w "%{http_code}" http://localhost:8090/user/search
curl -s -o /dev/null -w "%{http_code}" http://localhost:8090/user/new-project

# Risultato atteso: 302 (redirect) o 401 (unauthorized)
```

### FASE 2: Validazione Login e Accesso via Navbar
```bash
# Test 2: Login utente e accesso tramite navbar
# 1. Login utente test
# 2. Navigazione tramite mobile-nav.html
# 3. Verifica che tutte le pagine siano accessibili
```

### FASE 3: Validazione Tabelle SQL
```bash
# Test 3: Verifica funzionamento tabelle per ogni compartimento

# Dashboard
psql -d cip_immobiliare -c "SELECT COUNT(*) FROM users WHERE id = 1;"
psql -d cip_immobiliare -c "SELECT COUNT(*) FROM investments WHERE user_id = 1;"
psql -d cip_immobiliare -c "SELECT COUNT(*) FROM investment_yields;"
psql -d cip_immobiliare -c "SELECT COUNT(*) FROM referral_bonuses;"

# Portfolio
psql -d cip_immobiliare -c "SELECT COUNT(*) FROM investments WHERE user_id = 1;"
psql -d cip_immobiliare -c "SELECT COUNT(*) FROM projects WHERE status = 'active';"

# Projects
psql -d cip_immobiliare -c "SELECT COUNT(*) FROM projects WHERE status = 'active';"

# Referral
psql -d cip_immobiliare -c "SELECT COUNT(*) FROM users WHERE referred_by = 1;"
psql -d cip_immobiliare -c "SELECT COUNT(*) FROM referral_bonuses WHERE receiver_user_id = 1;"

# Profile
psql -d cip_immobiliare -c "SELECT * FROM users WHERE id = 1;"
```

### FASE 4: Validazione Isolamento Compartimenti
```bash
# Test 4: Verifica che ogni modulo acceda solo alle tabelle necessarie

# Controllo accessi database per ogni blueprint:
# - dashboard_bp: solo users, investments, investment_yields, referral_bonuses
# - portfolio_bp: solo investments, projects, investment_yields
# - projects_bp: solo projects (lettura)
# - referral_bp: solo users, investments, referral_bonuses
# - profile_bp: solo users
# - search_bp: solo projects (lettura)
# - new_project_bp: solo projects (lettura)
```

## 🔍 CRITERI DI SUCCESSO

### ✅ Accessibilità
- [ ] Tutte le route `/user/*` restituiscono 302/401 senza autenticazione
- [ ] Tutte le pagine sono accessibili tramite navbar dopo login
- [ ] Niente accessi diretti "sparsi" alle route

### ✅ Funzionalità Database
- [ ] Dashboard: calcola correttamente portfolio, rendimenti, bonus
- [ ] Portfolio: mostra investimenti attivi/completati
- [ ] Projects: lista progetti disponibili
- [ ] Referral: statistiche e bonus corretti
- [ ] Profile: lettura/scrittura dati utente
- [ ] Search: ricerca progetti funziona
- [ ] New Project: selezione progetti disponibili

### ✅ Isolamento Compartimenti
- [ ] Ogni blueprint accede solo alle tabelle necessarie
- [ ] Niente condivisione di logica tra moduli
- [ ] Ogni modulo è completamente autonomo

## 🚀 ESECUZIONE TEST

### Setup Ambiente Test
```bash
# 1. Attiva ambiente virtuale
source venv/bin/activate

# 2. Avvia applicazione
python main.py

# 3. Esegui test in sequenza
# 4. Verifica risultati
```

### Comandi di Test Rapido
```bash
# Test accessi diretti (deve fallire)
for route in dashboard portfolio projects referral profile search new-project; do
  echo "Testing /user/$route: $(curl -s -o /dev/null -w "%{http_code}" http://localhost:8090/user/$route)"
done

# Test database
psql -d cip_immobiliare -c "SELECT 'users' as table_name, COUNT(*) as count FROM users UNION ALL SELECT 'investments', COUNT(*) FROM investments UNION ALL SELECT 'projects', COUNT(*) FROM projects;"
```

## 📊 METRICHE DI SUCCESSO

- **100%** delle route protette da accesso diretto
- **100%** delle pagine accessibili tramite navbar
- **100%** delle tabelle SQL funzionanti
- **0%** di condivisione logica tra compartimenti
- **100%** di isolamento modulare

## 🔧 CORREZIONI NECESSARIE

Se un test fallisce:
1. **Identifica** il compartimento problematico
2. **Isola** la logica specifica
3. **Correggi** l'accesso alle tabelle
4. **Ritesta** il compartimento
5. **Verifica** l'isolamento completo
