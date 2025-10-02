#!/bin/bash

# Script per verificare che il branding sia stato aggiornato correttamente
# Da "CIP Academy" a "CIP Real Estate"

echo "🔍 Verifica Branding: CIP Real Estate"
echo "====================================="

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

# Verifica se siamo nella directory corretta
if [ ! -f "main.py" ]; then
    echo -e "${RED}❌ Questo script deve essere eseguito dalla directory root del progetto${NC}"
    echo "Usa: cd /var/www/cip_immobiliare && $0"
    exit 1
fi

echo "📋 Verifica file template..."

# 1. Verifica che "CIP Real Estate" sia presente
echo "Verifica presenza 'CIP Real Estate':"
grep -q "CIP Real Estate" frontend/templates/auth/register.html && print_result 0 "register.html" || print_result 1 "register.html"
grep -q "CIP Real Estate" frontend/templates/auth/login.html && print_result 0 "login.html" || print_result 1 "login.html"
grep -q "CIP Real Estate" frontend/templates/auth/privacy.html && print_result 0 "privacy.html" || print_result 1 "privacy.html"
grep -q "CIP Real Estate" frontend/templates/auth/terms.html && print_result 0 "terms.html" || print_result 1 "terms.html"
grep -q "CIP Real Estate" frontend/templates/auth/base_auth.html && print_result 0 "base_auth.html" || print_result 1 "base_auth.html"

echo ""
echo "Verifica assenza 'CIP Academy':"
# 2. Verifica che "CIP Academy" non sia più presente
if grep -r "CIP Academy" frontend/templates/ > /dev/null 2>&1; then
    print_result 1 "Trovati riferimenti a 'CIP Academy'"
    echo "File con 'CIP Academy':"
    grep -r "CIP Academy" frontend/templates/ | sed 's/^/  /'
else
    print_result 0 "Nessun riferimento a 'CIP Academy' trovato"
fi

echo ""
echo "Verifica assenza 'CIP Network':"
# 3. Verifica che "CIP Network" non sia più presente
if grep -r "CIP Network" frontend/templates/ > /dev/null 2>&1; then
    print_result 1 "Trovati riferimenti a 'CIP Network'"
    echo "File con 'CIP Network':"
    grep -r "CIP Network" frontend/templates/ | sed 's/^/  /'
else
    print_result 0 "Nessun riferimento a 'CIP Network' trovato"
fi

echo ""
echo "📋 Test endpoint web..."

# 4. Test endpoint se il server è accessibile
if command -v curl > /dev/null 2>&1; then
    # Test locale
    if curl -f http://localhost:8090/auth/login > /dev/null 2>&1; then
        print_result 0 "Endpoint login locale funzionante"
    else
        print_result 1 "Endpoint login locale NON funzionante"
    fi
    
    if curl -f http://localhost:8090/auth/register > /dev/null 2>&1; then
        print_result 0 "Endpoint registrazione locale funzionante"
    else
        print_result 1 "Endpoint registrazione locale NON funzionante"
    fi
    
    # Test pubblico se possibile
    if curl -f https://ciprealestate.eu/auth/login > /dev/null 2>&1; then
        print_result 0 "Endpoint login pubblico funzionante"
    else
        print_warning "Endpoint login pubblico non accessibile (normale se non in produzione)"
    fi
else
    print_warning "curl non disponibile - test endpoint saltati"
fi

echo ""
echo "📋 Riepilogo modifiche:"
echo "======================"

# Conta le occorrenze
CIP_REAL_ESTATE_COUNT=$(grep -r "CIP Real Estate" frontend/templates/ | wc -l)
CIP_ACADEMY_COUNT=$(grep -r "CIP Academy" frontend/templates/ 2>/dev/null | wc -l)
CIP_NETWORK_COUNT=$(grep -r "CIP Network" frontend/templates/ 2>/dev/null | wc -l)

echo "Occorrenze 'CIP Real Estate': $CIP_REAL_ESTATE_COUNT"
echo "Occorrenze 'CIP Academy': $CIP_ACADEMY_COUNT"
echo "Occorrenze 'CIP Network': $CIP_NETWORK_COUNT"

echo ""
if [ $CIP_REAL_ESTATE_COUNT -gt 0 ] && [ $CIP_ACADEMY_COUNT -eq 0 ] && [ $CIP_NETWORK_COUNT -eq 0 ]; then
    echo -e "${GREEN}🎉 BRANDING AGGIORNATO CORRETTAMENTE!${NC}"
    echo -e "${GREEN}✅ Tutti i file mostrano 'CIP Real Estate'${NC}"
    echo -e "${GREEN}✅ Rimosso 'CIP Academy' e 'CIP Network'${NC}"
else
    echo -e "${RED}❌ BRANDING NON AGGIORNATO CORRETTAMENTE${NC}"
    echo -e "${RED}⚠️ Alcuni file potrebbero non essere stati aggiornati${NC}"
fi

echo ""
echo "📋 File modificati:"
echo "=================="
echo "- frontend/templates/auth/register.html"
echo "- frontend/templates/auth/login.html"
echo "- frontend/templates/auth/privacy.html"
echo "- frontend/templates/auth/terms.html"
echo "- frontend/templates/auth/base_auth.html"

echo ""
echo "🌐 Per testare il sito:"
echo "======================"
echo "- Login: https://ciprealestate.eu/auth/login"
echo "- Registrazione: https://ciprealestate.eu/auth/register"
echo "- Privacy: https://ciprealestate.eu/auth/privacy"
echo "- Termini: https://ciprealestate.eu/auth/terms"
