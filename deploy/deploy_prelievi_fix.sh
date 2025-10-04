#!/bin/bash

# Script di deploy per fix sezione prelievi
# Esegui questo script per aggiornare il server con le modifiche

set -e

echo "🚀 Deploy Fix Sezione Prelievi"
echo "==============================="
echo ""

# CONFIGURAZIONE SSH - MODIFICA SE NECESSARIO
SERVER_USER="${SERVER_USER:-root}"
SERVER_HOST="${SERVER_HOST:-ciprealestate.eu}"
APP_DIR="/var/www/CIP"
SERVICE_NAME="cip-immobiliare"

# Colori
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m'

print_step() {
    echo -e "${GREEN}✅ $1${NC}"
}

print_error() {
    echo -e "${RED}❌ $1${NC}"
}

print_info() {
    echo -e "${YELLOW}ℹ️  $1${NC}"
}

# 1. Test connessione SSH
print_info "Test connessione SSH a $SERVER_USER@$SERVER_HOST..."
if ssh -o ConnectTimeout=10 $SERVER_USER@$SERVER_HOST "echo 'OK'" > /dev/null 2>&1; then
    print_step "Connessione SSH stabilita"
else
    print_error "Impossibile connettersi al server"
    echo ""
    echo "Verifica:"
    echo "  1. Server raggiungibile"
    echo "  2. Credenziali SSH corrette"
    echo "  3. Chiave SSH configurata"
    echo ""
    echo "Per configurare l'accesso SSH:"
    echo "  export SERVER_USER=tuo_utente"
    echo "  export SERVER_HOST=tuo_server.com"
    exit 1
fi

# 2. Backup dei file attuali
print_info "Creazione backup..."
ssh $SERVER_USER@$SERVER_HOST "cd $APP_DIR && mkdir -p backups && cp frontend/templates/user/portfolio.html backups/portfolio_backup_\$(date +%Y%m%d_%H%M%S).html 2>/dev/null || true"
print_step "Backup creato"

# 3. Git pull delle modifiche
print_info "Aggiornamento codice dal repository..."
ssh $SERVER_USER@$SERVER_HOST "cd $APP_DIR && sudo -u cipapp git pull origin main" || {
    print_error "Errore durante git pull"
    echo ""
    echo "Prova manualmente:"
    echo "  ssh $SERVER_USER@$SERVER_HOST"
    echo "  cd $APP_DIR"
    echo "  sudo -u cipapp git pull origin main"
    exit 1
}
print_step "Codice aggiornato"

# 4. Riavvio servizio
print_info "Riavvio applicazione..."
ssh $SERVER_USER@$SERVER_HOST "systemctl restart $SERVICE_NAME" || {
    print_error "Errore durante il riavvio"
    echo ""
    echo "Prova manualmente:"
    echo "  ssh $SERVER_USER@$SERVER_HOST"
    echo "  systemctl restart $SERVICE_NAME"
    exit 1
}
print_step "Applicazione riavviata"

# 5. Verifica stato servizio
print_info "Verifica stato servizio..."
sleep 3
if ssh $SERVER_USER@$SERVER_HOST "systemctl is-active --quiet $SERVICE_NAME"; then
    print_step "Servizio attivo e funzionante"
else
    print_error "Il servizio non è attivo"
    echo ""
    echo "Controlla i log:"
    echo "  ssh $SERVER_USER@$SERVER_HOST 'journalctl -u $SERVICE_NAME -n 50'"
    exit 1
fi

# 6. Test applicazione
print_info "Test applicazione..."
sleep 2
if curl -f -s https://ciprealestate.eu/user/portfolio > /dev/null 2>&1; then
    print_step "Applicazione accessibile"
else
    print_error "L'applicazione potrebbe non essere accessibile"
    echo ""
    echo "Verifica manualmente: https://ciprealestate.eu/user/portfolio"
fi

echo ""
echo "🎉 DEPLOY COMPLETATO!"
echo "===================="
echo ""
echo "✅ Modifiche applicate:"
echo "   - Sezione prelievi completamente ricostruita"
echo "   - Form prelievo con nuove funzioni JavaScript"
echo "   - Pulsante 'Conferma Prelievo' ora funzionante"
echo ""
echo "🌐 Testa il sito:"
echo "   https://ciprealestate.eu/user/portfolio"
echo ""
echo "📋 Comandi utili:"
echo "   - Log: ssh $SERVER_USER@$SERVER_HOST 'journalctl -u $SERVICE_NAME -f'"
echo "   - Stato: ssh $SERVER_USER@$SERVER_HOST 'systemctl status $SERVICE_NAME'"
echo "   - Riavvia: ssh $SERVER_USER@$SERVER_HOST 'systemctl restart $SERVICE_NAME'"
echo ""

print_step "Deploy completato con successo!"

