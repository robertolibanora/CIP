#!/bin/bash

# Script per aggiornare il server via SSH
# Modifica le credenziali SSH e l'indirizzo del server

set -e

echo "🚀 Deploy via SSH - Aggiornamento Branding"
echo "=========================================="

# CONFIGURAZIONE SSH - MODIFICA QUESTI VALORI
SERVER_IP="YOUR_SERVER_IP"  # Sostituisci con l'IP del tuo server
SSH_USER="root"              # Sostituisci con il tuo utente SSH
SSH_KEY=""                   # Sostituisci con il percorso alla tua chiave SSH (opzionale)

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

# Verifica configurazione
if [ "$SERVER_IP" = "YOUR_SERVER_IP" ]; then
    echo -e "${RED}❌ Configurazione SSH non impostata!${NC}"
    echo ""
    echo "Modifica questo script e imposta:"
    echo "1. SERVER_IP - L'indirizzo IP del tuo server"
    echo "2. SSH_USER - Il tuo utente SSH (es: root, ubuntu, etc.)"
    echo "3. SSH_KEY - Il percorso alla tua chiave SSH (opzionale)"
    echo ""
    echo "Esempio:"
    echo "SERVER_IP=\"192.168.1.100\""
    echo "SSH_USER=\"root\""
    echo "SSH_KEY=\"/path/to/your/key.pem\""
    exit 1
fi

# Costruisci comando SSH
SSH_CMD="ssh"
if [ -n "$SSH_KEY" ]; then
    SSH_CMD="$SSH_CMD -i $SSH_KEY"
fi
SSH_CMD="$SSH_CMD $SSH_USER@$SERVER_IP"

echo "📋 Configurazione SSH:"
echo "   Server: $SERVER_IP"
echo "   Utente: $SSH_USER"
echo "   Chiave: ${SSH_KEY:-'Password'}"
echo ""

# 1. Test connessione SSH
echo "📋 Test connessione SSH..."
if $SSH_CMD "echo 'Connessione SSH OK'" > /dev/null 2>&1; then
    print_result 0 "Connessione SSH stabilita"
else
    print_result 1 "Impossibile connettersi al server"
    echo ""
    echo "Controlla:"
    echo "1. L'IP del server è corretto"
    echo "2. Il server è raggiungibile"
    echo "3. Le credenziali SSH sono corrette"
    echo "4. La porta SSH (22) è aperta"
    exit 1
fi

# 2. Crea directory temporanea sul server
echo "📋 Preparazione server..."
$SSH_CMD "mkdir -p /tmp/cip_update"
print_result $? "Directory temporanea creata"

# 3. Copia file modificati sul server
echo "📋 Copia file modificati..."

# Copia i template modificati
scp -r frontend/templates/auth/ $SSH_USER@$SERVER_IP:/tmp/cip_update/ 2>/dev/null || {
    print_result 1 "Errore nella copia dei file"
    exit 1
}
print_result $? "File copiati sul server"

# 4. Esegui aggiornamento sul server
echo "📋 Esecuzione aggiornamento sul server..."

# Crea script di aggiornamento sul server
$SSH_CMD "cat > /tmp/cip_update/update_branding.sh << 'EOF'
#!/bin/bash
set -e

echo '🏢 Aggiornamento Branding: CIP Academy → CIP Real Estate'
echo '======================================================='

# Backup
BACKUP_DIR=\"/var/backups/cip_immobiliare_\$(date +%Y%m%d_%H%M%S)\"
mkdir -p \"\$BACKUP_DIR\"
cp -r /var/www/cip_immobiliare/frontend/templates/auth \"\$BACKUP_DIR/\" 2>/dev/null || true
echo \"✅ Backup creato in \$BACKUP_DIR\"

# Vai nella directory dell'applicazione
cd /var/www/cip_immobiliare

# Applica modifiche
echo '📋 Applicazione modifiche...'

# Aggiorna register.html
sed -i 's/alt=\"CIP Academy\"/alt=\"CIP Real Estate\"/g' frontend/templates/auth/register.html
sed -i 's/Unisciti a CIP Network/Unisciti a CIP Real Estate/g' frontend/templates/auth/register.html

# Aggiorna login.html
sed -i 's/alt=\"CIP Academy\"/alt=\"CIP Real Estate\"/g' frontend/templates/auth/login.html

# Aggiorna privacy.html
sed -i 's/Privacy Policy - CIP Academy/Privacy Policy - CIP Real Estate/g' frontend/templates/auth/privacy.html
sed -i 's/alt=\"CIP Academy\"/alt=\"CIP Real Estate\"/g' frontend/templates/auth/privacy.html

# Aggiorna terms.html
sed -i 's/Termini e Condizioni - CIP Academy/Termini e Condizioni - CIP Real Estate/g' frontend/templates/auth/terms.html
sed -i 's/alt=\"CIP Academy\"/alt=\"CIP Real Estate\"/g' frontend/templates/auth/terms.html

# Aggiorna base_auth.html
sed -i 's/{% block title %}CIP Academy{% endblock %}/{% block title %}CIP Real Estate{% endblock %}/g' frontend/templates/auth/base_auth.html

echo '✅ Template aggiornati'

# Aggiorna permessi
chown -R cipapp:cipapp frontend/templates/
chmod -R 644 frontend/templates/auth/*.html

echo '✅ Permessi aggiornati'

# Riavvia applicazione
systemctl restart CIP

echo '✅ Applicazione riavviata'

# Test
sleep 3
if curl -f http://localhost:8090/auth/login > /dev/null 2>&1; then
    echo '✅ Test login superato'
else
    echo '❌ Test login fallito'
fi

if curl -f http://localhost:8090/auth/register > /dev/null 2>&1; then
    echo '✅ Test registrazione superato'
else
    echo '❌ Test registrazione fallito'
fi

echo ''
echo '🎉 AGGIORNAMENTO COMPLETATO!'
echo '============================'
echo 'Il sito ora mostra \"CIP Real Estate\" invece di \"CIP Academy\"'
echo 'Testa su: https://ciprealestate.eu'
echo ''

# Pulisci file temporanei
rm -rf /tmp/cip_update

EOF"

# Esegui lo script sul server
$SSH_CMD "chmod +x /tmp/cip_update/update_branding.sh && /tmp/cip_update/update_branding.sh"

print_result $? "Aggiornamento completato sul server"

# 5. Test finale
echo "📋 Test finale..."
sleep 5

if curl -f https://ciprealestate.eu/auth/login > /dev/null 2>&1; then
    print_result 0 "✅ Sito accessibile pubblicamente"
else
    print_warning "⚠️ Il sito potrebbe non essere ancora accessibile pubblicamente"
fi

# 6. Riepilogo
echo ""
echo "🎉 DEPLOY COMPLETATO!"
echo "===================="
echo ""
echo "✅ Modifiche applicate:"
echo "   - Branding aggiornato da 'CIP Academy' a 'CIP Real Estate'"
echo "   - Tutti i template modificati"
echo "   - Applicazione riavviata"
echo ""
echo "🌐 Testa il sito:"
echo "   - Login: https://ciprealestate.eu/auth/login"
echo "   - Registrazione: https://ciprealestate.eu/auth/register"
echo ""
echo "📋 Comandi utili per il server:"
echo "   - Log: ssh $SSH_USER@$SERVER_IP 'journalctl -u CIP -f'"
echo "   - Stato: ssh $SSH_USER@$SERVER_IP 'systemctl status CIP'"
echo "   - Riavvia: ssh $SSH_USER@$SERVER_IP 'systemctl restart CIP'"
echo ""

print_info "Deploy completato con successo!"
