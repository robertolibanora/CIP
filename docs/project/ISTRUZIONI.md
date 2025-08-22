# 🚀 ISTRUZIONI COMPLETE - CIP Immobiliare

## ✅ Progetto Completato!

Il progetto è stato creato con successo nella cartella `cip_immobiliare/`. Ecco cosa fare ora:

## 📋 Prerequisiti

1. **Python 3.8+** installato
2. **PostgreSQL** installato e in esecuzione
3. **Git** (opzionale, per versioning)

## 🚀 Setup Automatico (Raccomandato)

```bash
cd cip_immobiliare
./setup.sh
```

Lo script farà tutto automaticamente!

## 🔧 Setup Manuale

### 1. Ambiente Virtuale
```bash
cd cip_immobiliare
python3 -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
```

### 2. Dipendenze
```bash
pip install -r requirements.txt
```

### 3. Configurazione
```bash
cp env.example .env
# MODIFICA .env con le tue credenziali PostgreSQL
```

### 4. Database
```bash
createdb cip
psql -d cip -f schema.sql
```

### 5. Utente Admin (Opzionale)
```bash
# Genera hash password
python generate_admin.py

# Copia l'hash nel file create_admin.sql
# Poi esegui:
psql -d cip -f create_admin.sql
```

### 6. Avvio
```bash
export FLASK_APP=admin.py
flask run --debug
```

## 🧪 Test Rapido

```bash
# In un altro terminale
cd cip_immobiliare
source .venv/bin/activate
python test_api.py
```

## 🌐 Endpoint Disponibili

### Pubblici
- `GET /auth/login` - Form login
- `POST /auth/register` - Registrazione
- `POST /auth/login` - Login

### Protetti (User)
- `GET /` - Dashboard utente
- `GET /portfolio` - Portafoglio
- `POST /requests/new` - Nuova richiesta
- `GET /documents` - Documenti

### Protetti (Admin)
- `GET /admin/` - Dashboard admin
- `GET /admin/users` - Gestione utenti
- `GET /admin/projects` - Gestione progetti
- `POST /admin/requests/<id>/approve` - Approva richieste

## 📁 Struttura File

```
cip_immobiliare/
├── admin.py              # App principale + admin
├── user.py               # Blueprint utente  
├── auth.py               # Blueprint auth
├── requirements.txt      # Dipendenze
├── env.example          # Template .env
├── schema.sql           # Schema DB
├── create_admin.sql     # Script admin
├── generate_admin.py    # Genera hash password
├── setup.sh             # Setup automatico
├── test_api.py          # Test API
├── README.md            # Documentazione
├── .gitignore           # Git ignore
├── static/css/
│   └── style.css        # CSS condiviso
└── templates/
    ├── base.html         # Layout base
    ├── admin/placeholder.html
    └── user/placeholder.html
```

## 🔒 Credenziali Default

- **Admin**: admin@cip.com / admin123 (se creato)
- **Utente**: test@example.com / password123 (via test)

## 🚨 Risoluzione Problemi

### Database non raggiungibile
```bash
# Verifica PostgreSQL
psql -U postgres -c "SELECT version();"

# Verifica connessione
psql -d cip -c "SELECT 1;"
```

### Porta occupata
```bash
# Cambia porta
export FLASK_RUN_PORT=5001
flask run --debug
```

### Errori import
```bash
# Verifica ambiente virtuale
which python
pip list | grep Flask
```

## 📞 Supporto

Se hai problemi:
1. Controlla i log Flask
2. Verifica la connessione database
3. Controlla le variabili d'ambiente
4. Assicurati che PostgreSQL sia attivo

## 🎯 Prossimi Passi

1. **Personalizza CSS** in `static/css/style.css`
2. **Aggiungi template HTML** per le tue pagine
3. **Estendi le API** secondo le tue esigenze
4. **Configura produzione** (WSGI, nginx, etc.)

---

**🎉 Il progetto è pronto per l'uso!**
