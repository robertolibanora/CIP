# 🚀 CIP Immobiliare - Guida Produzione

## 📋 Prerequisiti

- **Python 3.8+**
- **PostgreSQL 12+**
- **Nginx** (opzionale, per reverse proxy)
- **Gunicorn** per WSGI server

## 🔧 Installazione

### 1. Clona il repository
```bash
git clone <repository-url>
cd C.I.P.
```

### 2. Crea ambiente virtuale
```bash
python3 -m venv .venv
source .venv/bin/activate
```

### 3. Installa dipendenze
```bash
pip install -r requirements.txt
pip install gunicorn psycopg2-binary
```

### 4. Configura database
```bash
# Crea database e utente
psql -U postgres -f config/database/production.sql

# Aggiorna config/env.production con le credenziali reali
```

### 5. Configura variabili ambiente
```bash
cp config/env.production config/env.local
# Modifica config/env.local con i valori reali
```

## 🚀 Deploy

### Deploy automatico
```bash
export FLASK_ENV=production
./deploy.sh
```

### Deploy manuale
```bash
export FLASK_ENV=production
source .venv/bin/activate
gunicorn --bind 0.0.0.0:8090 --workers 4 main:app
```

## 📁 Struttura Produzione

```
C.I.P./
├── frontend/
│   ├── static/           # File statici (CSS, JS, immagini)
│   │   ├── css/         # CSS compilati
│   │   ├── js/          # JavaScript
│   │   └── icons/       # Icone PWA
│   ├── templates/        # Template Jinja2
│   └── uploads/         # File caricati dagli utenti
├── backend/              # Logica applicazione
├── config/               # Configurazioni
├── main.py              # Entry point
└── deploy.sh            # Script di deploy
```

## 🔒 Sicurezza

- **Cambia SECRET_KEY** in produzione
- **Usa HTTPS** in produzione
- **Configura firewall** per limitare accessi
- **Backup regolari** del database
- **Log di sicurezza** attivi

## 📊 Monitoraggio

- **Log applicazione**: `/var/log/cip_immobiliare/app.log`
- **Log accessi**: `/var/log/cip_immobiliare/access.log`
- **Log errori**: `/var/log/cip_immobiliare/error.log`

## 🆘 Troubleshooting

### Problemi comuni:

1. **Porta già in uso**: Cambia porta in `config/env.production`
2. **Database non raggiungibile**: Verifica credenziali e connessione
3. **CSS non caricati**: Verifica percorsi in `frontend/static/`
4. **Template error**: Verifica sintassi Jinja2

### Comandi utili:

```bash
# Verifica stato applicazione
ps aux | grep gunicorn

# Verifica log
tail -f /var/log/cip_immobiliare/app.log

# Riavvia applicazione
pkill -f gunicorn && ./deploy.sh
```

## 📞 Supporto

Per problemi tecnici, controlla:
1. Log dell'applicazione
2. Log del sistema
3. Stato del database
4. Configurazione ambiente

---

**⚠️ IMPORTANTE**: Cambia tutte le password di default prima del deploy in produzione!
