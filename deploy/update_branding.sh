#!/bin/bash

# Script per aggiornare il branding da "CIP Academy" a "CIP Real Estate"
# Esegui questo script sul server per applicare le modifiche

set -e

echo "🏢 Aggiornamento Branding: CIP Academy → CIP Real Estate"
echo "======================================================="

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

# Verifica se siamo nella directory corretta
if [ ! -f "main.py" ]; then
    echo -e "${RED}❌ Questo script deve essere eseguito dalla directory root del progetto${NC}"
    echo "Usa: cd /var/www/cip_immobiliare && sudo $0"
    exit 1
fi

# 1. Backup dei file modificati
echo "📋 Creazione backup..."
BACKUP_DIR="/var/backups/cip_immobiliare_$(date +%Y%m%d_%H%M%S)"
mkdir -p "$BACKUP_DIR"

# Backup dei template modificati
cp -r frontend/templates/auth "$BACKUP_DIR/" 2>/dev/null || true
print_result $? "Backup creato in $BACKUP_DIR"

# 2. Applica le modifiche ai template
echo "📋 Applicazione modifiche ai template..."

# Aggiorna register.html
sed -i 's/alt="CIP Academy"/alt="CIP Real Estate"/g' frontend/templates/auth/register.html
sed -i 's/Unisciti a CIP Network/Unisciti a CIP Real Estate/g' frontend/templates/auth/register.html

# Aggiorna login.html
sed -i 's/alt="CIP Academy"/alt="CIP Real Estate"/g' frontend/templates/auth/login.html

# Aggiorna privacy.html
sed -i 's/Privacy Policy - CIP Academy/Privacy Policy - CIP Real Estate/g' frontend/templates/auth/privacy.html
sed -i 's/alt="CIP Academy"/alt="CIP Real Estate"/g' frontend/templates/auth/privacy.html

# Aggiorna terms.html
sed -i 's/Termini e Condizioni - CIP Academy/Termini e Condizioni - CIP Real Estate/g' frontend/templates/auth/terms.html
sed -i 's/alt="CIP Academy"/alt="CIP Real Estate"/g' frontend/templates/auth/terms.html

# Aggiorna base_auth.html
sed -i 's/{% block title %}CIP Academy{% endblock %}/{% block title %}CIP Real Estate{% endblock %}/g' frontend/templates/auth/base_auth.html

print_result $? "Template aggiornati"

# 3. Verifica che le modifiche siano state applicate
echo "📋 Verifica modifiche..."
grep -q "CIP Real Estate" frontend/templates/auth/register.html && print_result 0 "register.html aggiornato" || print_result 1 "register.html NON aggiornato"
grep -q "CIP Real Estate" frontend/templates/auth/login.html && print_result 0 "login.html aggiornato" || print_result 1 "login.html NON aggiornato"
grep -q "CIP Real Estate" frontend/templates/auth/privacy.html && print_result 0 "privacy.html aggiornato" || print_result 1 "privacy.html NON aggiornato"
grep -q "CIP Real Estate" frontend/templates/auth/terms.html && print_result 0 "terms.html aggiornato" || print_result 1 "terms.html NON aggiornato"
grep -q "CIP Real Estate" frontend/templates/auth/base_auth.html && print_result 0 "base_auth.html aggiornato" || print_result 1 "base_auth.html NON aggiornato"

# 4. Verifica che non ci siano più riferimenti a "CIP Academy"
echo "📋 Verifica rimozione 'CIP Academy'..."
if grep -r "CIP Academy" frontend/templates/ > /dev/null 2>&1; then
    print_result 1 "Trovati ancora riferimenti a 'CIP Academy'"
    echo "Riferimenti rimanenti:"
    grep -r "CIP Academy" frontend/templates/
else
    print_result 0 "Nessun riferimento a 'CIP Academy' trovato"
fi

# 5. Aggiorna i permessi
echo "📋 Aggiornamento permessi..."
chown -R cipapp:cipapp frontend/templates/
chmod -R 644 frontend/templates/auth/*.html
print_result $? "Permessi aggiornati"

# 6. Riavvia l'applicazione
echo "📋 Riavvio applicazione..."
systemctl restart CIP
print_result $? "Applicazione riavviata"

# 7. Test della modifica
echo "📋 Test delle modifiche..."
sleep 3

# Test endpoint di login
if curl -f http://localhost:8090/auth/login > /dev/null 2>&1; then
    print_result 0 "Endpoint login funzionante"
else
    print_result 1 "Endpoint login NON funzionante"
fi

# Test endpoint di registrazione
if curl -f http://localhost:8090/auth/register > /dev/null 2>&1; then
    print_result 0 "Endpoint registrazione funzionante"
else
    print_result 1 "Endpoint registrazione NON funzionante"
fi

# 8. Verifica finale
echo ""
echo "🎉 AGGIORNAMENTO BRANDING COMPLETATO!"
echo "====================================="
echo ""
echo "✅ Modifiche applicate:"
echo "   - Tutti i template ora mostrano 'CIP Real Estate'"
echo "   - Rimosso 'CIP Academy' da tutti i file"
echo "   - Aggiornato 'CIP Network' con 'CIP Real Estate'"
echo ""
echo "🌐 Testa il sito:"
echo "   - Login: https://ciprealestate.eu/auth/login"
echo "   - Registrazione: https://ciprealestate.eu/auth/register"
echo ""
echo "📋 Comandi utili:"
echo "   - Log applicazione: journalctl -u CIP -f"
echo "   - Stato servizio: systemctl status CIP"
echo "   - Riavvia app: systemctl restart CIP"
echo ""

# 9. Mostra differenze
echo "📊 Differenze applicate:"
echo "======================="
echo "Prima: CIP Academy"
echo "Dopo:  CIP Real Estate"
echo ""
echo "File modificati:"
echo "- frontend/templates/auth/register.html"
echo "- frontend/templates/auth/login.html"
echo "- frontend/templates/auth/privacy.html"
echo "- frontend/templates/auth/terms.html"
echo "- frontend/templates/auth/base_auth.html"
echo ""

print_info "Backup salvato in: $BACKUP_DIR"
print_info "Le modifiche sono state applicate con successo!"
