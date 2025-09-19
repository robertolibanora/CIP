#!/bin/bash

# Script di verifica post-deploy per CIP Immobiliare
# Esegui questo script per verificare che tutto funzioni correttamente

set -e

echo "🔍 Verifica Deploy CIP Immobiliare"
echo "=================================="

# Colori per output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Funzione per stampare risultati
print_result() {
    if [ $1 -eq 0 ]; then
        echo -e "${GREEN}✅ $2${NC}"
    else
        echo -e "${RED}❌ $2${NC}"
    fi
}

print_warning() {
    echo -e "${YELLOW}⚠️ $1${NC}"
}

# 1. Verifica servizi di sistema
echo "📋 Verifica servizi di sistema..."

# PostgreSQL
systemctl is-active --quiet postgresql
print_result $? "PostgreSQL attivo"

# Nginx
systemctl is-active --quiet nginx
print_result $? "Nginx attivo"

# CIP Immobiliare
systemctl is-active --quiet CIP
print_result $? "CIP Immobiliare attivo"

# 2. Verifica porte
echo "📋 Verifica porte..."

# Porta 80 (HTTP)
netstat -tlnp | grep -q ":80 "
print_result $? "Porta 80 (HTTP) in ascolto"

# Porta 443 (HTTPS)
netstat -tlnp | grep -q ":443 "
print_result $? "Porta 443 (HTTPS) in ascolto"

# Porta 8090 (Applicazione)
netstat -tlnp | grep -q ":8090 "
print_result $? "Porta 8090 (Applicazione) in ascolto"

# Porta 5432 (PostgreSQL)
netstat -tlnp | grep -q ":5432 "
print_result $? "Porta 5432 (PostgreSQL) in ascolto"

# 3. Verifica connessione database
echo "📋 Verifica database..."

# Test connessione PostgreSQL
sudo -u postgres psql -c "SELECT 1;" > /dev/null 2>&1
print_result $? "Connessione PostgreSQL"

# Test database applicazione
sudo -u postgres psql cip_immobiliare_prod -c "SELECT COUNT(*) FROM users;" > /dev/null 2>&1
print_result $? "Database applicazione accessibile"

# 4. Verifica applicazione web
echo "📋 Verifica applicazione web..."

# Test endpoint health
curl -f http://localhost/health > /dev/null 2>&1
print_result $? "Endpoint /health risponde"

# Test endpoint principale
curl -f http://localhost/ > /dev/null 2>&1
print_result $? "Endpoint principale risponde"

# Test endpoint login
curl -f http://localhost/auth/login > /dev/null 2>&1
print_result $? "Endpoint login risponde"

# 5. Verifica SSL (se configurato)
echo "📋 Verifica SSL..."

if [ -f "/etc/letsencrypt/live/cipimmobiliare.it/fullchain.pem" ]; then
    # Test HTTPS
    curl -f https://localhost/health > /dev/null 2>&1
    print_result $? "HTTPS funzionante"
    
    # Verifica certificato
    openssl s_client -connect localhost:443 -servername localhost < /dev/null 2>/dev/null | grep -q "Verify return code: 0"
    print_result $? "Certificato SSL valido"
else
    print_warning "SSL non configurato"
fi

# 6. Verifica file e permessi
echo "📋 Verifica file e permessi..."

# Directory applicazione
[ -d "/var/www/cip_immobiliare" ]
print_result $? "Directory applicazione esiste"

# Ambiente virtuale
[ -d "/var/www/cip_immobiliare/.venv" ]
print_result $? "Ambiente virtuale esiste"

# File main.py
[ -f "/var/www/cip_immobiliare/main.py" ]
print_result $? "File main.py esiste"

# Directory uploads
[ -d "/var/www/cip_immobiliare/instance/uploads/kyc" ]
print_result $? "Directory uploads KYC esiste"

# Permessi directory
[ -w "/var/www/cip_immobiliare/instance/uploads/kyc" ]
print_result $? "Directory uploads scrivibile"

# 7. Verifica log
echo "📋 Verifica log..."

# Log applicazione
[ -f "/var/log/cip_immobiliare/app.log" ]
print_result $? "Log applicazione esiste"

# Log Nginx
[ -f "/var/log/nginx/cip_immobiliare_error.log" ]
print_result $? "Log Nginx esiste"

# 8. Verifica sicurezza
echo "📋 Verifica sicurezza..."

# Firewall attivo
ufw status | grep -q "Status: active"
print_result $? "Firewall attivo"

# Fail2ban attivo
systemctl is-active --quiet fail2ban
print_result $? "Fail2ban attivo"

# SSH configurato correttamente
grep -q "PermitRootLogin no" /etc/ssh/sshd_config
print_result $? "SSH root login disabilitato"

# 9. Verifica performance
echo "📋 Verifica performance..."

# Memoria disponibile
MEMORY_AVAILABLE=$(free -m | awk 'NR==2{printf "%.0f", $7}')
if [ $MEMORY_AVAILABLE -gt 500 ]; then
    print_result 0 "Memoria sufficiente (${MEMORY_AVAILABLE}MB disponibili)"
else
    print_warning "Memoria limitata (${MEMORY_AVAILABLE}MB disponibili)"
fi

# Spazio disco
DISK_AVAILABLE=$(df / | awk 'NR==2{printf "%.0f", $4}')
if [ $DISK_AVAILABLE -gt 1000 ]; then
    print_result 0 "Spazio disco sufficiente (${DISK_AVAILABLE}MB disponibili)"
else
    print_warning "Spazio disco limitato (${DISK_AVAILABLE}MB disponibili)"
fi

# 10. Test funzionalità specifiche
echo "📋 Test funzionalità specifiche..."

# Test caricamento CSS
curl -f http://localhost/assets/css/style.css > /dev/null 2>&1
print_result $? "File CSS caricabili"

# Test caricamento JS
curl -f http://localhost/assets/js/app.js > /dev/null 2>&1
print_result $? "File JavaScript caricabili"

# Test endpoint API
curl -f http://localhost/portfolio/ > /dev/null 2>&1
print_result $? "Endpoint API portfolio risponde"

# 11. Riepilogo finale
echo ""
echo "📊 RIEPILOGO VERIFICA"
echo "===================="

# Conta errori
ERRORS=0

# Verifica servizi critici
if ! systemctl is-active --quiet CIP; then
    ((ERRORS++))
fi

if ! systemctl is-active --quiet nginx; then
    ((ERRORS++))
fi

if ! systemctl is-active --quiet postgresql; then
    ((ERRORS++))
fi

# Verifica connessione web
if ! curl -f http://localhost/health > /dev/null 2>&1; then
    ((ERRORS++))
fi

if [ $ERRORS -eq 0 ]; then
    echo -e "${GREEN}🎉 TUTTI I TEST SUPERATI!${NC}"
    echo -e "${GREEN}✅ L'applicazione è pronta per la produzione${NC}"
    echo ""
    echo "🌐 URL applicazione:"
    echo "   - HTTP: http://$(curl -s ifconfig.me)"
    echo "   - HTTPS: https://$(curl -s ifconfig.me)"
    echo ""
    echo "🔐 Credenziali admin:"
    echo "   - Email: admin@cipimmobiliare.it"
    echo "   - Password: your-secure-admin-password"
    echo ""
    echo "⚠️ RACCOMANDAZIONI:"
    echo "1. Cambia la password admin"
    echo "2. Configura backup automatici"
    echo "3. Monitora i log regolarmente"
    echo "4. Testa tutte le funzionalità"
else
    echo -e "${RED}❌ TROVATI $ERRORS ERRORI${NC}"
    echo -e "${RED}⚠️ Risolvi gli errori prima di andare in produzione${NC}"
    echo ""
    echo "🔧 Per risolvere i problemi:"
    echo "1. Controlla i log: journalctl -u CIP -f"
    echo "2. Verifica la configurazione: nginx -t"
    echo "3. Riavvia i servizi: systemctl restart CIP nginx"
    echo "4. Controlla i permessi dei file"
fi

echo ""
echo "📋 Comandi utili:"
echo "   - Stato servizi: systemctl status CIP nginx postgresql"
echo "   - Log applicazione: journalctl -u CIP -f"
echo "   - Log Nginx: tail -f /var/log/nginx/cip_immobiliare_error.log"
echo "   - Riavvia app: systemctl restart CIP"
echo "   - Test configurazione: nginx -t"
