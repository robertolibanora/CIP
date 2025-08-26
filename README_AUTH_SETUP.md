# CIP Academy - Setup Autenticazione

## 🚀 Nuovo Sistema di Autenticazione

Questo progetto è stato aggiornato con nuovi template di login e registrazione basati sui file JavaScript forniti.

## 📋 Modifiche Implementate

### 1. Database Schema Aggiornato
- Aggiunti nuovi campi alla tabella `users`:
  - `nome` - Nome dell'utente
  - `cognome` - Cognome dell'utente  
  - `nome_telegram` - Username Telegram
  - `telefono` - Numero di telefono
  - `referral_link` - Link di referimento

### 2. Backend Aggiornato
- Rimosso hardcoding delle credenziali admin
- Aggiornate le route per gestire i nuovi campi
- Validazione migliorata per email e password
- Gestione referral system

### 3. Frontend Aggiornato
- Nuovi template con design moderno e responsive
- Validazione JavaScript lato client
- Stili CSS personalizzati per CIP Academy
- Icone SVG integrate

## 🗄️ Setup Database

### 1. Applica Schema Aggiornato
```sql
-- Esegui il file aggiornato
-- CIP/config/database/schema.sql
```

### 2. Inserisci Credenziali di Test
```sql
-- Esegui il file seed
-- CIP/scripts/seed_test_users.sql
```

### 3. Credenziali di Test Disponibili

#### Admin User
- **Email**: marktrapella06@gmail.com
- **Password**: admin123
- **Role**: admin

#### Test Users
- **Email**: test1@example.com
- **Password**: password123
- **Role**: investor

- **Email**: test2@example.com  
- **Password**: password123
- **Role**: investor

- **Email**: test3@example.com
- **Password**: password123
- **Role**: investor

## 🔧 Configurazione

### 1. File CSS
Il file `CIP/frontend/static/css/auth-forms.css` contiene tutti gli stili necessari per i nuovi template.

### 2. Logo
Sostituisci il file `CIP/frontend/static/logo-cip-academy.png` con il logo effettivo dell'azienda.

### 3. Variabili d'Ambiente
Assicurati che le seguenti variabili siano configurate:
- Database connection string
- Secret key per Flask
- CSRF protection

## 🚀 Avvio Applicazione

```bash
cd CIP
python main.py
```

L'applicazione sarà disponibile su `http://localhost:5000`

## 📱 Funzionalità

### Login
- Form responsive con validazione
- Gestione errori elegante
- Reindirizzamento automatico per admin/utenti

### Registrazione  
- Form completo con tutti i campi richiesti
- Validazione lato client e server
- Sistema referral integrato
- Conferma numero di telefono

### Sicurezza
- Password hashing (da implementare completamente)
- Validazione CSRF
- Session management
- Role-based access control

## 🔍 Troubleshooting

### Template non visualizzati correttamente
1. Verifica che `auth-forms.css` sia incluso
2. Controlla che il logo sia presente
3. Verifica che Tailwind CSS sia caricato

### Errori di database
1. Applica lo schema aggiornato
2. Esegui lo script di seed
3. Verifica la connessione al database

### Problemi di autenticazione
1. Verifica che le credenziali di test siano nel database
2. Controlla i log del backend
3. Verifica che le sessioni funzionino correttamente

## 📚 Documentazione Aggiuntiva

- [Schema Database](config/database/schema.sql)
- [Route Autenticazione](backend/auth/routes.py)
- [Template Base](frontend/templates/auth/base_auth.html)
- [Stili CSS](frontend/static/css/auth-forms.css)

---

**CIP Academy** - Sistema di autenticazione moderno e sicuro 🚀✨
