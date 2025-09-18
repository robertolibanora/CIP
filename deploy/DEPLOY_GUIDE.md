# 🚀 Guida Completa Deploy CIP Immobiliare su DigitalOcean

Questa guida ti accompagnerà passo passo per il deploy del progetto CIP Immobiliare su DigitalOcean con Ubuntu 24.04 LTS.

## 📋 Prerequisiti

- Account DigitalOcean attivo
- Dominio configurato (es. `cipimmobiliare.it`)
- Accesso SSH al server
- Repository Git del progetto

## 🎯 Panoramica Architettura

```
Internet → Nginx (80/443) → Gunicorn (8090) → Flask App → PostgreSQL (5432)
```

## 📦 FASE 1: Creazione Server DigitalOcean

### 1.1 Creazione Droplet

1. Accedi a [DigitalOcean](https://digitalocean.com)
2. Clicca su "Create" → "Droplets"
3. Configura:
   - **Image**: Ubuntu 24.04 LTS
   - **Plan**: Basic ($12/mese)
     - 2GB RAM
     - 1 vCPU
     - 50GB SSD
   - **Region**: Scegli la più vicina (es. Amsterdam per l'Europa)
   - **Authentication**: SSH Key (raccomandato)
   - **Hostname**: `cip-immobiliare-prod`
   - **Tags**: `production`, `web-app`

### 1.2 Accesso Iniziale

```bash
ssh root@YOUR_SERVER_IP
```

## 🔧 FASE 2: Preparazione Repository

### 2.1 Clona il Repository

```bash
# Sul server
cd /var/www
git clone https://github.com/your-username/cip-immobiliare.git
# oppure se hai un repository privato:
# git clone https://username:token@github.com/your-username/cip-immobiliare.git
```

### 2.2 Verifica Struttura

```bash
cd /var/www/cip_immobiliare
ls -la
# Dovresti vedere: main.py, requirements.txt, frontend/, backend/, config/, etc.
```

## 🚀 FASE 3: Deploy Automatico

### 3.1 Esegui Script di Deploy

```bash
cd /var/www/cip_immobiliare
chmod +x deploy/*.sh
sudo bash deploy/deploy.sh
```

Lo script eseguirà automaticamente:
- ✅ Configurazione server Ubuntu
- ✅ Installazione dipendenze
- ✅ Configurazione PostgreSQL
- ✅ Setup Nginx
- ✅ Configurazione SSL (opzionale)
- ✅ Hardening sicurezza
- ✅ Avvio servizi

### 3.2 Verifica Deploy

```bash
# Controlla stato servizi
systemctl status cip-immobiliare
systemctl status nginx

# Test applicazione
curl http://localhost/health

# Controlla log
journalctl -u cip-immobiliare -f
```

## 🌐 FASE 4: Configurazione DNS

### 4.1 Configura Record DNS

Nel pannello del tuo provider DNS, aggiungi:

```
Tipo: A
Nome: @
Valore: YOUR_SERVER_IP
TTL: 300

Tipo: A  
Nome: www
Valore: YOUR_SERVER_IP
TTL: 300
```

### 4.2 Verifica DNS

```bash
# Verifica risoluzione DNS
nslookup cipimmobiliare.it
dig cipimmobiliare.it
```

## 🔒 FASE 5: Configurazione SSL

### 5.1 SSL Automatico (se non configurato durante il deploy)

```bash
sudo bash /var/www/cip_immobiliare/deploy/setup_ssl.sh
```

### 5.2 Verifica SSL

```bash
# Test certificato
openssl s_client -connect cipimmobiliare.it:443 -servername cipimmobiliare.it

# Verifica rinnovo automatico
sudo certbot certificates
```

## 🔐 FASE 6: Configurazione Sicurezza

### 6.1 Cambia Password Admin

```bash
# Accedi al database
sudo -u postgres psql cip_immobiliare_prod

# Cambia password admin
UPDATE users SET password_hash = 'nuova_password_hash' WHERE email = 'admin@cipimmobiliare.it';
```

### 6.2 Configura Firewall

```bash
# Verifica stato firewall
sudo ufw status

# Aggiungi regole se necessario
sudo ufw allow from YOUR_IP to any port 22
```

## 📊 FASE 7: Monitoraggio e Manutenzione

### 7.1 Log Monitoring

```bash
# Log applicazione
journalctl -u cip-immobiliare -f

# Log Nginx
tail -f /var/log/nginx/cip_immobiliare_error.log

# Log sistema
tail -f /var/log/syslog
```

### 7.2 Backup Database

```bash
# Backup manuale
sudo -u postgres pg_dump cip_immobiliare_prod > backup_$(date +%Y%m%d).sql

# Backup automatico (aggiungi a crontab)
0 2 * * * sudo -u postgres pg_dump cip_immobiliare_prod > /var/backups/cip_$(date +\%Y\%m\%d).sql
```

### 7.3 Aggiornamenti

```bash
# Aggiorna sistema
sudo apt update && sudo apt upgrade -y

# Riavvia servizi se necessario
sudo systemctl restart cip-immobiliare
sudo systemctl restart nginx
```

## 🛠️ Comandi Utili

### Gestione Applicazione

```bash
# Stato servizio
sudo systemctl status cip-immobiliare

# Riavvia applicazione
sudo systemctl restart cip-immobiliare

# Stop applicazione
sudo systemctl stop cip-immobiliare

# Start applicazione
sudo systemctl start cip-immobiliare

# Log in tempo reale
sudo journalctl -u cip-immobiliare -f
```

### Gestione Nginx

```bash
# Test configurazione
sudo nginx -t

# Riavvia Nginx
sudo systemctl restart nginx

# Reload configurazione
sudo systemctl reload nginx

# Log Nginx
sudo tail -f /var/log/nginx/cip_immobiliare_error.log
```

### Gestione Database

```bash
# Accesso database
sudo -u postgres psql cip_immobiliare_prod

# Backup database
sudo -u postgres pg_dump cip_immobiliare_prod > backup.sql

# Restore database
sudo -u postgres psql cip_immobiliare_prod < backup.sql
```

## 🔧 Risoluzione Problemi

### Problema: Applicazione non si avvia

```bash
# Controlla log
sudo journalctl -u cip-immobiliare -n 50

# Verifica configurazione
sudo systemctl status cip-immobiliare

# Test manuale
cd /var/www/cip_immobiliare
sudo -u cipapp .venv/bin/python main.py
```

### Problema: Nginx non funziona

```bash
# Test configurazione
sudo nginx -t

# Controlla log
sudo tail -f /var/log/nginx/error.log

# Verifica porte
sudo netstat -tlnp | grep :80
sudo netstat -tlnp | grep :443
```

### Problema: Database non connesso

```bash
# Controlla stato PostgreSQL
sudo systemctl status postgresql

# Test connessione
sudo -u postgres psql -c "SELECT version();"

# Verifica configurazione
sudo -u postgres psql -c "\l"
```

## 📈 Ottimizzazioni Performance

### 1. Ottimizzazione Nginx

```bash
# Modifica /etc/nginx/nginx.conf
worker_processes auto;
worker_connections 1024;
keepalive_timeout 65;
gzip on;
gzip_types text/plain text/css application/json application/javascript text/xml application/xml;
```

### 2. Ottimizzazione PostgreSQL

```bash
# Modifica /etc/postgresql/15/main/postgresql.conf
shared_buffers = 512MB
effective_cache_size = 1GB
work_mem = 4MB
maintenance_work_mem = 64MB
```

### 3. Ottimizzazione Gunicorn

```bash
# Modifica /etc/systemd/system/cip-immobiliare.service
--workers 4
--worker-class sync
--worker-connections 1000
--max-requests 1000
```

## 🎉 Deploy Completato!

Il tuo sito CIP Immobiliare è ora online su:
- **HTTP**: http://cipimmobiliare.it
- **HTTPS**: https://cipimmobiliare.it

### Credenziali Admin
- **Email**: admin@cipimmobiliare.it
- **Password**: your-secure-admin-password

⚠️ **IMPORTANTE**: Cambia la password admin prima di andare in produzione!

### Prossimi Passi
1. ✅ Testa tutte le funzionalità
2. ✅ Configura backup automatici
3. ✅ Imposta monitoraggio
4. ✅ Cambia password admin
5. ✅ Configura notifiche di errore

## 📞 Supporto

Per problemi o domande:
1. Controlla i log dell'applicazione
2. Verifica la configurazione dei servizi
3. Consulta la documentazione del progetto
4. Contatta il team di sviluppo

---

**Buon deploy! 🚀**
