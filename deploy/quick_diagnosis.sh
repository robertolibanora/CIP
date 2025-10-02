#!/bin/bash

# Script di diagnosi rapida per errore 503
# CIP Immobiliare - ciprealestate.eu

echo "🔍 Diagnosi rapida errore 503"
echo "============================="

# Colori per output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

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

# 1. Verifica servizi
echo "📋 Stato servizi:"
systemctl is-active --quiet postgresql && print_result 0 "PostgreSQL attivo" || print_result 1 "PostgreSQL NON attivo"
systemctl is-active --quiet nginx && print_result 0 "Nginx attivo" || print_result 1 "Nginx NON attivo"
systemctl is-active --quiet CIP && print_result 0 "CIP Immobiliare attivo" || print_result 1 "CIP Immobiliare NON attivo"

# 2. Verifica porte
echo ""
echo "📋 Porte in ascolto:"
netstat -tlnp | grep -q ":80 " && print_result 0 "Porta 80 (HTTP)" || print_result 1 "Porta 80 NON in ascolto"
netstat -tlnp | grep -q ":443 " && print_result 0 "Porta 443 (HTTPS)" || print_result 1 "Porta 443 NON in ascolto"
netstat -tlnp | grep -q ":8090 " && print_result 0 "Porta 8090 (App)" || print_result 1 "Porta 8090 NON in ascolto"
netstat -tlnp | grep -q ":5432 " && print_result 0 "Porta 5432 (DB)" || print_result 1 "Porta 5432 NON in ascolto"

# 3. Test connessioni
echo ""
echo "📋 Test connessioni:"
curl -f http://localhost:8090/health > /dev/null 2>&1 && print_result 0 "App risponde su 8090" || print_result 1 "App NON risponde su 8090"
curl -f http://localhost/health > /dev/null 2>&1 && print_result 0 "Nginx proxy funziona" || print_result 1 "Nginx proxy NON funziona"

# 4. Verifica configurazione nginx
echo ""
echo "📋 Configurazione Nginx:"
nginx -t > /dev/null 2>&1 && print_result 0 "Configurazione Nginx valida" || print_result 1 "Configurazione Nginx NON valida"

# 5. Verifica log errori
echo ""
echo "📋 Ultimi errori nei log:"
echo "--- Log CIP Immobiliare (ultime 5 righe) ---"
journalctl -u CIP --no-pager -n 5 2>/dev/null || echo "Nessun log disponibile"

echo ""
echo "--- Log Nginx (ultime 5 righe) ---"
tail -n 5 /var/log/nginx/cip_immobiliare_error.log 2>/dev/null || echo "Nessun log disponibile"

# 6. Verifica file di configurazione
echo ""
echo "📋 File di configurazione:"
[ -f "/etc/nginx/sites-enabled/cip_immobiliare.conf" ] && print_result 0 "Config Nginx presente" || print_result 1 "Config Nginx mancante"
[ -f "/etc/systemd/system/CIP.service" ] && print_result 0 "Servizio systemd presente" || print_result 1 "Servizio systemd mancante"
[ -f "/var/www/cip_immobiliare/main.py" ] && print_result 0 "File main.py presente" || print_result 1 "File main.py mancante"

# 7. Verifica permessi
echo ""
echo "📋 Permessi directory:"
[ -r "/var/www/cip_immobiliare" ] && print_result 0 "Directory app leggibile" || print_result 1 "Directory app NON leggibile"
[ -w "/var/www/cip_immobiliare" ] && print_result 0 "Directory app scrivibile" || print_result 1 "Directory app NON scrivibile"

# 8. Suggerimenti
echo ""
echo "🔧 SUGGERIMENTI:"
echo "==============="

# Conta errori
ERRORS=0
systemctl is-active --quiet CIP || ((ERRORS++))
systemctl is-active --quiet nginx || ((ERRORS++))
systemctl is-active --quiet postgresql || ((ERRORS++))
curl -f http://localhost:8090/health > /dev/null 2>&1 || ((ERRORS++))

if [ $ERRORS -eq 0 ]; then
    echo -e "${GREEN}✅ Tutti i servizi funzionano correttamente!${NC}"
    echo "Il problema potrebbe essere:"
    echo "1. Configurazione DNS del dominio"
    echo "2. Firewall del server"
    echo "3. Problemi di rete temporanei"
else
    echo -e "${RED}❌ Trovati $ERRORS problemi${NC}"
    echo ""
    echo "Per risolvere:"
    echo "1. Esegui: sudo systemctl restart CIP nginx postgresql"
    echo "2. Controlla i log: journalctl -u CIP -f"
    echo "3. Esegui lo script di fix: sudo ./fix_503_error.sh"
fi

echo ""
echo "📋 Comandi utili:"
echo "   - Riavvia tutto: sudo systemctl restart CIP nginx postgresql"
echo "   - Log in tempo reale: journalctl -u CIP -f"
echo "   - Test configurazione: nginx -t"
echo "   - Stato servizi: systemctl status CIP nginx postgresql"
