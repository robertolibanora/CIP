#!/bin/bash

# Script per risolvere l'errore 503 Service Temporarily Unavailable
# CIP Immobiliare - ciprealestate.eu

set -e

echo "🔧 Risoluzione errore 503 - CIP Immobiliare"
echo "=========================================="

# Colori per output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Funzione per stampare risultati
print_result() {
    if [ $1 -eq 0 ]; then
        echo -e "${GREEN}✅ $2${NC}"
    else
        echo -e "${RED}❌ $2${NC}"
    fi
}

print_info() {
    echo -e "${BLUE}ℹ️ $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠️ $1${NC}"
}

# Verifica se siamo root
if [ "$EUID" -ne 0 ]; then
    echo -e "${RED}❌ Questo script deve essere eseguito come root${NC}"
    echo "Usa: sudo $0"
    exit 1
fi

# 1. Verifica e installa dipendenze
echo "📋 Verifica dipendenze..."

# PostgreSQL
if ! command -v psql &> /dev/null; then
    print_info "Installazione PostgreSQL..."
    apt update
    apt install -y postgresql postgresql-contrib
    systemctl enable postgresql
    systemctl start postgresql
fi
print_result $? "PostgreSQL installato e attivo"

# Nginx
if ! command -v nginx &> /dev/null; then
    print_info "Installazione Nginx..."
    apt install -y nginx
    systemctl enable nginx
    systemctl start nginx
fi
print_result $? "Nginx installato e attivo"

# Python e pip
if ! command -v python3 &> /dev/null; then
    print_info "Installazione Python..."
    apt install -y python3 python3-pip python3-venv
fi
print_result $? "Python installato"

# Gunicorn
if ! command -v gunicorn &> /dev/null; then
    print_info "Installazione Gunicorn..."
    apt install -y gunicorn
fi
print_result $? "Gunicorn installato"

# 2. Configurazione database
echo "📋 Configurazione database..."

# Crea utente database se non esiste
sudo -u postgres psql -c "CREATE USER cipapp WITH PASSWORD 'cipapp_password';" 2>/dev/null || true
sudo -u postgres psql -c "ALTER USER cipapp CREATEDB;" 2>/dev/null || true

# Crea database se non esiste
sudo -u postgres psql -c "CREATE DATABASE cip_immobiliare_prod OWNER cipapp;" 2>/dev/null || true

print_result $? "Database configurato"

# 3. Configurazione directory applicazione
echo "📋 Configurazione directory applicazione..."

# Crea directory se non esistono
mkdir -p /var/www/cip_immobiliare
mkdir -p /var/log/cip_immobiliare
mkdir -p /var/www/cip_immobiliare/instance/uploads/kyc
mkdir -p /var/www/cip_immobiliare/uploads/projects

# Crea utente applicazione se non esiste
if ! id "cipapp" &>/dev/null; then
    useradd -r -s /bin/false -d /var/www/cip_immobiliare cipapp
fi

# Copia file applicazione
if [ -d "/Users/macos/Desktop/CIP SRL/CIPRealEstate/CIP" ]; then
    print_info "Copia file applicazione dal sistema locale..."
    cp -r /Users/macos/Desktop/CIP\ SRL/CIPRealEstate/CIP/* /var/www/cip_immobiliare/
else
    print_warning "Directory sorgente non trovata. Assicurati che i file siano già in /var/www/cip_immobiliare"
fi

# Imposta permessi
chown -R cipapp:cipapp /var/www/cip_immobiliare
chown -R cipapp:cipapp /var/log/cip_immobiliare
chmod -R 755 /var/www/cip_immobiliare
chmod -R 777 /var/www/cip_immobiliare/instance/uploads
chmod -R 777 /var/www/cip_immobiliare/uploads

print_result $? "Directory applicazione configurata"

# 4. Configurazione ambiente virtuale Python
echo "📋 Configurazione ambiente Python..."

cd /var/www/cip_immobiliare

# Crea ambiente virtuale se non esiste
if [ ! -d ".venv" ]; then
    python3 -m venv .venv
fi

# Attiva ambiente virtuale e installa dipendenze
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt

print_result $? "Ambiente Python configurato"

# 5. Configurazione Nginx
echo "📋 Configurazione Nginx..."

# Copia configurazione nginx
cp /var/www/cip_immobiliare/config/nginx/cip_immobiliare.conf /etc/nginx/sites-available/
ln -sf /etc/nginx/sites-available/cip_immobiliare.conf /etc/nginx/sites-enabled/

# Rimuovi configurazione default se esiste
rm -f /etc/nginx/sites-enabled/default

# Test configurazione nginx
nginx -t
print_result $? "Configurazione Nginx valida"

# Riavvia nginx
systemctl restart nginx
print_result $? "Nginx riavviato"

# 6. Configurazione SSL (Let's Encrypt)
echo "📋 Configurazione SSL..."

# Installa certbot se non presente
if ! command -v certbot &> /dev/null; then
    apt install -y certbot python3-certbot-nginx
fi

# Genera certificato SSL se non esiste
if [ ! -f "/etc/letsencrypt/live/ciprealestate.eu/fullchain.pem" ]; then
    print_info "Generazione certificato SSL per ciprealestate.eu..."
    certbot --nginx -d ciprealestate.eu -d www.ciprealestate.eu --non-interactive --agree-tos --email admin@ciprealestate.eu
else
    print_info "Certificato SSL già esistente"
fi

print_result $? "SSL configurato"

# 7. Configurazione servizio systemd
echo "📋 Configurazione servizio systemd..."

# Copia file servizio
cp /var/www/cip_immobiliare/deploy/cip-immobiliare.service /etc/systemd/system/CIP.service

# Ricarica systemd
systemctl daemon-reload

# Abilita servizio
systemctl enable CIP

print_result $? "Servizio systemd configurato"

# 8. Inizializzazione database
echo "📋 Inizializzazione database..."

# Esegui script di inizializzazione database se esistono
if [ -f "/var/www/cip_immobiliare/config/database/schema_complete.sql" ]; then
    sudo -u postgres psql cip_immobiliare_prod < /var/www/cip_immobiliare/config/database/schema_complete.sql
fi

print_result $? "Database inizializzato"

# 9. Avvio servizi
echo "📋 Avvio servizi..."

# Riavvia PostgreSQL
systemctl restart postgresql
print_result $? "PostgreSQL riavviato"

# Avvia applicazione
systemctl start CIP
print_result $? "Applicazione avviata"

# Riavvia Nginx
systemctl restart nginx
print_result $? "Nginx riavviato"

# 10. Verifica finale
echo "📋 Verifica finale..."

# Attendi che l'applicazione si avvii
sleep 5

# Test connessione locale
curl -f http://localhost:8090/health > /dev/null 2>&1
print_result $? "Applicazione risponde su porta 8090"

# Test connessione tramite nginx
curl -f http://localhost/health > /dev/null 2>&1
print_result $? "Nginx proxy funzionante"

# Test HTTPS se configurato
if [ -f "/etc/letsencrypt/live/ciprealestate.eu/fullchain.pem" ]; then
    curl -f https://localhost/health > /dev/null 2>&1
    print_result $? "HTTPS funzionante"
fi

# 11. Riepilogo
echo ""
echo "🎉 CONFIGURAZIONE COMPLETATA!"
echo "============================="
echo ""
echo "🌐 Il tuo sito è ora disponibile su:"
echo "   - HTTP: http://ciprealestate.eu"
echo "   - HTTPS: https://ciprealestate.eu"
echo ""
echo "🔐 Credenziali admin:"
echo "   - Email: cipnetworksrl@gmail.com"
echo "   - Password: TRPMRK06S03A059N"
echo ""
echo "📋 Comandi utili:"
echo "   - Stato servizi: systemctl status CIP nginx postgresql"
echo "   - Log applicazione: journalctl -u CIP -f"
echo "   - Log Nginx: tail -f /var/log/nginx/cip_immobiliare_error.log"
echo "   - Riavvia app: systemctl restart CIP"
echo "   - Test configurazione: nginx -t"
echo ""
echo "⚠️ IMPORTANTE:"
echo "1. Cambia la password admin dopo il primo accesso"
echo "2. Configura backup automatici del database"
echo "3. Monitora i log regolarmente"
echo "4. Testa tutte le funzionalità dell'applicazione"
echo ""

# Test finale con curl esterno
print_info "Test connessione esterna..."
if curl -f https://ciprealestate.eu/health > /dev/null 2>&1; then
    print_result 0 "✅ Sito accessibile pubblicamente!"
else
    print_warning "⚠️ Il sito potrebbe non essere ancora accessibile pubblicamente. Controlla:"
    echo "   - Configurazione DNS del dominio"
    echo "   - Firewall del server"
    echo "   - Configurazione del provider di hosting"
fi

echo ""
echo "🔧 Se il problema persiste, controlla i log:"
echo "   journalctl -u CIP -f"
echo "   tail -f /var/log/nginx/cip_immobiliare_error.log"
