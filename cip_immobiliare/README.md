# CIP Immobiliare - Starter Kit Flask + PostgreSQL

Sistema completo per gestione investimenti immobiliari con Flask e PostgreSQL.

## 🚀 Setup Rapido

### 1. Ambiente Virtuale
```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
```

### 2. Dipendenze
```bash
pip install -r requirements.txt
```

### 3. Configurazione
```bash
cp env.example .env
# Modifica .env con le tue credenziali PostgreSQL
```

### 4. Database
```bash
createdb cip
psql -d cip -f schema.sql
```

### 5. Avvio
```bash
export FLASK_APP=admin.py
flask run --debug
```

## 📁 Struttura Progetto

```
cip_immobiliare/
├── admin.py              # App principale + blueprint admin
├── user.py               # Blueprint utente
├── auth.py               # Blueprint autenticazione
├── requirements.txt      # Dipendenze Python
├── env.example          # Template variabili ambiente
├── schema.sql           # Schema database PostgreSQL
├── static/css/
│   └── style.css        # CSS condiviso
└── templates/
    ├── base.html         # Layout base
    ├── admin/
    │   └── placeholder.html
    └── user/
        └── placeholder.html
```

## 🔧 Endpoint Principali

### Autenticazione
- `POST /auth/register` - Registrazione utente
- `POST /auth/login` - Login
- `GET /auth/me` - Info utente corrente
- `GET /auth/logout` - Logout

### Utente
- `GET /` - Dashboard utente
- `GET /portfolio` - Portafoglio investimenti
- `POST /requests/new` - Nuova richiesta investimento
- `GET /documents` - Gestione documenti

### Admin
- `GET /admin/` - Dashboard admin
- `GET /admin/users` - Lista utenti
- `GET /admin/projects` - Gestione progetti
- `POST /admin/requests/<id>/approve` - Approva richiesta

## 🧪 Test Rapidi

```bash
# Registrazione
curl -X POST http://localhost:5000/auth/register \
  -H "Content-Type: application/json" \
  -d '{"email":"test@example.com","password":"password","full_name":"Test User"}'

# Login
curl -X POST http://localhost:5000/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"test@example.com","password":"password"}'

# Dashboard (con cookie di sessione)
curl -b cookies.txt http://localhost:5000/
```

## 📊 Database

Il sistema include:
- **Users**: Gestione utenti con KYC e referral
- **Projects**: Progetti immobiliari
- **Investments**: Investimenti e rendimenti
- **Documents**: Sistema documenti con categorie
- **Notifications**: Sistema notifiche
- **Referral**: Bonus e struttura rete

## 🎨 UI/UX

- Design minimal e moderno
- CSS con variabili CSS personalizzabili
- Template placeholder per sviluppo frontend
- API RESTful per integrazione client

## 🔒 Sicurezza

- Autenticazione basata su sessione
- Middleware di autorizzazione per admin
- Hash password con Werkzeug
- Upload file sicuri
