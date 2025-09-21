#!/bin/bash

# Script per configurazione SSL del sottodominio portfolio.ciprealestate.eu
# File: deploy/setup_subdomain_ssl.sh

set -e

echo "🔐 Configurazione SSL per portfolio.ciprealestate.eu..."

# Verifica che il sottodominio punti al server
echo "📋 Verifica configurazione DNS..."
SUBDOMAIN_IP=$(dig +short portfolio.ciprealestate.eu | head -1)
SERVER_IP=$(curl -s ifconfig.me)

echo "IP del sottodominio: $SUBDOMAIN_IP"
echo "IP del server: $SERVER_IP"

if [ "$SUBDOMAIN_IP" != "$SERVER_IP" ]; then
    echo "⚠️  ATTENZIONE: Il sottodominio non punta al server corrente"
    echo "   Devi configurare il DNS per puntare a $SERVER_IP"
    echo ""
    echo "📋 Configurazione DNS richiesta:"
    echo "   Tipo: A"
    echo "   Nome: portfolio"
    echo "   Valore: $SERVER_IP"
    echo "   TTL: 3600 (o default)"
    echo ""
    echo "   Una volta configurato, esegui di nuovo questo script"
    exit 1
fi

# Crea directory per challenge
mkdir -p /var/www/html/.well-known/acme-challenge

# Ottieni certificato Let's Encrypt per il sottodominio
echo "📋 Richiesta certificato Let's Encrypt per portfolio.ciprealestate.eu..."
certbot certonly \
    --webroot \
    -w /var/www/html \
    -d portfolio.ciprealestate.eu \
    --non-interactive \
    --agree-tos \
    --email cipnetworksrl@gmail.com \
    --expand

# Aggiorna configurazione Nginx con certificato Let's Encrypt
echo "📋 Aggiornamento configurazione Nginx..."
sed -i 's|ssl_certificate /etc/ssl/cip_immobiliare/certificate.crt;|ssl_certificate /etc/letsencrypt/live/portfolio.ciprealestate.eu/fullchain.pem;|' /etc/nginx/sites-available/portfolio-ciprealestate
sed -i 's|ssl_certificate_key /etc/ssl/cip_immobiliare/private.key;|ssl_certificate_key /etc/letsencrypt/live/portfolio.ciprealestate.eu/privkey.pem;|' /etc/nginx/sites-available/portfolio-ciprealestate

# Riavvia Nginx
systemctl reload nginx

echo "✅ SSL configurato con successo!"
echo "🌐 Il sottodominio è ora disponibile su https://portfolio.ciprealestate.eu"

# Test del sottodominio
echo "📋 Test del sottodominio..."
if curl -s https://portfolio.ciprealestate.eu/health > /dev/null; then
    echo "✅ Health check: OK"
else
    echo "❌ Health check: FALLITO"
fi

echo "✅ Configurazione sottodominio completata!"
