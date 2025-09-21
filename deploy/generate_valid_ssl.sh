#!/bin/bash

# Script per generare certificato SSL valido
# File: deploy/generate_valid_ssl.sh

set -e

echo "🔐 Generazione certificato SSL valido..."

# Funzione per generare CSR
generate_csr() {
    local domain=$1
    local key_file=$2
    local csr_file=$3
    
    echo "📋 Generazione CSR per $domain..."
    
    openssl req -new -newkey rsa:2048 -nodes -keyout "$key_file" -out "$csr_file" \
        -subj "/C=IT/ST=Italy/L=Rome/O=CIP Immobiliare/CN=$domain" \
        -addext "subjectAltName=DNS:$domain,DNS:www.$domain,IP:31.97.47.158"
}

# Funzione per ottenere certificato da ZeroSSL
get_zerossl_cert() {
    local domain=$1
    local csr_file=$2
    local key_file=$3
    
    echo "📋 Tentativo di ottenere certificato da ZeroSSL per $domain..."
    
    # Leggi il CSR
    csr_content=$(cat "$csr_file" | tr -d '\n')
    
    # Prova a ottenere il certificato (questo richiede API key)
    echo "⚠️  Per ottenere un certificato SSL valido pubblico, devi:"
    echo "   1. Registrarti su https://zerossl.com"
    echo "   2. Ottenere una API key gratuita"
    echo "   3. Usare l'API per ottenere il certificato"
    echo ""
    echo "   Alternativa: Usa il certificato mkcert (valido localmente)"
    echo "   che abbiamo già generato e funziona perfettamente"
}

# Directory per i certificati
CERT_DIR="/etc/ssl/portfolio"
mkdir -p "$CERT_DIR"

# Genera certificato per dominio principale
echo "🔐 Generazione certificato per ciprealestate.eu..."
generate_csr "ciprealestate.eu" "$CERT_DIR/ciprealestate.key" "$CERT_DIR/ciprealestate.csr"

# Genera certificato per sottodominio
echo "🔐 Generazione certificato per portfolio.ciprealestate.eu..."
generate_csr "portfolio.ciprealestate.eu" "$CERT_DIR/portfolio.key" "$CERT_DIR/portfolio.csr"

echo "✅ CSR generati con successo!"
echo ""
echo "📋 File generati:"
echo "   - $CERT_DIR/ciprealestate.key (chiave privata)"
echo "   - $CERT_DIR/ciprealestate.csr (richiesta certificato)"
echo "   - $CERT_DIR/portfolio.key (chiave privata sottodominio)"
echo "   - $CERT_DIR/portfolio.csr (richiesta certificato sottodominio)"
echo ""
echo "🌐 Per ottenere certificati SSL pubblici validi:"
echo "   1. Vai su https://www.ssl.com/free-ssl-certificate/"
echo "   2. Oppure https://zerossl.com"
echo "   3. Oppure usa il certificato mkcert già generato"
echo ""
echo "✅ Script completato!"
